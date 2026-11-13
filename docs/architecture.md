# Kiến trúc hệ thống / System Architecture

## Sơ đồ luồng / Flow Diagram

```mermaid
flowchart TD
    E["Giám khảo nộp bài\n(essay + email)"] --> P1

    subgraph APP["Streamlit App"]
        P1["Trang 1: Nhập bài"] --> GS
        GS --> P2["Trang 2: Kết quả AI"]
        P2 --> P3["Trang 3: Duyệt"]
        P3 -->|accept| AS
        P3 -->|regrade| RS
        RS --> P2
        AS --> P4["Trang 4: Kết quả cuối"]
        P4 --> ES
    end

    subgraph AGENT["Agent Layer (LangGraph)"]
        VI["validate_input"] --> RR["retrieve_rubric"]
        RR --> GR["grade"]
        GR --> VO["validate_output"]
    end

    subgraph RAG["RAG Layer"]
        CHROMA["ChromaDB\n(persistent)"]
        MOCK["In-memory keyword\n(CI/test fallback)"]
    end

    subgraph DB["Data Layer"]
        SQLITE["SQLite\n(essays, ai_results, reviews,\nregrade_requests, emails, llm_calls)"]
        LOGGER["call_logger\n(latency, tokens, retries)"]
    end

    GS -->|run_grading| AGENT
    AGENT --> RAG
    AGENT --> LOGGER
    AS -->|save_review| SQLITE
    ES -->|send_email| EMAIL["Email\n(file mode / SMTP)"]
    SQLITE -.->|status column| AGENT
```

## Thành phần / Components

| Thành phần | Mô tả | Role |
|-----------|-------|------|
| `agent/graph.py` | LangGraph workflow 4 nodes | A |
| `agent/evaluate.py` | One function: first grade + regrade | A |
| `agent/prompts.py` | Prompt templates (TODO A2) | A |
| `rag/retriever.py` | ChromaDB + mock fallback | B |
| `rag/indexer.py` | Build ChromaDB index from JSONL | B |
| `guardrails/input_checks.py` | Email, word count, length | B |
| `guardrails/output_checks.py` | Band range, evidence in essay | B |
| `db/repo.py` | Typed DB functions, status transitions | C |
| `services/grading_service.py` | Orchestrate essay grading | C |
| `services/review_service.py` | Save review, trigger regrade | C |
| `services/email_service.py` | Send result email | C |
| `observability/call_logger.py` | Log every LLM/retrieval call | C |
| `app/pages/` | 5 Streamlit pages | D |

## Examiner review and re-grade

AI grading rows are immutable and use monotonically increasing versions. A re-grade retrieves
rubric chunks for one criterion, records both retrieval and model calls, and replaces only that
criterion in a copy of the latest AI result. `regrade_requests` links the examiner feedback to
the source and destination versions. Examiner drafts are stored separately in `reviews` and are
not overwritten by AI output; approval locks further edits and re-grades. The `reviews` migration
allows draft rows to have no `approved_at` timestamp while preserving older approved rows.
