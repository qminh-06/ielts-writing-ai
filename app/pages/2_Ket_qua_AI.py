"""Trang 2: Xem kết quả AI chấm điểm."""
import streamlit as st

from ielts_ai.services.grading_service import get_all_essays, get_latest_grading_result

st.set_page_config(page_title="Kết quả AI - IELTS AI", page_icon="📊", layout="wide")
st.header("📊 Bước 2: Kết quả đánh giá từ AI")

essays = get_all_essays()
if not essays:
    st.info("Chưa có bài viết nào được nộp. Vui lòng quay lại Trang 1 để nộp bài.")
    st.stop()

essay_ids = [e["id"] for e in essays]
default_id = st.session_state.get("current_essay_id", essay_ids[0])
selected_id = st.selectbox(
    "Chọn mã bài viết cần xem:",
    essay_ids,
    index=essay_ids.index(default_id) if default_id in essay_ids else 0,
)

res = get_latest_grading_result(selected_id)
if not res:
    st.warning("Bài viết này chưa có kết quả đánh giá AI.")
    st.stop()

# Hiển thị Overall Band nổi bật
st.metric(
    label="Overall Band Score (AI tính toán trong code)",
    value=f"{res.overall_band:.1f}",
)

if res.warnings:
    st.subheader("⚠️ Cảnh báo chất lượng / Guardrails:")
    for w in res.warnings:
        st.warning(w)

st.subheader("Chi tiết 4 tiêu chí IELTS:")
cols = st.columns(4)
for idx, cs in enumerate(res.criteria):
    with cols[idx]:
        st.markdown(f"### {cs.criterion.value}: **{cs.band:.1f}**")
        st.write(f"**Nhận xét:** {cs.comment}")
        if cs.evidence:
            st.markdown("**Dẫn chứng từ bài:**")
            for ev in cs.evidence:
                st.code(ev, language="text")

st.divider()
st.subheader("📚 Trích dẫn Rubric (RAG context):")
if res.retrieved_rubric:
    for chunk in res.retrieved_rubric:
        st.markdown(
            f"- **[{chunk.criterion.value} - Band {chunk.band}]** {chunk.text} *(Nguồn: {chunk.source})*"
        )
else:
    st.write("Không có rubric chunk nào.")
