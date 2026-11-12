# Task Map

| Task ID | Chủ sở hữu | Files chính | Mô tả |
|---------|-----------|-------------|-------|
| A1 | A | `docs/architecture.md`, `data/samples/` | Architecture diagram + mock JSON |
| A2 | A | `src/ielts_ai/agent/prompts.py` | IELTS grading prompt templates |
| A3 | A | `src/ielts_ai/agent/evaluate.py`, `src/ielts_ai/llm/client.py` | Real LLM client + evaluate_essay impl |
| A4 | A | `src/ielts_ai/agent/evaluate.py`, `src/ielts_ai/services/review_service.py` | Re-grading with examiner feedback |
| A5 | A | `src/ielts_ai/agent/graph.py` | LangGraph 4-node workflow |
| B1 | B | `data/rubric/` | Official rubric JSONL data |
| B2 | B | `src/ielts_ai/rag/` | ChromaDB indexer + retriever |
| B3 | B | `src/ielts_ai/agent/graph.py` (retrieve node) | Integrate RAG into graph |
| B4 | B | `src/ielts_ai/guardrails/output_checks.py`, `schemas.py` | Output validation |
| B5 | B | `src/ielts_ai/guardrails/input_checks.py` | Input validation |
| B6 | B | `src/ielts_ai/guardrails/injection.py` | Prompt injection detection |
| C1 | C | `src/ielts_ai/db/` | DB schema + init script |
| C2 | C | `src/ielts_ai/db/repo.py`, `services/` | DB repo functions |
| C3 | C | `src/ielts_ai/services/grading_service.py` | Grading service |
| C4 | C | `src/ielts_ai/services/review_service.py` | Review + regrade service |
| C5 | C | `src/ielts_ai/services/email_service.py` | Real SMTP email |
| C6 | C | `.env.example`, `src/ielts_ai/config.py`, `CONTRIBUTING.md` | Config & secrets management |
| C7 | C | `src/ielts_ai/observability/` | LLM call logging |
| C8 | C | `README.md`, `docs/` | Documentation |
| D1 | D | `app/pages/1_Nhap_bai.py` | Essay input page |
| D2 | D | `app/pages/2_Ket_qua_AI.py` | AI results page |
| D3 | D | `app/pages/3_Giam_khao_duyet.py` | Examiner review page |
| D4 | D | `app/pages/4_Ket_qua_cuoi.py` | Final result page |
| D5 | D | `app/pages/5_Logs.py` | LLM call logs page |
| D6 | D | `docs/demo-checklist.md` | Demo checklist |
| E1 | E | `data/samples/`, `data/eval_set/` | Sample data + eval set |
| E2 | E | `tests/` | Unit tests |
| E3 | E | `evals/` | Eval runner |
| E4 | E | `tests/` | Integration tests |
| E5 | E | `tests/` | Guardrail tests |
| E6 | E | `evals/` | Eval metrics |
| E7 | E | `docs/` | Final documentation |
