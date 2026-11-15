"""Regression tests for evidence retry feedback."""

from datetime import UTC, datetime

from ielts_ai.agent.graph import _evidence_retry_warning
from ielts_ai.schemas import Criterion, CriterionScore, GradingResult


def test_evidence_retry_names_only_quotes_not_found() -> None:
    result = GradingResult(
        essay_id=1,
        version=1,
        criteria=[
            CriterionScore(
                criterion=criterion,
                band=6.0,
                comment="",
                evidence=[quote],
            )
            for criterion, quote in (
                (Criterion.TR, "exact phrase in the essay"),
                (Criterion.CC, "fabricated exact quote"),
                (Criterion.LR, ""),
                (Criterion.GRA, ""),
            )
        ],
        warnings=[],
        retrieved_rubric=[],
        model="test",
        created_at=datetime.now(UTC),
    )

    instruction = _evidence_retry_warning(result, "The exact phrase in the essay is present.")

    assert "fabricated exact quote" in instruction
    assert "exact phrase in the essay" not in instruction
