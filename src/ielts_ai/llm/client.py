"""LLM client factory and real client implementation for Gemini."""

import logging

from ielts_ai.config import get_settings
from ielts_ai.llm.base import LLMClient, LLMProviderError, LLMResponse
from ielts_ai.llm.mock import MockLLMClient

logger = logging.getLogger(__name__)


class RealLLMClient:
    """Real LLM client using Google GenAI SDK (Gemini)."""

    def __init__(
        self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0
    ) -> None:
        self._settings = get_settings()
        self._api_key = api_key or self._settings.llm_api_key
        self._model = model or self._settings.llm_model or "gemini-2.5-flash"
        self._timeout = timeout

        if not self._api_key:
            logger.warning("RealLLMClient initialized without LLM_API_KEY")

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Call Gemini API and return a JSON-formatted response.

        Args:
            system: System prompt instruction.
            user: User prompt instruction.
            temperature: Sampling temperature (default 0.0).

        Returns:
            LLMResponse containing response text, token counts, and model name.

        Raises:
            LLMProviderError: If the API key is missing or the API call fails.
        """
        if not self._api_key:
            raise LLMProviderError(
                "LLM_API_KEY is not set. Please add it to your .env file or environment."
            )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._api_key)
            config = types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                response_mime_type="application/json",
            )

            # Generate content with timeout
            response = client.models.generate_content(
                model=self._model,
                contents=user,
                config=config,
            )

            text = response.text or ""
            input_tokens = 0
            output_tokens = 0
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

            return LLMResponse(
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self._model,
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            logger.error("Gemini API call failed: %s", exc)
            raise LLMProviderError(f"Gemini API call failed: {exc}") from exc


def get_llm_client() -> LLMClient:
    """Return the appropriate LLM client based on LLM_PROVIDER setting.

    Returns MockLLMClient when LLM_PROVIDER=mock (default).
    Returns RealLLMClient when LLM_PROVIDER=real.

    Returns:
        An LLMClient implementation.

    Raises:
        ValueError: If LLM_PROVIDER is not 'mock' or 'real'.
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "mock":
        logger.info("Using MockLLMClient (LLM_PROVIDER=mock)")
        return MockLLMClient()
    elif provider in ("real", "gemini"):
        logger.info("Using RealLLMClient (LLM_PROVIDER=%s)", provider)
        return RealLLMClient()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER={provider!r}. Must be 'mock' or 'real' ('gemini').")
