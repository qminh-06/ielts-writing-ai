"""Mock LLM client for testing and development without real API calls."""
import json
import logging
from pathlib import Path

from ielts_ai.llm.base import LLMClient, LLMResponse

logger = logging.getLogger(__name__)

_MOCK_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "samples" / "grading_result.mock.json"


class MockLLMClient:
    """Returns the content of data/samples/grading_result.mock.json.

    Fully implemented — no network calls, no model downloads.
    Used when LLM_PROVIDER=mock (default for CI and development).
    """

    def __init__(self, mock_path: Path | None = None) -> None:
        self._mock_path = mock_path or _MOCK_DATA_PATH

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Return mock grading result JSON regardless of input.

        Args:
            system: Ignored in mock mode.
            user: Ignored in mock mode.
            temperature: Ignored in mock mode.

        Returns:
            LLMResponse with mock JSON text and fake token counts.
        """
        logger.debug("MockLLMClient: returning mock grading result")
        text = self._mock_path.read_text(encoding="utf-8")
        # Estimate token counts (rough approximation for observability logging)
        input_tokens = len((system + user).split())
        output_tokens = len(text.split())
        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model="mock",
        )
