"""LLM client factory and real client stub."""
import logging

from ielts_ai.config import get_settings
from ielts_ai.llm.base import LLMClient, LLMResponse
from ielts_ai.llm.mock import MockLLMClient

logger = logging.getLogger(__name__)


class RealLLMClient:
    """Real LLM client — not yet implemented.

    # TODO(A3): Choose LLM provider (Gemini, OpenAI, etc.) and implement.
    # TODO(A3): Use self._settings.llm_api_key and self._settings.llm_model.
    # TODO(A3): Implement complete_json with proper error handling and retries.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        logger.warning("RealLLMClient is not implemented yet — use LLM_PROVIDER=mock")

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Call the real LLM API.

        # TODO(A3): Implement with actual LLM provider SDK.
        """
        raise NotImplementedError(
            "TODO(A3): Real LLM client not implemented. Set LLM_PROVIDER=mock for development."
        )


def get_llm_client() -> LLMClient:
    """Return the appropriate LLM client based on LLM_PROVIDER setting.

    Returns MockLLMClient when LLM_PROVIDER=mock (default).
    Returns RealLLMClient when LLM_PROVIDER=real (requires TODO A3).

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
    elif provider == "real":
        logger.info("Using RealLLMClient (LLM_PROVIDER=real)")
        return RealLLMClient()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER={provider!r}. Must be 'mock' or 'real'."
        )
