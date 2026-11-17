"""Essay evaluation — first grading and re-grading.

One function handles both:
- First grading: regrade_criterion=None, examiner_feedback=None
- Re-grading: regrade_criterion=<Criterion>, examiner_feedback=<str>
"""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from ielts_ai.agent.prompts import (
    PROMPT_VERSION,
    build_grading_prompt,
    build_regrade_prompt,
    format_rubric_context,
)
from ielts_ai.config import get_settings
from ielts_ai.guardrails.output_checks import normalize_model_response, validate_output
from ielts_ai.llm.base import LLMClient
from ielts_ai.observability.call_logger import log_call
from ielts_ai.schemas import Criterion, CriterionScore, GradingResult

logger = logging.getLogger(__name__)

REGRADE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "criterion": {"type": "STRING", "enum": ["TR", "CC", "LR", "GRA"]},
        "band": {"type": "NUMBER"},
        "comment": {"type": "STRING"},
        "evidence": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    },
    "required": ["criterion", "band", "comment", "evidence"],
}

GRADING_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "criteria": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "criterion": {"type": "STRING", "enum": ["TR", "CC", "LR", "GRA"]},
                    "band": {"type": "NUMBER"},
                    "comment": {"type": "STRING"},
                    "evidence": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                    },
                },
                "required": ["criterion", "band", "comment", "evidence"],
            },
        },
        "warnings": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    },
    "required": ["criteria"],
}


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
    previous_score: CriterionScore | None = None,
) -> GradingResult | CriterionScore:
    """Grade an IELTS Writing Task 2 essay (or re-grade a single criterion).

    Handles prompt construction, LLM completion, fence stripping, Pydantic validation,
    and automatic retries with validation feedback up to MAX_RETRIES.
    """
    settings = get_settings()
    rubric_context = format_rubric_context(rubric_chunks)
    max_retries = settings.llm_max_validation_attempts

    if regrade_criterion is not None:
        if examiner_feedback is None:
            raise ValueError("examiner_feedback is required for re-grading")
        system, user = build_regrade_prompt(
            prompt_text=prompt_text,
            essay_text=essay_text,
            rubric_context=rubric_context,
            criterion=regrade_criterion.value,
            examiner_feedback=examiner_feedback,
            previous_score=previous_score.band if previous_score else 0.0,
            previous_comment=previous_score.comment if previous_score else "",
            previous_evidence=previous_score.evidence if previous_score else [],
        )
        step = "regrade"
        active_schema = REGRADE_SCHEMA
        expected_shape_msg = (
            '{\n  "criterion": "' + regrade_criterion.value + '",\n'
            '  "band": 6.5,\n'
            '  "comment": "Concise explanation.",\n'
            '  "evidence": ["verbatim quote from essay"]\n}'
        )
    else:
        system, user = build_grading_prompt(
            prompt_text=prompt_text,
            essay_text=essay_text,
            rubric_context=rubric_context,
            warnings=warnings,
        )
        step = "grade"
        active_schema = GRADING_SCHEMA
        expected_shape_msg = (
            '{\n  "criteria": [\n'
            '    {"criterion": "TR", "band": 6.5, "comment": "...", "evidence": ["..."]},\n'
            '    {"criterion": "CC", "band": 6.0, "comment": "...", "evidence": ["..."]},\n'
            '    {"criterion": "LR", "band": 6.5, "comment": "...", "evidence": ["..."]},\n'
            '    {"criterion": "GRA", "band": 6.0, "comment": "...", "evidence": ["..."]}\n'
            '  ],\n  "warnings": []\n}'
        )

    last_error: Exception | None = None
    retries = 0
    current_user_prompt = user

    for attempt in range(max_retries + 1):
        try:
            with log_call(step, essay_id=essay_id, db_path=settings.db_path) as ctx:
                ctx.set_retries(retries)
                try:
                    try:
                        response = llm_client.complete_json(
                            system,
                            current_user_prompt,
                            temperature=0.0,
                            response_schema=active_schema,
                        )
                    except TypeError:
                        # Client doesn't accept response_schema parameter
                        response = llm_client.complete_json(
                            system,
                            current_user_prompt,
                            temperature=0.0,
                        )
                finally:
                    ctx.set_retries(retries + getattr(llm_client, "last_attempt_retries", 0))
                ctx.set_tokens(
                    response.input_tokens, response.output_tokens, response.thinking_tokens
                )

                # Strip markdown fences and attempt raw JSON decode first
                raw_json_str = _strip_markdown_fences(response.text)
                parsed_json = json.loads(raw_json_str)

                # Tolerant normalization BEFORE pydantic validation
                try:
                    normalized_dict, norm_warnings = normalize_model_response(
                        parsed_json,
                        regrade_criterion=regrade_criterion,
                    )
                except ValueError as norm_err:
                    # Synthesize a ValidationError so safe call logging captures sanitized diagnostics
                    if regrade_criterion is not None:
                        err = ValidationError.from_exception_data(
                            title="CriterionScore",
                            line_errors=[
                                {
                                    "type": "value_error",
                                    "loc": ("root",),
                                    "input": None,
                                    "ctx": {"error": str(norm_err)},
                                }
                            ],
                        )
                    else:
                        err = ValidationError.from_exception_data(
                            title="GradingResult",
                            line_errors=[
                                {
                                    "type": "value_error",
                                    "loc": ("root",),
                                    "input": None,
                                    "ctx": {"error": str(norm_err)},
                                }
                            ],
                        )
                    err.raw_model_text = response.text  # type: ignore[attr-defined]
                    raise err from norm_err

                if regrade_criterion is not None:
                    try:
                        score = CriterionScore.model_validate(normalized_dict)
                    except ValidationError as v_err:
                        v_err.raw_model_text = response.text  # type: ignore[attr-defined]
                        raise v_err
                    if score.criterion != regrade_criterion:
                        raise ValueError(
                            f"Expected criterion {regrade_criterion.value}, "
                            f"got {score.criterion.value}"
                        )
                    return score

                normalized_dict["essay_id"] = essay_id
                normalized_dict["version"] = version
                normalized_dict["model"] = f"{response.model} (prompt:v{PROMPT_VERSION})"
                normalized_dict["created_at"] = datetime.now(UTC).isoformat()
                normalized_dict["retrieved_rubric"] = [
                    c.model_dump() if hasattr(c, "model_dump") else c for c in rubric_chunks
                ]

                try:
                    result = GradingResult.model_validate(normalized_dict)
                except ValidationError as v_err:
                    v_err.raw_model_text = response.text  # type: ignore[attr-defined]
                    raise v_err

                for nw in norm_warnings:
                    if nw not in result.warnings:
                        result.warnings.append(nw)

                output_warnings = validate_output(result, essay_text)
                if output_warnings:
                    for ow in output_warnings:
                        if ow not in result.warnings:
                            result.warnings.append(ow)
                    logger.warning(
                        "Output warnings for essay %s: %d evidence or band warning(s).",
                        essay_id,
                        len(output_warnings),
                    )

                return result

        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            retries += 1
            logger.warning(
                "Grading attempt %d failed for essay %s (%s). Feeding validation feedback "
                "back for retry.",
                attempt + 1,
                essay_id,
                type(exc).__name__,
            )

            # Build detailed problem list: field path + message
            problems: list[str] = []
            if isinstance(exc, ValidationError):
                for err in exc.errors():
                    field_loc = " -> ".join(str(p) for p in err.get("loc", ()))
                    msg = err.get("msg", "")
                    problems.append(f"- Field '{field_loc}': {msg}")
            else:
                problems.append(f"- Error: {str(exc)}")

            problems_str = "\n".join(problems)
            current_user_prompt = (
                f"{user}\n\n"
                f"ATTENTION: Your previous response failed validation with the following problems:\n"
                f"{problems_str}\n\n"
                f"You must fix these problems and return strictly valid JSON matching this exact structure:\n"
                f"{expected_shape_msg}\n"
                f"Do not include markdown explanation, wrappers, or extra keys."
            )
            if attempt >= max_retries:
                break

    raise ValueError(
        f"Failed to grade essay {essay_id} after {max_retries + 1} attempts. "
        f"Last error: {type(last_error).__name__ if last_error else 'unknown'}."
    )
