"""Opt-in SMTP smoke test, enabled only with explicit test credentials."""

import pytest

from ielts_ai.config import get_settings
from ielts_ai.services.email_service import send_email


def _smtp_configured() -> bool:
    settings = get_settings()
    return all(
        (
            settings.smtp_host,
            settings.smtp_user,
            settings.smtp_password,
            settings.smtp_test_to,
        )
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not _smtp_configured(),
    reason="SMTP integration requires SMTP settings and SMTP_TEST_TO.",
)
def test_smtp_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Send an explicit integration-only email using configured SMTP credentials."""
    monkeypatch.setenv("EMAIL_MODE", "smtp")
    settings = get_settings()
    assert send_email(
        settings.smtp_test_to,
        "IELTS AI SMTP integration test",
        "This is an opt-in SMTP integration test.",
    )
