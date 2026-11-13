"""Persistence and orchestration for examiner reviews and single-criterion re-grades."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from ielts_ai.agent.evaluate import evaluate_essay
from ielts_ai.config import get_settings
from ielts_ai.db.repo import (
    get_essay,
    get_review_draft,
    get_review_record,
    list_ai_results,
    list_regrade_requests,
    save_ai_result,
    save_regrade_request,
    set_status,
)
from ielts_ai.db.repo import (
    save_review as persist_review,
)
from ielts_ai.guardrails.injection import detect_injection
from ielts_ai.guardrails.output_checks import evidence_in_essay, validate_output
from ielts_ai.llm.client import get_llm_client
from ielts_ai.observability.call_logger import log_call
from ielts_ai.rag.retriever import search_rubric
from ielts_ai.schemas import (
    Criterion,
    CriterionScore,
    EssayStatus,
    GradingResult,
    ReviewDecision,
    calculate_overall_band,
)
from ielts_ai.services.email_service import send_email

logger = logging.getLogger(__name__)


class ReviewValidationError(ValueError):
    """A review or re-grade request violates examiner workflow rules."""


def final_overall_band(final_bands: dict[Criterion, float]) -> float:
    """Compute examiner overall using the same half-up-to-0.5 rule as AI results."""
    if set(final_bands) != set(Criterion):
        raise ReviewValidationError("Final bands must contain exactly TR, CC, LR, and GRA.")
    for criterion, band in final_bands.items():
        if not isinstance(band, int | float) or band < 0 or band > 9 or band * 2 % 1:
            raise ReviewValidationError(
                f"{criterion.value} band must be between 0 and 9 in 0.5 steps."
            )
    return calculate_overall_band(list(final_bands.values()))


def _editable_essay(essay_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    settings = get_settings()
    essay = get_essay(settings.db_path, essay_id)
    if essay is None:
        raise LookupError(f"Essay {essay_id} not found")
    if essay["status"] not in (EssayStatus.ai_done.value, EssayStatus.reviewing.value):
        raise ReviewValidationError(f"Essay cannot be edited in status {essay['status']!r}.")
    versions = list_ai_results(settings.db_path, essay_id)
    if not versions:
        raise ReviewValidationError("Essay has no AI grading result to review.")
    return essay, versions


def save_review(decision: ReviewDecision) -> int | GradingResult:
    """Save a draft, approve a review, or dispatch its requested re-grade."""
    if decision.action == "regrade":
        if decision.regrade_criterion is None or decision.regrade_feedback is None:
            raise ReviewValidationError("Re-grade criterion and feedback are required.")
        return request_regrade(
            decision.essay_id, decision.regrade_criterion, decision.regrade_feedback
        )
    if decision.action not in ("draft", "accept"):
        raise ReviewValidationError("Review action must be 'draft', 'accept', or 'regrade'.")

    essay, _ = _editable_essay(decision.essay_id)
    final_overall_band(decision.final_bands)
    settings = get_settings()
    bands = {criterion.value: band for criterion, band in decision.final_bands.items()}
    review_id = persist_review(
        settings.db_path,
        decision.essay_id,
        json.dumps(bands),
        decision.examiner_comment,
        action="draft" if decision.action == "draft" else "accept",
    )
    if essay["status"] == EssayStatus.ai_done.value:
        set_status(settings.db_path, decision.essay_id, EssayStatus.reviewing.value)
    if decision.action == "accept":
        set_status(settings.db_path, decision.essay_id, EssayStatus.approved.value)
    return review_id


def save_examiner_review(decision: ReviewDecision) -> int | GradingResult:
    """Backward-compatible public name for saving examiner decisions."""
    return save_review(decision)


def request_regrade(essay_id: int, criterion: Criterion, feedback: str) -> GradingResult:
    """Re-grade exactly one criterion and persist an immutable next AI version."""
    essay, versions = _editable_essay(essay_id)
    try:
        criterion = Criterion(criterion)
    except ValueError as error:
        raise ReviewValidationError("Criterion must be one of TR, CC, LR, or GRA.") from error
    clean_feedback = feedback.strip()
    if not 10 <= len(clean_feedback) <= 1000:
        raise ReviewValidationError("Examiner feedback must be 10-1000 characters after trimming.")

    previous = GradingResult.model_validate_json(versions[0]["result_json"])
    old_score = next(score for score in previous.criteria if score.criterion == criterion)
    settings = get_settings()
    warnings = list(detect_injection(clean_feedback))
    query = f"{criterion.value} {clean_feedback}"
    with log_call("regrade_retrieve", essay_id=essay_id, db_path=settings.db_path) as ctx:
        rubric_chunks = search_rubric(criterion, query=query, top_k=3)
        ctx.set_tokens(len(query.split()), sum(len(chunk.text.split()) for chunk in rubric_chunks))

    llm_client = get_llm_client()
    revised: CriterionScore | None = None
    for attempt in range(2):
        try:
            result = evaluate_essay(
                essay_id=essay_id,
                prompt_text=essay["prompt_text"],
                essay_text=essay["essay_text"],
                rubric_chunks=rubric_chunks,
                llm_client=llm_client,
                regrade_criterion=criterion,
                examiner_feedback=clean_feedback,
                version=previous.version + 1,
                previous_score=old_score,
            )
        except Exception:
            raise
        if not isinstance(result, CriterionScore):
            raise ReviewValidationError(
                "Re-grade provider did not return a single criterion score."
            )
        if result.criterion != criterion:
            raise ReviewValidationError("Re-grade provider returned the wrong criterion.")
        revised = result
        if all(evidence_in_essay(quote, essay["essay_text"]) for quote in revised.evidence):
            break
        if attempt == 0:
            clean_feedback += "\nUse only exact quotes copied from the essay as evidence."

    assert revised is not None
    next_result = previous.model_copy(deep=True)
    next_result.version = previous.version + 1
    next_result.created_at = datetime.now(UTC)
    next_result.retrieved_rubric = [
        *[chunk for chunk in previous.retrieved_rubric if chunk.criterion != criterion],
        *rubric_chunks,
    ]
    next_result.criteria = [
        revised if score.criterion == criterion else score for score in previous.criteria
    ]
    next_result.warnings.extend(
        warning for warning in warnings if warning not in next_result.warnings
    )
    if abs(revised.band - old_score.band) >= 1.0:
        next_result.warnings.append(
            f"Large change after re-grade ({old_score.band:.1f} -> {revised.band:.1f}); please review"
        )
    next_result.warnings.append(
        f"Re-graded {criterion.value}: {old_score.band:.1f} -> {revised.band:.1f}."
    )
    for warning in validate_output(next_result, essay["essay_text"]):
        if warning not in next_result.warnings:
            next_result.warnings.append(warning)

    save_ai_result(settings.db_path, essay_id, next_result.version, next_result.model_dump_json())
    save_regrade_request(
        settings.db_path,
        essay_id,
        criterion.value,
        feedback.strip(),
        previous.version,
        next_result.version,
    )
    if essay["status"] == EssayStatus.ai_done.value:
        set_status(settings.db_path, essay_id, EssayStatus.reviewing.value)
    return next_result


def get_review_state(essay_id: int) -> dict[str, Any]:
    """Return essay status, AI versions and diffs, draft/final review, and re-grade history."""
    settings = get_settings()
    essay = get_essay(settings.db_path, essay_id)
    if essay is None:
        raise LookupError(f"Essay {essay_id} not found")
    rows = list(reversed(list_ai_results(settings.db_path, essay_id)))
    versions = [GradingResult.model_validate_json(row["result_json"]) for row in rows]
    diffs: dict[int, dict[str, dict[str, tuple[float, float]]]] = {}
    for prior, current in zip(versions, versions[1:], strict=False):
        before = {score.criterion.value: score.band for score in prior.criteria}
        after = {score.criterion.value: score.band for score in current.criteria}
        diffs[current.version] = {
            key: (before[key], after[key]) for key in before if before[key] != after[key]
        }
    return {
        "essay": essay,
        "status": essay["status"],
        "latest": versions[-1] if versions else None,
        "versions": versions,
        "diffs": diffs,
        "draft": get_review_draft(settings.db_path, essay_id),
        "final_review": get_review_record(settings.db_path, essay_id),
        "regrade_history": list_regrade_requests(settings.db_path, essay_id),
    }


def approve_and_send(essay_id: int) -> dict[str, Any]:
    """Approve essay and dispatch final result email, only after examiner approval."""
    settings = get_settings()
    essay = get_essay(settings.db_path, essay_id)
    if not essay:
        raise LookupError(f"Essay {essay_id} not found")
    if essay["status"] != EssayStatus.approved.value:
        raise ValueError(
            f"Cannot send email: essay {essay_id} has status {essay['status']!r}, must be 'approved'."
        )
    to_email = essay["candidate_email"]
    subject = f"Kết quả chấm điểm IELTS Writing Task 2 (Bài #{essay_id})"
    body = (
        "Kính gửi thí sinh,\n\nBài viết của bạn đã được giám khảo chấm và phê duyệt.\n"
        "Chi tiết kết quả có thể tra cứu tại hệ thống.\n\nTrân trọng,\nIELTS Writing Assistant Team"
    )
    success = send_email(to=to_email, subject=subject, body=body, essay_id=essay_id)
    if success:
        set_status(settings.db_path, essay_id, EssayStatus.emailed.value)
    return {"essay_id": essay_id, "status": "emailed" if success else "failed"}
