# IELTS Writing AI Assistant

Hệ thống hỗ trợ chấm điểm bài viết IELTS Task 2 sử dụng AI.

## Kiến trúc / Architecture

```mermaid
flowchart TD
    subgraph UI["Giao diện (Streamlit)"]
        P1["1. Nhập bài"] --> P2["2. Kết quả AI"]
        P2 --> P3["3. Giám khảo duyệt"]
        P3 --> P4["4. Kết quả cuối"]
        P5["5. Nhật ký"]
    end

    subgraph SVC["Services"]
        GS[grading_service]
        RS[review_service]
        ES[email_service]
    end

    subgraph AGENT["Agent (LangGraph)"]
        N1[validate_input] --> N2[retrieve_rubric]
        N2 --> N3[grade]
        N3 --> N4[validate_output]
    end

    UI --> SVC
    SVC --> AGENT
    AGENT --> RAG["ChromaDB / Mock RAG"]
    SVC --> DB["SQLite"]
    AGENT --> LOG["call_logger"]
```

## Cài đặt / Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

cp .env.example .env
make install
make init-db
```

## Chạy ứng dụng / Run

```bash
make run
```

## Kiểm thử / Test

```bash
make check
```

## Phân công vai trò / Role Map

| Role | Phụ trách |
|------|-----------|
| A | Agent, workflow, prompt engineering |
| B | Rubric/RAG, guardrails |
| C | DB, services, email, observability |
| D | Streamlit UI |
| E | Tests, evals, docs, slides |

## Giới hạn hiện tại / Current Limitations

- LLM thực chưa được tích hợp (dùng mock client)
- ChromaDB chưa được index (dùng in-memory keyword fallback)
- SMTP thực chưa được cấu hình (dùng file mode)
- Prompt thực chưa được viết (TODO A2)
