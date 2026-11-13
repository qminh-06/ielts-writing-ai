"""Evaluation metrics for IELTS Writing AI Assistant.

Four key metrics:
1. Schema-valid rate
2. Evidence-valid rate
3. Run-to-run variance
4. Guardrail test pass rate
"""

import statistics
from typing import Any

from ielts_ai.guardrails.output_checks import evidence_in_essay
from ielts_ai.schemas import GradingResult


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
