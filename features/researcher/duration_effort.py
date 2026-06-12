"""
features/researcher/duration_effort.py
=======================================
Tab 3: Duration & Effort - 时长与感知强度。
关键问题：
  - 不同时长的运动用什么音乐？
  - 自报强度和实测心率匹配吗？
  - 感知强度 vs 音乐特征 的关系如何？
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from .styles import (
    get_plotly_layout,
    render_section_title,
    render_insight_card,
    COLORS,
)
from .stats_utils import add_ols_line, spearmanr


def render(df: pd.DataFrame):
    """渲染 Duration & Effort tab。"""

    if df is None or len(df) == 0:
        st.info("No data to display.")
        return

    # === 1. 时长 × 音乐特征 ===
    if "duration_min" in df.columns:
        render_section_title(
            "Duration × Music Characteristics",
            "How does music choice change with workout length?",
        )
        _render_duration_analysis(df)

    # === 2. 自报强度 vs 实测心率（一致性分析）===
    if "perceived_intensity" in df.columns and "avg_heart_rate" in df.columns:
        render_section_title(
            "Subjective vs Objective Effort",
            "Do self-reported intensity ratings match actual heart rate?",
        )
        _render_effort_hr_consistency(df)

    # === 3. 感知强度 × 音乐特征 ===
    if "perceived_intensity" in df.columns:
        render_section_title(
            "Perceived Effort × Music",
            "What music do people choose when they feel they're working hard?",
        )
        _render_effort_music(df)


def _render_duration_analysis(df: pd.DataFrame):
    """时长分组 × 音乐特征对比。"""
    df = df.copy()

    # 时长分桶
    df["duration_bucket"] = pd.cut(
        df["duration_min"],
        bins=[0, 20, 45, 75, 200],
        labels=["Short (<20m)", "Medium (20-45m)", "Long (45-75m)", "Very long (>75m)"],
    )

    available_features = [
        f for f in ["music_energy", "music_tempo", "music_valence"]
        if f in df.columns
    ]

    if len(available_features) == 0:
        st.info("No music features available.")
        return

    col_l, col_r = st.columns([1, 3])
    with col_l:
        feature = st.selectbox(
            "Music feature",
            options=available_features,
            format_func=lambda x: x.replace("music_", "").title(),
            key="de_duration_feature",
        )
        split_by_activity = st.checkbox(
            "Split by activity",
            value=True,
            key="de_duration_split",
        )

    with col_r:
        if split_by_activity:
            fig = px.box(
                df.dropna(subset=["duration_bucket"]),
                x="duration_bucket",
                y=feature,
                color="activity_type",
                points="outliers",
                labels={
                    feature: feature.replace("music_", "").title(),
                    "duration_bucket": "Duration",
                },
            )
        else:
            fig = px.box(
                df.dropna(subset=["duration_bucket"]),
                x="duration_bucket",
                y=feature,
                points="all",
                labels={
                    feature: feature.replace("music_", "").title(),
                    "duration_bucket": "Duration",
                },
                color_discrete_sequence=[COLORS["accent_primary"]],
            )

        fig.update_layout(**get_plotly_layout(height=400))
        st.plotly_chart(fig, use_container_width=True)


def _render_effort_hr_consistency(df: pd.DataFrame):
    """自报强度 vs 实测心率 - 一致性分析。"""
    valid = df.dropna(subset=["perceived_intensity", "avg_heart_rate"])

    if len(valid) < 5:
        st.info("Not enough data for consistency analysis.")
        return

    col_l, col_r = st.columns([2, 1])

    with col_l:
        fig = px.scatter(
            valid,
            x="perceived_intensity",
            y="avg_heart_rate",
            color="activity_type",
            size="duration_min" if "duration_min" in valid.columns else None,
            opacity=0.7,
            labels={
                "perceived_intensity": "Self-reported intensity (1-5)",
                "avg_heart_rate": "Avg Heart Rate (bpm)",
            },
        )
        add_ols_line(fig, valid, "perceived_intensity", "avg_heart_rate", COLORS["accent_primary"])
        fig.update_layout(**get_plotly_layout(height=400))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        # 计算 Spearman 等级相关（适合 5 点 likert × 连续）
        try:
            r, p = spearmanr(valid["perceived_intensity"], valid["avg_heart_rate"])
            st.metric("Spearman ρ", f"{r:+.3f}")
            st.metric("p-value", f"{p:.4f}")

            if p < 0.05 and r > 0.5:
                st.success(
                    "✅ Strong agreement between self-report and HR. "
                    "Either signal could power the product."
                )
            elif p < 0.05 and r > 0.3:
                st.info(
                    "ℹ️ Moderate agreement. Combining both signals likely improves robustness."
                )
            else:
                st.warning(
                    "⚠️ Weak agreement. Heart rate is preferred over self-report."
                )
        except Exception as e:
            st.warning(f"Could not compute correlation: {e}")

    # 显示每个 intensity 等级的 HR 分布
    st.markdown(
        '<div class="subsection-title">HR Distribution per Reported Intensity</div>',
        unsafe_allow_html=True,
    )
    fig = px.violin(
        valid,
        x="perceived_intensity",
        y="avg_heart_rate",
        color="perceived_intensity",
        box=True,
        points="all",
        color_discrete_sequence=COLORS["hr_zones"],
        labels={
            "perceived_intensity": "Self-reported intensity",
            "avg_heart_rate": "Avg Heart Rate (bpm)",
        },
    )
    fig.update_layout(**get_plotly_layout(height=400, showlegend=False))
    st.plotly_chart(fig, use_container_width=True)


def _render_effort_music(df: pd.DataFrame):
    """感知强度 × 音乐特征。"""
    available_features = [
        f for f in ["music_energy", "music_tempo", "music_valence", "music_danceability"]
        if f in df.columns
    ]

    if len(available_features) == 0:
        st.info("No music features available.")
        return

    # 显示所有特征的趋势（小倍数图）
    intensity_summary = (
        df.groupby("perceived_intensity")[available_features].mean().reset_index()
    )

    # 归一化以便在同一图中显示
    melted = []
    for feat in available_features:
        if feat in intensity_summary.columns:
            vals = intensity_summary[feat]
            normalized = (vals - vals.min()) / (vals.max() - vals.min() + 1e-9)
            for idx, row in intensity_summary.iterrows():
                melted.append({
                    "intensity": row["perceived_intensity"],
                    "feature": feat.replace("music_", "").title(),
                    "value": row[feat],
                    "normalized": normalized.iloc[idx],
                })

    melted_df = pd.DataFrame(melted)

    fig = px.line(
        melted_df,
        x="intensity",
        y="normalized",
        color="feature",
        markers=True,
        labels={
            "intensity": "Perceived Intensity (1-5)",
            "normalized": "Normalized value (0-1)",
            "feature": "Music feature",
        },
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=10))
    fig.update_layout(**get_plotly_layout(height=400))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div class="helper-text">'
        "💡 Lines are normalized so you can compare trends across features with different scales. "
        "Hover for raw values."
        "</div>",
        unsafe_allow_html=True,
    )

    # 显示原始平均值表
    with st.expander("📊 Raw average values by intensity"):
        st.dataframe(
            intensity_summary.set_index("perceived_intensity").round(2),
            use_container_width=True,
        )
