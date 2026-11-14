"""Safe file and SMTP delivery for examiner-approved result emails."""

import logging
import re
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from ielts_ai.config import get_settings

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)


class EmailSendError(RuntimeError):
    """A sanitized delivery error safe to show to an examiner."""


def _validate_header(value: str, label: str) -> str:
    """Reject header injection and empty values."""
    cleaned = value.strip()
    if not cleaned or "\r" in value or "\n" in value:
        raise EmailSendError(f"{label} is invalid.")
    return cleaned


def _validate_recipient(address: str) -> str:
    """Validate a simple single-recipient email address."""
    cleaned = _validate_header(address, "Recipient")
    if not _EMAIL_RE.fullmatch(cleaned):
        raise EmailSendError("Recipient email address is invalid.")
    return cleaned


def _safe_error(error: Exception, mode: str) -> str:
    """Map SMTP errors to a credential-safe message."""
    if isinstance(error, EmailSendError):
        return str(error)
    if mode == "file" and isinstance(error, OSError):
        return "Email could not be saved to outbox."
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "SMTP authentication failed. Check SMTP settings."
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return "SMTP rejected the recipient address."
    if isinstance(error, smtplib.SMTPException | TimeoutError | OSError):
        return "SMTP delivery failed. Check the server settings and try again."
    return "Email delivery failed. Please try again."


def send_email(to: str, subject: str, body: str, essay_id: int | None = None) -> bool:
    """Deliver an email in file or SMTP mode without recording database state.

    ``essay_id`` is retained for backward compatibility and only names the file-mode artifact.
    The caller owns claim, success, and failure persistence.
    """
    recipient = _validate_recipient(to)
    clean_subject = _validate_header(subject, "Subject")
    settings = get_settings()
    mode = settings.email_mode.lower()
    try:
        if mode == "file":
            outbox = Path("outbox")
            outbox.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
            identifier = str(essay_id) if essay_id is not None else "test"
            path = outbox / f"{identifier}_{timestamp}.txt"
            path.write_text(
                f"To: {recipient}\nSubject: {clean_subject}\n\n{body}", encoding="utf-8"
            )
            logger.info("Email saved in file mode for essay %s", identifier)
            return True
        if mode != "smtp":
            raise EmailSendError("EMAIL_MODE must be 'file' or 'smtp'.")

        message = EmailMessage()
        message["To"] = recipient
        message["From"] = _validate_recipient(settings.smtp_user)
        message["Subject"] = clean_subject
        message.set_content(body, charset="utf-8")
        timeout = 15
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=timeout
            ) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
        logger.info("SMTP email delivered for essay %s", essay_id)
        return True
    except Exception as error:
        safe = _safe_error(error, mode)
        logger.warning("Email delivery failed for essay %s: %s", essay_id, safe)
        raise EmailSendError(safe) from None
