# Kiến trúc hệ thống / System Architecture

## Sơ đồ luồng / Flow Diagram

```mermaid
flowchart TD
    E["Giám khảo nộp bài\n(essay + email)"] --> P1

    subgraph APP["Streamlit App"]
        P1["Trang 1: Nhập bài"] --> GS
        GS --> P2["Trang 2: Kết quả AI"]
        P2 --> P3["Trang 3: Duyệt"]
        P3 -->|"Lưu nháp / Duyệt"| RV["reviews"]
        P3 -->|"Chấm lại"| RG["Re-grade criterion"]
        RG -->|version mới| P2
        P3 -->|approved| P4["Trang 4: Kết quả cuối"]
        P4 -->|examiner confirms + clicks send| CLAIM
        P5["Trang 5: Logs"] --> MS["metrics_service"]
    end

    subgraph AGENT["Agent Layer (LangGraph)"]
        VI["validate_input"] --> RR["retrieve_rubric"]
        RR --> GR["grade"]
        GR --> VO["validate_output"]
        VO -->|success| AIDONE["ai_done"]
        VI -->|input error; status unchanged| PENDING["pending"]
        RR -->|retrieval error| FAILED["grading_failed"]
        GR -->|provider error| FAILED
        FAILED -->|retry| PENDING
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
    RV --> SQLITE
    RG -->|append immutable AI version + request| SQLITE
    AIDONE -->|review| REVIEWING["reviewing"]
    REVIEWING -->|examiner approves| APPROVED["approved"]
    APPROVED --> CLAIM["Atomic email claim\nstatus=sending"]
    CLAIM -->|send_email| EMAIL["Email\n(file mode / SMTP)"]
    EMAIL -->|success; attempt sent| EMAILED["emailed"]
    EMAIL -->|failure; attempt failed| APPROVED
    SQLITE -.-> P5
    MS --> SQLITE
```

## Thành phần / Components

| Thành phần | Mô tả | Role |
|-----------|-------|------|
| `agent/graph.py` | LangGraph workflow 4 nodes | A |
| `agent/evaluate.py` | One function: first grade + regrade | A |
| `agent/prompts.py` | Prompt templates for the grading provider | A |
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

The email sender is never called by the AI workflow. The examiner must approve the result and
explicitly request delivery. A `sending` row is claimed under a SQLite write transaction before
delivery; a successful attempt updates the email and essay to `sent`/`emailed` atomically. Failed
attempts are recorded as `failed`, leave the essay `approved`, and allow a deliberate retry.
