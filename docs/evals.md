# Evaluation metrics

Run the default offline evaluation with `python evals/run_evals.py`. It uses the mock provider,
evaluates the synthetic essay set, executes each data-driven guardrail case against the real
validators/services with offline providers, prints four metrics, and writes
`evals/results/latest.json`. With the mock provider, evidence-valid rate and run-to-run variance
print `n/a (mock provider)`: the canned mock response is not conditioned on the essay, so these
values would misleadingly look like quality measurements.

For a bounded live evidence diagnostic, configure `LLM_PROVIDER=real`, `LLM_API_KEY`, and
`LLM_MODEL`, then run:

```powershell
python evals/run_evals.py --provider real --limit 3 --sleep-between-calls 1
```

`--limit N` restricts the run to the first N synthetic essays; `--sleep-between-calls SECONDS`
pauses between live calls. Each invalid quote is printed with its essay ID, criterion, quote, and
closest essay substring. The full diagnostic is written to
`evals/results/day6_evidence_debug.json`. If no API key is configured, the run is skipped and the
debug report records the reason without printing credentials.

Use `python evals/run_evals.py --provider real --variance --runs 3` only when intentionally making
repeated live calls. This evaluates each essay three times and reports per-criterion range and
sample standard deviation. Variance is `skipped` for real runs unless the explicit three-run mode
is selected. Use `python evals/regrade_probe.py` for the separate real-provider probe of whether
deliberately unsupported examiner feedback raises a score.

The opt-in SMTP smoke test is separate: configure SMTP settings and `SMTP_TEST_TO`, then run
`python -m pytest -m integration`. The default `python -m pytest` suite is offline.

## Metrics

- **Schema-valid rate:** valid `GradingResult` outputs divided by attempted synthetic essays;
  failed evaluations count as invalid.
- **Evidence-valid rate:** for real-provider runs, mean per-essay fraction of evidence strings
  present in the essay after Unicode, punctuation, and whitespace normalization. Mock evidence is
  canned and therefore reported as `n/a`, not as a quality score.
- **Run-to-run variance:** proportion of essays whose four criteria each stay within a 0.5-band
  range, with per-criterion range and sample standard deviation. It runs only in the explicit
  three-run real-provider mode.
- **Guardrail pass rate:** proportion of cases in `data/eval_set/guardrail_cases.json` whose
  expected behavior is observed offline. Cases cover input checks, injection, evidence, grading
  failure, approval, re-grade, and duplicate-send boundaries.
- **MAE:** mean absolute error of overall band against reference bands. It is skipped unless every
  eval essay has a non-null reference band and was evaluated successfully.

## Limitations

The included essays are synthetic. They have no reference bands, so MAE is skipped. Mock scores and
evidence are not meaningful quality measurements; mock evidence and variance are `n/a`. Real
provider runs can be slow, vary between runs, and consume API quota. The rubric corpus and source
still need human verification. Treat these numbers as diagnostic evidence, not proof of grading
validity.
