"""
features/researcher/styles.py
==============================
Researcher Dashboard 的视觉样式。
匹配 data donation 页面的风格：
  - 深色背景 (#0e1117 / #1a1d24)
  - 橙红色强调 (#FF6B4A / #E84C3D) - 类似你们 active radio 颜色
  - 现代圆角卡片
  - 白色文本 + 灰色副文本
"""

import streamlit as st


# 主题色彩常量
COLORS = {
    "bg_primary": "#0e1117",
    "bg_secondary": "#1a1d24",
    "bg_card": "#1e2129",
    "accent_primary": "#FF6B4A",      # 橙红主色，对应你们的 active 状态
    "accent_secondary": "#E84C3D",    # 深一点的红橙
    "text_primary": "#FFFFFF",
    "text_secondary": "#9CA3AF",
    "border": "rgba(255, 255, 255, 0.08)",
    # 数据可视化用的色板（活动类型）
    "viz_palette": [
        "#FF6B4A",  # 橙红
        "#4DA8DA",  # 蓝
        "#4DDA8B",  # 绿
        "#F5C661",  # 黄
        "#B084F5",  # 紫
        "#F58FB3",  # 粉
    ],
    # HR Zone 渐变色（从冷到热）
    "hr_zones": [
        "#4DA8DA",  # Z1 蓝
        "#4DDA8B",  # Z2 绿
        "#F5C661",  # Z3 黄
        "#F58A4A",  # Z4 橙
        "#E84C3D",  # Z5 红
    ],
}


def apply_researcher_style():
    """注入 Researcher Dashboard 的 CSS。"""
    st.markdown(
        f"""
        <style>
            /* === Researcher Header === */
            .researcher-header {{
                padding: 1.5rem 0;
                margin-bottom: 1rem;
                border-bottom: 1px solid {COLORS["border"]};
            }}
            .researcher-header h1 {{
                color: {COLORS["text_primary"]};
                font-size: 2.4rem;
                font-weight: 700;
                margin: 0;
                letter-spacing: -0.5px;
            }}
            .researcher-header .subtitle {{
                color: {COLORS["text_secondary"]};
                font-size: 1.05rem;
                margin: 0.4rem 0 0 0;
            }}

            /* === Section Titles === */
            .section-title {{
                color: {COLORS["text_primary"]};
                font-size: 1.4rem;
                font-weight: 600;
                margin: 1.5rem 0 0.8rem 0;
                padding-left: 0.6rem;
                border-left: 3px solid {COLORS["accent_primary"]};
            }}
            .subsection-title {{
                color: {COLORS["text_primary"]};
                font-size: 1.1rem;
                font-weight: 600;
                margin: 1rem 0 0.6rem 0;
            }}
            .helper-text {{
                color: {COLORS["text_secondary"]};
                font-size: 0.9rem;
                margin-top: -0.4rem;
                margin-bottom: 0.6rem;
                font-style: italic;
            }}

            /* === Tabs === */
            .stTabs [data-baseweb="tab-list"] {{
                gap: 0.5rem;
                background: transparent;
                border-bottom: 1px solid {COLORS["border"]};
                padding-bottom: 0;
            }}
            .stTabs [data-baseweb="tab"] {{
                background: transparent;
                border-radius: 6px 6px 0 0;
                padding: 0.6rem 1.2rem;
                color: {COLORS["text_secondary"]};
                font-weight: 500;
                border: none;
            }}
            .stTabs [data-baseweb="tab"]:hover {{
                color: {COLORS["text_primary"]};
                background: rgba(255, 107, 74, 0.05);
            }}
            .stTabs [aria-selected="true"] {{
                color: {COLORS["accent_primary"]} !important;
                background: transparent !important;
                border-bottom: 2px solid {COLORS["accent_primary"]} !important;
            }}

            /* === Metric Cards === */
            [data-testid="stMetric"] {{
                background: {COLORS["bg_card"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 12px;
                padding: 1rem 1.2rem;
            }}
            [data-testid="stMetricLabel"] {{
                color: {COLORS["text_secondary"]} !important;
                font-size: 0.85rem !important;
            }}
            [data-testid="stMetricValue"] {{
                color: {COLORS["text_primary"]} !important;
                font-weight: 700 !important;
            }}

            /* === Insight Cards (自动洞察) === */
            .insight-card {{
                background: linear-gradient(
                    135deg,
                    rgba(255, 107, 74, 0.08) 0%,
                    rgba(255, 107, 74, 0.03) 100%
                );
                border-left: 3px solid {COLORS["accent_primary"]};
                padding: 1rem 1.2rem;
                margin: 0.6rem 0;
                border-radius: 8px;
            }}
            .insight-card .insight-title {{
                color: {COLORS["accent_primary"]};
                font-weight: 600;
                font-size: 0.95rem;
                margin-bottom: 0.3rem;
            }}
            .insight-card .insight-body {{
                color: {COLORS["text_primary"]};
                font-size: 0.95rem;
                line-height: 1.5;
            }}
            .insight-card .insight-meta {{
                color: {COLORS["text_secondary"]};
                font-size: 0.8rem;
                margin-top: 0.4rem;
                font-style: italic;
            }}

            /* === Quote Cards === */
            .quote-card {{
                background: {COLORS["bg_card"]};
                border-left: 3px solid {COLORS["accent_primary"]};
                padding: 0.9rem 1.1rem;
                margin: 0.5rem 0;
                border-radius: 6px;
            }}
            .quote-card .quote-text {{
                color: {COLORS["text_primary"]};
                font-style: italic;
                font-size: 0.95rem;
                margin: 0;
                line-height: 1.5;
            }}
            .quote-card .quote-meta {{
                color: {COLORS["text_secondary"]};
                font-size: 0.78rem;
                margin-top: 0.5rem;
            }}

            /* === Recommendation Box (Tab 5 模拟器) === */
            .rec-box {{
                background: linear-gradient(
                    135deg,
                    rgba(255, 107, 74, 0.15) 0%,
                    rgba(232, 76, 61, 0.08) 100%
                );
                border: 1px solid rgba(255, 107, 74, 0.3);
                border-radius: 12px;
                padding: 1.5rem;
                margin: 1rem 0;
            }}
            .rec-box .rec-title {{
                color: {COLORS["accent_primary"]};
                font-size: 1.2rem;
                font-weight: 700;
                margin-bottom: 1rem;
            }}
            .rec-box .rec-row {{
                display: flex;
                justify-content: space-between;
                padding: 0.4rem 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }}
            .rec-box .rec-label {{
                color: {COLORS["text_secondary"]};
                font-size: 0.9rem;
            }}
            .rec-box .rec-value {{
                color: {COLORS["text_primary"]};
                font-weight: 600;
                font-size: 0.95rem;
            }}

            /* === HR Zone Badge === */
            .hr-zone-badge {{
                display: inline-block;
                padding: 0.25rem 0.7rem;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 600;
                color: white;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_plotly_layout(height: int = 400, **kwargs) -> dict:
    """统一的 plotly layout，匹配深色主题。"""
    layout = dict(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text_primary"], family="sans-serif", size=12),
        height=height,
        margin=dict(l=40, r=20, t=40, b=40),
        colorway=COLORS["viz_palette"],
    )
    layout.update(kwargs)
    return layout


def render_insight_card(title: str, body: str, meta: str = ""):
    """渲染一个洞察卡片。"""
    meta_html = (
        f'<div class="insight-meta">{meta}</div>' if meta else ""
    )
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-title">📌 {title}</div>
            <div class="insight-body">{body}</div>
            {meta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(text: str, helper: str = ""):
    """渲染区块标题 + 可选辅助说明。"""
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)
    if helper:
        st.markdown(f'<div class="helper-text">{helper}</div>', unsafe_allow_html=True)
