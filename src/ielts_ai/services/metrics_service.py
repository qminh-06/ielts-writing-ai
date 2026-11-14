"""Read-only metrics for LLM/retrieval calls and email attempts."""

import math
from collections import defaultdict
from typing import Any

from ielts_ai.config import get_settings
from ielts_ai.db.repo import list_email_attempts, list_llm_calls


def _percentile_95(values: list[float]) -> float:
    """Return a nearest-rank p95 value without external dependencies."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def get_call_metrics(
    essay_id: int | None = None,
    step: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Return filtered operational metrics and data for basic Streamlit charts."""
    calls = list_llm_calls(get_settings().db_path, essay_id)
    filtered = [
        call
        for call in calls
        if (step is None or call["step"] == step) and (status is None or call["status"] == status)
    ]
    counts: dict[str, int] = defaultdict(int)
    per_step: dict[str, dict[str, float | int]] = {}
    latency_by_step: dict[str, list[float]] = defaultdict(list)
    calls_by_minute: dict[str, int] = defaultdict(int)
    for call in filtered:
        counts[call["step"]] += 1
        latency_by_step[call["step"]].append(call["latency_ms"])
        calls_by_minute[call["ts"][:16]] += 1
        aggregate = per_step.setdefault(
            call["step"], {"calls": 0, "input_tokens": 0, "output_tokens": 0, "retries": 0}
        )
        aggregate["calls"] += 1
        aggregate["input_tokens"] += call["input_tokens"]
        aggregate["output_tokens"] += call["output_tokens"]
        aggregate["retries"] += call["retries"]
    total = len(filtered)
    return {
        "total_calls": total,
        "average_latency_ms": sum(call["latency_ms"] for call in filtered) / total
        if total
        else 0.0,
        "p95_latency_ms": _percentile_95([call["latency_ms"] for call in filtered]),
        "error_rate": sum(call["status"] != "ok" for call in filtered) / total if total else 0.0,
        "retry_rate": sum(call["retries"] > 0 for call in filtered) / total if total else 0.0,
        "counts_per_step": dict(counts),
        "per_step": per_step,
        "latency_per_step": {
            step_name: sum(latencies) / len(latencies)
            for step_name, latencies in latency_by_step.items()
        },
        "recent_calls": filtered[: max(0, limit)],
        "calls_series": [
            {"ts": timestamp, "calls": count}
            for timestamp, count in sorted(calls_by_minute.items())
        ],
    }


def _mask_email(address: str) -> str:
    """Mask an email address for observability views."""
    if "@" not in address:
        return "***"
    local, domain = address.split("@", 1)
    return f"{local[:1]}***@{domain}"


def get_email_metrics(essay_id: int | None = None, limit: int = 100) -> dict[str, Any]:
    """Return masked email attempt metrics for the Logs page."""
    attempts = list_email_attempts(get_settings().db_path, essay_id)
    counts: dict[str, int] = defaultdict(int)
    for attempt in attempts:
        counts[attempt["status"]] += 1
    safe_attempts = [
        {**attempt, "to_email": _mask_email(attempt["to_email"])}
        for attempt in attempts[: max(0, limit)]
    ]
    return {"counts": dict(counts), "recent_attempts": safe_attempts}
