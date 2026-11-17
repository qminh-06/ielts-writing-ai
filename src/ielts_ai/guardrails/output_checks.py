"""Output validation guardrails for LLM grading results.

Checks run AFTER the LLM returns a result, before saving to DB.
"""

import logging
import math
import re
import unicodedata
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ielts_ai.schemas import GradingResult

logger = logging.getLogger(__name__)

VALID_BANDS = {b / 2 for b in range(0, 19)}  # {0.0, 0.5, 1.0, ..., 9.0}
MIN_BAND = 0.0
MAX_BAND = 9.0

CRITERION_MAP: dict[str, str] = {
    "tr": "TR",
    "task response": "TR",
    "task_response": "TR",
    "cc": "CC",
    "coherence and cohesion": "CC",
    "coherence & cohesion": "CC",
    "coherence_and_cohesion": "CC",
    "lr": "LR",
    "lexical resource": "LR",
    "lexical_resource": "LR",
    "gra": "GRA",
    "grammatical range and accuracy": "GRA",
    "grammatical range & accuracy": "GRA",
    "grammatical_range_and_accuracy": "GRA",
}


def _strip_outer_markdown_fences(text: str) -> str:
    """Strip markdown code block fences and leading/trailing text around JSON."""
    cleaned = text.strip()
    match = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```$", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    elif cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            cleaned = "\n".join(lines[1:-1]).strip()

    # Find first { or [ and last } or ]
    first_curly = cleaned.find("{")
    first_square = cleaned.find("[")
    first_idx = -1
    if first_curly != -1 and first_square != -1:
        first_idx = min(first_curly, first_square)
    elif first_curly != -1:
        first_idx = first_curly
    elif first_square != -1:
        first_idx = first_square

    last_curly = cleaned.rfind("}")
    last_square = cleaned.rfind("]")
    last_idx = max(last_curly, last_square)

    if first_idx != -1 and last_idx != -1 and last_idx >= first_idx:
        cleaned = cleaned[first_idx : last_idx + 1]

    return cleaned


def _snap_band(band_raw: Any, warnings: list[str]) -> float:
    """Validate, parse, and snap band to nearest 0.5 using half-up rule."""
    if isinstance(band_raw, str):
        band_raw = band_raw.strip()
        try:
            val = float(band_raw)
        except ValueError as err:
            raise ValueError(f"Band value {band_raw!r} is not numeric.") from err
    elif isinstance(band_raw, int | float):
        val = float(band_raw)
    else:
        raise ValueError(f"Invalid band type {type(band_raw).__name__}: {band_raw!r}")

    if val < MIN_BAND or val > MAX_BAND:
        raise ValueError(f"Band {val} is outside valid range [0, 9].")

    snapped = math.floor(val * 2 + 0.5) / 2
    if abs(snapped - val) > 1e-6:
        warnings.append(f"Band rounded from {val} to {snapped}")
    return snapped


def _normalize_single_score_dict(
    d: dict[str, Any],
    warnings: list[str],
    target_criterion: Any | None = None,
) -> dict[str, Any]:
    """Normalize a single criterion score dictionary."""
    crit_raw = d.get("criterion")
    if crit_raw is None and target_criterion is not None:
        target_val = (
            target_criterion.value if hasattr(target_criterion, "value") else str(target_criterion)
        )
        crit_val = target_val
        warnings.append(f"Missing criterion assumed as {crit_val}")
    elif crit_raw is not None:
        crit_key = str(crit_raw).strip().lower()
        if crit_key in CRITERION_MAP:
            crit_val = CRITERION_MAP[crit_key]
            if str(crit_raw).strip() != crit_val:
                warnings.append(f"Normalized criterion name from {crit_raw!r} to {crit_val}")
        else:
            crit_val = str(crit_raw).strip().upper()
    else:
        raise ValueError("Missing 'criterion' field.")

    if target_criterion is not None:
        target_val = (
            target_criterion.value if hasattr(target_criterion, "value") else str(target_criterion)
        )
        if crit_val != target_val:
            raise ValueError(f"Model returned criterion {crit_val}, but expected {target_val}.")

    if "band" not in d:
        raise ValueError("Missing 'band' field.")
    band = _snap_band(d["band"], warnings)

    if "comment" not in d:
        raise ValueError("Missing 'comment' field.")
    comment = str(d["comment"])

    evidence_raw = d.get("evidence", [])
    if isinstance(evidence_raw, str):
        evidence = [evidence_raw]
        warnings.append("Wrapped single string evidence into list.")
    elif isinstance(evidence_raw, list):
        evidence = [str(x) for x in evidence_raw]
    else:
        evidence = [str(evidence_raw)]
        warnings.append("Coerced evidence into list of strings.")

    # Drop unknown extra keys
    return {
        "criterion": crit_val,
        "band": band,
        "comment": comment,
        "evidence": evidence,
    }


def normalize_model_response(
    raw_data: Any,
    *,
    regrade_criterion: Any | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Tolerant normalization BEFORE pydantic validation.

    Accepts raw parsed JSON (or parses string), unwraps single-level containers,
    filters criterion for re-grade, maps criterion names case-insensitively,
    snaps bands to 0.5 grid, normalizes evidence, and drops extra keys.

    Returns:
        (normalized_dict, warnings_list)
    """
    import json

    warnings: list[str] = []

    if isinstance(raw_data, str):
        cleaned_text = _strip_outer_markdown_fences(raw_data)
        data = json.loads(cleaned_text)
    else:
        data = raw_data

    # Unwrap single wrapper level: {"result": {...}}, {"criterion_score": {...}}, list of 1 element
    while isinstance(data, list) and len(data) == 1:
        data = data[0]
        warnings.append("Unwrapped list of 1 element.")

    if isinstance(data, dict):
        for key in ("result", "criterion_score", "score", "data"):
            if len(data) == 1 and key in data and isinstance(data[key], dict | list):
                data = data[key]
                warnings.append(f"Unwrapped single wrapper key {key!r}.")
                break

    while isinstance(data, list) and len(data) == 1:
        data = data[0]
        warnings.append("Unwrapped list of 1 element.")

    if regrade_criterion is not None:
        target_val = (
            regrade_criterion.value
            if hasattr(regrade_criterion, "value")
            else str(regrade_criterion)
        )

        # If model returned a full result with 'criteria' list
        if isinstance(data, dict) and "criteria" in data and isinstance(data["criteria"], list):
            matching = []
            for item in data["criteria"]:
                if isinstance(item, dict):
                    c_key = str(item.get("criterion", "")).strip().lower()
                    c_mapped = CRITERION_MAP.get(c_key, c_key.upper())
                    if c_mapped == target_val:
                        matching.append(item)
            if not matching:
                raise ValueError(
                    f"Model returned full criteria list without requested criterion {target_val}."
                )
            data = matching[0]
            warnings.append(f"Extracted requested criterion {target_val} from full criteria list.")

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object for re-grade, got {type(data).__name__}.")

        norm_score = _normalize_single_score_dict(
            data, warnings, target_criterion=regrade_criterion
        )
        return norm_score, warnings

    # Full 4-criteria grading flow
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object for grading result, got {type(data).__name__}.")

    criteria_raw = data.get("criteria")
    if not isinstance(criteria_raw, list):
        raise ValueError("Missing or invalid 'criteria' list in grading response.")

    norm_criteria = []
    for item in criteria_raw:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid criterion item: {item!r}")
        norm_criteria.append(_normalize_single_score_dict(item, warnings))

    existing_warnings = data.get("warnings", [])
    if isinstance(existing_warnings, list):
        warnings.extend(str(w) for w in existing_warnings if str(w) not in warnings)

    res_dict = {
        "criteria": norm_criteria,
        "warnings": warnings,
    }
    return res_dict, warnings


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
