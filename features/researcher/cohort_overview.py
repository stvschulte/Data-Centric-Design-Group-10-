"""
features/researcher/cohort_overview.py
=======================================
Tab 1: Cohort Overview - 队列概览。
回答：我们的研究对象是谁？数据覆盖了什么？
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .styles import get_plotly_layout, render_section_title, COLORS


def render(df: pd.DataFrame):
    """渲染 Cohort Overview tab。"""

    if df is None or len(df) == 0:
        st.info("No data to display.")
        return

    # === 上半：两个图并排 ===
    render_section_title(
        "Cohort Composition",
        "Who participated and what activities they logged.",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            '<div class="subsection-title">Activities per Participant</div>',
            unsafe_allow_html=True,
        )
        _render_per_participant_chart(df)

    with col2:
        st.markdown(
            '<div class="subsection-title">Activity Type Distribution</div>',
            unsafe_allow_html=True,
        )
        _render_activity_distribution(df)

    # === 中部：时间覆盖 ===
    render_section_title(
        "Data Coverage Over Time",
        "How are activities distributed across the study period?",
    )
    _render_timeline_heatmap(df)

    # === 下部：参与者画像表 ===
    render_section_title(
        "Participant Profiles",
        "Summary statistics per participant.",
    )
    _render_participant_table(df)

    # 原始数据导出
    with st.expander("🔍 View raw aggregated data"):
        st.dataframe(df, use_container_width=True, height=300)
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name="researcher_data.csv",
            mime="text/csv",
        )


def _render_per_participant_chart(df: pd.DataFrame):
    """每个参与者的活动数 + 活动类型分布（堆叠柱状图）。"""
    counts = (
        df.groupby(["participant_id", "activity_type"])
        .size()
        .reset_index(name="count")
    )

    fig = px.bar(
        counts,
        x="participant_id",
        y="count",
        color="activity_type",
        labels={"count": "Activities", "participant_id": "Participant"},
    )
    fig.update_layout(
        **get_plotly_layout(
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5),
            barmode="stack",
        )
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_activity_distribution(df: pd.DataFrame):
    """活动类型饼图。"""
    counts = df["activity_type"].value_counts().reset_index()
    counts.columns = ["activity", "count"]

    fig = px.pie(
        counts,
        values="count",
        names="activity",
        hole=0.5,
    )
    fig.update_traces(
        textposition="outside",
        textinfo="label+percent",
        textfont_color=COLORS["text_primary"],
    )
    fig.update_layout(
        **get_plotly_layout(
            height=380,
            showlegend=False,
        )
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_timeline_heatmap(df: pd.DataFrame):
    """时间轴热力图：参与者 × 日期 → 活动数量。"""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["date_str"] = df["date"].dt.strftime("%m-%d")

    pivot = (
        df.groupby(["participant_id", "date_str"])
        .size()
        .reset_index(name="count")
        .pivot(index="participant_id", columns="date_str", values="count")
        .fillna(0)
    )

    fig = px.imshow(
        pivot,
        labels=dict(x="Date", y="Participant", color="Activities"),
        color_continuous_scale=[
            [0.0, COLORS["bg_card"]],
            [0.3, "#FFB58A"],
            [1.0, COLORS["accent_primary"]],
        ],
        aspect="auto",
    )
    fig.update_layout(
        **get_plotly_layout(height=300),
        coloraxis_colorbar=dict(title="Count"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_participant_table(df: pd.DataFrame):
    """参与者画像汇总表。"""
    summary_dict = {
        "Activities": ("activity_type", "count"),
    }

    if "duration_min" in df.columns:
        summary_dict["Total minutes"] = ("duration_min", "sum")
        summary_dict["Avg duration (min)"] = ("duration_min", "mean")
    if "avg_heart_rate" in df.columns:
        summary_dict["Avg HR"] = ("avg_heart_rate", "mean")
    if "perceived_intensity" in df.columns:
        summary_dict["Avg intensity"] = ("perceived_intensity", "mean")
    if "music_energy" in df.columns:
        summary_dict["Avg music energy"] = ("music_energy", "mean")
    if "music_tempo" in df.columns:
        summary_dict["Avg BPM"] = ("music_tempo", "mean")

    summary = df.groupby("participant_id").agg(**summary_dict).round(1)

    # Most common activity
    top_activity = (
        df.groupby("participant_id")["activity_type"]
        .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "—")
        .rename("Top activity")
    )
    summary = summary.join(top_activity)

    st.dataframe(summary, use_container_width=True)
