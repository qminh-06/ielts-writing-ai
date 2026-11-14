# Evaluation metrics

Run the default offline evaluation with `python evals/run_evals.py`. It uses the mock provider,
evaluates the synthetic essay set, executes each data-driven guardrail case against the real
validators/services with offline providers, prints four metrics, and writes
`evals/results/latest.json`.

Use `python evals/run_evals.py --provider real --variance --runs 3` only after configuring
`LLM_PROVIDER=real`, `LLM_API_KEY`, and `LLM_MODEL`. This makes live provider calls and evaluates
each essay three times, reporting per-criterion range and sample standard deviation. Variance is
`skipped` in all other modes. Use `python evals/regrade_probe.py` for the separate real-provider
probe of whether deliberately unsupported examiner feedback raises a score.

The opt-in SMTP smoke test is separate: configure SMTP settings and `SMTP_TEST_TO`, then run
`python -m pytest -m integration`. The default `python -m pytest` suite is offline.

## Metrics

- **Schema-valid rate:** valid `GradingResult` outputs divided by attempted synthetic essays;
  failed evaluations count as invalid.
- **Evidence-valid rate:** mean per-essay fraction of evidence strings present in the essay after
  normalization.
- **Run-to-run variance:** proportion of essays whose four criteria each stay within a 0.5-band
  range, with per-criterion range and sample standard deviation. It runs only in the explicit
  three-run real-provider mode.
- **Guardrail pass rate:** proportion of cases in `data/eval_set/guardrail_cases.json` whose
  expected behavior is observed offline. Cases cover input checks, injection, evidence, grading
  failure, approval, re-grade, and duplicate-send boundaries.
- **MAE:** mean absolute error of overall band against reference bands. It is skipped unless every
  eval essay has a non-null reference band and was evaluated successfully.

## Limitations

The included essays are synthetic. They have no official reference bands, so MAE is skipped. Mock
scores and evidence are not meaningful quality measurements; the mock provider cannot measure real
model consistency. Real-provider runs can vary and consume API quota. The rubric corpus still needs
verified official text. Treat these numbers as diagnostic/calibration evidence, not proof of
grading validity.
