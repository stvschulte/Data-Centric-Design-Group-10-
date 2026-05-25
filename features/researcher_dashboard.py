"""
features/researcher_dashboard.py
=================================
Researcher Dashboard 主入口。
包含 5 个 Tab：
  1. Cohort Overview      - 队列概览
  2. Music × Heart Rate   - 音乐与心率（核心）
  3. Duration & Effort    - 时长与感知强度
  4. Text & Emotion       - 文本与情绪
  5. Design Insights      - 设计洞察 + 推荐模拟器

与 features/researcher/ 子模块协作，每个 tab 一个文件。
"""

import streamlit as st
import pandas as pd
from pathlib import Path

# 导入各个 tab 模块
from features.researcher import (
    cohort_overview,
    music_heart_rate,
    duration_effort,
    text_emotion,
    design_insights,
)
from features.researcher.styles import apply_researcher_style
from features.researcher.data_loader import load_aggregated_data


def render_researcher_dashboard():
    """主入口函数。从 app.py 中调用。"""

    # 应用样式
    apply_researcher_style()

    # 标题区
    st.markdown(
        """
        <div class="researcher-header">
            <h1>🔬 Researcher Dashboard</h1>
            <p class="subtitle">
                Cross-participant analysis of music × physical activity patterns.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 加载数据
    df = load_aggregated_data()

    if df is None or len(df) == 0:
        st.warning(
            "⚠️ No participant data available yet. "
            "Once participants upload their Spotify and Strava files, "
            "their aggregated data will appear here."
        )
        with st.expander("ℹ️ Demo mode: load sample data"):
            if st.button("Load sample data for demonstration"):
                from features.researcher.data_loader import generate_sample_data
                st.session_state["researcher_sample_data"] = generate_sample_data()
                st.rerun()
        if "researcher_sample_data" in st.session_state:
            df = st.session_state["researcher_sample_data"]
            st.info("🧪 Currently showing sample (synthetic) data for demonstration.")
        else:
            return

    # 全局筛选器（侧边栏右侧）
    filtered_df = _render_global_filters(df)

    # 顶部 KPI 卡片
    _render_top_kpis(filtered_df)

    st.markdown("<br>", unsafe_allow_html=True)

    # 5 个 Tab
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📊  Cohort Overview",
            "🎵  Music × Heart Rate",
            "⏱️  Duration & Effort",
            "💬  Text & Emotion",
            "💡  Design Insights",
        ]
    )

    with tab1:
        cohort_overview.render(filtered_df)

    with tab2:
        music_heart_rate.render(filtered_df)

    with tab3:
        duration_effort.render(filtered_df)

    with tab4:
        text_emotion.render(filtered_df)

    with tab5:
        design_insights.render(filtered_df)


def _render_global_filters(df: pd.DataFrame) -> pd.DataFrame:
    """渲染全局筛选器，返回筛选后的数据。"""
    with st.expander("🎛️  Global Filters", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            participants = sorted(df["participant_id"].unique())
            selected_p = st.multiselect(
                "Participants",
                options=participants,
                default=participants,
                key="filter_participants",
            )

        with col2:
            activities = sorted(df["activity_type"].dropna().unique())
            selected_a = st.multiselect(
                "Activity Types",
                options=activities,
                default=activities,
                key="filter_activities",
            )

        with col3:
            if "perceived_intensity" in df.columns:
                intensity_range = st.slider(
                    "Perceived Intensity",
                    min_value=1,
                    max_value=5,
                    value=(1, 5),
                    key="filter_intensity",
                )
            else:
                intensity_range = (1, 5)

    # 应用筛选
    filtered = df[
        (df["participant_id"].isin(selected_p))
        & (df["activity_type"].isin(selected_a))
    ].copy()

    if "perceived_intensity" in filtered.columns:
        filtered = filtered[
            (filtered["perceived_intensity"] >= intensity_range[0])
            & (filtered["perceived_intensity"] <= intensity_range[1])
        ]

    return filtered


def _render_top_kpis(df: pd.DataFrame):
    """顶部 KPI 卡片。"""
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Participants", df["participant_id"].nunique())
    with col2:
        st.metric("Activities", len(df))
    with col3:
        if "avg_heart_rate" in df.columns:
            st.metric("Avg HR", f"{df['avg_heart_rate'].mean():.0f} bpm")
        else:
            st.metric("Avg HR", "—")
    with col4:
        if "music_energy" in df.columns:
            st.metric("Avg Energy", f"{df['music_energy'].mean():.2f}")
        else:
            st.metric("Avg Energy", "—")
    with col5:
        if "music_tempo" in df.columns:
            st.metric("Avg BPM", f"{df['music_tempo'].mean():.0f}")
        else:
            st.metric("Avg BPM", "—")
