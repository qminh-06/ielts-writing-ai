"""Detect likely prompt injection text in untrusted essay and feedback data."""

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Lowercase text, strip Vietnamese accents, and collapse whitespace."""
    lowered = text.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", plain).strip()


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(pattern))
    for label, pattern in (
        (
            "ignore previous instructions",
            r"\b(ignore|disregard|forget)\s+(all\s+)?(the\s+)?(previous|above|prior)\s+(instructions?|rules?)\b",
        ),
        (
            "score override",
            r"\b(give|assign|set|raise|award)\s+(this\s+)?(essay|me|the candidate)?\s*(a\s+)?band\s*9\b",
        ),
        ("persona override", r"\b(you are now|act as|pretend you are)\b"),
        ("system prompt", r"\b(system prompt|developer instructions?)\b"),
        ("Vietnamese instruction override", r"\b(bo qua|hay bo qua)\s+(cac\s+)?huong dan\b"),
        ("Vietnamese score override", r"\b(cho|hay cho)\s+(bai nay\s+)?band\s*9\b"),
        ("delimiter escape", r"</essay>|</examiner_feedback>|\[end of essay\]"),
    )
)


def detect_injection(text: str) -> list[str]:
    """Return warnings for instruction-like overrides in untrusted text."""
    normalized = _normalize(text)
    warnings: list[str] = []
    for label, pattern in _PATTERNS:
        if pattern.search(normalized):
            warnings.append(f"Potential injection detected: {label}")
            logger.warning("Injection pattern detected: %s", label)
    return warnings
