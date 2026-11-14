"""Send one configured test email without exposing credentials."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ielts_ai.config import get_settings
from ielts_ai.services.email_service import EmailSendError, send_email


def main() -> None:
    """Send a short test message to the explicitly supplied recipient."""
    parser = argparse.ArgumentParser(description="Send an IELTS AI SMTP/file-mode test email")
    parser.add_argument("recipient", help="Recipient email address")
    args = parser.parse_args()
    try:
        send_email(args.recipient, "IELTS AI test email", "Kết nối email hoạt động.")
    except EmailSendError as error:
        print(f"Test email failed: {error}")
        raise SystemExit(1) from error
    if get_settings().email_mode.lower() == "file":
        print("Test email saved to outbox successfully.")
    else:
        print("Test email sent successfully.")


if __name__ == "__main__":
    main()
