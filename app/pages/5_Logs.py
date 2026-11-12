"""Trang 5: Nhật ký quan sát cuộc gọi AI (Observability / Call logs)."""
import pandas as pd
import streamlit as st

from ielts_ai.config import get_settings
from ielts_ai.db.repo import list_llm_calls

st.set_page_config(page_title="Nhật ký hệ thống - IELTS AI", page_icon="📈", layout="wide")
st.header("📈 Bước 5: Nhật ký & Độ trễ mô hình (Observability)")

settings = get_settings()
calls = list_llm_calls(settings.db_path)

if not calls:
    st.info("Chưa có bản ghi nhật ký LLM call nào.")
    st.stop()

df = pd.DataFrame(calls)

col1, col2, col3 = st.columns(3)
total_calls = len(df)
avg_latency = df["latency_ms"].mean()
error_count = len(df[df["status"] != "ok"])
error_rate = (error_count / total_calls) * 100 if total_calls > 0 else 0.0

col1.metric("Tổng số cuộc gọi LLM", total_calls)
col2.metric("Độ trễ trung bình (ms)", f"{avg_latency:.1f} ms")
col3.metric("Tỷ lệ lỗi (%)", f"{error_rate:.1f}%")

st.subheader("Chi tiết từng cuộc gọi:")
st.dataframe(
    df[["id", "ts", "essay_id", "step", "latency_ms", "input_tokens", "output_tokens", "retries", "status", "error"]],
    use_container_width=True,
)
