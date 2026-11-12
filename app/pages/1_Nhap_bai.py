"""Trang 1: Nhập bài viết và gửi chấm điểm."""

import streamlit as st

from ielts_ai.services.grading_service import submit_and_grade

st.set_page_config(page_title="Nhập bài - IELTS AI", page_icon="📝")
st.header("📝 Bước 1: Nhập bài thi IELTS Task 2")

with st.form("essay_form"):
    email = st.text_input("Email thí sinh", value="candidate@example.com")
    prompt_text = st.text_area(
        "Đề bài (Task Prompt)",
        value="Some people believe that unpaid community service should be a compulsory part of high school programmes. To what extent do you agree or disagree?",
        height=100,
    )
    essay_text = st.text_area(
        "Bài viết của thí sinh (Tối thiểu 250 từ)",
        height=300,
        placeholder="Dán toàn bộ bài làm IELTS Writing Task 2 tại đây...",
    )
    submitted = st.form_submit_button("Gửi bài chấm điểm")

if submitted:
    if not essay_text.strip():
        st.error("Vui lòng nhập bài viết!")
    else:
        with st.spinner("AI đang phân tích và chấm điểm bài viết..."):
            res = submit_and_grade(
                candidate_email=email,
                prompt_text=prompt_text,
                essay_text=essay_text,
            )

        if res["errors"]:
            for err in res["errors"]:
                st.error(err)
        else:
            st.success(f"Nộp bài thành công! Mã bài viết: #{res['essay_id']}")
            if res["warnings"]:
                for w in res["warnings"]:
                    st.warning(w)
            st.session_state["current_essay_id"] = res["essay_id"]
            st.info("Vui lòng chuyển qua **Trang 2: Kết quả AI** để xem chi tiết.")
