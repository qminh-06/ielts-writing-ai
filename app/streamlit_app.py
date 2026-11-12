"""Trang chủ ứng dụng IELTS Writing AI Assistant."""
import streamlit as st

st.set_page_config(
    page_title="IELTS Writing AI Assistant",
    page_icon="📝",
    layout="wide",
)

st.title("📝 IELTS Writing AI Assistant (Task 2)")
st.markdown("""
Chào mừng bạn đến với hệ thống chấm điểm và hỗ trợ giám khảo IELTS Writing Task 2.

### Quy trình hoạt động:
1. **Trang 1 - Nhập bài:** Thí sinh / Giám khảo gửi đề bài và bài viết.
2. **Trang 2 - Kết quả AI:** AI đánh giá sơ bộ 4 tiêu chí (TR, CC, LR, GRA) kèm dẫn chứng và rubric.
3. **Trang 3 - Giám khảo duyệt:** Giám khảo chỉnh sửa điểm, yêu cầu AI chấm lại 1 tiêu chí, hoặc duyệt.
4. **Trang 4 - Kết quả cuối:** Xem bảng điểm đã phê duyệt và thông tin gửi email.
5. **Trang 5 - Logs:** Theo dõi độ trễ, token, số lần retry của các lời gọi LLM.

---
*Dự án phát triển dựa trên kiến trúc Multi-Agent & RAG, tuân thủ nguyên tắc An toàn AI.*
""")
