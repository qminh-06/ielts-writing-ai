"""LLM client factory and real client implementation for Gemini."""

import logging
import time
from typing import Any

from ielts_ai.config import get_settings
from ielts_ai.llm.base import LLMClient, LLMProviderError, LLMResponse
from ielts_ai.llm.mock import MockLLMClient

logger = logging.getLogger(__name__)


class RealLLMClient:
    """Real LLM client using Google GenAI SDK (Gemini)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._settings = get_settings()
        self._api_key = api_key or self._settings.llm_api_key
        self._model = model or self._settings.llm_model or "gemini-3.8-flash"
        self._timeout = timeout if timeout is not None else self._settings.llm_timeout_seconds
        self.last_attempt_retries = 0

        if not self._api_key:
            logger.warning("RealLLMClient initialized without LLM_API_KEY")

    @staticmethod
    def _status_code(error: Exception) -> int | None:
        """Return a provider HTTP status without depending on SDK exception classes."""
        for value in (
            getattr(error, "code", None),
            getattr(error, "status_code", None),
            getattr(getattr(error, "response", None), "status_code", None),
        ):
            try:
                status = int(value)
            except (TypeError, ValueError):
                continue
            if 100 <= status <= 599:
                return status
        return None

    @staticmethod
    def _safe_error(error: Exception, status: int | None) -> str:
        """Return a sanitized provider error suitable for UI and persistent logs."""
        if isinstance(error, TimeoutError):
            return "Gemini API request timed out."
        if status is not None:
            return f"Gemini API request failed with HTTP {status}."
        return "Gemini API request failed."

    @staticmethod
    def _is_transient(status: int | None) -> bool:
        return status == 429 or status is not None and 500 <= status <= 599

    @staticmethod
    def _is_unsupported_thinking(error: Exception, status: int | None) -> bool:
        return status == 400 and "thinking" in str(error).casefold()

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Call Gemini API and return a JSON-formatted response.

        Args:
            system: System prompt instruction.
            user: User prompt instruction.
            temperature: Sampling temperature (default 0.0).
            response_schema: Optional JSON schema dictionary to constrain model output.

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

            client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(timeout=round(self._timeout * 1000)),
            )
            use_thinking_budget = self._settings.llm_thinking_budget is not None
            use_schema = response_schema is not None
            self.last_attempt_retries = 0
            for attempt in range(1, self._settings.llm_max_attempts + 1):
                config_values: dict[str, Any] = {
                    "system_instruction": system,
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                    "max_output_tokens": self._settings.llm_max_output_tokens,
                }
                if use_schema:
                    try:
                        config_values["response_schema"] = response_schema
                    except Exception as schema_err:
                        logger.warning(
                            "Failed to configure response_schema (%s); falling back without schema.",
                            schema_err,
                        )
                        use_schema = False
                if use_thinking_budget:
                    config_values["thinking_config"] = types.ThinkingConfig(
                        thinking_budget=self._settings.llm_thinking_budget
                    )
                try:
                    config = types.GenerateContentConfig(**config_values)
                except Exception as cfg_err:
                    if use_schema:
                        logger.warning(
                            "GenerateContentConfig rejected response_schema (%s); falling back without it.",
                            cfg_err,
                        )
                        use_schema = False
                        config_values.pop("response_schema", None)
                        config = types.GenerateContentConfig(**config_values)
                    else:
                        raise cfg_err
                try:
                    response = client.models.generate_content(
                        model=self._model,
                        contents=user,
                        config=config,
                    )
                    usage = response.usage_metadata
                    return LLMResponse(
                        text=response.text or "",
                        input_tokens=usage.prompt_token_count or 0 if usage else 0,
                        output_tokens=usage.candidates_token_count or 0 if usage else 0,
                        thinking_tokens=(
                            getattr(usage, "thoughts_token_count", 0) or 0 if usage else 0
                        ),
                        model=self._model,
                    )
                except Exception as exc:
                    status = self._status_code(exc)
                    if use_thinking_budget and self._is_unsupported_thinking(exc, status):
                        if attempt < self._settings.llm_max_attempts:
                            use_thinking_budget = False
                            self.last_attempt_retries += 1
                            logger.info(
                                "LLM_THINKING_BUDGET is unsupported by the selected model; "
                                "retrying without it."
                            )
                            continue
                    if use_schema and status == 400:
                        logger.warning(
                            "Gemini API returned 400 with response_schema; falling back without schema."
                        )
                        use_schema = False
                        continue
                    if self._is_transient(status) and attempt < self._settings.llm_max_attempts:
                        self.last_attempt_retries += 1
                        delay = min(2 ** (attempt - 1), 20)
                        logger.warning(
                            "Gemini API returned HTTP %s; retrying attempt %s/%s in %s seconds.",
                            status,
                            attempt + 1,
                            self._settings.llm_max_attempts,
                            delay,
                        )
                        time.sleep(delay)
                        continue

                    safe_error = self._safe_error(exc, status)
                    logger.error("Gemini API request failed: %s", safe_error)
                    raise LLMProviderError(safe_error) from None
            raise LLMProviderError("Gemini API request failed after the configured attempts.")
        except LLMProviderError:
            raise
        except Exception as exc:
            safe_error = self._safe_error(exc, self._status_code(exc))
            logger.error("Gemini API request failed: %s", safe_error)
            raise LLMProviderError(safe_error) from None


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
