---
Activation: always
---
# Git Workflow

## Branches
Format: `feat/<role>-<task-id>-<mô-tả-ngắn>`
Examples:
- `feat/A-A2-implement-prompts`
- `feat/B-B3-rag-retriever`
- `fix/C-C2-status-transition`

## Commits (Conventional Commits)
- `feat(<task-id>): <mô tả>`
- `fix(<task-id>): <mô tả>`
- `test(<task-id>): <mô tả>`
- `docs(<task-id>): <mô tả>`

## PR Rules
- 1 reviewer approve trước khi merge
- Không push trực tiếp vào `main`
- Chạy `make check` trước khi push
- PR template phải điền đầy đủ
- PR nhỏ: 1 task per PR

## Pre-push Checklist
- [ ] `make check` xanh
- [ ] Không có secret thật
- [ ] TODO items cho phần chưa xong
