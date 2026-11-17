"""Unit tests for tolerant normalization, schema constraints, and regrade error handling."""

import pytest

from ielts_ai.config import get_settings
from ielts_ai.db.repo import (
    get_essay,
    get_review_draft,
    init_db,
    list_ai_results,
    list_llm_calls,
    list_regrade_requests,
)
from ielts_ai.guardrails.output_checks import normalize_model_response
from ielts_ai.llm.base import LLMResponse
from ielts_ai.schemas import Criterion, ReviewDecision
from ielts_ai.services.grading_service import submit_and_grade
from ielts_ai.services.review_service import RegradeFailedError, request_regrade, save_review


@pytest.fixture(autouse=True)
def setup_tmp_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "app.db")
    init_db(db_file)
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("USE_MOCK_RAG", "true")


def _essay_text() -> str:
    return (
        "Governments should prioritise renewable energy over fossil fuels. Furthermore, academic "
        "achievements combined with practical experience help students acquire essential skills. "
        "Students who participate in extracurricular activities often learn how to communicate. "
        "Schools should continue offering comprehensive support so critical thinkers and resilient "
        "leaders emerge. In conclusion, broad educational investment remains essential, and "
        "investing in educational resources benefits both individuals and the whole community."
    )


# --- 2. Unit tests for normalize_model_response ---


def test_normalization_strip_fences_and_surrounding_text():
    raw_text = 'Here is the score you requested:\n```json\n{"criterion": "TR", "band": 6.5, "comment": "Good job.", "evidence": ["quote"]}\n```\nHope that helps!'
    norm, warnings = normalize_model_response(raw_text, regrade_criterion=Criterion.TR)
    assert norm["criterion"] == "TR"
    assert norm["band"] == 6.5
    assert norm["comment"] == "Good job."
    assert norm["evidence"] == ["quote"]


def test_normalization_unwrap_result_wrapper():
    raw = {
        "result": {
            "criterion": "CC",
            "band": 7.0,
            "comment": "Well structured.",
            "evidence": ["quote"],
        }
    }
    norm, warnings = normalize_model_response(raw, regrade_criterion=Criterion.CC)
    assert norm["criterion"] == "CC"
    assert norm["band"] == 7.0
    assert any("Unwrapped single wrapper key 'result'" in w for w in warnings)


def test_normalization_unwrap_criterion_score_wrapper():
    raw = {
        "criterion_score": {
            "criterion": "LR",
            "band": 6.0,
            "comment": "Okay vocabulary.",
            "evidence": ["quote"],
        }
    }
    norm, warnings = normalize_model_response(raw, regrade_criterion=Criterion.LR)
    assert norm["criterion"] == "LR"
    assert norm["band"] == 6.0
    assert any("Unwrapped single wrapper key 'criterion_score'" in w for w in warnings)


def test_normalization_unwrap_single_element_list():
    raw = [{"criterion": "GRA", "band": 6.5, "comment": "Accurate.", "evidence": ["quote"]}]
    norm, warnings = normalize_model_response(raw, regrade_criterion=Criterion.GRA)
    assert norm["criterion"] == "GRA"
    assert norm["band"] == 6.5
    assert any("Unwrapped list of 1 element" in w for w in warnings)


def test_normalization_regrade_takes_only_requested_criterion_from_full_criteria_list():
    raw = {
        "criteria": [
            {"criterion": "TR", "band": 5.0, "comment": "TR comment", "evidence": ["tr"]},
            {"criterion": "LR", "band": 7.5, "comment": "LR comment", "evidence": ["lr"]},
            {"criterion": "CC", "band": 6.0, "comment": "CC comment", "evidence": ["cc"]},
            {"criterion": "GRA", "band": 6.0, "comment": "GRA comment", "evidence": ["gra"]},
        ]
    }
    norm, warnings = normalize_model_response(raw, regrade_criterion=Criterion.LR)
    assert norm["criterion"] == "LR"
    assert norm["band"] == 7.5
    assert norm["comment"] == "LR comment"
    assert any("Extracted requested criterion LR" in w for w in warnings)


def test_normalization_criterion_name_case_insensitive_mapping():
    # Test lowercase & long names
    test_cases = [
        ("tr", "TR"),
        ("Task Response", "TR"),
        ("cc", "CC"),
        ("Coherence and Cohesion", "CC"),
        ("lr", "LR"),
        ("Lexical Resource", "LR"),
        ("gra", "GRA"),
        ("Grammatical Range and Accuracy", "GRA"),
    ]
    for raw_crit, expected_crit in test_cases:
        raw = {"criterion": raw_crit, "band": 6.5, "comment": "Valid.", "evidence": ["quote"]}
        norm, warnings = normalize_model_response(raw, regrade_criterion=Criterion(expected_crit))
        assert norm["criterion"] == expected_crit


def test_normalization_band_string_and_snap_half_up():
    # 6.2 -> 6.0, 6.25 -> 6.5, 6.75 -> 7.0
    raw_str = {"criterion": "TR", "band": "6.25", "comment": "C", "evidence": ["e"]}
    norm, warnings = normalize_model_response(raw_str, regrade_criterion=Criterion.TR)
    assert norm["band"] == 6.5
    assert any("Band rounded from 6.25 to 6.5" in w for w in warnings)

    raw_snap = {"criterion": "TR", "band": 6.2, "comment": "C", "evidence": ["e"]}
    norm_snap, warnings_snap = normalize_model_response(raw_snap, regrade_criterion=Criterion.TR)
    assert norm_snap["band"] == 6.0
    assert any("Band rounded from 6.2 to 6.0" in w for w in warnings_snap)


def test_normalization_evidence_single_string_wrapped_and_drop_extra_keys():
    raw = {
        "criterion": "CC",
        "band": 6.5,
        "comment": "Nice.",
        "evidence": "single string quote",
        "unwanted_extra_key": 12345,
    }
    norm, warnings = normalize_model_response(raw, regrade_criterion=Criterion.CC)
    assert norm["evidence"] == ["single string quote"]
    assert "unwanted_extra_key" not in norm
    assert any("Wrapped single string evidence into list" in w for w in warnings)


def test_normalization_must_still_fail():
    # 1. Missing comment
    with pytest.raises(ValueError, match="Missing 'comment'"):
        normalize_model_response(
            {"criterion": "TR", "band": 6.5, "evidence": ["e"]},
            regrade_criterion=Criterion.TR,
        )

    # 2. Band out of range (11)
    with pytest.raises(ValueError, match="outside valid range"):
        normalize_model_response(
            {"criterion": "TR", "band": 11, "comment": "c", "evidence": ["e"]},
            regrade_criterion=Criterion.TR,
        )

    # 3. Wrong criterion requested
    with pytest.raises(ValueError, match="Model returned criterion"):
        normalize_model_response(
            {"criterion": "TR", "band": 6.5, "comment": "c", "evidence": ["e"]},
            regrade_criterion=Criterion.LR,
        )


# --- 1, 5, 6. Diagnostics, Retries, and RegradeFailedError atomic failure tests ---


def test_regrade_failed_error_on_invalid_schema_no_partial_writes(monkeypatch):
    """When model keeps returning invalid schema, RegradeFailedError is raised with no partial write."""
    result = submit_and_grade("fail@test.com", "Discuss education.", _essay_text())
    essay_id = result["essay_id"]
    original = result["result"]
    original_version = original.version
    db_path = get_settings().db_path

    draft = ReviewDecision(
        essay_id=essay_id,
        final_bands={Criterion.TR: 6.5, Criterion.CC: 6.0, Criterion.LR: 6.5, Criterion.GRA: 6.0},
        examiner_comment="Examiner draft before failure.",
        action="draft",
    )
    save_review(draft)
    draft_before = get_review_draft(db_path, essay_id)
    essay_before = get_essay(db_path, essay_id)

    # Mock client that returns invalid schema missing comment
    class InvalidSchemaClient:
        def __init__(self):
            self.calls = 0

        def complete_json(self, system, user, *, temperature=0.0, response_schema=None):
            self.calls += 1
            return LLMResponse(
                text='{"criterion": "TR", "band": 6.5, "evidence": ["quote"]}',
                input_tokens=10,
                output_tokens=10,
                model="fake-invalid",
            )

    client = InvalidSchemaClient()
    monkeypatch.setattr("ielts_ai.services.review_service.get_llm_client", lambda: client)

    with pytest.raises(RegradeFailedError) as exc_info:
        request_regrade(essay_id, Criterion.TR, "Please regrade TR with more detail.")

    assert "Chấm lại thất bại" in exc_info.value.user_message
    assert "Logs" in exc_info.value.user_message

    # Invariants check: NO partial writes
    # 1. No new ai_results version
    results_after = list_ai_results(db_path, essay_id)
    assert len(results_after) == 1
    assert results_after[0]["version"] == original_version

    # 2. No regrade_requests row left half-done
    regrade_reqs = list_regrade_requests(db_path, essay_id)
    assert len(regrade_reqs) == 0

    # 3. Essay status unchanged
    essay_after = get_essay(db_path, essay_id)
    assert essay_after["status"] == essay_before["status"]

    # 4. Examiner draft untouched
    draft_after = get_review_draft(db_path, essay_id)
    assert draft_after["examiner_comment"] == draft_before["examiner_comment"]
    assert draft_after["final_bands_json"] == draft_before["final_bands_json"]

    # 5. Diagnostic logged in llm_calls: error summary without raw inputs
    calls = list_llm_calls(db_path, essay_id)
    regrade_calls = [c for c in calls if c["step"] == "regrade"]
    assert len(regrade_calls) >= 1
    last_call = regrade_calls[-1]
    assert last_call["status"] == "error"
    # Ensure error has diagnostic info
    assert len(last_call["error"]) <= 2000
    assert "Provider response did not match the grading schema" in last_call["error"]
    assert "Raw snippet" in last_call["error"]
