"""Tests for RealLLMClient, markdown fence stripping, and opt-in live integration."""

import os
from unittest.mock import MagicMock, patch

import pytest

from ielts_ai.agent.evaluate import _strip_markdown_fences
from ielts_ai.llm.base import LLMProviderError
from ielts_ai.llm.client import RealLLMClient
from ielts_ai.schemas import Criterion, CriterionScore, GradingResult


def test_strip_markdown_fences() -> None:
    # 1. Plain text without fences
    assert _strip_markdown_fences('{"test": 1}') == '{"test": 1}'

    # 2. Markdown json block
    fenced = '```json\n{"test": 1}\n```'
    assert _strip_markdown_fences(fenced) == '{"test": 1}'

    # 3. Markdown without json tag
    fenced_no_tag = '```\n{"test": 2}\n```'
    assert _strip_markdown_fences(fenced_no_tag) == '{"test": 2}'


def test_real_llm_client_missing_key() -> None:
    client = RealLLMClient(api_key="", model="gemini-2.5-flash")
    with pytest.raises(LLMProviderError, match="LLM_API_KEY is not set"):
        client.complete_json("system", "user")


def test_real_llm_client_mocked_gemini() -> None:
    """Test RealLLMClient with monkeypatched google.genai Client."""
    fake_response = MagicMock()
    fake_response.text = '{"criteria": [], "warnings": []}'
    fake_response.usage_metadata.prompt_token_count = 120
    fake_response.usage_metadata.candidates_token_count = 80

    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.return_value = fake_response
        mock_client_cls.return_value = mock_instance

        client = RealLLMClient(api_key="fake-test-key", model="gemini-2.5-flash")
        resp = client.complete_json("system prompt", "user prompt", temperature=0.0)

        assert resp.text == '{"criteria": [], "warnings": []}'
        assert resp.input_tokens == 120
        assert resp.output_tokens == 80
        assert resp.model == "gemini-2.5-flash"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("LLM_API_KEY"),
    reason="Live integration test requires LLM_API_KEY environment variable.",
)
def test_real_llm_live_grading() -> None:
    """Live opt-in integration test with Gemini API."""
    from ielts_ai.agent.evaluate import evaluate_essay
    from ielts_ai.guardrails.output_checks import validate_output
    from ielts_ai.rag.retriever import search_rubric

    client = RealLLMClient()
    essay = (
        "In many countries, youth crime has become an escalating concern for educators and lawmakers. "
        "Some believe that stricter parental responsibility and family guidance are the best preventative measures. "
        "In conclusion, addressing family support alongside educational programs will significantly lower juvenile offenses."
    )
    prompt = "Discuss the causes and solutions for juvenile delinquency."

    rubric_chunks = []
    for crit in Criterion:
        rubric_chunks.extend(search_rubric(crit, "juvenile delinquency", top_k=1))

    result = evaluate_essay(
        essay_id=999,
        prompt_text=prompt,
        essay_text=essay,
        rubric_chunks=rubric_chunks,
        llm_client=client,
    )

    assert isinstance(result, GradingResult)
    assert len(result.criteria) == 4
    for cs in result.criteria:
        assert isinstance(cs, CriterionScore)
        assert 0.0 <= cs.band <= 9.0

    output_warnings = validate_output(result, essay)
    assert isinstance(output_warnings, list)
