"""Trang 2: Xem kết quả AI chấm điểm, tiêu chí, dẫn chứng, rubric và cảnh báo."""

from collections import defaultdict

import streamlit as st

from app.ui_helpers import format_grading_error, select_essay
from ielts_ai.services.grading_service import (
    GradingInProgressError,
    get_essay_details,
    get_latest_grading_result,
    start_grading,
)

st.set_page_config(page_title="Kết quả AI - IELTS AI", page_icon="📊", layout="wide")
st.header("📊 Bước 2: Kết quả đánh giá từ AI")


def _run_grading(essay_id: int) -> None:
    busy_key = f"grading_busy_{essay_id}"
    error_key = f"grading_error_{essay_id}"
    if st.session_state.get(busy_key, False):
        st.warning("Bài viết này đang được chấm; yêu cầu thứ hai đã được bỏ qua.")
        return
    st.session_state[busy_key] = True
    try:
        with st.spinner("AI đang truy xuất rubric và phân tích bài viết..."):
            result = start_grading(essay_id)
        if result.get("errors"):
            st.session_state[error_key] = "\n".join(result["errors"])
        else:
            st.session_state.pop(error_key, None)
            st.success("Chấm điểm thành công!")
    except GradingInProgressError:
        st.session_state[error_key] = "Bài viết này đang được chấm; yêu cầu thứ hai đã được bỏ qua."
    except (ValueError, LookupError) as error:
        st.session_state[error_key] = str(error)
    finally:
        st.session_state[busy_key] = False
    st.rerun()


selected_id = select_essay("Chọn mã bài viết cần xem")
if selected_id is None:
    st.stop()

essay_info = get_essay_details(selected_id)
if not essay_info:
    st.error("Không tìm thấy thông tin bài viết.")
    st.stop()

current_status = essay_info.get("status", "pending")
st.caption(
    f"Trạng thái bài viết: **{current_status}** | Thí sinh: `{essay_info.get('candidate_email')}`"
)

# 1. Error state with Retry button
if current_status == "grading_failed":
    failure = st.session_state.pop(f"grading_error_{selected_id}", "")
    st.error(
        format_grading_error(failure)
        if failure
        else "Quá trình chấm bài thất bại. Kiểm tra cấu hình rồi thử chấm lại."
    )
    if st.button(
        "🔄 Thử chấm lại (Retry Grading)",
        type="primary",
        disabled=st.session_state.get(f"grading_busy_{selected_id}", False),
    ):
        _run_grading(selected_id)
    st.stop()

# 2. Pending state with Start button
if current_status == "pending":
    st.info("Bài viết đang ở trạng thái chờ chấm điểm.")
    failure = st.session_state.pop(f"grading_error_{selected_id}", "")
    if failure:
        st.error(format_grading_error(failure))
    if st.button(
        "🚀 Bắt đầu chấm điểm với AI",
        type="primary",
        disabled=st.session_state.get(f"grading_busy_{selected_id}", False),
    ):
        _run_grading(selected_id)
    st.stop()

# 3. Finished state (ai_done, reviewing, approved, emailed)
res = get_latest_grading_result(selected_id)
if not res:
    st.warning("Bài viết này chưa có kết quả đánh giá AI.")
    st.stop()

# Overall Band display
col_band, col_meta = st.columns([1, 2])
with col_band:
    st.metric(
        label="Overall Band Score (Tính bằng code Python)",
        value=f"{res.overall_band:.1f}",
        help="Làm tròn nửa điểm (Half-up): floor(mean * 2 + 0.5) / 2",
    )
with col_meta:
    st.write(f"**Mô hình đánh giá:** `{res.model}`")
    st.write(
        f"**Phiên bản chấm:** v{res.version} | **Thời gian:** {res.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )

# Warning Badges
if res.warnings:
    st.subheader("🛡️ Cảnh báo & Giám sát An toàn (Guardrails)")
    badge_cols = st.columns(3)
    evidence_warnings = [w for w in res.warnings if "evidence not found" in w.lower()]
    length_warnings = [
        w for w in res.warnings if "250" in w or "ít hơn" in w or "short" in w.lower()
    ]
    injection_warnings = [w for w in res.warnings if "injection" in w.lower()]
    other_warnings = [
        w
        for w in res.warnings
        if w not in evidence_warnings and w not in length_warnings and w not in injection_warnings
    ]

    with badge_cols[0]:
        if evidence_warnings:
            st.error(f"⚠️ Dẫn chứng nghi vấn: {len(evidence_warnings)} câu không khớp bài")
        else:
            st.success("✅ Dẫn chứng: 100% trích xuất từ bài")

    with badge_cols[1]:
        if length_warnings:
            st.warning("⚠️ Số từ: Dưới 250 từ tiêu chuẩn")
        else:
            st.success("✅ Số từ: Đạt yêu cầu")

    with badge_cols[2]:
        if injection_warnings:
            st.error("🚨 Prompt Injection: Phát hiện lệnh đáng ngờ")
        else:
            st.success("✅ An toàn dữ liệu: Không phát hiện injection")

    with st.expander("Xem chi tiết các thông báo cảnh báo", expanded=False):
        for w in res.warnings:
            st.markdown(f"- {w}")

st.divider()

# Chi tiết 4 tiêu chí
st.subheader("📋 Điểm chi tiết 4 tiêu chí IELTS:")
crit_cols = st.columns(4)
for idx, cs in enumerate(res.criteria):
    with crit_cols[idx]:
        st.markdown(f"#### {cs.criterion.value}: **{cs.band:.1f}**")
        st.info(cs.comment)
        if cs.evidence:
            st.markdown("**Dẫn chứng từ bài:**")
            for ev in cs.evidence:
                st.code(ev, language="text")

st.divider()

# Per-criterion retrieved rubric chunks
st.subheader("📚 Rubric trích xuất theo từng tiêu chí (RAG Context):")
if res.retrieved_rubric:
    rubric_by_crit = defaultdict(list)
    for chunk in res.retrieved_rubric:
        crit_key = (
            chunk.criterion.value if hasattr(chunk.criterion, "value") else str(chunk.criterion)
        )
        rubric_by_crit[crit_key].append(chunk)

    tabs = st.tabs(
        [
            "Task Response (TR)",
            "Coherence & Cohesion (CC)",
            "Lexical Resource (LR)",
            "Grammar Range (GRA)",
        ]
    )
    tab_mapping = {
        "TR": tabs[0],
        "CC": tabs[1],
        "LR": tabs[2],
        "GRA": tabs[3],
    }
    for crit_code, tab in tab_mapping.items():
        with tab:
            chunks = rubric_by_crit.get(crit_code, [])
            if chunks:
                for c in chunks:
                    st.markdown(f"**[Band {c.band}]** {c.text}\n\n*Nguồn:* `{c.source}`")
                    st.markdown("---")
            else:
                st.caption("Không có rubric chunk nào cho tiêu chí này.")
else:
    st.info("Không có dữ liệu rubric trích xuất.")
