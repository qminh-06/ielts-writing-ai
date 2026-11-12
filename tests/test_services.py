"""Tests for email gates and end-to-end mock flow."""
import pytest
from ielts_ai.db.repo import init_db
from ielts_ai.schemas import Criterion, ReviewDecision
from ielts_ai.services.grading_service import submit_and_grade
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
    # 1. Create essay directly through submit
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


def test_end_to_end_mock_flow() -> None:
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

    # 3. Approve and send in file mode
    out = approve_and_send(essay_id)
    assert out["status"] == "emailed"
