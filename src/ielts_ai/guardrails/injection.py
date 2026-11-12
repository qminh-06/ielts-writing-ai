"""Prompt injection detection guardrail.

Detects attempts by essay text to escape its data context and inject
instructions into the grading prompt.

# TODO(B6): Implement robust injection detection (P1).
# Current implementation: simple keyword list (intentionally minimal).
"""

import logging

logger = logging.getLogger(__name__)

# TODO(B6): Expand this list with more sophisticated patterns.
# Consider: semantic similarity to instruction verbs, delimiter escapes, role switching.
_INJECTION_KEYWORDS: list[str] = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard the above",
    "you are now",
    "new instructions:",
    "system prompt:",
    "forget everything",
    "as an ai",
    "pretend you are",
    "act as",
    "</essay>",
    "[end of essay]",
    "###",
]


def detect_injection(text: str) -> list[str]:
    """Detect potential prompt injection attempts in essay text.

    Args:
        text: Essay text to check.

    Returns:
        List of detected injection patterns (empty if clean).
        Each string describes what was detected.

    # TODO(B6): Replace with a more robust detection approach.
    # Ideas: regex patterns, semantic classifier, LLM-based detection.
    """
    lower = text.lower()
    detected = []
    for keyword in _INJECTION_KEYWORDS:
        if keyword in lower:
            detected.append(f"Potential injection detected: {keyword!r}")
            logger.warning("Injection pattern detected in essay: %r", keyword)
    return detected
