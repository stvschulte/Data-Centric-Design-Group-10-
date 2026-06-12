"""
features/researcher/text_emotion.py
====================================
Tab 4: Text & Emotion - 文本情感 + 视觉疲劳分析。

文本数据：VADER 情感分析（用户备注、访谈文本）
视觉数据：FER 疲劳分数（如果有照片上传）
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
from .stats_utils import add_ols_line

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False


SENTIMENT_COLORS = {
    "Positive": "#4DDA8B",
    "Neutral": "#9CA3AF",
    "Negative": "#E84C3D",
}


def render(df: pd.DataFrame):
    """渲染 Text & Emotion tab。"""

    if df is None or len(df) == 0:
        st.info("No data to display.")
        return

    has_text = "notes" in df.columns and df["notes"].notna().any()
    has_fer = (
        "fer_fatigue_score" in df.columns and df["fer_fatigue_score"].notna().any()
    )

    if not has_text and not has_fer:
        st.warning(
            "⚠️ No text or FER data available. "
            "Make sure participants provided notes or uploaded photos."
        )
        return

    # === VADER 文本分析 ===
    if has_text:
        if not VADER_AVAILABLE:
            st.error(
                "⚠️ VADER not installed. Run: `pip install vaderSentiment`"
            )
        else:
            _render_text_section(df)

    # === FER 视觉疲劳分析 ===
    if has_fer:
        st.markdown("<br>", unsafe_allow_html=True)
        _render_fer_section(df)

    # === 多模态融合（如果两者都有）===
    if has_text and has_fer and VADER_AVAILABLE:
        st.markdown("<br>", unsafe_allow_html=True)
        _render_multimodal_section(df)


def _analyze_sentiments(df: pd.DataFrame) -> pd.DataFrame:
    """对 notes 做 VADER 分析，返回带情感列的 df。"""
    analyzer = SentimentIntensityAnalyzer()

    def get_compound(text):
        if pd.isna(text) or text == "":
            return None
        return analyzer.polarity_scores(str(text))["compound"]

    def classify(score):
        if pd.isna(score):
            return None
        if score >= 0.05:
            return "Positive"
        if score <= -0.05:
            return "Negative"
        return "Neutral"

    out = df.copy()
    out["compound"] = out["notes"].apply(get_compound)
    out["sentiment"] = out["compound"].apply(classify)
    return out


def _render_text_section(df: pd.DataFrame):
    """文本 VADER 情感分析模块。"""
    render_section_title(
        "Text Sentiment Analysis (VADER)",
        "Sentiment analysis of participant notes about their workouts.",
    )

    text_df = _analyze_sentiments(df)
    text_df = text_df.dropna(subset=["compound", "notes"])
    text_df = text_df[text_df["notes"].str.strip() != ""]

    if len(text_df) == 0:
        st.info("No text data after cleaning.")
        return

    # KPI
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total texts", len(text_df))
    with c2:
        st.metric("Avg sentiment", f"{text_df['compound'].mean():+.2f}")
    with c3:
        pos_pct = (text_df["sentiment"] == "Positive").mean() * 100
        st.metric("Positive", f"{pos_pct:.0f}%")
    with c4:
        neg_pct = (text_df["sentiment"] == "Negative").mean() * 100
        st.metric("Negative", f"{neg_pct:.0f}%")

    # 两列：饼图 + 强度对比
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(
            '<div class="subsection-title">Sentiment Distribution</div>',
            unsafe_allow_html=True,
        )
        s_counts = text_df["sentiment"].value_counts().reset_index()
        s_counts.columns = ["sentiment", "count"]
        fig = px.pie(
            s_counts,
            values="count",
            names="sentiment",
            hole=0.5,
            color="sentiment",
            color_discrete_map=SENTIMENT_COLORS,
        )
        fig.update_traces(textinfo="label+percent")
        fig.update_layout(**get_plotly_layout(height=340, showlegend=False))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        if "perceived_intensity" in text_df.columns:
            st.markdown(
                '<div class="subsection-title">Sentiment vs Intensity</div>',
                unsafe_allow_html=True,
            )
            fig = px.box(
                text_df,
                x="perceived_intensity",
                y="compound",
                points="all",
                color="perceived_intensity",
                color_discrete_sequence=COLORS["hr_zones"],
                labels={
                    "perceived_intensity": "Perceived Intensity",
                    "compound": "VADER compound score",
                },
            )
            fig.update_layout(
                **get_plotly_layout(height=340, showlegend=False)
            )
            st.plotly_chart(fig, use_container_width=True)

    # 按活动类型的情感
    st.markdown(
        '<div class="subsection-title">Sentiment by Activity Type</div>',
        unsafe_allow_html=True,
    )
    activity_sent = (
        text_df.groupby("activity_type")
        .agg(avg_sentiment=("compound", "mean"), count=("notes", "count"))
        .reset_index()
        .sort_values("avg_sentiment", ascending=False)
    )

    fig = px.bar(
        activity_sent,
        x="activity_type",
        y="avg_sentiment",
        color="avg_sentiment",
        color_continuous_scale=[
            [0.0, SENTIMENT_COLORS["Negative"]],
            [0.5, SENTIMENT_COLORS["Neutral"]],
            [1.0, SENTIMENT_COLORS["Positive"]],
        ],
        text="count",
        labels={
            "avg_sentiment": "Average sentiment",
            "activity_type": "Activity",
            "count": "N",
        },
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(**get_plotly_layout(height=380), coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    # Quote browser
    st.markdown(
        '<div class="subsection-title">Quote Browser</div>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns([1, 3])
    with col1:
        s_filter = st.selectbox(
            "Sentiment",
            ["All", "Positive", "Neutral", "Negative"],
            key="te_quote_filter",
        )
    with col2:
        search = st.text_input("Search in quotes", "", key="te_quote_search")

    display = text_df.copy()
    if s_filter != "All":
        display = display[display["sentiment"] == s_filter]
    if search:
        display = display[
            display["notes"].str.contains(search, case=False, na=False)
        ]

    st.caption(f"Showing {len(display)} matching quotes")

    for _, row in display.head(8).iterrows():
        color = SENTIMENT_COLORS.get(row["sentiment"], COLORS["accent_primary"])
        intensity_str = (
            f"Intensity {row['perceived_intensity']}/5"
            if "perceived_intensity" in row and pd.notna(row.get("perceived_intensity"))
            else ""
        )
        st.markdown(
            f"""
            <div class="quote-card" style="border-left-color: {color};">
                <p class="quote-text">"{row['notes']}"</p>
                <p class="quote-meta">
                    — {row['participant_id']} · {row.get('activity_type', '')}
                    · {intensity_str} ·
                    <strong style='color: {color};'>{row['sentiment']}</strong>
                    ({row['compound']:+.2f})
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if len(display) > 8:
        st.info(f"Showing first 8 of {len(display)} — refine filters to narrow down.")

    # 局限性说明
    with st.expander("⚠️ About VADER limitations"):
        st.markdown(
            """
            VADER was built for social media text and may misread fitness-specific slang:
            - "I **crushed** it" → VADER may classify as negative (actually positive)
            - "**Burning** sensation" → workout context is good; VADER may say negative
            - "**Killed** the workout" → positive in context

            **Our mitigation:** Use VADER for **relative trends** (e.g., low vs high intensity)
            rather than absolute labels. We also manually validated a sample of texts.
            """
        )


def _render_fer_section(df: pd.DataFrame):
    """FER 视觉疲劳分析模块。"""
    render_section_title(
        "Visual Fatigue Analysis (FER)",
        "Fatigue scores extracted from post-workout photos via facial expression recognition.",
    )

    fer_df = df.dropna(subset=["fer_fatigue_score"])

    if len(fer_df) == 0:
        st.info("No FER data after filtering.")
        return

    # KPI
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Photos analyzed", len(fer_df))
    with c2:
        st.metric("Avg fatigue score", f"{fer_df['fer_fatigue_score'].mean():.1f} / 10")
    with c3:
        high = (fer_df["fer_fatigue_score"] >= 7).sum()
        st.metric("High-fatigue sessions", high)

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(
            '<div class="subsection-title">FER Fatigue vs HR</div>',
            unsafe_allow_html=True,
        )
        if "avg_heart_rate" in fer_df.columns:
            fig = px.scatter(
                fer_df,
                x="avg_heart_rate",
                y="fer_fatigue_score",
                color="activity_type",
                opacity=0.7,
                labels={
                    "avg_heart_rate": "Avg Heart Rate (bpm)",
                    "fer_fatigue_score": "FER Fatigue Score (0-10)",
                },
            )
            add_ols_line(fig, fer_df, "avg_heart_rate", "fer_fatigue_score", COLORS["accent_primary"])
            fig.update_layout(**get_plotly_layout(height=380))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("HR data missing.")

    with col_r:
        st.markdown(
            '<div class="subsection-title">FER vs Self-Reported Effort</div>',
            unsafe_allow_html=True,
        )
        if "perceived_intensity" in fer_df.columns:
            fig = px.box(
                fer_df,
                x="perceived_intensity",
                y="fer_fatigue_score",
                color="perceived_intensity",
                points="all",
                color_discrete_sequence=COLORS["hr_zones"],
                labels={
                    "perceived_intensity": "Self-reported intensity",
                    "fer_fatigue_score": "FER Fatigue (0-10)",
                },
            )
            fig.update_layout(
                **get_plotly_layout(height=380, showlegend=False)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Intensity data missing.")


def _render_multimodal_section(df: pd.DataFrame):
    """三种数据融合视图。"""
    render_section_title(
        "Multimodal Story Browser",
        "All four data types (HR + music + text + visual) for a single workout.",
    )

    text_df = _analyze_sentiments(df)

    # 选一次运动
    text_df = text_df.dropna(subset=["compound"])
    text_df["session_label"] = (
        text_df["participant_id"].astype(str)
        + " · "
        + text_df["date"].astype(str).str.slice(0, 10)
        + " · "
        + text_df["activity_type"].astype(str)
    )

    if len(text_df) == 0:
        st.info("No complete sessions to show.")
        return

    selected = st.selectbox(
        "Select a session",
        options=text_df["session_label"].tolist(),
        key="te_multimodal_select",
    )

    row = text_df[text_df["session_label"] == selected].iloc[0]

    # 4 列布局
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="insight-card">
                <div class="insight-title">⏱️ Physical</div>
                <div class="insight-body">
                HR: <b>{int(row.get('avg_heart_rate', 0)) if pd.notna(row.get('avg_heart_rate')) else '—'}</b> bpm<br>
                Zone: <b>Z{int(row.get('hr_zone', 0)) if pd.notna(row.get('hr_zone')) else '—'}</b><br>
                Duration: <b>{int(row.get('duration_min', 0))} min</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="insight-card">
                <div class="insight-title">🎵 Music</div>
                <div class="insight-body">
                Tempo: <b>{int(row.get('music_tempo', 0)) if pd.notna(row.get('music_tempo')) else '—'}</b> BPM<br>
                Energy: <b>{row.get('music_energy', 0):.2f}</b><br>
                Valence: <b>{row.get('music_valence', 0):.2f}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        sent_color = SENTIMENT_COLORS.get(row["sentiment"], "#888")
        st.markdown(
            f"""
            <div class="insight-card">
                <div class="insight-title">💬 Text</div>
                <div class="insight-body">
                Sentiment: <b style='color:{sent_color}'>{row['sentiment']}</b><br>
                Score: <b>{row['compound']:+.2f}</b><br>
                <i>"{row['notes'][:60]}..."</i>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        fer_val = row.get("fer_fatigue_score")
        fer_display = f"{fer_val:.1f} / 10" if pd.notna(fer_val) else "—"
        st.markdown(
            f"""
            <div class="insight-card">
                <div class="insight-title">📸 Visual (FER)</div>
                <div class="insight-body">
                Fatigue: <b>{fer_display}</b><br>
                Reported: <b>{int(row.get('perceived_intensity', 0)) if pd.notna(row.get('perceived_intensity')) else '—'} / 5</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
