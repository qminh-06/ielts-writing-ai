"""Tests for input and output guardrails."""

from datetime import UTC, datetime

from ielts_ai.guardrails.input_checks import validate_input
from ielts_ai.guardrails.output_checks import evidence_in_essay, validate_output
from ielts_ai.schemas import Criterion, CriterionScore, GradingResult


def test_input_checks() -> None:
    # 1. Invalid email
    res1 = validate_input("A valid length essay " * 30, "invalid-email")
    assert not res1.is_valid
    assert any("Email không hợp lệ" in err for err in res1.errors)

    # 2. Too short
    res2 = validate_input("Short text", "student@test.com")
    assert not res2.is_valid
    assert any("quá ngắn" in err for err in res2.errors)

    # 3. Valid input with under-length word warning
    # around 30 words (> 100 chars, < 250 words)
    text = "In modern society, education plays a vital and indispensable role in personal growth and career success. Many students face pressures from both academic demands and future work expectations."
    res3 = validate_input(text, "student@test.com")
    assert res3.is_valid
    assert len(res3.warnings) > 0


def test_output_checks_evidence() -> None:
    essay = "Community service helps students develop essential empathy and teamwork abilities in daily life."

    # Evidence exists (case-insensitive & whitespace normalized)
    assert evidence_in_essay("essential empathy and teamwork", essay)
    assert evidence_in_essay("COMMUNITY   SERVICE", essay)

    # Evidence missing
    assert not evidence_in_essay("completely fabricated phrase", essay)

    # Validate output check warnings
    crit = [
        CriterionScore(
            criterion=Criterion.TR, band=6.5, comment="ok", evidence=["essential empathy"]
        ),
        CriterionScore(criterion=Criterion.CC, band=6.0, comment="ok", evidence=["absent quote"]),
        CriterionScore(criterion=Criterion.LR, band=6.5, comment="ok", evidence=[]),
        CriterionScore(criterion=Criterion.GRA, band=6.0, comment="ok", evidence=[]),
    ]
    res = GradingResult(
        essay_id=1,
        version=1,
        criteria=crit,
        warnings=[],
        retrieved_rubric=[],
        model="mock",
        created_at=datetime.now(UTC),
    )

    warnings = validate_output(res, essay)
    assert any("evidence not found" in w.lower() for w in warnings)
