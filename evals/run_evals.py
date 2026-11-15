"""Evaluation runner executing test cases from data/eval_set/ and reporting metrics table.

Supports:
- Default: mock provider (offline)
- Real: --provider real (calls Gemini API if LLM_API_KEY is configured)
"""

import argparse
import difflib
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

# Ensure root and src are on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evals.metrics import (
    compute_evidence_valid_rate,
    compute_guardrail_pass_rate,
    compute_schema_valid_rate,
    evaluate_guardrail_cases,
    run_to_run_variance,
)
from ielts_ai.agent.evaluate import evaluate_essay
from ielts_ai.config import get_settings
from ielts_ai.db.repo import init_db
from ielts_ai.guardrails.output_checks import _normalize, evidence_in_essay
from ielts_ai.llm.base import LLMClient, LLMResponse
from ielts_ai.llm.client import MockLLMClient, RealLLMClient
from ielts_ai.rag.retriever import search_rubric
from ielts_ai.schemas import Criterion, GradingResult


class _PacedClient:
    """Pause between provider calls to limit pressure during diagnostic runs."""

    def __init__(self, client: LLMClient, seconds: float) -> None:
        self._client = client
        self._seconds = seconds
        self._calls = 0

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> LLMResponse:
        if self._calls:
            time.sleep(self._seconds)
        self._calls += 1
        return self._client.complete_json(system, user, temperature=temperature)


def _closest_substring(quote: str, essay: str) -> str:
    """Find the most similar essay word window using difflib."""
    tokens = list(re.finditer(r"\S+", essay))
    if not tokens:
        return ""
    target_words = max(1, len(re.findall(r"\w+", quote)))
    widths = {max(1, min(len(tokens), target_words + offset)) for offset in range(-2, 3)}
    target = _normalize(re.sub(r"(?:\.{3,}|\u2026+)", " ", quote))
    closest = ""
    highest_ratio = -1.0
    for width in widths:
        for start in range(max(1, len(tokens) - width + 1)):
            end = start + width - 1
            candidate = essay[tokens[start].start() : tokens[end].end()]
            ratio = difflib.SequenceMatcher(
                None, target, _normalize(candidate), autojunk=False
            ).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                closest = candidate
    return closest


def _debug_failed_quotes(results: list[tuple[GradingResult, str]]) -> list[dict[str, Any]]:
    """Collect invalid model evidence and the closest matching essay substrings."""
    failures: list[dict[str, Any]] = []
    for result, essay_text in results:
        for score in result.criteria:
            for quote in score.evidence:
                if quote and not evidence_in_essay(quote, essay_text):
                    failures.append(
                        {
                            "essay_id": result.essay_id,
                            "criterion": score.criterion.value,
                            "quote": quote,
                            "closest_substring": _closest_substring(quote, essay_text),
                        }
                    )
    return failures


def run_evals(
    provider: str = "mock",
    variance: bool = False,
    runs: int = 3,
    limit: int | None = None,
    sleep_between_calls: float = 0.0,
) -> dict:
    provider = provider.lower()
    real_provider = provider in ("real", "gemini")
    variance_enabled = real_provider and variance and runs == 3
    settings = get_settings()
    init_db(settings.db_path)

    eval_file = Path(__file__).parent.parent / "data" / "eval_set" / "synthetic_essays.json"
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    if not eval_file.exists():
        raise FileNotFoundError(f"Evaluation set not found at {eval_file}")

    with open(eval_file, encoding="utf-8") as f:
        essays = json.load(f)
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        essays = essays[:limit]

    if real_provider:
        if not settings.llm_api_key:
            reason = "LLM_API_KEY is not set; real-provider evaluation was not run."
            debug_path = results_dir / "day6_evidence_debug.json"
            debug_path.write_text(
                json.dumps(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "provider": provider,
                        "status": "skipped",
                        "reason": reason,
                        "failed_quotes": [],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(reason)
            print(f"Evidence debug report written to: {debug_path}")
            guardrail_rate = compute_guardrail_pass_rate(
                evaluate_guardrail_cases(
                    Path(__file__).parent.parent / "data" / "eval_set" / "guardrail_cases.json"
                )
            )
            return {
                "provider": provider,
                "status": "skipped",
                "reason": reason,
                "guardrail_pass_rate": guardrail_rate,
            }
        client = _PacedClient(RealLLMClient(), sleep_between_calls)
    else:
        client = MockLLMClient()

    raw_results = []
    parsed_results: list[tuple[GradingResult, str]] = []
    variance_results: list[dict] = []

    print(f"\nEvaluating {len(essays)} synthetic essays using provider={provider!r}...")
    if not real_provider:
        print(
            "Mock output is for workflow/schema checks only; its scores and evidence say nothing "
            "about grading quality."
        )
    if variance and not real_provider:
        print("Notice: run-to-run variance is meaningless with the deterministic mock provider.")
    if variance and real_provider and runs != 3:
        print("Notice: run-to-run variance is only enabled with exactly 3 runs.")

    # Retrieve rubric chunks for all criteria once
    rubric_chunks = []
    if real_provider:
        for crit in Criterion:
            rubric_chunks.extend(search_rubric(crit, "IELTS Task 2 academic evaluation", top_k=2))
    else:
        with patch.dict(os.environ, {"USE_MOCK_RAG": "true"}):
            for crit in Criterion:
                rubric_chunks.extend(
                    search_rubric(crit, "IELTS Task 2 academic evaluation", top_k=2)
                )

    for item in essays:
        essay_text = item["essay"]
        prompt_text = item["prompt"]
        try:
            res = evaluate_essay(
                essay_id=item["id"],
                prompt_text=prompt_text,
                essay_text=essay_text,
                rubric_chunks=rubric_chunks,
                llm_client=client,
            )
            raw_results.append(res.model_dump())
            parsed_results.append((res, essay_text))
        except Exception as exc:
            raw_results.append({})
            print(
                f"Error evaluating essay #{item['id']}: evaluation failed "
                f"({type(exc).__name__})."
            )
            continue
        if variance_enabled:
            try:
                repeated = [res]
                for _ in range(2):
                    repeated.append(
                        evaluate_essay(
                            essay_id=item["id"],
                            prompt_text=prompt_text,
                            essay_text=essay_text,
                            rubric_chunks=rubric_chunks,
                            llm_client=client,
                        )
                    )
                variance_results.append(
                    {
                        "essay_id": item["id"],
                        **run_to_run_variance(repeated, n_runs=runs),
                    }
                )
            except Exception as exc:
                print(
                    f"Variance run failed for essay #{item['id']}: "
                    f"evaluation failed ({type(exc).__name__})."
                )

    # Compute Day 3 metrics
    schema_rate = compute_schema_valid_rate(raw_results)

    evidence_rates = [compute_evidence_valid_rate(res, text) for res, text in parsed_results]
    avg_evidence_rate = sum(evidence_rates) / len(parsed_results) if parsed_results else 0.0

    guardrail_path = Path(__file__).parent.parent / "data" / "eval_set" / "guardrail_cases.json"
    guardrail_rate = compute_guardrail_pass_rate(evaluate_guardrail_cases(guardrail_path))
    reference_bands = {item["id"]: item.get("reference_band") for item in essays}
    has_references = all(
        isinstance(band, int | float) and not isinstance(band, bool)
        for band in reference_bands.values()
    )
    results_by_essay = {result.essay_id: result for result, _ in parsed_results}
    mae_values = (
        [
            abs(results_by_essay[essay_id].overall_band - reference)
            for essay_id, reference in reference_bands.items()
            if essay_id in results_by_essay
        ]
        if has_references
        else []
    )
    mae = (
        sum(mae_values) / len(mae_values)
        if has_references and len(mae_values) == len(essays)
        else None
    )

    failed_quotes = _debug_failed_quotes(parsed_results) if real_provider else []
    metrics_summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "provider": provider,
        "sample_count": len(essays),
        "schema_valid_rate": round(schema_rate, 4),
        "evidence_valid_rate": (
            round(avg_evidence_rate, 4) if real_provider else "n/a (mock provider)"
        ),
        "run_to_run_variance": "skipped" if real_provider else "n/a (mock provider)",
        "guardrail_pass_rate": round(guardrail_rate, 4),
        "mae": round(mae, 4) if mae is not None else None,
    }
    if variance_enabled:
        variance_share = (
            sum(item["all_criteria_within_0_5"] for item in variance_results)
            / len(variance_results)
            if variance_results
            else 0.0
        )
        metrics_summary["run_to_run_variance"] = {
            "runs_per_essay": runs,
            "share_all_criteria_within_0_5": variance_share,
            "essays": variance_results,
        }

    # Print table
    print("\n" + "=" * 54)
    print("      IELTS Writing AI - Day 6 Evaluation Report       ")
    print("=" * 54)
    print(f"{'Metric':<32} | {'Value':<16}")
    print("-" * 54)
    print(f"{'1. Schema-valid Rate':<32} | {schema_rate * 100:.1f}%")
    evidence_display = f"{avg_evidence_rate * 100:.1f}%" if real_provider else "n/a (mock provider)"
    print(f"{'2. Evidence-valid Rate':<32} | {evidence_display}")
    if variance_enabled:
        print(
            f"{'3. Essays within 0.5 across criteria':<32} | {metrics_summary['run_to_run_variance']['share_all_criteria_within_0_5']:.1%}"
        )
    else:
        variance_display = "skipped" if real_provider else "n/a (mock provider)"
        print(f"{'3. Run-to-run Variance':<32} | {variance_display}")
    print(f"{'4. Guardrail Pass Rate':<32} | {guardrail_rate * 100:.1f}%")
    print(
        f"{'MAE':<32} | {mae:.4f}"
        if mae is not None
        else "MAE                              | skipped: no reference bands"
    )
    print("=" * 54)
    if variance_enabled:
        print("\nPer-essay criterion variance (range / standard deviation)")
        for essay_result in variance_results:
            criterion_metrics = ", ".join(
                f"{criterion}: {values['range']:.1f} / {values['standard_deviation']:.3f}"
                for criterion, values in essay_result["criteria"].items()
            )
            print(f"Essay #{essay_result['essay_id']}: {criterion_metrics}")

    output_path = results_dir / "latest.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2)

    print(f"Evaluation report written to: {output_path}\n")
    if real_provider:
        debug_path = results_dir / "day6_evidence_debug.json"
        debug_path.write_text(
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "provider": provider,
                    "status": "completed",
                    "sample_count": len(essays),
                    "evidence_valid_rate": round(avg_evidence_rate, 4),
                    "failed_quote_count": len(failed_quotes),
                    "failed_quotes": failed_quotes,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        for failure in failed_quotes:
            print(
                "Evidence mismatch — "
                f"essay_id={failure['essay_id']} "
                f"criterion={failure['criterion']} "
                f"quote={failure['quote']!r} "
                f"closest_substring={failure['closest_substring']!r}"
            )
        print(f"Evidence debug report written to: {debug_path}")
    return metrics_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run IELTS AI evaluation suite")
    parser.add_argument(
        "--provider",
        choices=["mock", "real"],
        default="mock",
        help="LLM provider: 'mock' (default offline) or 'real' (live API)",
    )
    parser.add_argument(
        "--variance", action="store_true", help="Repeat each essay to measure score variance"
    )
    parser.add_argument("--runs", type=int, default=3, help="Runs per essay for variance analysis")
    parser.add_argument("--limit", type=int, help="Evaluate only the first N synthetic essays.")
    parser.add_argument(
        "--sleep-between-calls",
        type=float,
        default=0.0,
        help="Seconds to wait between provider calls.",
    )
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be at least 2")
    if args.provider == "real" and args.variance and args.runs != 3:
        parser.error("--provider real --variance requires exactly --runs 3")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.sleep_between_calls < 0:
        parser.error("--sleep-between-calls must be non-negative")
    run_evals(
        args.provider,
        variance=args.variance,
        runs=args.runs,
        limit=args.limit,
        sleep_between_calls=args.sleep_between_calls,
    )


if __name__ == "__main__":
    main()
