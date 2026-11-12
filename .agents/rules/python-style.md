---
Activation: glob **/*.py
---
# Python Style Guide

## Type Hints
- Type hints ở mọi nơi: params, return types, variables
- Dùng `list[T]`, `dict[K,V]`, `Optional[T]` (Python 3.11+)

## Functions
- Hàm nhỏ, thuần túy (pure functions) khi có thể
- Docstrings bằng tiếng Anh cho code, tiếng Việt cho UI strings và docs

## Pydantic
- Dùng pydantic v2 ở mọi boundary (LLM output, DB input/output, API)
- Validate mọi LLM output với pydantic trước khi dùng

## Logging
- Dùng `logging` thay vì `print`
- Mọi LLM/retrieval call phải đi qua `call_logger`

## Code Quality
- Ruff clean (line-length=100, rules E,F,I,UP,B)
- `# TODO(<task-id>): <mô tả>` cho phần chưa xong
- Không commit code bị comment out hoặc debug prints
