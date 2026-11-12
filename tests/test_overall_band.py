"""Tests for overall band score computation.

Rules:
- mean of 4 bands
- rounded half-up to nearest 0.5: floor(mean * 2 + 0.5) / 2
- examples:
  6.25 -> 6.5
  6.75 -> 7.0
  6.0  -> 6.0
"""

from datetime import UTC, datetime

from ielts_ai.schemas import Criterion, CriterionScore, GradingResult


def _make_result(bands: list[float]) -> GradingResult:
    criteria = [
        CriterionScore(criterion=Criterion.TR, band=bands[0], comment="ok", evidence=[]),
        CriterionScore(criterion=Criterion.CC, band=bands[1], comment="ok", evidence=[]),
        CriterionScore(criterion=Criterion.LR, band=bands[2], comment="ok", evidence=[]),
        CriterionScore(criterion=Criterion.GRA, band=bands[3], comment="ok", evidence=[]),
    ]
    return GradingResult(
        essay_id=1,
        version=1,
        criteria=criteria,
        warnings=[],
        retrieved_rubric=[],
        model="mock",
        created_at=datetime.now(UTC),
    )


def test_overall_band_calculation() -> None:
    # 6.25 -> 6.5 (e.g. 6.5, 6.0, 6.5, 6.0 = 25.0 / 4 = 6.25)
    r1 = _make_result([6.5, 6.0, 6.5, 6.0])
    assert r1.overall_band == 6.5

    # 6.75 -> 7.0 (e.g. 7.0, 6.5, 7.0, 6.5 = 27.0 / 4 = 6.75)
    r2 = _make_result([7.0, 6.5, 7.0, 6.5])
    assert r2.overall_band == 7.0

    # 6.0 -> 6.0
    r3 = _make_result([6.0, 6.0, 6.0, 6.0])
    assert r3.overall_band == 6.0
