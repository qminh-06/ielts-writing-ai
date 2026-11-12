"""Trang 3: Giám khảo kiểm tra, sửa điểm, re-grade hoặc phê duyệt."""
import streamlit as st

from ielts_ai.schemas import Criterion, ReviewDecision
from ielts_ai.services.grading_service import get_all_essays, get_latest_grading_result
from ielts_ai.services.review_service import request_regrade, save_examiner_review

st.set_page_config(page_title="Giám khảo duyệt - IELTS AI", page_icon="⚖️", layout="wide")
st.header("⚖️ Bước 3: Giám khảo xem xét & Phê duyệt điểm")

essays = get_all_essays()
if not essays:
    st.info("Chưa có bài viết nào.")
    st.stop()

essay_ids = [e["id"] for e in essays]
default_id = st.session_state.get("current_essay_id", essay_ids[0])
selected_id = st.selectbox(
    "Chọn mã bài viết cần duyệt:",
    essay_ids,
    index=essay_ids.index(default_id) if default_id in essay_ids else 0,
)

res = get_latest_grading_result(selected_id)
if not res:
    st.warning("Bài viết chưa có kết quả AI.")
    st.stop()

st.write(f"Trạng thái hiện tại: Điểm AI dự kiến **{res.overall_band:.1f}**")

tab1, tab2 = st.tabs(["Chỉnh sửa & Duyệt điểm", "Yêu cầu AI chấm lại (Re-grade)"])

with tab1:
    with st.form("review_form"):
        st.subheader("Điều chỉnh điểm 4 tiêu chí:")
        col1, col2, col3, col4 = st.columns(4)
        c_bands = {c.criterion: c.band for c in res.criteria}

        with col1:
            tr_band = st.number_input(
                "Task Response (TR)", 0.0, 9.0, float(c_bands.get(Criterion.TR, 6.0)), step=0.5
            )
        with col2:
            cc_band = st.number_input(
                "Coherence & Cohesion (CC)", 0.0, 9.0, float(c_bands.get(Criterion.CC, 6.0)), step=0.5
            )
        with col3:
            lr_band = st.number_input(
                "Lexical Resource (LR)", 0.0, 9.0, float(c_bands.get(Criterion.LR, 6.0)), step=0.5
            )
        with col4:
            gra_band = st.number_input(
                "Grammatical Range (GRA)", 0.0, 9.0, float(c_bands.get(Criterion.GRA, 6.0)), step=0.5
            )

        comment = st.text_area(
            "Nhận xét chung của giám khảo:",
            value="Bài làm đạt yêu cầu, lập luận rõ ràng, vốn từ vựng tương đối tốt.",
        )
        approved = st.form_submit_button("Phê duyệt kết quả (Approve)")

    if approved:
        decision = ReviewDecision(
            essay_id=selected_id,
            final_bands={
                Criterion.TR: tr_band,
                Criterion.CC: cc_band,
                Criterion.LR: lr_band,
                Criterion.GRA: gra_band,
            },
            examiner_comment=comment,
            action="accept",
        )
        save_examiner_review(decision)
        st.success("Đã phê duyệt kết quả thành công! Vui lòng chuyển sang Trang 4 để gửi email.")

with tab2:
    with st.form("regrade_form"):
        st.subheader("Yêu cầu AI chấm lại 1 tiêu chí kèm phản hồi giám khảo:")
        target_criterion = st.selectbox("Chọn tiêu chí cần chấm lại:", list(Criterion))
        feedback = st.text_area(
            "Phản hồi / Gợi ý của giám khảo cho AI:",
            value="Thí sinh có sử dụng nhiều từ vựng chủ đề giáo dục phong phú, xem xét nâng điểm LR.",
        )
        regrade_btn = st.form_submit_button("Gửi yêu cầu Re-grade")

    if regrade_btn:
        with st.spinner("AI đang chấm lại tiêu chí..."):
            new_res = request_regrade(selected_id, target_criterion, feedback)
            st.success(f"Đã chấm lại xong! Overall Band mới: {new_res.overall_band:.1f}")
            st.rerun()
