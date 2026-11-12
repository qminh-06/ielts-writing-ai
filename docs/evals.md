# Định nghĩa Metrics / Eval Metrics

## M1: Schema-valid Rate
Tỷ lệ GradingResult output validate thành công qua pydantic schema.
`schema_valid_rate = count(valid) / count(total)`

## M2: Evidence-valid Rate
Tỷ lệ evidence strings thực sự xuất hiện trong essay (whitespace-normalized, case-insensitive).
`evidence_valid_rate = count(evidence_found_in_essay) / count(total_evidence)`

## M3: Run-to-run Variance
Chạy cùng essay 3 lần, đo độ lệch chuẩn của band scores.
`variance = std([band_run1, band_run2, band_run3])` cho mỗi criterion.
Target: variance < 0.5 (mock client luôn = 0).

## M4: Guardrail Test Pass Rate
Tỷ lệ test cases guardrail pass.
`guardrail_pass_rate = count(passed) / count(total_guardrail_tests)`
