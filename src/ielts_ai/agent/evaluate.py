"""Essay evaluation — first grading and re-grading.

One function handles both:
- First grading: regrade_criterion=None, examiner_feedback=None
- Re-grading: regrade_criterion=<Criterion>, examiner_feedback=<str>
"""

import json
import logging
import re
from datetime import UTC, datetime

from ielts_ai.agent.prompts import (
    PROMPT_VERSION,
    build_grading_prompt,
    build_regrade_prompt,
    format_rubric_context,
)
from ielts_ai.config import get_settings
from ielts_ai.guardrails.output_checks import validate_output
from ielts_ai.llm.base import LLMClient
from ielts_ai.observability.call_logger import log_call
from ielts_ai.schemas import Criterion, GradingResult

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code blocks such as ```json ... ``` from LLM response."""
    cleaned = text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```$", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Fallback: if text starts with ``` and ends with ```
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return cleaned


def evaluate_essay(
    essay_id: int,
    prompt_text: str,
    essay_text: str,
    rubric_chunks: list,
    llm_client: LLMClient,
    *,
    regrade_criterion: Criterion | None = None,
    examiner_feedback: str | None = None,
    warnings: list[str] | None = None,
    version: int = 1,
) -> GradingResult:
    """Grade an IELTS Writing Task 2 essay (or re-grade a single criterion).

    Handles prompt construction, LLM completion, fence stripping, Pydantic validation,
    and automatic retries with validation feedback up to MAX_RETRIES.
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
            warnings=warnings,
        )
        step = "grade"

    last_error: Exception | None = None
    retries = 0
    current_user_prompt = user

    for attempt in range(MAX_RETRIES + 1):
        try:
            with log_call(step, essay_id=essay_id, db_path=settings.db_path) as ctx:
                ctx.set_retries(retries)
                response = llm_client.complete_json(system, current_user_prompt, temperature=0.0)
                ctx.set_tokens(response.input_tokens, response.output_tokens)

            cleaned_text = _strip_markdown_fences(response.text)
            raw = json.loads(cleaned_text)

            # Populate metadata
            raw["essay_id"] = essay_id
            raw["version"] = version
            raw["model"] = f"{response.model} (prompt:v{PROMPT_VERSION})"
            raw["created_at"] = datetime.now(UTC).isoformat()
            raw["retrieved_rubric"] = [
                c.model_dump() if hasattr(c, "model_dump") else c for c in rubric_chunks
            ]

            result = GradingResult.model_validate(raw)

            # Run output checks & collect warnings (without failing)
            output_warnings = validate_output(result, essay_text)
            if output_warnings:
                for ow in output_warnings:
                    if ow not in result.warnings:
                        result.warnings.append(ow)
                logger.warning("Output warnings for essay %s: %s", essay_id, output_warnings)

            return result

        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            retries += 1
            logger.warning(
                "Grading attempt %d failed for essay %s: %s. Feeding error back for retry.",
                attempt + 1,
                essay_id,
                exc,
            )
            # Feed back validation error to the LLM on retry
            current_user_prompt = (
                f"{user}\n\n"
                f"ATTENTION: Your previous response was invalid JSON or failed schema validation with error:\n"
                f"{exc}\n"
                f"Please fix this and output strictly valid JSON conforming to the schema."
            )
            if attempt >= MAX_RETRIES:
                break

    raise ValueError(
        f"Failed to grade essay {essay_id} after {MAX_RETRIES + 1} attempts. "
        f"Last error: {last_error}"
    )
