"""Grading service orchestrating essay creation and running the grading agent.

UI pages interact through this service, never importing agent or db directly.
"""

import logging
from typing import Any

from ielts_ai.agent.graph import run_grading
from ielts_ai.config import get_settings
from ielts_ai.db.repo import create_essay, get_essay, list_ai_results, list_essays, set_status
from ielts_ai.schemas import GradingResult

logger = logging.getLogger(__name__)


def start_grading(essay_id: int) -> dict[str, Any]:
    """Grade an existing essay record by ID.

    Idempotent: Refuses to re-grade unless status is 'pending' or 'grading_failed'.
    Runs the LangGraph workflow, saves ai_results version 1, and transitions to 'ai_done'.

    Args:
        essay_id: ID of the essay in the database.

    Returns:
        Dict with 'essay_id', 'status', 'result', 'errors', 'warnings'.

    Raises:
        LookupError: If essay_id is not found.
        ValueError: If essay status is not 'pending' or 'grading_failed'.
    """
    settings = get_settings()
    essay = get_essay(settings.db_path, essay_id)
    if not essay:
        raise LookupError(f"Essay {essay_id} not found")

    current_status = essay["status"]
    if current_status not in ("pending", "grading_failed"):
        raise ValueError(
            f"Cannot start grading for essay {essay_id}: status is {current_status!r}. "
            "Grading is only permitted when status is 'pending' or 'grading_failed'."
        )
    if current_status == "grading_failed":
        set_status(settings.db_path, essay_id, "pending")

    state = run_grading(
        essay_id=essay_id,
        prompt_text=essay["prompt_text"],
        essay_text=essay["essay_text"],
        candidate_email=essay["candidate_email"],
        version=1,
    )

    final_essay = get_essay(settings.db_path, essay_id)
    final_status = final_essay["status"] if final_essay else current_status

    return {
        "essay_id": essay_id,
        "status": final_status,
        "result": state.get("result"),
        "errors": state.get("errors", []),
        "warnings": state.get("warnings", []),
    }


def submit_and_grade(
    candidate_email: str,
    prompt_text: str,
    essay_text: str,
) -> dict[str, Any]:
    """Submit a new essay and immediately start grading.

    Args:
        candidate_email: Candidate email address.
        prompt_text: The IELTS task 2 prompt.
        essay_text: Candidate response text.

    Returns:
        Dict with 'essay_id', 'status', 'result', 'errors', 'warnings'.
    """
    settings = get_settings()
    essay_id = create_essay(
        db_path=settings.db_path,
        candidate_email=candidate_email,
        prompt_text=prompt_text,
        essay_text=essay_text,
    )

    return start_grading(essay_id)


def get_latest_grading_result(essay_id: int) -> GradingResult | None:
    """Retrieve the most recent GradingResult for an essay."""
    settings = get_settings()
    results = list_ai_results(settings.db_path, essay_id)
    if not results:
        return None
    raw_json = results[0]["result_json"]
    return GradingResult.model_validate_json(raw_json)


def get_essay_details(essay_id: int) -> dict[str, Any] | None:
    """Get raw essay record by ID."""
    settings = get_settings()
    return get_essay(settings.db_path, essay_id)


def get_all_essays() -> list[dict[str, Any]]:
    """List all essays in the database."""
    settings = get_settings()
    return list_essays(settings.db_path)
