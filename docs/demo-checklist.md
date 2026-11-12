# Demo Checklist (10 bước / 10 steps)

## Bước 1: Nhập bài
- [ ] Mở trang "Nhập bài"
- [ ] Điền email thí sinh hợp lệ
- [ ] Điền đề bài và bài viết (>250 từ)
- [ ] Nhấn "Gửi để chấm điểm"
- [ ] Thấy thông báo thành công, chuyển sang trang 2

## Bước 2: Xem kết quả AI
- [ ] Hiển thị 4 tiêu chí (TR, CC, LR, GRA) với điểm và nhận xét
- [ ] Hiển thị Overall Band (tính đúng theo công thức)
- [ ] Hiển thị evidence cho mỗi tiêu chí
- [ ] Hiển thị warnings (nếu có)
- [ ] Hiển thị retrieved rubric chunks

## Bước 3: Giám khảo chỉnh sửa
- [ ] Giám khảo có thể sửa điểm từng tiêu chí
- [ ] Giám khảo thêm nhận xét tổng thể
- [ ] Nhấn "Chấp nhận" để approve

## Bước 4: Re-grade một tiêu chí
- [ ] Chọn tiêu chí cần chấm lại (ví dụ: CC)
- [ ] Nhập phản hồi cho AI
- [ ] Nhấn "Chấm lại"
- [ ] Kết quả mới hiển thị

## Bước 5: Phê duyệt cuối cùng
- [ ] Giám khảo review lần cuối
- [ ] Nhấn "Phê duyệt & Gửi email"
- [ ] Hệ thống từ chối nếu chưa approve

## Bước 6: Gửi email
- [ ] Email được tạo trong outbox/
- [ ] Trang 4 hiển thị kết quả cuối

## Bước 7: Kiểm tra guardrail/lỗi
- [ ] Thử nhập essay quá ngắn (<100 ký tự) → warning
- [ ] Thử nhập email không hợp lệ → error
- [ ] Thử gửi email khi chưa approve → error rõ ràng

## Bước 8: Observability
- [ ] Mở trang "Nhật ký (Logs)"
- [ ] Thấy count, avg latency, error rate của LLM calls

## Bước 9: Evals
- [ ] Chạy `make evals`
- [ ] Thấy bảng 4 metrics

## Bước 10: Submission package
- [ ] README đầy đủ
- [ ] `make check` xanh
- [ ] GitHub repo có CI xanh
- [ ] Video demo sẵn sàng
