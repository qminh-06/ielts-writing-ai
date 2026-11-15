"""Output validation guardrails for LLM grading results.

Checks run AFTER the LLM returns a result, before saving to DB.
"""

import logging
import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ielts_ai.schemas import GradingResult

logger = logging.getLogger(__name__)

VALID_BANDS = {b / 2 for b in range(0, 19)}  # {0.0, 0.5, 1.0, ..., 9.0}
MIN_BAND = 0.0
MAX_BAND = 9.0


_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u2032": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2033": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
    }
)
_ELLIPSIS_RE = re.compile(r"(?:\.{3,}|\u2026+)")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _normalize(text: str) -> str:
    """Normalize common typography and whitespace for evidence matching."""
    normalized = unicodedata.normalize("NFKC", text).translate(_QUOTE_TRANSLATION)
    return " ".join(normalized.casefold().split())


def _trim_edge_punctuation(text: str) -> str:
    """Ignore punctuation added only at the beginning or end of a quote."""
    start = 0
    end = len(text)
    while start < end and unicodedata.category(text[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(text[end - 1]).startswith("P"):
        end -= 1
    return text[start:end]


def _contains_in_order(essay: str, fragments: list[str]) -> bool:
    """Check that each normalized fragment appears after the preceding fragment."""
    position = 0
    for fragment in fragments:
        found = essay.find(fragment, position)
        if found < 0:
            return False
        position = found + len(fragment)
    return True


def evidence_in_essay(evidence: str, essay_text: str) -> bool:
    """Check normalized verbatim evidence, including ordered ellipsis fragments.

    Args:
        evidence: Evidence string from LLM output.
        essay_text: Original essay text.

    Returns:
        True if evidence appears in the normalized essay.
    """
    normalized_essay = _normalize(essay_text)
    if _ELLIPSIS_RE.search(evidence):
        fragments = [
            _trim_edge_punctuation(_normalize(fragment))
            for fragment in _ELLIPSIS_RE.split(evidence)
            if len(_WORD_RE.findall(fragment)) >= 4
        ]
        return bool(fragments) and _contains_in_order(normalized_essay, fragments)

    normalized_evidence = _trim_edge_punctuation(_normalize(evidence))
    return bool(normalized_evidence) and normalized_evidence in normalized_essay


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
                warnings.append(f"{cs.criterion.value}: evidence not found in essay: {ev!r}")
                logger.warning(
                    "Evidence not found in essay — criterion=%s evidence_length=%d",
                    cs.criterion.value,
                    len(ev),
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
