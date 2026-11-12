"""Email service for dispatching grading results to candidates.

Supports:
- file mode (EMAIL_MODE=file): writes mock .txt email files into outbox/
- smtp mode (EMAIL_MODE=smtp): connects to real SMTP server (# TODO(C5))
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

from ielts_ai.config import get_settings
from ielts_ai.db.repo import record_email

logger = logging.getLogger(__name__)


def send_email(
    to: str,
    subject: str,
    body: str,
    essay_id: int | None = None,
) -> bool:
    """Send an email to the candidate.

    In file mode, writes a file into outbox/<timestamp>_<to>.txt.
    In smtp mode, uses smtplib (# TODO(C5)).
    """
    settings = get_settings()
    mode = settings.email_mode.lower()

    if mode == "file":
        outbox = Path("outbox")
        outbox.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_to = to.replace("@", "_at_").replace(".", "_")
        filepath = outbox / f"{ts}_{safe_to}.txt"

        content = f"To: {to}\nSubject: {subject}\n\n{body}"
        filepath.write_text(content, encoding="utf-8")
        logger.info("Email written to outbox file: %s", filepath)

        if essay_id is not None:
            record_email(settings.db_path, essay_id, to, status="sent")
        return True

    elif mode == "smtp":
        # TODO(C5): Implement real SMTP sending via smtplib
        logger.warning("SMTP mode requested, but real SMTP is TODO(C5).")
        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = settings.smtp_user or "noreply@ielts-ai.com"
            msg["To"] = to

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_user and settings.smtp_password:
                    server.starttls()
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            if essay_id is not None:
                record_email(settings.db_path, essay_id, to, status="sent")
            return True
        except Exception as exc:
            logger.error("SMTP send failed: %s", exc)
            if essay_id is not None:
                record_email(settings.db_path, essay_id, to, status="failed", error=str(exc))
            return False
    else:
        raise ValueError(f"Unknown EMAIL_MODE={mode!r}")
