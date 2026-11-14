# IELTS Writing AI Assistant

Ứng dụng Streamlit hỗ trợ giám khảo chấm IELTS Writing Task 2. AI tạo đề xuất theo bốn tiêu chí; chỉ giám khảo mới được lưu điểm cuối cùng, phê duyệt và bấm gửi email.

## Kiến trúc

`Streamlit → services → LangGraph/RAG/guardrails/SQLite`. Luồng trạng thái là `pending → ai_done → reviewing → approved → emailed`; re-grade tạo AI version mới, không sửa version cũ. Mọi call LLM và retrieval được lưu trong `llm_calls`.

## Cài đặt

Yêu cầu Python 3.11.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
Copy-Item .env.example .env
python scripts/init_db.py
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
cp .env.example .env
python scripts/init_db.py
```

## Chạy ứng dụng và kiểm thử

```powershell
python scripts/init_db.py
python -m streamlit run app/streamlit_app.py
python -m pytest -q
python -m pytest -m integration
python -m ruff check .
python -m ruff format --check .
```

`python -m pytest -q` không gọi mạng. Lệnh `-m integration` là opt-in và có thể gửi email
thật khi SMTP settings cùng `SMTP_TEST_TO` được cấu hình.

## Luồng sử dụng

1. Trang **Nhập bài**: điền email, đề bài, bài viết; nhấn **"Gửi bài chấm điểm"**.
2. Trang **Kết quả AI**: chọn bài theo ID/status; nếu đang `pending`, nhấn
   **"🚀 Bắt đầu chấm điểm với AI"** để xem điểm đề xuất, evidence, warnings và rubric.
3. Trang **Giám khảo duyệt**: sửa bốn band/nhận xét; dùng **"Lưu nháp"** hoặc gửi yêu cầu
   **"Chấm lại"** cho một tiêu chí. AI tạo version mới, không phê duyệt kết quả.
4. Tại trang **Giám khảo duyệt**, chọn xác nhận và nhấn **"Duyệt"**. Chỉ sau bước này status mới là
   `approved`.
5. Trang **Kết quả cuối** hiển thị điểm cuối, nhận xét và email preview. Chọn xác nhận gửi rồi nhấn
   **"Gửi email kết quả"**; nếu một lần gửi thất bại, dùng **"Thử gửi lại"**. File mode chỉ lưu
   `.txt` vào `outbox/`; SMTP mới gửi thư thật.
6. Trang **Nhật ký hệ thống** có tab LLM/retrieval để lọc và xem latency/token/calls, cùng tab
   Email với recipient đã mask.

Chạy eval mock offline:

```powershell
python evals/run_evals.py
```

Chạy variance bằng real provider (cần `LLM_API_KEY`):

```powershell
python evals/run_evals.py --provider real --variance --runs 3
python evals/regrade_probe.py
```

## RAG, LLM và email

- Rebuild Chroma index: `python scripts/build_rubric_index.py` và đặt `USE_MOCK_RAG=false`.
- Real Gemini: đặt `LLM_PROVIDER=real`, `LLM_API_KEY`, và tùy chọn `LLM_MODEL` trong `.env`.
- Mặc định `EMAIL_MODE=file`: email UTF-8 được lưu ở `outbox/`, không gửi thật.
- SMTP: đặt `EMAIL_MODE=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`; port 465 dùng SSL, các port khác dùng STARTTLS.
- Gửi test: `python scripts/send_test_email.py your-address@example.com`.
- Rebuild index sau khi đã cung cấp rubric JSONL phù hợp: `python scripts/build_rubric_index.py`;
  đặt `USE_MOCK_RAG=false` để dùng ChromaDB. Không có official rubric text được thêm vào repo.

Không đưa API key, SMTP password, hoặc `.env` vào Git. Gmail yêu cầu bật 2FA và dùng App Password; Mailtrap phù hợp cho môi trường thử nghiệm.

## Giới hạn hiện tại

- Synthetic eval essays không có reference band, nên MAE được báo là skipped.
- Mock provider có kết quả xác định; variance mock không có ý nghĩa.
- Cần official rubric text và real essays/reference bands để đánh giá chất lượng thực tế.
- Sau Day 5, dự án feature frozen: chỉ nhận bug fix, test và documentation.
