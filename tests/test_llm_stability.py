"""Regression tests for real-provider retries, limits, logging, and failure status."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ielts_ai.db.repo import create_essay, init_db, list_llm_calls
from ielts_ai.llm.client import RealLLMClient
from ielts_ai.services.grading_service import start_grading

ESSAY = " ".join(["Students learn through shared work and careful feedback."] * 45)
MOCK_RESPONSE = json.loads(
    (Path(__file__).parents[1] / "data" / "samples" / "grading_result.mock.json").read_text(
        encoding="utf-8"
    )
)
for _criterion in MOCK_RESPONSE["criteria"]:
    _criterion["evidence"] = []


class ProviderHttpError(Exception):
    def __init__(self, status: int, message: str = "provider failure") -> None:
        super().__init__(message)
        self.code = status


def _configured_grading(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    responses: list[object],
    *,
    max_attempts: int = 3,
    thinking_budget: int | None = None,
) -> tuple[dict, str, MagicMock, list[float]]:
    db_path = str(tmp_path / "llm.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("LLM_PROVIDER", "real")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", str(max_attempts))
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("LLM_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "1234")
    if thinking_budget is not None:
        monkeypatch.setenv("LLM_THINKING_BUDGET", str(thinking_budget))
    else:
        monkeypatch.delenv("LLM_THINKING_BUDGET", raising=False)
    monkeypatch.setenv("USE_MOCK_RAG", "true")
    essay_id = create_essay(db_path, "student@example.com", "Discuss education.", ESSAY)
    fake_google_client = MagicMock()
    fake_google_client.models.generate_content.side_effect = responses
    google_client_factory = MagicMock(return_value=fake_google_client)
    monkeypatch.setattr("google.genai.Client", google_client_factory)
    sleeps: list[float] = []
    monkeypatch.setattr("ielts_ai.llm.client.time.sleep", sleeps.append)
    client = RealLLMClient(api_key="secret-test-api-key", model="test-model")
    monkeypatch.setattr("ielts_ai.agent.graph.get_llm_client", lambda: client)
    result = start_grading(essay_id)
    return result, db_path, (fake_google_client, google_client_factory), sleeps


def _response() -> SimpleNamespace:
    return SimpleNamespace(
        text=json.dumps(MOCK_RESPONSE),
        usage_metadata=SimpleNamespace(
            prompt_token_count=31,
            candidates_token_count=17,
            thoughts_token_count=9,
        ),
    )


def test_real_provider_retries_429_and_5xx_and_records_limits_and_tokens(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, db_path, clients, sleeps = _configured_grading(
        tmp_path,
        monkeypatch,
        [ProviderHttpError(429), ProviderHttpError(503), _response()],
    )
    client, client_factory = clients

    grade_call = next(
        call for call in list_llm_calls(db_path, result["essay_id"]) if call["step"] == "grade"
    )
    assert result["status"] == "ai_done"
    assert client.models.generate_content.call_count == 3
    assert sleeps == [1, 2]
    assert grade_call["status"] == "ok"
    assert grade_call["retries"] == 2
    assert grade_call["input_tokens"] == 31
    assert grade_call["output_tokens"] == 17
    assert grade_call["thinking_tokens"] == 9

    call_args = client.models.generate_content.call_args
    assert call_args.kwargs["config"].max_output_tokens == 1234
    assert client.models.generate_content.call_args_list[0].kwargs["config"].thinking_config is None
    assert client_factory.call_args.kwargs["http_options"].timeout == 1000


def test_http_429_after_max_attempts_fails_with_safe_log_and_status(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, db_path, clients, sleeps = _configured_grading(
        tmp_path,
        monkeypatch,
        [
            ProviderHttpError(429, "secret-test-api-key"),
            ProviderHttpError(429),
            ProviderHttpError(429),
        ],
    )
    client, _ = clients

    grade_call = next(
        call for call in list_llm_calls(db_path, result["essay_id"]) if call["step"] == "grade"
    )
    assert result["status"] == "grading_failed"
    assert client.models.generate_content.call_count == 3
    assert sleeps == [1, 2]
    assert grade_call["status"] == "error"
    assert grade_call["retries"] == 2
    assert "HTTP 429" in grade_call["error"]
    assert "secret-test-api-key" not in grade_call["error"]
    assert "secret-test-api-key" not in str(result["errors"])


def test_provider_timeout_fails_without_retry_and_is_logged(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, db_path, clients, sleeps = _configured_grading(
        tmp_path,
        monkeypatch,
        [TimeoutError("secret-test-api-key")],
    )
    client, _ = clients

    grade_call = next(
        call for call in list_llm_calls(db_path, result["essay_id"]) if call["step"] == "grade"
    )
    assert result["status"] == "grading_failed"
    assert client.models.generate_content.call_count == 1
    assert sleeps == []
    assert grade_call["status"] == "error"
    assert grade_call["error"] == "Gemini API request timed out."


def test_invalid_provider_json_is_logged_and_marks_essay_failed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_json_response = _response()
    bad_json_response.text = "not-json"
    result, db_path, clients, _ = _configured_grading(
        tmp_path,
        monkeypatch,
        [bad_json_response for _ in range(3)],
        max_attempts=1,
    )
    client, _ = clients

    grade_calls = [
        call for call in list_llm_calls(db_path, result["essay_id"]) if call["step"] == "grade"
    ]
    assert result["status"] == "grading_failed"
    assert client.models.generate_content.call_count == 3
    assert len(grade_calls) == 3
    assert all(call["status"] == "error" for call in grade_calls)
    assert all(call["error"] == "Provider returned invalid JSON." for call in grade_calls)
    assert all("not-json" not in call["error"] for call in grade_calls)


def test_unsupported_thinking_budget_is_logged_and_ignored(
    tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO")
    result, db_path, clients, _ = _configured_grading(
        tmp_path,
        monkeypatch,
        [
            ProviderHttpError(400, "thinking budget unsupported"),
            _response(),
        ],
        thinking_budget=512,
    )
    client, _ = clients

    grade_call = next(
        call for call in list_llm_calls(db_path, result["essay_id"]) if call["step"] == "grade"
    )
    configs = [call.kwargs["config"] for call in client.models.generate_content.call_args_list]
    assert result["status"] == "ai_done"
    assert grade_call["retries"] == 1
    assert configs[0].thinking_config.thinking_budget == 512
    assert configs[1].thinking_config is None
    assert "LLM_THINKING_BUDGET is unsupported" in caplog.text


def test_real_requests_are_spaced_across_client_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    import ielts_ai.llm.client as llm_client_module

    monkeypatch.setenv("LLM_MIN_INTERVAL_SECONDS", "5")
    monkeypatch.setattr(llm_client_module, "_next_request_at", 0.0)
    clock = [0.0]
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(llm_client_module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(llm_client_module.time, "sleep", fake_sleep)
    response = _response()
    google_client = MagicMock()
    google_client.models.generate_content.return_value = response
    monkeypatch.setattr("google.genai.Client", MagicMock(return_value=google_client))

    RealLLMClient(api_key="test-key", model="test-model").complete_json("system", "first")
    RealLLMClient(api_key="test-key", model="test-model").complete_json("system", "second")

    assert google_client.models.generate_content.call_count == 2
    assert sleeps == [5.0]
