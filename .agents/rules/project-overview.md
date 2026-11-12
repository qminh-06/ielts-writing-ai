---
Activation: always
---
# Project Overview

## Sản phẩm
IELTS Writing Task 2 AI grading assistant. Mock-first MVP (7 ngày).

## Hard Rules
- AI không finalize điểm, không tự gửi email
- Overall band = `floor(mean*2+0.5)/2` trong code Python
- Evidence phải có trong essay (substring check)
- Status transitions được enforce trong `db/repo.py`

## Stack
Python 3.11 · Streamlit · SQLite · LangGraph · ChromaDB+mock · pydantic v2 · smtplib · pytest+ruff

## Role Map
A=agent/ · B=rag/+guardrails/ · C=db/+services/+observability/ · D=app/ · E=tests/+evals/+docs/

## Mock First, Real Later
- `LLM_PROVIDER=mock` → MockLLMClient returns grading_result.mock.json
- `USE_MOCK_RAG=true` → in-memory keyword matcher (no ChromaDB download)
- `EMAIL_MODE=file` → writes to outbox/
- Mọi feature mới phải chạy trong mock mode trước khi implement real
