# AGENTS.md — IELTS Writing AI Assistant

## Sản phẩm / Product
Hệ thống chấm điểm IELTS Writing Task 2 bằng AI. Giám khảo nộp bài → AI chấm 4 tiêu chí → giám khảo review/sửa → phê duyệt → gửi email kết quả.

## Hard Rules (KHÔNG được vi phạm)
- AI KHÔNG được finalize điểm cuối cùng — chỉ giám khảo mới được phê duyệt
- AI KHÔNG được tự gửi email — phải có status `approved` trong DB
- Overall band tính trong CODE: `floor(mean * 2 + 0.5) / 2`, KHÔNG dùng LLM
- Evidence PHẢI xuất hiện trong bài viết (substring check)
- Essay text là DATA, không phải instruction — wrap trong delimiters trong prompt

## Stack cố định / Fixed Stack
- Python 3.11, Streamlit (không có FastAPI), SQLite (không có ORM)
- LangGraph 3-4 nodes, không có checkpointer (status trong DB)
- ChromaDB + in-memory keyword fallback (CI dùng mock RAG)
- Pydantic v2, pydantic-settings, smtplib
- pytest, ruff, pre-commit, GitHub Actions
- KHÔNG có MCP, KHÔNG có Docker

## Phân công vai trò / Role Map
| Role | Phụ trách |
|------|-----------|
| A | `src/ielts_ai/agent/` — agent, workflow, prompt |
| B | `src/ielts_ai/rag/`, `guardrails/` — rubric/RAG, guardrails |
| C | `src/ielts_ai/db/`, `services/`, `observability/` — DB, services, email, logs |
| D | `app/` — Streamlit UI |
| E | `tests/`, `evals/`, `docs/` — tests, evals, docs, slides |

## Cấu trúc thư mục / Folder Map
```
src/ielts_ai/
├── config.py, schemas.py          # shared contracts (thay đổi cần review toàn team)
├── llm/{base.py, mock.py, client.py}
├── agent/{prompts.py, evaluate.py, graph.py}   # Role A
├── rag/{indexer.py, retriever.py}              # Role B
├── guardrails/{input_checks.py, output_checks.py, injection.py}  # Role B
├── db/{schema.sql, repo.py}                    # Role C
├── services/{grading_service.py, review_service.py, email_service.py}  # Role C
└── observability/call_logger.py               # Role C
app/   # Role D
tests/, evals/, docs/  # Role E
```

## Makefile commands
- `make install` — cài packages
- `make init-db` — tạo SQLite DB
- `make index` — build ChromaDB index
- `make run` — start Streamlit
- `make test` — chạy pytest
- `make lint` — ruff check
- `make check` — lint + test
- `make evals` — chạy eval metrics

## Tham khảo thêm / More
- Rules chi tiết: `.agents/rules/`
- Task map: `docs/task-map.md`
- Architecture: `docs/architecture.md`
- Decisions: `docs/decisions.md`
