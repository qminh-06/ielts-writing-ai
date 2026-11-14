"""Vietnamese final-result preview and explicit email delivery screen."""

import json

import streamlit as st

from app.ui_helpers import select_essay
from ielts_ai.config import get_settings
from ielts_ai.services.grading_service import get_essay_details
from ielts_ai.services.review_service import (
    Criterion,
    EmailSendError,
    approve_and_send,
    final_overall_band,
    get_email_history,
    get_email_preview,
    get_review_state,
)

st.set_page_config(page_title="Kết quả cuối - IELTS AI", page_icon="🎓", layout="wide")
st.header("Bước 4: Kết quả cuối cùng và gửi email")
essay_id = select_essay("Chọn bài viết")
if essay_id is None:
    st.stop()
essay = get_essay_details(essay_id)
if essay is None:
    st.error("Không tìm thấy bài viết.")
    st.stop()

settings = get_settings()
if settings.email_mode.lower() == "file":
    st.info("Chế độ file: email được lưu vào outbox/, không gửi thật.")
else:
    st.warning("Chế độ SMTP: email sẽ được gửi thật qua SMTP.")
st.caption(f"Trạng thái: **{essay['status']}** · Người nhận: `{essay['candidate_email']}`")

if essay["status"] in ("approved", "emailed"):
    try:
        review = get_review_state(essay_id)["final_review"]
        if review is None:
            raise LookupError("Không tìm thấy quyết định phê duyệt của giám khảo.")
        final_bands = {
            Criterion(code): float(band)
            for code, band in json.loads(review["final_bands_json"]).items()
        }
        st.subheader("Điểm cuối cùng đã được giám khảo phê duyệt")
        score_cols = st.columns(4)
        for column, criterion in zip(score_cols, Criterion, strict=True):
            column.metric(criterion.value, f"{final_bands[criterion]:.1f}")
        st.metric("Overall band", f"{final_overall_band(final_bands):.1f}")
        st.write(f"**Nhận xét của giám khảo:** {review['examiner_comment']}")
        preview = get_email_preview(essay_id)
        st.subheader("Xem trước email")
        st.write(f"**Đến:** {preview['recipient']}")
        st.write(f"**Tiêu đề:** {preview['subject']}")
        st.text(preview["body"])
    except LookupError as error:
        st.error(str(error))
else:
    st.warning("Bài viết cần được giám khảo duyệt trước khi gửi email.")

confirmed = st.checkbox("Tôi xác nhận gửi kết quả đã được giám khảo phê duyệt")
busy_key = f"email_busy_{essay_id}"
send_disabled = (
    essay["status"] != "approved" or not confirmed or st.session_state.get(busy_key, False)
)
history = get_email_history(essay_id)
retry_available = essay["status"] == "approved" and any(
    item["status"] == "failed" for item in history
)
button_label = "Thử gửi lại" if retry_available else "Gửi email kết quả"
if st.button(button_label, type="primary", disabled=send_disabled):
    st.session_state[busy_key] = True
    try:
        with st.spinner("Đang gửi email kết quả..."):
            approve_and_send(essay_id)
        st.success("Đã gửi email kết quả.")
        st.rerun()
    except (EmailSendError, ValueError) as error:
        st.session_state[busy_key] = False
        st.error(str(error))

st.subheader("Lịch sử gửi email")
if history:
    st.dataframe(history, use_container_width=True)
    if essay["status"] == "approved" and any(item["status"] == "failed" for item in history):
        st.caption("Bạn có thể xác nhận và thử gửi lại sau lần gửi thất bại.")
else:
    st.info("Chưa có lần gửi email nào.")
