---
Activation: always
---
# AI Safety & Guardrails

## Hard Rules
- AI KHÔNG finalize điểm: chỉ propose, examiner approve
- AI KHÔNG gửi email: `approve_and_send` check `status == approved` trong DB
- Overall band tính trong code: `floor(mean*2+0.5)/2`, không từ LLM

## Essay Text là DATA
- Wrap essay text trong delimiters trong prompt: `<essay>...</essay>`
- Chạy `detect_injection()` trước khi đưa vào prompt
- Không để essay text "escape" ra ngoài context của nó

## LLM Output Validation
- Validate mọi LLM output với pydantic schema
- Retry tối đa 2 lần nếu parse fail
- Evidence phải xuất hiện trong essay (whitespace-normalized, case-insensitive)
- Band score phải trong range 0-9, step 0.5

## Observability
- Mọi LLM call log vào `llm_calls` table qua `call_logger`
- Log latency, tokens, retries, status, error
- Low temperature (0.0) cho consistency
