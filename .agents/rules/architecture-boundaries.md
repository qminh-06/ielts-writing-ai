---
Activation: always
---
# Architecture Boundaries

## Import Rules (QUAN TRỌNG)
```
app/ → services/ → (agent/, rag/, guardrails/, db/, observability/)
```
- `app/` chỉ được import từ `services/`
- `services/` không được import từ `app/`
- Không import ngược chiều
- `schemas.py` là contract dùng chung — thay đổi cần PR reviewed bởi tất cả roles

## Thêm dependency mới
- Phải được team approval trước
- Thêm vào `requirements.txt` với version range
- Cập nhật `docs/decisions.md`

## LLM calls
- Mọi LLM call phải qua `LLMClient` interface (không gọi SDK trực tiếp)
- Mọi call phải wrap trong `call_logger`
