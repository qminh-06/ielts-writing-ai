---
title: /new-task — Implement một task
description: Implement một task ID từ task-map
---
# /new-task Workflow

1. Đọc `docs/task-map.md` để tìm task ID → files cần sửa
2. Đọc `src/ielts_ai/schemas.py` để hiểu contracts
3. Đọc `AGENTS.md` để hiểu hard rules
4. List các files cần chạm vào, confirm với user nếu không chắc
5. Implement task:
   - Chỉ implement task ID đó, không làm thêm
   - Thêm `# TODO(<task-id>): ...` cho phần chưa xong
   - Giữ nguyên comments và docstrings không liên quan
6. Thêm/cập nhật tests trong `tests/`
7. Chạy `/check` để confirm không break gì
