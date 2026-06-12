"""
features/researcher/music_heart_rate.py
========================================
Tab 2: Music × Heart Rate - 核心分析。
直接回答 Main RQ:
"How can a connected product create music suggestion
 to push user into higher HR zone or guide them into recover?"
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
from .data_loader import HR_ZONE_INFO
from .stats_utils import add_ols_line, pearsonr


# 用于分析的 5 个音乐特征
MUSIC_FEATURES = [
    "music_tempo",
    "music_energy",
    "music_valence",
    "music_danceability",
    "music_loudness",
]

FEATURE_LABELS = {
    "music_tempo": "Tempo (BPM)",
    "music_energy": "Energy",
    "music_valence": "Valence",
    "music_danceability": "Danceability",
    "music_loudness": "Loudness (dB)",
}


def render(df: pd.DataFrame):
    """渲染 Music × Heart Rate tab。"""

    if df is None or len(df) == 0:
        st.info("No data to display.")
        return

    if "avg_heart_rate" not in df.columns:
        st.warning("⚠️ No heart rate data available in current dataset.")
        return

    # === 1. HR Zone × Music Features 热力图（核心图）===
    render_section_title(
        "Heart Rate Zones × Music Characteristics",
        "Mean value of each music feature within each HR zone (normalized for comparison).",
    )
    _render_hr_zone_heatmap(df)

    # === 2. 箱线图：每个特征在不同 zone 的分布 ===
    render_section_title(
        "Feature Distribution by HR Zone",
        "Select a music feature to see its distribution across heart rate zones.",
    )
    _render_feature_by_zone_boxplot(df)

    # === 3. 连续相关：HR × Music Feature 散点 ===
    render_section_title(
        "Continuous Relationship: HR ↔ Music",
        "Direct correlation between heart rate and music characteristics.",
    )
    _render_hr_music_scatter(df)

    # === 4. 自动洞察 ===
    render_section_title(
        "Automated Findings",
        "Statistical insights generated from the current filtered data.",
    )
    _render_auto_insights(df)


def _render_hr_zone_heatmap(df: pd.DataFrame):
    """HR Zone × 音乐特征 的归一化热力图。"""
    if "hr_zone" not in df.columns:
        st.warning("HR Zone column missing.")
        return

    available = [f for f in MUSIC_FEATURES if f in df.columns]
    if len(available) == 0:
        st.warning("No music feature columns found.")
        return

    # 按 zone 聚合
    zone_means = df.groupby("hr_zone")[available].mean()
    zone_means = zone_means.reindex(sorted(zone_means.index))

    # 归一化（每列 0-1）以便对比不同尺度的特征
    normalized = (zone_means - zone_means.min()) / (
        zone_means.max() - zone_means.min() + 1e-9
    )

    # 显示原始值（hover）+ 归一化颜色
    hover_text = []
    for zone in normalized.index:
        row_text = []
        for feat in normalized.columns:
            raw_val = zone_means.loc[zone, feat]
            row_text.append(
                f"Zone {zone}<br>{FEATURE_LABELS.get(feat, feat)}<br>"
                f"<b>{raw_val:.2f}</b>"
            )
        hover_text.append(row_text)

    fig = go.Figure(
        data=go.Heatmap(
            z=normalized.values,
            x=[FEATURE_LABELS.get(f, f) for f in normalized.columns],
            y=[
                f"Zone {z} - {HR_ZONE_INFO.get(z, {}).get('name', '')}"
                for z in normalized.index
            ],
            text=zone_means.round(2).values,
            texttemplate="%{text}",
            textfont={"color": COLORS["text_primary"], "size": 12},
            hovertext=hover_text,
            hoverinfo="text",
            colorscale=[
                [0.0, "#1a1d24"],
                [0.5, "#F58A4A"],
                [1.0, COLORS["accent_primary"]],
            ],
            showscale=True,
            colorbar=dict(title="Normalized"),
        )
    )
    fig.update_layout(**get_plotly_layout(height=400))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div class="helper-text">'
        "💡 Reading: darker orange = higher feature value within that HR zone. "
        "Numbers shown are the raw averages."
        "</div>",
        unsafe_allow_html=True,
    )


def _render_feature_by_zone_boxplot(df: pd.DataFrame):
    """选定特征的箱线图（按 HR zone 分组）。"""
    available = [f for f in MUSIC_FEATURES if f in df.columns]
    if len(available) == 0:
        return

    col_l, col_r = st.columns([1, 3])
    with col_l:
        feature = st.selectbox(
            "Music feature",
            options=available,
            format_func=lambda x: FEATURE_LABELS.get(x, x),
            key="mhr_boxplot_feature",
        )

    with col_r:
        # 把 HR Zone 变成 categorical 以保持顺序
        plot_df = df.copy()
        plot_df["hr_zone_str"] = plot_df["hr_zone"].apply(
            lambda z: f"Z{z}"
        )

        fig = px.box(
            plot_df,
            x="hr_zone_str",
            y=feature,
            color="hr_zone_str",
            points="all",
            color_discrete_sequence=COLORS["hr_zones"],
            category_orders={"hr_zone_str": ["Z1", "Z2", "Z3", "Z4", "Z5"]},
            labels={
                feature: FEATURE_LABELS.get(feature, feature),
                "hr_zone_str": "HR Zone",
            },
        )
        fig.update_layout(
            **get_plotly_layout(height=380, showlegend=False),
        )
        st.plotly_chart(fig, use_container_width=True)


def _render_hr_music_scatter(df: pd.DataFrame):
    """HR vs 音乐特征的散点图 + 趋势线。"""
    available = [f for f in MUSIC_FEATURES if f in df.columns]
    if len(available) == 0:
        return

    col1, col2 = st.columns(2)
    with col1:
        feature = st.selectbox(
            "Music feature (Y axis)",
            options=available,
            index=1 if len(available) > 1 else 0,  # 默认 energy
            format_func=lambda x: FEATURE_LABELS.get(x, x),
            key="mhr_scatter_feature",
        )
    with col2:
        color_by = st.selectbox(
            "Color by",
            options=["activity_type", "participant_id"],
            key="mhr_scatter_color",
        )

    fig = px.scatter(
        df,
        x="avg_heart_rate",
        y=feature,
        color=color_by,
        hover_data=[
            c for c in ["participant_id", "activity_type", "duration_min"] if c in df.columns
        ],
        opacity=0.65,
        labels={
            "avg_heart_rate": "Avg Heart Rate (bpm)",
            feature: FEATURE_LABELS.get(feature, feature),
        },
    )
    add_ols_line(fig, df, "avg_heart_rate", feature, COLORS["accent_primary"])
    fig.update_layout(**get_plotly_layout(height=450))
    st.plotly_chart(fig, use_container_width=True)

    # 显示统计结果
    if len(df) > 3:
        try:
            valid = df[["avg_heart_rate", feature]].dropna()
            if len(valid) > 3:
                r, p = pearsonr(valid["avg_heart_rate"], valid[feature])
                sig_emoji = "🟢" if p < 0.05 else "🟡" if p < 0.1 else "🔴"

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Pearson r", f"{r:+.3f}")
                with c2:
                    st.metric("p-value", f"{p:.4f}")
                with c3:
                    sig = "Significant" if p < 0.05 else "Not significant"
                    st.metric("Status", f"{sig_emoji} {sig}")
        except Exception:
            pass


def _render_auto_insights(df: pd.DataFrame):
    """根据数据自动生成洞察。"""
    insights = []

    # 洞察 1：HR ↔ 各音乐特征的相关性
    for feature in MUSIC_FEATURES:
        if feature in df.columns:
            valid = df[["avg_heart_rate", feature]].dropna()
            if len(valid) > 10:
                try:
                    r, p = pearsonr(valid["avg_heart_rate"], valid[feature])
                    if p < 0.05 and abs(r) > 0.2:
                        direction = "increases" if r > 0 else "decreases"
                        insights.append(
                            {
                                "title": f"HR ↔ {FEATURE_LABELS.get(feature, feature)}",
                                "body": (
                                    f"As heart rate rises, "
                                    f"<b>{FEATURE_LABELS.get(feature, feature)}</b> "
                                    f"{direction} significantly."
                                ),
                                "meta": f"Pearson r = {r:+.2f}, p = {p:.4f}, N = {len(valid)}",
                            }
                        )
                except Exception:
                    pass

    # 洞察 2：Zone 1 vs Zone 5 的音乐特征对比
    if "hr_zone" in df.columns:
        z1 = df[df["hr_zone"] == 1]
        z5 = df[df["hr_zone"] == 5]

        if len(z1) >= 3 and len(z5) >= 3:
            if "music_energy" in df.columns:
                e1 = z1["music_energy"].mean()
                e5 = z5["music_energy"].mean()
                if not (pd.isna(e1) or pd.isna(e5)):
                    insights.append(
                        {
                            "title": "Recovery vs Peak Music Energy",
                            "body": (
                                f"Music energy in <b>Zone 1 (recovery)</b> averages "
                                f"<b>{e1:.2f}</b>, while in <b>Zone 5 (peak)</b> it averages "
                                f"<b>{e5:.2f}</b> — a {((e5-e1)/max(e1,0.01)*100):.0f}% increase."
                            ),
                            "meta": f"N(Z1) = {len(z1)}, N(Z5) = {len(z5)}",
                        }
                    )

            if "music_tempo" in df.columns:
                t1 = z1["music_tempo"].mean()
                t5 = z5["music_tempo"].mean()
                if not (pd.isna(t1) or pd.isna(t5)):
                    insights.append(
                        {
                            "title": "Recovery vs Peak BPM",
                            "body": (
                                f"Average tempo in <b>Zone 1</b> is <b>{t1:.0f} BPM</b>, "
                                f"in <b>Zone 5</b> is <b>{t5:.0f} BPM</b> "
                                f"(Δ = {t5-t1:+.0f} BPM)."
                            ),
                            "meta": "Suggests BPM is a strong candidate signal for adaptive recommendation.",
                        }
                    )

    # 洞察 3：最高强度活动类型
    if "music_energy" in df.columns:
        try:
            top_activity_grp = df.groupby("activity_type")["music_energy"].mean()
            top = top_activity_grp.idxmax()
            top_val = top_activity_grp.max()
            insights.append(
                {
                    "title": "Highest Energy Activity",
                    "body": (
                        f"Participants listen to the highest-energy music during "
                        f"<b>{top}</b> sessions (avg energy = <b>{top_val:.2f}</b>)."
                    ),
                    "meta": "Useful for activity-specific playlist defaults.",
                }
            )
        except Exception:
            pass

    if len(insights) == 0:
        st.info("Not enough data variation to generate insights yet.")
        return

    for ins in insights:
        render_insight_card(ins["title"], ins["body"], ins.get("meta", ""))
