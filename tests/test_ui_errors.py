"""Tests for safe Vietnamese UI messages from service errors."""

from app.ui_helpers import format_email_error, format_grading_error


def test_provider_error_messages_are_vietnamese_and_actionable() -> None:
    assert "HTTP 429" in format_grading_error("Gemini API request failed with HTTP 429.")
    assert "thời gian chờ" in format_grading_error("Gemini API request timed out.")
    assert "python scripts/build_rubric_index.py" in format_grading_error(
        "Rubric index not found. Run python scripts/build_rubric_index.py."
    )
    assert "không đúng định dạng" in format_grading_error(
        "Failed to grade essay after 3 attempts. Last error: JSONDecodeError."
    )


def test_smtp_error_messages_do_not_echo_raw_credentials_or_provider_details() -> None:
    message = format_email_error("SMTP authentication failed; password=secret-value")

    assert "App Password" in message
    assert "secret-value" not in message
    assert "Gửi email thất bại" in format_email_error("unexpected provider detail")
