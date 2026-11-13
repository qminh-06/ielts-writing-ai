"""Trang 5: Tóm tắt nhật ký lời gọi AI và truy xuất."""

import pandas as pd
import streamlit as st

from ielts_ai.services.grading_service import get_all_essays
from ielts_ai.services.metrics_service import get_call_metrics

st.set_page_config(page_title="Nhật ký hệ thống - IELTS AI", page_icon="📈", layout="wide")
st.header("Bước 5: Nhật ký và độ trễ mô hình")
essay_options = [None] + [item["id"] for item in get_all_essays()]
selected = st.selectbox(
    "Lọc theo bài viết",
    essay_options,
    format_func=lambda value: "Tất cả" if value is None else str(value),
)
metrics = get_call_metrics(selected)
col1, col2, col3 = st.columns(3)
col1.metric("Tổng số lời gọi", metrics["total_calls"])
col2.metric("Độ trễ trung bình", f"{metrics['average_latency_ms']:.1f} ms")
col3.metric("Tỷ lệ lỗi", f"{metrics['error_rate']:.1%}")
st.subheader("Số lời gọi theo bước")
step_rows = [
    {"Bước": step, "Số lời gọi": count} for step, count in metrics["counts_per_step"].items()
]
st.dataframe(pd.DataFrame(step_rows), use_container_width=True)
st.subheader("Lời gọi gần đây")
if metrics["recent_calls"]:
    st.dataframe(pd.DataFrame(metrics["recent_calls"]), use_container_width=True)
else:
    st.info("Chưa có bản ghi nhật ký lời gọi nào.")
