# Demo Checklist (10 bước / 10 steps)

## Bước 1: Nhập bài — `app/pages/1_Nhap_bai.py`
- [ ] Điền email thí sinh hợp lệ, đề bài và bài viết
- [ ] Nhấn **"Gửi bài chấm điểm"**
- [ ] Ghi nhận mã bài và status sau khi chấm

## Bước 2: Xem kết quả AI — `app/pages/2_Ket_qua_AI.py`
- [ ] Chọn bài qua selector **"Chọn mã bài viết cần xem"** (selector hiển thị status)
- [ ] Nếu status `pending`, nhấn **"🚀 Bắt đầu chấm điểm với AI"**
- [ ] Xem bốn tiêu chí, Overall Band, evidence, warnings và rubric chunks

## Bước 3: Giám khảo chỉnh sửa — `app/pages/3_Giam_khao_duyet.py`
- [ ] Chọn bài qua selector **"Chọn mã bài viết cần duyệt"**
- [ ] Sửa band từng tiêu chí và nhập **"Nhận xét của giám khảo"**
- [ ] Nhấn **"Lưu nháp"** để lưu tạm; nháp chưa phê duyệt

## Bước 4: Re-grade một tiêu chí — `app/pages/3_Giam_khao_duyet.py`
- [ ] Chọn tiêu chí trong **"Tiêu chí"**, nhập **"Phản hồi giám khảo (10-1000 ký tự)"**
- [ ] Nhấn **"Chấm lại"** và kiểm tra version mới cùng phần diff

## Bước 5: Phê duyệt — `app/pages/3_Giam_khao_duyet.py`
- [ ] Chọn điểm cuối và nhập nhận xét của giám khảo
- [ ] Chọn **"Tôi xác nhận phê duyệt kết quả cuối cùng"**
- [ ] Nhấn **"Duyệt"**; status chuyển sang `approved`

## Bước 6: Xem kết quả và gửi email — `app/pages/4_Ket_qua_cuoi.py`
- [ ] Kiểm tra điểm từng tiêu chí, Overall Band, nhận xét, người nhận và email preview
- [ ] Kiểm tra banner chế độ file hoặc SMTP
- [ ] Chọn **"Tôi xác nhận gửi kết quả đã được giám khảo phê duyệt"**
- [ ] Nhấn **"Gửi email kết quả"**; sau một lỗi thử nút **"Thử gửi lại"**
- [ ] File mode tạo `.txt` trong `outbox/`; sau thành công status là `emailed`

## Bước 7: Kiểm tra guardrail/lỗi
- [ ] Essay quá ngắn hoặc quá dài bị từ chối; bài dưới 250 từ phát cảnh báo
- [ ] Email không hợp lệ hoặc có CR/LF bị từ chối
- [ ] Gửi trước approve, re-grade sau approve và gửi lần hai đều bị từ chối
- [ ] Lỗi gửi giữ status `approved` và cho phép retry

## Bước 8: Observability — `app/pages/5_Logs.py`
- [ ] Tab **"LLM và truy xuất"**: lọc bài, bước và trạng thái
- [ ] Xem số calls, latency TB/p95, error/retry rate, token theo bước
- [ ] Xem chart latency-per-step, calls-over-time và recent calls
- [ ] Tab **"Email"**: sent/failed counts và lịch sử có địa chỉ đã mask

## Bước 9: Evals
- [ ] Chạy `python evals/run_evals.py`
- [ ] Kiểm tra đủ bốn metrics, variance skipped và MAE skipped khi không có reference bands

## Bước 10: Submission package
- [ ] Chạy `python -m ruff check .`, `python -m ruff format --check .` và `python -m pytest -q`
- [ ] Kiểm tra README, không commit `.env`/credentials và CI
- [ ] Slides, video và presentation không thuộc scope Day 5
