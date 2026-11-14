"""Tests for email gates, idempotency, observability completeness, and end-to-end mock flow."""

import pytest

from ielts_ai.config import get_settings
from ielts_ai.db.repo import create_essay, get_essay, init_db, list_llm_calls, set_status
from ielts_ai.schemas import Criterion, ReviewDecision
from ielts_ai.services.grading_service import start_grading, submit_and_grade
from ielts_ai.services.review_service import approve_and_send, save_examiner_review


@pytest.fixture(autouse=True)
def setup_tmp_db(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = str(tmp_path / "app.db")
    init_db(db_file)
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("USE_MOCK_RAG", "true")
    monkeypatch.setenv("EMAIL_MODE", "file")


def test_email_gate() -> None:
    essay_text = (
        "In modern society, education plays an indispensable role in developing essential skills. "
        "Students who participate in extracurricular activities often learn how to communicate and solve problems. "
        "Furthermore, academic achievements combined with practical experience prepare young people for future careers. "
        "Therefore, schools should continue offering comprehensive support to students in all aspects of life."
    )
    res = submit_and_grade(
        candidate_email="test@candidate.com",
        prompt_text="Discuss education significance.",
        essay_text=essay_text,
    )
    essay_id = res["essay_id"]

    # Essay status is now 'ai_done'. Attempting to approve_and_send should fail
    with pytest.raises(ValueError, match="must be 'approved'"):
        approve_and_send(essay_id)


def test_start_grading_idempotency() -> None:
    essay_text = (
        "Education enables communities to cultivate critical thinkers and resilient leaders. "
        "Through structured instruction and shared dialogue, individuals acquire knowledge and mutual understanding. "
        "In conclusion, broad educational investment remains essential for long-term social progress."
    )
    res = submit_and_grade(
        candidate_email="idempotent@test.com",
        prompt_text="Discuss role of education.",
        essay_text=essay_text,
    )
    essay_id = res["essay_id"]
    assert res["status"] == "ai_done"

    # Calling start_grading again on an essay with status 'ai_done' must be refused
    with pytest.raises(ValueError, match="Cannot start grading"):
        start_grading(essay_id)


def test_grading_failed_essay_can_be_retried() -> None:
    settings = get_settings()
    essay_id = create_essay(
        settings.db_path,
        "retry@test.com",
        "Discuss education.",
        " ".join(["Education supports resilient communities and progress."] * 45),
    )
    set_status(settings.db_path, essay_id, "grading_failed")

    result = start_grading(essay_id)

    assert result["status"] == "ai_done"
    assert get_essay(settings.db_path, essay_id)["status"] == "ai_done"


def test_observability_llm_calls_completeness() -> None:
    settings = get_settings()

    # Essay contains the exact evidence strings from the mock result so no retry is needed
    essay_text = (
        "It is argued that governments should prioritise renewable energy over fossil fuels to protect our environment. "
        "Furthermore, academic achievements combined with practical experience help students acquire essential skills. "
        "Students who participate in extracurricular activities often learn how to communicate effectively. "
        "Schools should continue offering comprehensive support so that critical thinkers and resilient leaders emerge. "
        "In conclusion, broad educational investment remains essential, and investing in educational resources benefits both individuals and the whole community."
    )
    res = submit_and_grade(
        candidate_email="obs@test.com",
        prompt_text="Should renewable energy and education be prioritized?",
        essay_text=essay_text,
    )
    essay_id = res["essay_id"]
    assert res["status"] == "ai_done"

    calls = list_llm_calls(settings.db_path, essay_id)

    # Exactly 5 calls: 4 retrieve calls + 1 grade call
    assert len(calls) == 5

    retrieve_calls = [c for c in calls if c["step"] == "retrieve"]
    grade_calls = [c for c in calls if c["step"] == "grade"]

    assert len(retrieve_calls) == 4
    assert len(grade_calls) == 1

    for c in calls:
        assert c["status"] == "ok"
        assert c["latency_ms"] >= 0.0
        assert c["input_tokens"] >= 0
        assert c["output_tokens"] >= 0


def test_end_to_end_mock_flow() -> None:
    settings = get_settings()
    essay_text = (
        "Education is fundamental to personal and economic advancement across modern communities. "
        "When students engage in diverse learning environments, they develop critical thinking and collaboration. "
        "In conclusion, investing in educational resources benefits both individuals and the whole community."
    )
    # 1. Submit and grade
    res = submit_and_grade(
        candidate_email="e2e@candidate.com",
        prompt_text="Explain importance of education.",
        essay_text=essay_text,
    )
    essay_id = res["essay_id"]
    assert res["status"] == "ai_done"

    # 2. Examiner review
    decision = ReviewDecision(
        essay_id=essay_id,
        final_bands={
            Criterion.TR: 6.5,
            Criterion.CC: 6.5,
            Criterion.LR: 6.0,
            Criterion.GRA: 6.0,
        },
        examiner_comment="Well-structured essay.",
        action="accept",
    )
    save_examiner_review(decision)
    assert get_essay(settings.db_path, essay_id) is not None

    # 3. Approve and send in file mode
    out = approve_and_send(essay_id)
    assert out["status"] == "emailed"
