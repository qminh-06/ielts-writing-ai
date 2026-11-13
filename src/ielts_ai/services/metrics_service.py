"""Read-only service for LLM and retrieval call metrics."""

from collections import defaultdict
from typing import Any

from ielts_ai.config import get_settings
from ielts_ai.db.repo import list_llm_calls


def get_call_metrics(essay_id: int | None = None, limit: int = 100) -> dict[str, Any]:
    """Return grouped counts, average latency, error rate, and recent calls."""
    calls = list_llm_calls(get_settings().db_path, essay_id)
    counts: dict[str, int] = defaultdict(int)
    for call in calls:
        counts[call["step"]] += 1
    total = len(calls)
    return {
        "counts_per_step": dict(counts),
        "average_latency_ms": sum(call["latency_ms"] for call in calls) / total if total else 0.0,
        "error_rate": sum(call["status"] != "ok" for call in calls) / total if total else 0.0,
        "total_calls": total,
        "recent_calls": calls[: max(0, limit)],
    }
