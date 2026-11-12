# Quyết định thiết kế / Design Decisions

## D1: RAG thay vì MCP
**Quyết định:** Dùng ChromaDB RAG để retrieve rubric chunks.
**Lý do:** Yêu cầu môn học, RAG phù hợp với bài toán retrieval rubric theo criterion+band.

## D2: Status trong DB thay vì LangGraph checkpoint
**Quyết định:** Dùng cột `status` trong bảng `essays` để track trạng thái.
**Lý do:** Không cần checkpointer phức tạp; examiner review là async (có thể mất nhiều giờ); DB dễ query và debug hơn.

## D3: Một hàm `evaluate_essay` cho cả grading và re-grading
**Quyết định:** `evaluate_essay(prompt_text, essay_text, rubric_chunks, *, regrade_criterion, examiner_feedback)`.
**Lý do:** Logic giống nhau; regrade chỉ thêm context về criterion và feedback của examiner.

## D4: Overall band tính trong code, không dùng LLM
**Quyết định:** `floor(mean * 2 + 0.5) / 2` trong Python.
**Lý do:** Hard rule của hệ thống; LLM không được phép quyết định điểm cuối cùng.

## D5: Evidence phải tồn tại trong bài viết
**Quyết định:** Whitespace-normalized, case-insensitive substring check.
**Lý do:** Tránh LLM "bịa" evidence; đảm bảo tính minh bạch với thí sinh.

## D6: Streamlit không có FastAPI
**Quyết định:** Streamlit gọi trực tiếp service functions.
**Lý do:** MVP 7 ngày; đủ cho demo; tránh thêm complexity và dependency.
