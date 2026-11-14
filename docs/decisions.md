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

## D7: Google GenAI (Gemini SDK) làm Real LLM Provider
**Quyết định:** Sử dụng thư viện `google-genai` làm SDK duy nhất cho `RealLLMClient`.
**Lý do:** Hỗ trợ native JSON mode (`response_mime_type="application/json"`), tốc độ inference nhanh, phù hợp quy mô dự án và đáp ứng tiêu chí định dạng JSON có cấu trúc.
## D8: Claim email before delivery
**Quyết định:** Tạo email attempt trạng thái `sending` trong transaction trước khi gọi sender.
**Lý do:** Chặn double-click và chỉ cho phép retry sau khi attempt trước chuyển `failed`.

## D9: File mode is the default
**Quyết định:** `EMAIL_MODE=file` là mặc định; SMTP chỉ bật qua `.env`.
**Lý do:** Demo và test offline không gửi thư thật.

## D10: Credentials policy
**Quyết định:** API key và SMTP credentials chỉ đọc từ environment hoặc `.env`, không ghi vào code, logs, database hay test output.
**Lý do:** Bảo vệ thông tin xác thực và tránh secret leak qua repository.

## D11: Feature freeze after Day 5
**Quyết định:** Sau Day 5 chỉ nhận bug fix, test và documentation.
**Lý do:** Ổn định luồng demo và tránh tăng phạm vi MVP.
