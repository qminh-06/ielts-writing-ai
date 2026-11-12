---
title: /pre-demo — Kiểm tra trước demo
description: Walk through demo checklist
---
# /pre-demo Workflow

1. Chạy `make check` — phải xanh
2. Chạy `make init-db` — tạo DB sạch
3. Start app: `make run` (headless check)
4. Walk through `docs/demo-checklist.md` từng bước:
   - Bước 1: Input essay
   - Bước 2: AI grading result
   - Bước 3: Examiner edit
   - Bước 4: Re-grade
   - Bước 5: Final approve
   - Bước 6: Email (file mode)
   - Bước 7: Guardrail checks
   - Bước 8: Observability logs
   - Bước 9: Evals table
   - Bước 10: Submission package
5. Report pass/fail cho từng bước
