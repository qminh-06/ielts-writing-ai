"""Input validation guardrails for essay submissions.

Checks run BEFORE the essay enters the grading pipeline.
"""

import logging
import re
from dataclasses import dataclass, field

from ielts_ai.guardrails.injection import detect_injection

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

MIN_CHARS = 100  # Hard minimum — below this is clearly not an essay
MAX_CHARS = 10_000  # Hard maximum — prevents abuse
WORD_COUNT_WARNING = 250  # IELTS Task 2 minimum is 250 words


@dataclass
class InputCheckResult:
    """Result of input validation.

    errors: Fatal problems — grading should NOT proceed.
    warnings: Non-fatal issues — grading proceeds but examiner is notified.
    """

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if there are no fatal errors."""
        return len(self.errors) == 0


def _count_words(text: str) -> int:
    """Count words in text (split on whitespace)."""
    return len(text.split())


def validate_input(essay_text: str, email: str) -> InputCheckResult:
    """Validate essay text and candidate email before grading.

    Args:
        essay_text: The candidate's essay text.
        email: The candidate's email address.

    Returns:
        InputCheckResult with any errors (fatal) and warnings (non-fatal).
    """
    result = InputCheckResult()

    # --- Email validation ---
    if not email or not email.strip():
        result.errors.append("Email không được để trống / Email is required.")
    elif not _EMAIL_RE.match(email.strip()):
        result.errors.append(f"Email không hợp lệ: {email!r} / Invalid email format: {email!r}")

    # --- Essay text validation ---
    if not essay_text or not essay_text.strip():
        result.errors.append("Bài viết không được để trống / Essay text is required.")
        return result  # No point checking length on empty text

    stripped = essay_text.strip()
    char_count = len(stripped)
    word_count = _count_words(stripped)

    if char_count < MIN_CHARS:
        result.errors.append(
            f"Bài viết quá ngắn ({char_count} ký tự, tối thiểu {MIN_CHARS}) / "
            f"Essay too short ({char_count} chars, minimum {MIN_CHARS})."
        )
    elif char_count > MAX_CHARS:
        result.errors.append(
            f"Bài viết quá dài ({char_count} ký tự, tối đa {MAX_CHARS}) / "
            f"Essay too long ({char_count} chars, maximum {MAX_CHARS})."
        )

    if word_count < WORD_COUNT_WARNING:
        result.warnings.append(
            f"Bài viết có {word_count} từ, ít hơn 250 từ yêu cầu của IELTS Task 2 / "
            f"Essay has {word_count} words, below the 250-word IELTS Task 2 minimum."
        )

    result.warnings.extend(detect_injection(stripped))

    logger.debug(
        "Input check: email=%s, chars=%d, words=%d, errors=%d, warnings=%d",
        email,
        char_count,
        word_count,
        len(result.errors),
        len(result.warnings),
    )
    return result
