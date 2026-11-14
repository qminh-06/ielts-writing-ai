"""Offline tests for approval-gated file/SMTP email behavior."""

from pathlib import Path

import pytest

from ielts_ai.db.repo import get_essay, init_db, list_email_attempts
from ielts_ai.schemas import ReviewDecision
from ielts_ai.services.email_service import EmailSendError, send_email
from ielts_ai.services.grading_service import submit_and_grade
from ielts_ai.services.review_service import approve_and_send, get_email_preview, save_review

ESSAY = " ".join(["Education supports personal progress and resilient communities."] * 45)


@pytest.fixture(autouse=True)
def email_environment(tmp_path, monkeypatch):
    db_path = str(tmp_path / "email.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("USE_MOCK_RAG", "true")
    monkeypatch.setenv("EMAIL_MODE", "file")
    monkeypatch.chdir(tmp_path)
    return db_path


def _approved() -> int:
    result = submit_and_grade("candidate@example.com", "Discuss education.", ESSAY)
    save_review(
        ReviewDecision(
            essay_id=result["essay_id"],
            final_bands={score.criterion: score.band for score in result["result"].criteria},
            examiner_comment="Examiner confirmed this result.",
            action="accept",
        )
    )
    return result["essay_id"]


def test_file_mode_writes_expected_message():
    assert send_email("candidate@example.com", "Kết quả", "Nội dung", essay_id=12)
    files = list(Path("outbox").glob("12_*.txt"))
    assert len(files) == 1
    contents = files[0].read_text(encoding="utf-8")
    assert "To: candidate@example.com" in contents
    assert "Subject: Kết quả" in contents
    assert "Nội dung" in contents


def test_header_injection_and_bad_recipient_refused():
    with pytest.raises(EmailSendError):
        send_email("candidate@example.com\r\nBcc: other@example.com", "Subject", "Body")
    with pytest.raises(EmailSendError):
        send_email("not-an-address", "Subject", "Body")
    with pytest.raises(EmailSendError):
        send_email("candidate@example.com", "Subject\nBcc: other@example.com", "Body")


def test_failed_delivery_keeps_approved_and_can_retry(monkeypatch, email_environment):
    essay_id = _approved()

    def fail_once(*args, **kwargs):
        raise EmailSendError("SMTP delivery failed. Check the server settings and try again.")

    monkeypatch.setattr("ielts_ai.services.review_service.send_email", fail_once)
    with pytest.raises(EmailSendError):
        approve_and_send(essay_id)
    assert list_email_attempts(email_environment, essay_id)[0]["status"] == "failed"
    assert get_essay(email_environment, essay_id)["status"] == "approved"

    monkeypatch.setattr("ielts_ai.services.review_service.send_email", send_email)
    assert approve_and_send(essay_id)["status"] == "emailed"


def test_send_claim_exists_before_delivery(monkeypatch, email_environment):
    essay_id = _approved()

    def check_claim(*args, **kwargs):
        attempts = list_email_attempts(email_environment, essay_id)
        assert len(attempts) == 1
        assert attempts[0]["status"] == "sending"
        with pytest.raises(ValueError, match="already sending"):
            approve_and_send(essay_id)

    monkeypatch.setattr("ielts_ai.services.review_service.send_email", check_claim)
    assert approve_and_send(essay_id)["status"] == "emailed"
    assert list_email_attempts(email_environment, essay_id)[0]["status"] == "sent"


def test_approved_result_preview_and_file_send_share_the_same_content(email_environment):
    essay_id = _approved()
    preview = get_email_preview(essay_id)
    assert preview["recipient"] == "candidate@example.com"
    assert all(
        label in preview["body"]
        for label in ("Task Response (TR)", "Overall Band:", "Nhận xét của giám khảo")
    )
    assert "được giám khảo xác nhận" in preview["body"]

    approve_and_send(essay_id)
    output = next(Path("outbox").glob(f"{essay_id}_*.txt")).read_text(encoding="utf-8")
    assert preview["subject"] in output
    assert preview["body"] in output
    assert get_essay(email_environment, essay_id)["status"] == "emailed"


def test_password_is_not_exposed_in_error_database_or_logs(monkeypatch, email_environment, caplog):
    monkeypatch.setenv("EMAIL_MODE", "smtp")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "very-secret-password")
    essay_id = _approved()

    class BrokenSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            raise OSError(f"authentication failed for {password}")

    monkeypatch.setattr("ielts_ai.services.email_service.smtplib.SMTP", BrokenSMTP)
    with pytest.raises(EmailSendError) as error:
        approve_and_send(essay_id)
    assert "very-secret-password" not in str(error.value)
    assert "very-secret-password" not in caplog.text
    assert (
        "very-secret-password" not in list_email_attempts(email_environment, essay_id)[0]["error"]
    )
