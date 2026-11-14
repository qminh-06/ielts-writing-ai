"""Vietnamese observability page for model and email activity."""

import pandas as pd
import streamlit as st

from app.ui_helpers import select_essay
from ielts_ai.services.metrics_service import get_call_metrics, get_email_metrics

st.set_page_config(page_title="Nhật ký hệ thống - IELTS AI", page_icon="📈", layout="wide")
st.header("Bước 5: Nhật ký hệ thống")
model_tab, email_tab = st.tabs(["LLM và truy xuất", "Email"])

with model_tab:
    essay_id = select_essay("Lọc theo bài viết")
    filter_cols = st.columns(2)
    with filter_cols[0]:
        step = st.selectbox("Bước", ["Tất cả", "retrieve", "grade", "regrade_retrieve", "regrade"])
    with filter_cols[1]:
        status = st.selectbox("Trạng thái", ["Tất cả", "ok", "error"])
    metrics = get_call_metrics(
        essay_id,
        None if step == "Tất cả" else step,
        None if status == "Tất cả" else status,
    )
    cols = st.columns(5)
    cols[0].metric("Tổng lời gọi", metrics["total_calls"])
    cols[1].metric("Latency TB", f"{metrics['average_latency_ms']:.1f} ms")
    cols[2].metric("Latency p95", f"{metrics['p95_latency_ms']:.1f} ms")
    cols[3].metric("Tỷ lệ lỗi", f"{metrics['error_rate']:.1%}")
    cols[4].metric("Tỷ lệ retry", f"{metrics['retry_rate']:.1%}")
    if metrics["total_calls"]:
        step_frame = pd.DataFrame.from_dict(metrics["per_step"], orient="index")
        st.subheader("Tokens và retry theo bước")
        st.dataframe(step_frame, use_container_width=True)
        st.subheader("Độ trễ theo bước")
        latency_frame = pd.DataFrame.from_dict(
            metrics["latency_per_step"], orient="index", columns=["latency_ms"]
        )
        st.bar_chart(latency_frame)
        st.subheader("Lời gọi theo thời gian")
        calls_frame = pd.DataFrame(metrics["calls_series"])
        st.line_chart(calls_frame.set_index("ts")["calls"])
        st.subheader("Token theo bước")
        st.dataframe(
            step_frame[["calls", "input_tokens", "output_tokens"]], use_container_width=True
        )
        st.subheader("Lời gọi gần đây")
        st.dataframe(metrics["recent_calls"], use_container_width=True)
    else:
        st.info("Không có lời gọi nào khớp bộ lọc.")

with email_tab:
    email_metrics = get_email_metrics()
    counts = email_metrics["counts"]
    columns = st.columns(2)
    columns[0].metric("Đã gửi", counts.get("sent", 0))
    columns[1].metric("Thất bại", counts.get("failed", 0))
    if email_metrics["recent_attempts"]:
        st.subheader("Lần gửi gần đây")
        st.dataframe(email_metrics["recent_attempts"], use_container_width=True)
    else:
        st.info("Chưa có lần gửi email nào.")
