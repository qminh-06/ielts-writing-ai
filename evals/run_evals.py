"""Evaluation runner executing test cases from data/eval_set/ and reporting metrics table.

Supports:
- Default: mock provider (offline)
- Real: --provider real (calls Gemini API if LLM_API_KEY is configured)
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure root and src are on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evals.metrics import (
    compute_evidence_valid_rate,
    compute_guardrail_pass_rate,
    compute_run_to_run_variance,
    compute_schema_valid_rate,
)
from ielts_ai.agent.evaluate import evaluate_essay
from ielts_ai.config import get_settings
from ielts_ai.db.repo import init_db
from ielts_ai.llm.client import MockLLMClient, RealLLMClient
from ielts_ai.rag.retriever import search_rubric
from ielts_ai.schemas import Criterion, GradingResult


def run_evals(provider: str = "mock") -> dict:
    settings = get_settings()
    init_db(settings.db_path)

    eval_file = Path(__file__).parent.parent / "data" / "eval_set" / "synthetic_essays.json"
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    if not eval_file.exists():
        raise FileNotFoundError(f"Evaluation set not found at {eval_file}")

    with open(eval_file, encoding="utf-8") as f:
        essays = json.load(f)

    if provider.lower() in ("real", "gemini"):
        client = RealLLMClient()
    else:
        client = MockLLMClient()

    raw_results = []
    parsed_results: list[tuple[GradingResult, str]] = []

    print(f"\nEvaluating {len(essays)} synthetic essays using provider={provider!r}...")

    # Retrieve rubric chunks for all criteria once
    rubric_chunks = []
    for crit in Criterion:
        rubric_chunks.extend(search_rubric(crit, "IELTS Task 2 academic evaluation", top_k=2))

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
            print(f"Error evaluating essay #{item['id']}: {exc}")

    # Compute Day 3 metrics
    schema_rate = compute_schema_valid_rate(raw_results)

    evidence_rates = [compute_evidence_valid_rate(res, text) for res, text in parsed_results]
    avg_evidence_rate = sum(evidence_rates) / len(evidence_rates) if evidence_rates else 0.0

    # Day 4-5 stubs
    variance_stub = compute_run_to_run_variance([6.5, 6.5, 6.5])
    guardrail_stub = compute_guardrail_pass_rate([True, True, True, True])

    metrics_summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "provider": provider,
        "sample_count": len(essays),
        "schema_valid_rate": round(schema_rate, 4),
        "evidence_valid_rate": round(avg_evidence_rate, 4),
        "run_to_run_variance": round(variance_stub, 4),
        "guardrail_pass_rate": round(guardrail_stub, 4),
    }

    # Print table
    print("\n" + "=" * 54)
    print("      IELTS Writing AI - Day 3 Evaluation Report       ")
    print("=" * 54)
    print(f"{'Metric':<32} | {'Value':<16}")
    print("-" * 54)
    print(f"{'1. Schema-valid Rate':<32} | {schema_rate * 100:.1f}%")
    print(f"{'2. Evidence-valid Rate':<32} | {avg_evidence_rate * 100:.1f}%")
    print(f"{'3. Run-to-run Variance (stub)':<32} | {variance_stub:.4f}")
    print(f"{'4. Guardrail Pass Rate (stub)':<32} | {guardrail_stub * 100:.1f}%")
    print("=" * 54)

    # Save to evals/results/eval_results.json
    output_path = results_dir / "eval_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2)

    print(f"Evaluation report written to: {output_path}\n")
    return metrics_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run IELTS AI evaluation suite")
    parser.add_argument(
        "--provider",
        choices=["mock", "real"],
        default="mock",
        help="LLM provider: 'mock' (default offline) or 'real' (live API)",
    )
    args = parser.parse_args()
    run_evals(args.provider)


if __name__ == "__main__":
    main()
