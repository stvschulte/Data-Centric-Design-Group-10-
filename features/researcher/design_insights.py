"""
features/researcher/design_insights.py
=======================================
Tab 5: Design Insights - 设计原则汇总 + 推荐模拟器。
这是评审会的"杀器" tab：
  - 数据驱动的设计原则
  - 互动式推荐模拟器（拖滑块演示产品逻辑）
  - 导出洞察供 DCD log 使用
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from .styles import (
    get_plotly_layout,
    render_section_title,
    render_insight_card,
    COLORS,
)
from .data_loader import HR_ZONE_INFO
from .stats_utils import spearmanr


def render(df: pd.DataFrame):
    """渲染 Design Insights tab。"""

    if df is None or len(df) == 0:
        st.info("No data to display.")
        return

    # === 1. 自动生成的设计原则 ===
    render_section_title(
        "Data-Driven Design Principles",
        "Recommendations generated from the patterns in our data.",
    )
    principles = _generate_design_principles(df)
    for p in principles:
        render_insight_card(p["title"], p["body"], p.get("meta", ""))

    if len(principles) > 0:
        if st.button("📥 Export principles as Markdown"):
            md = "# Design Principles\n\n"
            for p in principles:
                md += f"## {p['title']}\n\n{p['body']}\n\n*{p.get('meta', '')}*\n\n"
            st.download_button(
                "Download principles.md",
                data=md,
                file_name="design_principles.md",
                mime="text/markdown",
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # === 2. 推荐模拟器（核心互动）===
    render_section_title(
        "Recommendation Simulator",
        "Adjust the user's current state to see how the system would recommend music.",
    )
    _render_recommendation_simulator(df)

    st.markdown("<br>", unsafe_allow_html=True)

    # === 3. Push vs Recover 策略对比 ===
    render_section_title(
        "Push vs Recover: Two Music Strategies",
        "What does the data say about music for each goal?",
    )
    _render_push_vs_recover(df)


def _generate_design_principles(df: pd.DataFrame) -> list:
    """根据数据自动生成设计原则。"""
    principles = []

    # 原则 1：HR Zone × 推荐 BPM 范围
    if "hr_zone" in df.columns and "music_tempo" in df.columns:
        zone_tempo = df.groupby("hr_zone")["music_tempo"].agg(["mean", "std", "count"])
        zone_tempo = zone_tempo[zone_tempo["count"] >= 2]
        if len(zone_tempo) > 0:
            lines = []
            for zone, row in zone_tempo.iterrows():
                lo = int(row["mean"] - row["std"]) if pd.notna(row["std"]) else int(row["mean"])
                hi = int(row["mean"] + row["std"]) if pd.notna(row["std"]) else int(row["mean"])
                zone_name = HR_ZONE_INFO.get(zone, {}).get("name", f"Zone {zone}")
                lines.append(
                    f"&nbsp;&nbsp;• <b>{zone_name}</b>: recommend BPM <b>{lo}–{hi}</b>"
                )
            principles.append(
                {
                    "title": "Tempo Recommendation by HR Zone",
                    "body": "<br>".join(lines),
                    "meta": "Based on ±1 standard deviation around observed mean BPM.",
                }
            )

    # 原则 2：HR Zone × 推荐 Energy 范围
    if "hr_zone" in df.columns and "music_energy" in df.columns:
        zone_energy = df.groupby("hr_zone")["music_energy"].agg(["mean", "std", "count"])
        zone_energy = zone_energy[zone_energy["count"] >= 2]
        if len(zone_energy) > 0:
            lines = []
            for zone, row in zone_energy.iterrows():
                lo = max(0, row["mean"] - row["std"]) if pd.notna(row["std"]) else row["mean"]
                hi = min(1, row["mean"] + row["std"]) if pd.notna(row["std"]) else row["mean"]
                zone_name = HR_ZONE_INFO.get(zone, {}).get("name", f"Zone {zone}")
                lines.append(
                    f"&nbsp;&nbsp;• <b>{zone_name}</b>: target energy <b>{lo:.2f}–{hi:.2f}</b>"
                )
            principles.append(
                {
                    "title": "Energy Targeting by HR Zone",
                    "body": "<br>".join(lines),
                    "meta": "Energy is a strong continuous proxy for arousal in music.",
                }
            )

    # 原则 3：活动类型 → 默认特征档案
    if "activity_type" in df.columns and "music_energy" in df.columns:
        act_summary = df.groupby("activity_type").agg(
            avg_energy=("music_energy", "mean"),
            avg_tempo=("music_tempo", "mean") if "music_tempo" in df.columns else ("music_energy", "mean"),
            n=("music_energy", "count"),
        ).round(2)
        act_summary = act_summary[act_summary["n"] >= 2]

        if len(act_summary) > 0:
            lines = []
            for act, row in act_summary.iterrows():
                lines.append(
                    f"&nbsp;&nbsp;• <b>{act}</b>: energy ≈ <b>{row['avg_energy']:.2f}</b>, "
                    f"BPM ≈ <b>{row['avg_tempo']:.0f}</b>"
                )
            principles.append(
                {
                    "title": "Activity-Specific Default Profiles",
                    "body": "<br>".join(lines),
                    "meta": "Use these as cold-start defaults before personalization kicks in.",
                }
            )

    # 原则 4：感知 vs 实际心率 → 信号选择
    if "perceived_intensity" in df.columns and "avg_heart_rate" in df.columns:
        valid = df.dropna(subset=["perceived_intensity", "avg_heart_rate"])
        if len(valid) > 10:
            try:
                r, p = spearmanr(
                    valid["perceived_intensity"], valid["avg_heart_rate"]
                )
                if p < 0.05:
                    if r > 0.6:
                        msg = (
                            f"Self-reported intensity and HR show strong agreement "
                            f"(ρ = {r:+.2f}). The product can fall back to self-report "
                            f"when HR data is unavailable."
                        )
                    elif r > 0.3:
                        msg = (
                            f"Self-report and HR are moderately correlated "
                            f"(ρ = {r:+.2f}). Combining both signals will improve "
                            f"recommendation accuracy."
                        )
                    else:
                        msg = (
                            f"Self-report and HR show weak agreement (ρ = {r:+.2f}). "
                            f"Prioritize HR data; treat self-report as supplementary."
                        )
                    principles.append(
                        {
                            "title": "Primary Signal Selection",
                            "body": msg,
                            "meta": f"Spearman ρ = {r:+.3f}, p = {p:.4f}, N = {len(valid)}",
                        }
                    )
            except Exception:
                pass

    return principles


def _render_recommendation_simulator(df: pd.DataFrame):
    """互动式推荐模拟器：输入用户当前状态，输出推荐音乐特征。"""

    st.markdown(
        '<div class="helper-text">'
        "Drag the sliders to simulate a user's current state. "
        "The recommendation is computed from observed patterns in our data."
        "</div>",
        unsafe_allow_html=True,
    )

    col_input, col_output = st.columns([1, 1])

    with col_input:
        st.markdown(
            '<div class="subsection-title">👤 Current User State</div>',
            unsafe_allow_html=True,
        )

        # HR 输入
        hr_min = int(df["avg_heart_rate"].min()) if "avg_heart_rate" in df.columns else 60
        hr_max = int(df["avg_heart_rate"].max()) if "avg_heart_rate" in df.columns else 180
        current_hr = st.slider(
            "Current Heart Rate (bpm)",
            min_value=hr_min,
            max_value=hr_max,
            value=(hr_min + hr_max) // 2,
            key="sim_hr",
        )

        # 活动类型
        activities = sorted(df["activity_type"].unique())
        current_activity = st.selectbox(
            "Current Activity",
            options=activities,
            key="sim_activity",
        )

        # 目标
        goal = st.radio(
            "Goal",
            options=["🔥 Push harder", "💤 Recover / cool down", "🎯 Maintain current state"],
            key="sim_goal",
        )

        # 求 HR Zone
        max_hr_estimate = df[df["activity_type"] == current_activity][
            "max_heart_rate"
        ].mean() if "max_heart_rate" in df.columns else 180
        if pd.isna(max_hr_estimate):
            max_hr_estimate = 180

        hr_pct = current_hr / max_hr_estimate
        if hr_pct < 0.6:
            current_zone = 1
        elif hr_pct < 0.7:
            current_zone = 2
        elif hr_pct < 0.8:
            current_zone = 3
        elif hr_pct < 0.9:
            current_zone = 4
        else:
            current_zone = 5

        zone_info = HR_ZONE_INFO.get(current_zone, {})
        zone_color = zone_info.get("color", COLORS["accent_primary"])

        st.markdown(
            f"""
            <div style='margin-top: 1rem;'>
                <span class='hr-zone-badge' style='background:{zone_color};'>
                    Current: Zone {current_zone} - {zone_info.get('name', '')}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_output:
        st.markdown(
            '<div class="subsection-title">🎵 Recommendation</div>',
            unsafe_allow_html=True,
        )

        # 决定目标 zone
        if "Push" in goal:
            target_zone = min(5, current_zone + 1)
            strategy = "Push"
        elif "Recover" in goal:
            target_zone = max(1, current_zone - 1)
            strategy = "Recover"
        else:
            target_zone = current_zone
            strategy = "Maintain"

        # 从数据中查同区间 + 同活动的歌曲特征
        candidates = df[df["hr_zone"] == target_zone]
        if "activity_type" in candidates.columns:
            activity_subset = candidates[candidates["activity_type"] == current_activity]
            if len(activity_subset) >= 2:
                candidates = activity_subset

        if len(candidates) == 0:
            st.warning("Not enough data for this combination — falling back to overall averages.")
            candidates = df

        rec_tempo = candidates["music_tempo"].mean() if "music_tempo" in candidates.columns else None
        rec_energy = candidates["music_energy"].mean() if "music_energy" in candidates.columns else None
        rec_valence = candidates["music_valence"].mean() if "music_valence" in candidates.columns else None
        rec_danceability = candidates["music_danceability"].mean() if "music_danceability" in candidates.columns else None

        tempo_range = (
            f"{int(rec_tempo - 10)}–{int(rec_tempo + 10)} BPM"
            if rec_tempo and not pd.isna(rec_tempo)
            else "—"
        )
        energy_range = (
            f"{max(0, rec_energy - 0.1):.2f}–{min(1, rec_energy + 0.1):.2f}"
            if rec_energy and not pd.isna(rec_energy)
            else "—"
        )
        valence_str = f"{rec_valence:.2f}" if rec_valence and not pd.isna(rec_valence) else "—"
        dance_str = (
            f"{rec_danceability:.2f}"
            if rec_danceability and not pd.isna(rec_danceability)
            else "—"
        )

        target_zone_name = HR_ZONE_INFO.get(target_zone, {}).get("name", f"Zone {target_zone}")
        target_zone_color = HR_ZONE_INFO.get(target_zone, {}).get("color", COLORS["accent_primary"])

        st.markdown(
            f"""
            <div class="rec-box">
                <div class="rec-title">{strategy} → {target_zone_name}</div>
                <div class="rec-row">
                    <span class="rec-label">Target Tempo</span>
                    <span class="rec-value">{tempo_range}</span>
                </div>
                <div class="rec-row">
                    <span class="rec-label">Target Energy</span>
                    <span class="rec-value">{energy_range}</span>
                </div>
                <div class="rec-row">
                    <span class="rec-label">Target Valence</span>
                    <span class="rec-value">{valence_str}</span>
                </div>
                <div class="rec-row">
                    <span class="rec-label">Target Danceability</span>
                    <span class="rec-value">{dance_str}</span>
                </div>
                <div class="rec-row" style="border-bottom: none;">
                    <span class="rec-label">Based on</span>
                    <span class="rec-value">{len(candidates)} similar sessions</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 显示几首匹配的"真实歌曲"（如果数据中有歌曲名）
        if "track_name" in candidates.columns:
            st.markdown(
                '<div class="subsection-title">Sample tracks fitting this profile</div>',
                unsafe_allow_html=True,
            )
            sample = candidates.dropna(subset=["track_name"]).head(5)
            for _, row in sample.iterrows():
                st.markdown(
                    f"- **{row['track_name']}** "
                    f"({row.get('music_tempo', 0):.0f} BPM, "
                    f"energy {row.get('music_energy', 0):.2f})"
                )


def _render_push_vs_recover(df: pd.DataFrame):
    """Push vs Recover 两种策略的音乐特征对比。"""
    if "hr_zone" not in df.columns:
        st.info("HR zone data missing.")
        return

    push_df = df[df["hr_zone"].isin([4, 5])]
    recover_df = df[df["hr_zone"].isin([1, 2])]

    if len(push_df) == 0 or len(recover_df) == 0:
        st.info("Need data in both high-intensity (Z4-5) and low-intensity (Z1-2) zones.")
        return

    features = [
        f for f in ["music_tempo", "music_energy", "music_valence", "music_danceability"]
        if f in df.columns
    ]

    comparison = []
    for feat in features:
        comparison.append({
            "feature": feat.replace("music_", "").title(),
            "Push (Z4-5)": push_df[feat].mean(),
            "Recover (Z1-2)": recover_df[feat].mean(),
        })

    comp_df = pd.DataFrame(comparison)

    # 归一化（对每个特征，把两个值缩放到 0-1）
    # 不归一化的话 tempo (BPM ~150) 会让其他特征 (0-1) 看不到
    plot_data = []
    for _, row in comp_df.iterrows():
        max_val = max(row["Push (Z4-5)"], row["Recover (Z1-2)"]) or 1
        plot_data.append({
            "feature": row["feature"],
            "strategy": "🔥 Push (Z4-5)",
            "value": row["Push (Z4-5)"],
            "normalized": row["Push (Z4-5)"] / max_val,
        })
        plot_data.append({
            "feature": row["feature"],
            "strategy": "💤 Recover (Z1-2)",
            "value": row["Recover (Z1-2)"],
            "normalized": row["Recover (Z1-2)"] / max_val,
        })

    plot_df = pd.DataFrame(plot_data)

    import plotly.express as px
    fig = px.bar(
        plot_df,
        x="feature",
        y="normalized",
        color="strategy",
        barmode="group",
        text="value",
        color_discrete_map={
            "🔥 Push (Z4-5)": COLORS["accent_primary"],
            "💤 Recover (Z1-2)": "#4DA8DA",
        },
        labels={
            "normalized": "Normalized value",
            "feature": "Music feature",
        },
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(
        **get_plotly_layout(
            height=420,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
            ),
        )
    )
    st.plotly_chart(fig, use_container_width=True)

    # 显示数值对比表
    with st.expander("📊 Exact values comparison"):
        display = comp_df.copy()
        display["Δ"] = display["Push (Z4-5)"] - display["Recover (Z1-2)"]
        st.dataframe(display.set_index("feature").round(2), use_container_width=True)
