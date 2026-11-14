"""Evaluation metrics for IELTS Writing AI Assistant.

Four key metrics:
1. Schema-valid rate
2. Evidence-valid rate
3. Run-to-run variance
4. Guardrail test pass rate
"""

import json
import os
import statistics
import tempfile
from contextlib import chdir
from pathlib import Path
from typing import Any
from unittest.mock import patch

from ielts_ai.db.repo import create_essay, get_essay, init_db
from ielts_ai.guardrails.input_checks import validate_input
from ielts_ai.guardrails.output_checks import evidence_in_essay
from ielts_ai.schemas import Criterion, GradingResult, ReviewDecision
from ielts_ai.services.email_service import EmailSendError, send_email
from ielts_ai.services.grading_service import start_grading, submit_and_grade
from ielts_ai.services.review_service import (
    ReviewValidationError,
    approve_and_send,
    request_regrade,
    save_review,
)


def compute_schema_valid_rate(results: list[dict[str, Any]]) -> float:
    """Calculate ratio of outputs passing Pydantic schema validation."""
    if not results:
        return 0.0
    valid_count = 0
    for r in results:
        try:
            GradingResult.model_validate(r)
            valid_count += 1
        except Exception:
            pass
    return valid_count / len(results)


def compute_evidence_valid_rate(result: GradingResult, essay_text: str) -> float:
    """Calculate ratio of evidence phrases that accurately exist in the essay."""
    all_evidence = []
    for c in result.criteria:
        all_evidence.extend(c.evidence)

    if not all_evidence:
        return 1.0

    valid_count = sum(1 for ev in all_evidence if evidence_in_essay(ev, essay_text))
    return valid_count / len(all_evidence)


def compute_run_to_run_variance(band_runs: list[float]) -> float:
    """Calculate standard deviation of band scores across multiple runs of the same essay."""
    if len(band_runs) < 2:
        return 0.0
    return float(statistics.stdev(band_runs))


def run_to_run_variance(essay: list[Any], n_runs: int = 3) -> dict[str, Any]:
    """Summarize criterion band ranges and sample standard deviations for one essay's runs.

    ``essay`` is the ordered collection of GradingResult objects (or serialized dicts)
    collected by running the same essay repeatedly.
    """
    runs = essay[:n_runs]
    if not runs:
        return {"runs": 0, "criteria": {}, "all_criteria_within_0_5": False}

    def values(result: Any) -> dict[str, float]:
        if isinstance(result, GradingResult):
            return {score.criterion.value: score.band for score in result.criteria}
        return {item["criterion"]: float(item["band"]) for item in result["criteria"]}

    per_run = [values(result) for result in runs]
    summary: dict[str, Any] = {}
    for criterion in ("TR", "CC", "LR", "GRA"):
        bands = [result[criterion] for result in per_run if criterion in result]
        if not bands:
            continue
        summary[criterion] = {
            "min": min(bands),
            "max": max(bands),
            "range": max(bands) - min(bands),
            "standard_deviation": statistics.stdev(bands) if len(bands) > 1 else 0.0,
        }
    within = (
        len(per_run) == n_runs
        and len(summary) == 4
        and all(item["range"] <= 0.5 for item in summary.values())
    )
    return {"runs": len(runs), "criteria": summary, "all_criteria_within_0_5": within}


def compute_guardrail_pass_rate(test_results: list[bool]) -> float:
    """Calculate pass rate for guardrail test cases."""
    if not test_results:
        return 1.0
    return sum(1 for r in test_results if r) / len(test_results)


def evaluate_guardrail_case(case: dict[str, Any]) -> bool:
    """Execute one guardrail fixture against the offline validators and services."""
    outcomes = {"error", "warning", "refused", "ok"}
    valid_essay = " ".join(["Education supports personal growth and community progress."] * 45)
    short_valid_essay = " ".join(["Education supports personal growth and progress."] * 20)
    case_id = case["id"]
    data = case["input"]
    expected = case["expected"]
    if expected not in outcomes:
        raise ValueError(f"Unknown expected guardrail outcome: {expected}")

    with tempfile.TemporaryDirectory() as workdir:
        db_path = str(Path(workdir) / "guardrails.db")
        environment = {
            "DB_PATH": db_path,
            "LLM_PROVIDER": "mock",
            "USE_MOCK_RAG": "true",
            "EMAIL_MODE": "file",
        }
        with patch.dict(os.environ, environment), chdir(workdir):
            init_db(db_path)
            if case_id in {
                "empty_essay",
                "short_essay",
                "long_essay",
                "invalid_email",
                "under_250_words",
                "benign_essay",
            }:
                essay = data.get("essay", "")
                essay = essay.replace("SHORT_VALID_ESSAY", short_valid_essay)
                essay = essay.replace("VALID_ESSAY", valid_essay)
                essay = essay.replace("LONG_ESSAY", "x" * 10001)
                result = validate_input(essay, data["email"])
                if expected == "error":
                    return bool(result.errors)
                if expected == "warning":
                    return not result.errors and bool(result.warnings)
                return result.is_valid and not result.warnings

            if case_id.startswith("injection_"):
                result = validate_input(f"{valid_essay}\n{data['text']}", "student@example.com")
                return (
                    expected == "warning"
                    and not result.errors
                    and any("injection" in warning.lower() for warning in result.warnings)
                )

            if case_id == "fabricated_evidence":
                return expected == "warning" and not evidence_in_essay(
                    data["evidence"], valid_essay
                )

            if case_id == "llm_failure":
                essay_id = create_essay(
                    db_path, "student@example.com", "Discuss education.", valid_essay
                )

                class FailingProvider:
                    def complete_json(self, system: str, user: str, *, temperature: float = 0.0):
                        raise RuntimeError("offline fake provider failure")

                with patch("ielts_ai.agent.graph.get_llm_client", return_value=FailingProvider()):
                    result = start_grading(essay_id)
                essay = get_essay(db_path, essay_id)
                return (
                    expected == "error"
                    and result["status"] == "grading_failed"
                    and essay["status"] == "grading_failed"
                )

            if case_id == "send_before_approval":
                essay_id = create_essay(
                    db_path, "student@example.com", "Discuss education.", valid_essay
                )
                try:
                    approve_and_send(essay_id)
                except ReviewValidationError:
                    return expected == "refused"
                return False

            if case_id in {"regrade_after_approval", "double_send"}:
                result = submit_and_grade("student@example.com", "Discuss education.", valid_essay)
                essay_id = result["essay_id"]
                bands = {score.criterion: score.band for score in result["result"].criteria}
                save_review(
                    ReviewDecision(
                        essay_id=essay_id,
                        final_bands=bands,
                        examiner_comment="Approved by examiner.",
                        action="accept",
                    )
                )
                if case_id == "regrade_after_approval":
                    try:
                        request_regrade(
                            essay_id, Criterion.TR, "Please reconsider the task response score."
                        )
                    except ReviewValidationError:
                        return expected == "refused"
                    return False
                approve_and_send(essay_id)
                try:
                    approve_and_send(essay_id)
                except ReviewValidationError:
                    return expected == "refused"
                return False

            if case_id in {"recipient_crlf", "recipient_invalid"}:
                try:
                    send_email(data["recipient"], "Subject", "Body")
                except EmailSendError:
                    return expected == "refused"
                return False

    raise ValueError(f"Unknown guardrail case id: {case_id}")


def evaluate_guardrail_cases(path: Path) -> list[bool]:
    """Run all offline fixtures through real validators and service functions."""
    cases = json.loads(path.read_text(encoding="utf-8"))
    return [evaluate_guardrail_case(case) for case in cases]
