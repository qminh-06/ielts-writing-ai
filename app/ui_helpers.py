"""Shared Streamlit selection controls for essay-oriented pages."""

import streamlit as st

from ielts_ai.services.grading_service import get_all_essays


def select_essay(label: str = "Chọn bài viết") -> int | None:
    """Select and remember an essay ID while displaying its current status."""
    essays = get_all_essays()
    if not essays:
        st.info("Chưa có bài viết nào.")
        return None
    ids = [essay["id"] for essay in essays]
    default = st.session_state.get("current_essay_id", ids[0])
    selected = st.selectbox(
        label,
        ids,
        index=ids.index(default) if default in ids else 0,
        format_func=lambda essay_id: next(
            f"Bài #{essay_id} — {essay['status']}" for essay in essays if essay["id"] == essay_id
        ),
    )
    st.session_state["current_essay_id"] = selected
    return selected
