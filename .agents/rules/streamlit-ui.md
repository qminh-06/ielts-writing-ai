---
Activation: glob app/**
---
# Streamlit UI Rules

## Vietnamese Labels
- Mọi label, button, header, error message → tiếng Việt
- Code và comments → tiếng Anh

## Import Rules
- UI pages chỉ import từ `src/ielts_ai/services/`
- KHÔNG import trực tiếp từ `db/`, `agent/`, `rag/`

## State Management
- Dùng `st.session_state` cho app state
- Không dùng global variables

## UX Patterns
- Show loading spinner khi gọi service (`st.spinner`)
- Show error message rõ ràng khi có lỗi (`st.error`)
- Disable buttons khi action không hợp lệ theo status
- Show current essay status ở đầu trang
