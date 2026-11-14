"""Tests for filtered operational metrics and masked email activity."""

from ielts_ai.config import get_settings
from ielts_ai.db.repo import create_essay, init_db, log_llm_call, record_email
from ielts_ai.services.metrics_service import get_call_metrics, get_email_metrics


def test_call_metrics_aggregate_filtered_calls(monkeypatch, tmp_path):
    db_path = str(tmp_path / "metrics.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    settings = get_settings()

    log_llm_call(db_path, 7, "retrieve", 25, 10, 4)
    log_llm_call(db_path, 7, "grade", 50, 20, 8, retries=1)
    log_llm_call(db_path, 7, "grade", 100, 30, 12, status="error", error="provider unavailable")
    log_llm_call(db_path, 8, "grade", 200, 1, 1)

    metrics = get_call_metrics(essay_id=7)
    assert metrics["total_calls"] == 3
    assert metrics["average_latency_ms"] == 175 / 3
    assert metrics["p95_latency_ms"] == 100
    assert metrics["error_rate"] == 1 / 3
    assert metrics["retry_rate"] == 1 / 3
    assert metrics["per_step"]["grade"]["input_tokens"] == 50
    assert metrics["latency_per_step"]["grade"] == 75
    assert sum(item["calls"] for item in metrics["calls_series"]) == 3

    filtered = get_call_metrics(essay_id=7, step="grade", status="ok")
    assert filtered["total_calls"] == 1
    assert filtered["per_step"]["grade"]["output_tokens"] == 8
    assert settings.db_path == db_path


def test_email_metrics_mask_recipient_and_return_empty_state(monkeypatch, tmp_path):
    db_path = str(tmp_path / "metrics.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)

    empty = get_email_metrics()
    assert empty == {"counts": {}, "recent_attempts": []}

    essay_id = create_essay(db_path, "alice@example.com", "Prompt", "Essay")
    record_email(db_path, essay_id, "alice@example.com", "sent")
    record_email(db_path, essay_id, "bob@example.org", "failed", error="delivery failed")
    metrics = get_email_metrics()
    assert metrics["counts"] == {"failed": 1, "sent": 1}
    assert {attempt["to_email"] for attempt in metrics["recent_attempts"]} == {
        "a***@example.com",
        "b***@example.org",
    }
