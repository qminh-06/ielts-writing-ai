"""Output validation guardrails for LLM grading results.

Checks run AFTER the LLM returns a result, before saving to DB.
"""
import re
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ielts_ai.schemas import GradingResult

logger = logging.getLogger(__name__)

VALID_BANDS = {b / 2 for b in range(0, 19)}  # {0.0, 0.5, 1.0, ..., 9.0}
MIN_BAND = 0.0
MAX_BAND = 9.0


def _normalize(text: str) -> str:
    """Normalize text for substring matching: lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def evidence_in_essay(evidence: str, essay_text: str) -> bool:
    """Check if evidence string appears in the essay (case-insensitive, whitespace-normalized).

    Args:
        evidence: Evidence string from LLM output.
        essay_text: Original essay text.

    Returns:
        True if evidence is a substring of normalized essay.
    """
    return _normalize(evidence) in _normalize(essay_text)


def check_bands(result: "GradingResult") -> list[str]:
    """Validate that all band scores are in [0, 9] with 0.5 step.

    Args:
        result: GradingResult to check.

    Returns:
        List of warning messages (empty if all bands are valid).
    """
    warnings = []
    for cs in result.criteria:
        if cs.band not in VALID_BANDS:
            warnings.append(
                f"{cs.criterion.value}: band {cs.band} is not a valid IELTS band "
                f"(must be 0–9 in 0.5 steps)."
            )
        if cs.band < MIN_BAND or cs.band > MAX_BAND:
            warnings.append(
                f"{cs.criterion.value}: band {cs.band} is out of range [{MIN_BAND}, {MAX_BAND}]."
            )
    return warnings


def check_evidence(result: "GradingResult", essay_text: str) -> list[str]:
    """Validate that all evidence strings appear in the essay.

    Invalid evidence is added to warnings; it does NOT fail grading.

    Args:
        result: GradingResult with criteria and evidence lists.
        essay_text: Original essay text.

    Returns:
        List of warning messages for evidence not found in essay.
    """
    warnings = []
    for cs in result.criteria:
        for ev in cs.evidence:
            if ev and not evidence_in_essay(ev, essay_text):
                warnings.append(
                    f"{cs.criterion.value}: evidence not found in essay: {ev!r}"
                )
                logger.warning(
                    "Evidence not found in essay — criterion=%s evidence=%r",
                    cs.criterion.value, ev,
                )
    return warnings


def validate_output(result: "GradingResult", essay_text: str) -> list[str]:
    """Run all output checks and return combined warnings.

    Args:
        result: GradingResult from LLM.
        essay_text: Original essay text.

    Returns:
        List of warnings. These are added to result.warnings before saving.
    """
    warnings = []
    warnings.extend(check_bands(result))
    warnings.extend(check_evidence(result, essay_text))
    return warnings
