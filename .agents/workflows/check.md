---
title: /check — Kiểm tra code quality
description: Chạy make check và fix lỗi
---
# /check Workflow

1. Chạy `make lint` — xem ruff errors
2. Fix tất cả lint errors mà không thay đổi logic
3. Chạy `make test` — xem test failures
4. Fix test failures
5. Chạy lại `make check` để confirm xanh
6. Báo cáo: số lỗi đã fix, tests pass/fail
