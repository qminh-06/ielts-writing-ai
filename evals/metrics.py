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


def compute_guardrail_pass_rate(test_results: list[bool]) -> float:
    """Calculate pass rate for guardrail test cases."""
    if not test_results:
        return 1.0
    return sum(1 for r in test_results if r) / len(test_results)
