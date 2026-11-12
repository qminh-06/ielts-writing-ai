"""Essay evaluation — first grading and re-grading.

One function handles both:
- First grading: regrade_criterion=None, examiner_feedback=None
- Re-grading: regrade_criterion=<Criterion>, examiner_feedback=<str>
"""
import json
import logging
from datetime import datetime, timezone

from ielts_ai.agent.prompts import build_grading_prompt, build_regrade_prompt, format_rubric_context
from ielts_ai.config import get_settings
from ielts_ai.guardrails.output_checks import validate_output
from ielts_ai.llm.base import LLMClient
from ielts_ai.observability.call_logger import log_call
from ielts_ai.schemas import Criterion, GradingResult

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def evaluate_essay(
    essay_id: int,
    prompt_text: str,
    essay_text: str,
    rubric_chunks: list,
    llm_client: LLMClient,
    *,
    regrade_criterion: Criterion | None = None,
    examiner_feedback: str | None = None,
    version: int = 1,
) -> GradingResult:
    """Grade an IELTS Writing Task 2 essay (or re-grade a single criterion).

    # TODO(A3): Connect real LLM client and finalize prompts (A2).
    # TODO(A4): Handle partial re-grade (merge new criterion score with existing).
    """
    settings = get_settings()
    rubric_context = format_rubric_context(rubric_chunks)

    if regrade_criterion is not None:
        if examiner_feedback is None:
            raise ValueError("examiner_feedback is required for re-grading")
        system, user = build_regrade_prompt(
            prompt_text=prompt_text,
            essay_text=essay_text,
            rubric_context=rubric_context,
            criterion=regrade_criterion.value,
            examiner_feedback=examiner_feedback,
        )
        step = f"regrade_{regrade_criterion.value}"
    else:
        system, user = build_grading_prompt(
            prompt_text=prompt_text,
            essay_text=essay_text,
            rubric_context=rubric_context,
        )
        step = "grade"

    last_error: Exception | None = None
    retries = 0

    for attempt in range(MAX_RETRIES + 1):
        try:
            with log_call(step, essay_id=essay_id, db_path=settings.db_path) as ctx:
                ctx.set_retries(retries)
                response = llm_client.complete_json(system, user, temperature=0.0)
                ctx.set_tokens(response.input_tokens, response.output_tokens)

            raw = json.loads(response.text)
            raw["essay_id"] = essay_id
            raw["version"] = version
            raw["model"] = response.model
            raw["created_at"] = datetime.now(timezone.utc).isoformat()
            raw["retrieved_rubric"] = [
                c.model_dump() if hasattr(c, "model_dump") else c for c in rubric_chunks
            ]

            result = GradingResult.model_validate(raw)

            output_warnings = validate_output(result, essay_text)
            if output_warnings:
                result.warnings.extend(output_warnings)
                logger.warning(
                    "Output warnings for essay %s: %s", essay_id, output_warnings
                )

            return result

        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            retries += 1
            logger.warning(
                "Grading attempt %d failed for essay %s: %s",
                attempt + 1, essay_id, exc,
            )
            if attempt >= MAX_RETRIES:
                break

    raise ValueError(
        f"Failed to grade essay {essay_id} after {MAX_RETRIES + 1} attempts. "
        f"Last error: {last_error}"
    )
