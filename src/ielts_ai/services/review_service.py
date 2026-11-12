"""Review service handling human examiner decisions, score adjustments, regrades, and approval."""

import json
import logging
from typing import Any

from ielts_ai.agent.evaluate import evaluate_essay
from ielts_ai.config import get_settings
from ielts_ai.db.repo import (
    get_essay,
    list_ai_results,
    save_ai_result,
    save_review,
    set_status,
)
from ielts_ai.llm.client import get_llm_client
from ielts_ai.rag.retriever import search_rubric
from ielts_ai.schemas import Criterion, EssayStatus, GradingResult, ReviewDecision
from ielts_ai.services.email_service import send_email

logger = logging.getLogger(__name__)


def save_examiner_review(decision: ReviewDecision) -> int:
    """Save examiner review decision to database.

    Updates essay status to 'approved' if action is 'accept',
    or keeps/transitions appropriately.
    """
    settings = get_settings()
    essay = get_essay(settings.db_path, decision.essay_id)
    if not essay:
        raise LookupError(f"Essay {decision.essay_id} not found")

    # Serialize final bands
    bands_dict = {c.value: band for c, band in decision.final_bands.items()}
    rev_id = save_review(
        db_path=settings.db_path,
        essay_id=decision.essay_id,
        final_bands_json=json.dumps(bands_dict),
        examiner_comment=decision.examiner_comment,
    )

    if decision.action == "accept":
        # First ensure in reviewing, then approved
        if essay["status"] == "ai_done":
            set_status(settings.db_path, decision.essay_id, EssayStatus.reviewing.value)
        set_status(settings.db_path, decision.essay_id, EssayStatus.approved.value)

    return rev_id


def request_regrade(
    essay_id: int,
    criterion: Criterion,
    feedback: str,
) -> GradingResult:
    """Request AI re-grade for a specific criterion with examiner feedback.

    # TODO(A4): Implement partial score merging and version history.
    """
    settings = get_settings()
    essay = get_essay(settings.db_path, essay_id)
    if not essay:
        raise LookupError(f"Essay {essay_id} not found")

    # Transition to reviewing/ai_done
    if essay["status"] == "reviewing":
        set_status(settings.db_path, essay_id, EssayStatus.ai_done.value)

    results = list_ai_results(settings.db_path, essay_id)
    new_version = (results[0]["version"] + 1) if results else 2

    rubric_chunks = search_rubric(criterion, f"{criterion.value} regrade", top_k=2)
    llm_client = get_llm_client()

    new_result = evaluate_essay(
        essay_id=essay_id,
        prompt_text=essay["prompt_text"],
        essay_text=essay["essay_text"],
        rubric_chunks=rubric_chunks,
        llm_client=llm_client,
        regrade_criterion=criterion,
        examiner_feedback=feedback,
        version=new_version,
    )

    save_ai_result(
        db_path=settings.db_path,
        essay_id=essay_id,
        version=new_version,
        result_json=new_result.model_dump_json(),
    )
    return new_result


def approve_and_send(essay_id: int) -> dict[str, Any]:
    """Approve essay and dispatch final result email.

    HARD RULE: Refuses unless current status is 'approved'.
    """
    settings = get_settings()
    essay = get_essay(settings.db_path, essay_id)
    if not essay:
        raise LookupError(f"Essay {essay_id} not found")

    if essay["status"] != EssayStatus.approved.value:
        raise ValueError(
            f"Cannot send email: essay {essay_id} has status {essay['status']!r}, "
            f"must be 'approved'."
        )

    # Prepare email body
    to_email = essay["candidate_email"]
    subject = f"Kết quả chấm điểm IELTS Writing Task 2 (Bài #{essay_id})"
    body = (
        "Kính gửi thí sinh,\n\n"
        "Bài viết của bạn đã được giám khảo chấm và phê duyệt.\n"
        "Chi tiết kết quả có thể tra cứu tại hệ thống.\n\n"
        "Trân trọng,\nIELTS Writing Assistant Team"
    )

    success = send_email(to=to_email, subject=subject, body=body, essay_id=essay_id)
    if success:
        set_status(settings.db_path, essay_id, EssayStatus.emailed.value)

    return {"essay_id": essay_id, "status": "emailed" if success else "failed"}
