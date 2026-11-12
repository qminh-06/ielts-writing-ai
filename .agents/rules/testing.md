---
Activation: glob tests/**
---
# Testing Rules

## Setup
- pytest với `pythonpath = ["src"]`
- Không có network calls trong tests
- Không có real LLM trong tests (dùng MockLLMClient)
- Dùng temp SQLite (`:memory:` hoặc `tmp_path`)

## Required Test Cases
- `test_overall_band`: 6.25→6.5, 6.75→7.0, 6.0→6.0
- `test_input_checks`: email validation, word count, length
- `test_output_checks`: evidence present vs absent
- `test_db_status_transitions`: valid và invalid transitions
- `test_email_gate`: approve_and_send refuses khi chưa approved
- `test_end_to_end_mock`: create→grade→review→approve→email

## Fixtures
- `tmp_db`: SQLite in-memory hoặc tmp file
- `mock_llm`: MockLLMClient
- `mock_rag`: in-memory keyword retriever

## Coverage
- Mọi guardrail phải có test
- Mọi status transition (valid + invalid) phải có test
