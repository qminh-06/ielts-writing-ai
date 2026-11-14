"""Data-driven offline regression suite for Day 5 guardrail cases."""

import json
from pathlib import Path

import pytest

from evals.metrics import evaluate_guardrail_case

CASES = json.loads(
    (Path(__file__).parents[1] / "data" / "eval_set" / "guardrail_cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_guardrail_case(case):
    """Run every fixture through real offline validators/services and a fake provider."""
    assert evaluate_guardrail_case(case), f"Guardrail case failed: {case['id']}"
