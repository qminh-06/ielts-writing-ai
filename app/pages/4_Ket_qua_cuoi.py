"""Trang 4: Xem kết quả cuối cùng và gửi thông báo kết quả qua email."""
import streamlit as st

from ielts_ai.services.grading_service import get_all_essays, get_essay_details
from ielts_ai.services.review_service import approve_and_send

st.set_page_config(page_title="Kết quả cuối - IELTS AI", page_icon="🎓")
st.header("🎓 Bước 4: Kết quả cuối cùng & Gửi Email")

essays = get_all_essays()
if not essays:
    st.info("Chưa có bài viết nào.")
    st.stop()

essay_ids = [e["id"] for e in essays]
default_id = st.session_state.get("current_essay_id", essay_ids[0])
selected_id = st.selectbox(
    "Chọn bài viết:",
    essay_ids,
    index=essay_ids.index(default_id) if default_id in essay_ids else 0,
)

essay = get_essay_details(selected_id)
if not essay:
    st.stop()

st.write(f"**Thí sinh:** {essay['candidate_email']}")
st.write(f"**Trạng thái hiện tại:** `{essay['status']}`")

if essay["status"] != "approved" and essay["status"] != "emailed":
    st.warning("⚠️ Bài viết chưa được giám khảo phê duyệt (Trạng thái phải là 'approved').")
    st.info("Vui lòng quay lại Trang 3 để giám khảo phê duyệt trước khi gửi email.")

if essay["status"] == "approved":
    if st.button("Xác nhận & Gửi Email kết quả cho thí sinh"):
        with st.spinner("Đang gửi thông báo kết quả..."):
            res = approve_and_send(selected_id)
            if res.get("status") == "emailed":
                st.success("Đã gửi email kết quả thành công cho thí sinh!")
                st.rerun()
            else:
                st.error("Gửi email thất bại.")

if essay["status"] == "emailed":
    st.success("✅ Email thông báo kết quả đã được gửi thành công đến hòm thư thí sinh.")
