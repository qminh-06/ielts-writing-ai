"""Grading service orchestrating essay creation and running the grading agent.

UI pages interact through this service, never importing agent or db directly.
"""
import logging
from typing import Any

from ielts_ai.agent.graph import run_grading
from ielts_ai.config import get_settings
from ielts_ai.db.repo import create_essay, get_essay, list_ai_results, list_essays
from ielts_ai.schemas import GradingResult

logger = logging.getLogger(__name__)


def submit_and_grade(
    candidate_email: str,
    prompt_text: str,
    essay_text: str,
) -> dict[str, Any]:
    """Submit a new essay and immediately invoke the AI grading workflow.

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

    state = run_grading(
        essay_id=essay_id,
        prompt_text=prompt_text,
        essay_text=essay_text,
        candidate_email=candidate_email,
        version=1,
    )

    return {
        "essay_id": essay_id,
        "status": "ai_done" if state.get("result") else "grading_failed",
        "result": state.get("result"),
        "errors": state.get("errors", []),
        "warnings": state.get("warnings", []),
    }


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
