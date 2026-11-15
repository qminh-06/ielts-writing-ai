"""Tests for input and output guardrails."""

from datetime import UTC, datetime

import pytest

from ielts_ai.db.repo import create_essay, init_db, list_llm_calls
from ielts_ai.guardrails.input_checks import validate_input
from ielts_ai.guardrails.output_checks import evidence_in_essay, validate_output
from ielts_ai.rag.retriever import RubricIndexNotFoundError, search_rubric
from ielts_ai.schemas import Criterion, CriterionScore, GradingResult
from ielts_ai.services.grading_service import start_grading


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


def test_evidence_matching_normalizes_typographic_variants_and_edge_punctuation() -> None:
    essay = "The student’s well-being — including\u00a0mental health — should matter."
    assert evidence_in_essay('"THE student\'s well-being - including mental   health,"', essay)


def test_ellipsis_evidence_fragments_must_match_in_order() -> None:
    essay = (
        "First evidence fragment has four words, then the second evidence fragment also has four."
    )
    assert evidence_in_essay(
        "“First evidence fragment has four words…” ... ‘second evidence fragment also has four!’",
        essay,
    )
    assert not evidence_in_essay(
        "second evidence fragment also has four ... First evidence fragment has four words",
        essay,
    )


def test_ellipsis_short_fragments_are_not_used_as_evidence() -> None:
    assert not evidence_in_essay(
        "only three words ... and just three", "only three words and just three"
    )


def test_unusual_unicode_and_overlong_essays_fail_validation_without_crashing() -> None:
    unusual = "Cafe\u0301\u00a0🙂\u2028" * 2500
    result = validate_input(unusual, "student@example.com")

    assert not result.is_valid
    assert any("quá dài" in error for error in result.errors)


def test_missing_chroma_index_suggests_index_build_command(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_RAG", "false")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "empty-chroma"))

    with pytest.raises(RubricIndexNotFoundError) as error:
        search_rubric(Criterion.TR, "task response", top_k=1)
    assert "python scripts/build_rubric_index.py" in str(error.value)


def test_missing_chroma_index_fails_grading_and_logs_retrieval_error(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "grading.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("USE_MOCK_RAG", "false")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "empty-chroma"))
    essay_id = create_essay(
        db_path,
        "student@example.com",
        "Discuss community service.",
        " ".join(["Community service can help students learn useful skills."] * 50),
    )

    result = start_grading(essay_id)

    assert result["status"] == "grading_failed"
    assert "python scripts/build_rubric_index.py" in result["errors"][0]
    retrieve_call = next(
        call for call in list_llm_calls(db_path, essay_id) if call["step"] == "retrieve"
    )
    assert retrieve_call["status"] == "error"
    assert retrieve_call["error"] == "Call failed (RubricIndexNotFoundError)."
