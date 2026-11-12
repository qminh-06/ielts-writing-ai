"""LLM client protocol and response type."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class LLMProviderError(Exception):
    """Raised when an external LLM provider call fails."""

    pass


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    text: str
    input_tokens: int
    output_tokens: int
    model: str


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients. All implementations must satisfy this interface."""

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Send a prompt and return a JSON-formatted response.

        Args:
            system: System prompt text.
            user: User prompt text.
            temperature: Sampling temperature (default 0.0 for consistency).

        Returns:
            LLMResponse with text, token counts, and model name.
        """
        ...
