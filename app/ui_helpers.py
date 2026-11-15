"""Shared Streamlit selection controls for essay-oriented pages."""

import streamlit as st

from ielts_ai.services.grading_service import get_all_essays


def format_grading_error(error: str) -> str:
    """Render common provider and retrieval failures in Vietnamese."""
    lowered = error.casefold()
    if "timed out" in lowered or "timeout" in lowered:
        return "Đã hết thời gian chờ khi gọi mô hình. Hãy kiểm tra kết nối rồi thử chấm lại."
    if "http 429" in lowered or "rate limit" in lowered:
        return "Mô hình đang giới hạn số yêu cầu (HTTP 429). Hãy chờ một lúc rồi thử lại."
    if "http 5" in lowered:
        return "Dịch vụ mô hình đang gặp lỗi tạm thời. Hãy chờ một lúc rồi thử lại."
    if "rubric index" in lowered or "chromadb" in lowered:
        return (
            "Không truy xuất được rubric. Hãy kiểm tra dữ liệu và chạy "
            "`python scripts/build_rubric_index.py`, sau đó thử lại."
        )
    if "jsondecodeerror" in lowered or "invalid json" in lowered:
        return "Mô hình trả kết quả không đúng định dạng sau các lần thử. Bạn có thể thử lại."
    return f"Chấm điểm thất bại. Bạn có thể thử lại. Chi tiết an toàn: {error}"


def format_email_error(error: str) -> str:
    """Render sanitized SMTP errors without exposing raw provider details."""
    lowered = error.casefold()
    if "authentication failed" in lowered:
        return "Gmail từ chối xác thực. Hãy kiểm tra tài khoản và App Password SMTP."
    if "rejected the recipient" in lowered or "recipient email address is invalid" in lowered:
        return "Máy chủ email từ chối địa chỉ người nhận. Hãy kiểm tra lại email."
    if "delivery failed" in lowered:
        return "Không gửi được email do lỗi kết nối máy chủ. Hãy kiểm tra SMTP rồi thử lại."
    return "Gửi email thất bại. Hãy kiểm tra địa chỉ nhận và cấu hình SMTP rồi thử lại."


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
