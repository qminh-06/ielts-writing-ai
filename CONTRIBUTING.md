# Hướng dẫn đóng góp / Contributing Guide

## Quy trình nhánh / Branch Workflow

- Tên nhánh: `feat/<role>-<task-id>-<mô-tả-ngắn>`
- Ví dụ: `feat/A-A2-implement-prompts`, `feat/B-B3-rag-retriever`

## Quy tắc commit / Commit Convention

Dùng [Conventional Commits](https://www.conventionalcommits.org/):
- `feat(A2): implement grading prompt template`
- `fix(C1): fix status transition validation`
- `test(E2): add input guardrail tests`
- `docs(C8): update architecture diagram`

## Quy trình PR / PR Process

1. Tạo nhánh từ `main`
2. Chạy `make check` trước khi push
3. Mở PR với PR template đầy đủ
4. Cần 1 reviewer approve trước khi merge
5. Không push trực tiếp vào `main`

## Chế độ Mock / Mock Mode

Tất cả logic phát triển mới **phải chạy được** với:
- `LLM_PROVIDER=mock`
- `USE_MOCK_RAG=true`
- `EMAIL_MODE=file`

Không có network call, không có model download trong CI.

## Định nghĩa "Done" / Definition of Done

- [ ] `make check` xanh (lint + test)
- [ ] Chạy được trong mock mode
- [ ] Có TODO(<task-id>) cho phần chưa xong
- [ ] Không commit secret thật
- [ ] Docs cập nhật nếu cần
