# Báo cáo chạy thử Day 6

## Môi trường và kết quả tổng quát

- Chạy Streamlit ở chế độ `LLM_PROVIDER=mock`, `USE_MOCK_RAG=true`,
  `EMAIL_MODE=file`, với SQLite và `outbox/` tạm trong thư mục hệ điều hành.
- Không đọc hoặc ghi DB/outbox đang dùng trong repo; thư mục thử nghiệm đã được tách riêng.
- Luồng giao diện bước 1-8 hoàn tất. Bài thử chuyển qua `ai_done`, `reviewing`, `approved`,
  rồi `emailed`; email chỉ được ghi thành file, không gửi thật.
- UI timings không được đo riêng theo thao tác. Từ Logs của bài mock: 9 calls, latency trung bình
  3.3 ms, p95 15.0 ms, error rate 0%, retry rate 0%. Đây là số liệu của mock/local, không dự báo
  latency của Gemini.
- Chạy thật `python evals/run_evals.py --provider real --limit 3 --sleep-between-calls 1`:
  Gemini trả HTTP 504 cho essay #2 và #3; 1/3 lần đánh giá thành công. Evidence-valid là 100%
  trên một kết quả parse được, không đại diện cho cả ba essay. Không có quote sai trong kết quả
  thành công; chi tiết ở `evals/results/day6_evidence_debug.json`. Schema-valid rate là 33.3%,
  guardrail pass rate 100%, variance và MAE bị bỏ qua.
- `python scripts/time_grading.py` ghi nhận một lần grade thật thất bại với HTTP 504 sau 2 retries:
  model call 180015 ms, tổng thời gian 180.292 giây. Bốn retrieval mock mất 0-16 ms mỗi call.
  Đây là lỗi/độ trễ từ provider, không phải kết quả chất lượng chấm điểm.

## Theo từng bước

### Bước 1 — Nhập bài: PASS

Gửi bài synthetic qua **Gửi bài chấm điểm**; UI báo mã bài `#1`, trạng thái chuyển sang
`ai_done`. Bài có 268 từ. Phần thời gian grade nằm trong số liệu Logs nêu trên; không đo riêng
thời gian thao tác trình duyệt.

### Bước 2 — Kết quả AI: PASS

Trang kết quả hiển thị bốn tiêu chí, Overall Band 6.5, rubric chunks và cảnh báo. Mock trả evidence
không khớp bài, nên UI hiển thị tám cảnh báo evidence thay vì che giấu chúng; đây là giới hạn đã
biết của canned mock response.

### Bước 3 — Lưu nháp: PASS

Nhập nhận xét giám khảo và dùng **Lưu nháp**. Nhận xét được nạp lại từ draft, trạng thái vẫn là
`reviewing`, chưa được phê duyệt.

### Bước 4 — Re-grade: PASS

Dùng **Chấm lại** cho tiêu chí TR với phản hồi hợp lệ. UI hiển thị version `v2`, lịch sử và diff;
điểm mock của TR giữ nguyên 6.5.

### Bước 5 — Phê duyệt: PASS

Chọn **Tôi xác nhận phê duyệt kết quả cuối cùng** rồi nhấn **Duyệt**. DB/UI chuyển sang
`approved`; form điểm và nhận xét bị khóa.

### Bước 6 — Preview và gửi email: PASS

Trang cuối hiển thị recipient, điểm đã duyệt, nhận xét và preview; banner xác nhận `file` mode.
Sau xác nhận và nhấn **Gửi email kết quả**, bài chuyển sang `emailed`, lịch sử có một lần `sent`,
và file UTF-8 được tạo trong outbox tạm. UI không gửi email thật.

### Bước 7 — Guardrails và lỗi: PASS

`python -m pytest -q` bao gồm 15 data-driven guardrail cases và các ca provider timeout/HTTP 429,
invalid JSON, SMTP authentication/timeout/refused connection, lỗi evidence, double grade/re-grade/
send, feedback Unicode và essay quá dài. Gửi trước approve hoặc gửi lặp bị từ chối; lỗi SMTP giữ
trạng thái `approved` và cho retry. Missing Chroma index đưa bài sang `grading_failed`, ghi lỗi
retrieval và hướng dẫn chạy `python scripts/build_rubric_index.py`.

### Bước 8 — Logs: PASS

Tab **LLM và truy xuất** hiển thị 9 calls, latency, error/retry rate, bộ lọc và charts. Tab
**Email** hiển thị 1 sent, 0 failed. Kiểm tra trực tiếp metrics service trả recipient dạng mask
`c***@example.com`; địa chỉ đầy đủ không xuất hiện trong Logs.

### Bước 9 — Offline evals: PASS

`python evals/run_evals.py` cho schema-valid 100%, evidence và variance
`n/a (mock provider)`, guardrail pass 100%, MAE `skipped: no reference bands`.

### Bước 10 — Check và tài liệu: PASS

`.\scripts\check.ps1` chạy Ruff check, Ruff format check và pytest: lint/format đều pass,
`65 passed, 2 deselected`. Clean clone của `fix/day6-stabilization` dùng Python 3.11.9 (máy không
có launcher `py`, nên dùng `python -m venv`), cài requirements và editable package thành công,
`pip check` không có dependency conflict, `scripts/init_db.py` và mock eval pass, Streamlit headless
trả HTTP 200. Chroma index không cần build vì mock-RAG default hoạt động; clone tạm đã được xóa.

## Sự cố quan sát được

- Lần chạy real bị HTTP 504 và mất khoảng ba phút cho một grading call; cần chạy lại eval/timing
  khi Gemini ổn định trước khi diễn giải điểm số.
- Mock evidence là canned data và không thể đánh giá chất lượng evidence; warning vẫn được giữ lại
  trong UI.
- Lần khởi chạy UI thử đầu tiên dùng DB tạm chưa khởi tạo. Sau khi chạy
  `python scripts/init_db.py` với `DB_PATH` trỏ tới file tạm, toàn bộ luồng giao diện hoàn tất.
