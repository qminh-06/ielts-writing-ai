"""Trang giám khảo xem bài, lưu nháp, chấm lại một tiêu chí và phê duyệt."""

import json

import streamlit as st

from app.ui_helpers import select_essay
from ielts_ai.services.review_service import (
    Criterion,
    ReviewDecision,
    ReviewValidationError,
    final_overall_band,
    get_review_state,
    save_review,
)

st.set_page_config(page_title="Giám khảo duyệt - IELTS AI", page_icon="⚖️", layout="wide")
st.header("Bước 3: Giám khảo xem xét và phê duyệt")
essay_id = select_essay("Chọn mã bài viết cần duyệt")
if essay_id is None:
    st.stop()

state = get_review_state(essay_id)
essay = state["essay"]
latest = state["latest"]
if latest is None:
    st.warning("Bài viết chưa có kết quả AI.")
    st.stop()

success_key = f"regrade_success_{essay_id}"
if success_key in st.session_state:
    st.success(st.session_state.pop(success_key))
st.caption(f"Trạng thái: **{state['status']}** · Phiên bản AI mới nhất: v{latest.version}")
st.subheader("Bài viết")
st.text_area("Nội dung bài viết", value=essay["essay_text"], height=260, disabled=True)
versions = {result.version: result for result in state["versions"]}
selected_version = st.selectbox("Xem phiên bản AI", list(versions), index=len(versions) - 1)
selected_result = versions[selected_version]
if selected_version in state["diffs"]:
    diff = state["diffs"][selected_version]
    if diff:
        st.info(
            "Khác biệt: "
            + ", ".join(
                f"{criterion} {before:.1f} → {after:.1f}"
                for criterion, (before, after) in diff.items()
            )
        )
    else:
        st.info("Không có thay đổi điểm so với phiên bản trước.")

st.subheader(f"Điểm AI phiên bản {selected_result.version}")
score_cols = st.columns(4)
for column, score in zip(score_cols, selected_result.criteria, strict=False):
    with column:
        st.markdown(f"#### {score.criterion.value}: {score.band:.1f}")
        st.write(score.comment)
        for quote in score.evidence:
            st.caption(f"Dẫn chứng: “{quote}”")
injection_warnings = [
    warning for warning in selected_result.warnings if "injection" in warning.lower()
]
if injection_warnings:
    st.error("Cảnh báo dữ liệu có dấu hiệu prompt injection.")
for warning in selected_result.warnings:
    if warning not in injection_warnings:
        st.warning(warning)
if selected_result.retrieved_rubric:
    with st.expander("Rubric đã truy xuất"):
        for chunk in selected_result.retrieved_rubric:
            st.markdown(f"**{chunk.criterion.value} · Band {chunk.band}** — {chunk.text}")

locked = state["status"] in ("approved", "emailed")
draft = state["draft"]
initial_bands = {score.criterion.value: score.band for score in latest.criteria}
if draft:
    initial_bands.update(json.loads(draft["final_bands_json"]))
st.subheader("Điểm cuối cùng của giám khảo")
columns = st.columns(4)
final_bands = {}
for column, criterion in zip(columns, Criterion, strict=True):
    with column:
        final_bands[criterion] = st.number_input(
            criterion.value,
            min_value=0.0,
            max_value=9.0,
            step=0.5,
            value=float(initial_bands[criterion.value]),
            key=f"review_{essay_id}_{criterion.value}",
            disabled=locked,
        )
st.metric("Overall band của giám khảo", f"{final_overall_band(final_bands):.1f}")
comment = st.text_area(
    "Nhận xét của giám khảo",
    value=draft["examiner_comment"] if draft else "",
    key=f"review_comment_{essay_id}",
    disabled=locked,
)
confirm = st.checkbox("Tôi xác nhận phê duyệt kết quả cuối cùng", disabled=locked)
save_col, approve_col = st.columns(2)
with save_col:
    save_draft = st.button("Lưu nháp", disabled=locked, key=f"save_draft_{essay_id}")
with approve_col:
    approve = st.button("Duyệt", type="primary", disabled=locked, key=f"approve_{essay_id}")
if save_draft or approve:
    try:
        if approve and not confirm:
            st.error("Vui lòng xác nhận trước khi duyệt.")
        else:
            save_review(
                ReviewDecision(
                    essay_id=essay_id,
                    final_bands=final_bands,
                    examiner_comment=comment,
                    action="accept" if approve else "draft",
                )
            )
            st.success("Đã phê duyệt." if approve else "Đã lưu bản nháp.")
            st.rerun()
    except (ReviewValidationError, ValueError, LookupError) as error:
        st.error(str(error))

if state["regrade_history"]:
    with st.expander("Lịch sử chấm lại"):
        for item in state["regrade_history"]:
            st.write(
                f"{item['criterion']}: v{item['from_version']} → v{item['to_version']} · "
                f"{item['feedback']}"
            )

with st.expander("Chấm lại một tiêu chí"):
    busy_key = f"regrade_busy_{essay_id}"

    def reset_busy() -> None:
        st.session_state[busy_key] = False

    target = st.selectbox(
        "Tiêu chí",
        list(Criterion),
        key=f"regrade_criterion_{essay_id}",
        on_change=reset_busy,
        disabled=locked,
    )
    feedback = st.text_area(
        "Phản hồi giám khảo (10-1000 ký tự)",
        key=f"regrade_feedback_{essay_id}",
        on_change=reset_busy,
        disabled=locked,
    )
    st.caption(f"Độ dài: {len(feedback.strip())} / 1000 ký tự")
    submit_regrade = st.button(
        "Chấm lại",
        key=f"submit_regrade_{essay_id}",
        disabled=locked or st.session_state.get(busy_key, False),
    )
    if submit_regrade:
        if not 10 <= len(feedback.strip()) <= 1000:
            st.error("Phản hồi cần có từ 10 đến 1000 ký tự sau khi bỏ khoảng trắng thừa.")
        else:
            try:
                st.session_state[busy_key] = True
                with st.spinner("AI đang xem xét lại tiêu chí..."):
                    save_review(
                        ReviewDecision(
                            essay_id=essay_id,
                            final_bands=final_bands,
                            examiner_comment=comment,
                            action="draft",
                        )
                    )
                    decision = ReviewDecision(
                        essay_id=essay_id,
                        final_bands=final_bands,
                        examiner_comment=comment,
                        action="regrade",
                        regrade_criterion=target,
                        regrade_feedback=feedback,
                    )
                    new_result = save_review(decision)
                new_band = next(
                    score.band for score in new_result.criteria if score.criterion == target
                )
                old_band = next(
                    score.band for score in latest.criteria if score.criterion == target
                )
                st.session_state[f"regrade_success_{essay_id}"] = (
                    f"{target.value}: {old_band:.1f} → {new_band:.1f}"
                )
                st.rerun()
            except (ReviewValidationError, ValueError, LookupError) as error:
                st.session_state[busy_key] = False
                st.error(str(error))
