import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db_handler import log_strava_upload


STRAVA_ORANGE = "#FC4C02"
REQUIRED_STRAVA_COLUMNS = ["Activity Date", "Elapsed Time", "Activity Name", "Activity Type"]


def inject_strava_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                linear-gradient(90deg, rgba(255,255,255,0.98), rgba(255,247,242,0.94)),
                url("https://images.unsplash.com/photo-1502904550040-7534597429ae?auto=format&fit=crop&w=1800&q=80");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #18181b;
        }}
        .strava-hero {{
            min-height: 250px;
            padding: 56px 54px;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(252,76,2,0.18), rgba(255,255,255,0.88));
            border: 1px solid rgba(252,76,2,0.34);
            box-shadow: 0 24px 80px rgba(35,24,18,0.18);
            margin-bottom: 28px;
        }}
        .strava-hero h1 {{
            margin: 0;
            color: #111827;
            font-size: 52px;
            font-weight: 850;
            letter-spacing: 0;
        }}
        .strava-hero p {{
            max-width: 760px;
            color: #3f3f46;
            font-size: 18px;
            line-height: 1.6;
        }}
        div[data-testid="stMetric"] {{
            background: rgba(255,255,255,0.94);
            border: 1px solid rgba(252,76,2,0.25);
            border-radius: 14px;
            padding: 18px;
            box-shadow: 0 10px 32px rgba(17,24,39,0.08);
        }}
        div[data-testid="stMetricValue"] {{
            color: {STRAVA_ORANGE};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def parse_strava_csv(uploaded_files) -> pd.DataFrame:
    """Parse Strava CSV using the exact columns required by the project.

    Expected source columns:
    - Activity Date: workout start timestamp
    - Elapsed Time: workout duration in seconds
    - Activity Name: display name
    - Activity Type: workout category
    """
    frames = []
    for uploaded_file in uploaded_files:
        try:
            frames.append(pd.read_csv(uploaded_file))
        except Exception as exc:
            st.error(f"Could not read `{uploaded_file.name}` as CSV: {exc}")

    if not frames:
        return pd.DataFrame(columns=REQUIRED_STRAVA_COLUMNS)

    raw_df = pd.concat(frames, ignore_index=True)
    raw_df.columns = [str(column).replace("\ufeff", "").strip() for column in raw_df.columns]
    missing = [column for column in REQUIRED_STRAVA_COLUMNS if column not in raw_df.columns]
    if missing:
        st.error(f"Strava CSV is missing required columns: {', '.join(missing)}")
        st.caption(f"Detected columns: {', '.join(raw_df.columns.astype(str).tolist())}")
        return pd.DataFrame(columns=REQUIRED_STRAVA_COLUMNS)

    df = raw_df[REQUIRED_STRAVA_COLUMNS].copy()
    df["Activity Date"] = pd.to_datetime(df["Activity Date"], errors="coerce")
    if getattr(df["Activity Date"].dt, "tz", None) is not None:
        df["Activity Date"] = df["Activity Date"].dt.tz_convert(None)

    df["Elapsed Time"] = pd.to_numeric(df["Elapsed Time"], errors="coerce")
    df["Activity Name"] = df["Activity Name"].fillna("Unknown").replace("", "Unknown")
    df["Activity Type"] = df["Activity Type"].fillna("Unknown").replace("", "Unknown")

    # Invalid timestamps or missing durations cannot be used for time-window merging.
    df = df.dropna(subset=["Activity Date", "Elapsed Time"])
    df = df[df["Elapsed Time"] > 0]
    return df.sort_values("Activity Date").reset_index(drop=True)


def render_strava_kpis(df: pd.DataFrame) -> None:
    total_workouts = len(df)
    total_hours = df["Elapsed Time"].sum() / 3600
    most_common_type = df["Activity Type"].mode().iloc[0] if not df.empty else "N/A"

    cols = st.columns(3)
    cols[0].metric("Total Workouts", f"{total_workouts:,}")
    cols[1].metric("Total Active Hours", f"{total_hours:,.1f}")
    cols[2].metric("Most Frequent Type", most_common_type)


def render_strava_charts(df: pd.DataFrame) -> None:
    chart_df = df.copy()
    chart_df["Duration Minutes"] = chart_df["Elapsed Time"] / 60

    fig_scatter = px.scatter(
        chart_df,
        x="Activity Date",
        y="Duration Minutes",
        size="Duration Minutes",
        color="Activity Type",
        hover_data=["Activity Name", "Activity Type", "Duration Minutes"],
        title="Workouts Over Time",
        color_discrete_sequence=[STRAVA_ORANGE, "#111827", "#2563EB", "#16A34A", "#9333EA"],
    )
    fig_scatter.update_layout(height=470, paper_bgcolor="rgba(255,255,255,0.94)", plot_bgcolor="rgba(255,255,255,0.94)")
    st.plotly_chart(fig_scatter, use_container_width=True)

    type_counts = chart_df["Activity Type"].value_counts().reset_index()
    type_counts.columns = ["Activity Type", "Workouts"]
    fig_donut = px.pie(
        type_counts,
        names="Activity Type",
        values="Workouts",
        hole=0.55,
        title="Activity Type Frequency",
        color_discrete_sequence=[STRAVA_ORANGE, "#111827", "#2563EB", "#16A34A", "#9333EA"],
    )
    fig_donut.update_layout(height=430, paper_bgcolor="rgba(255,255,255,0.94)")
    st.plotly_chart(fig_donut, use_container_width=True)


def render_strava_feature() -> None:
    inject_strava_css()
    st.markdown(
        """
        <section class="strava-hero">
            <h1>Upload Strava Activities</h1>
            <p>Use a Strava CSV export with Activity Date, Elapsed Time, Activity Name, and Activity Type columns.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader("Strava CSV files", type=["csv"], accept_multiple_files=True)

    if not uploaded_files:
        st.info("Upload one or more Strava CSV files to continue.")
        return

    df = parse_strava_csv(uploaded_files)
    if df.empty:
        st.warning("No valid Strava workouts were found after parsing dates and elapsed time.")
        return

    logged_files = st.session_state.setdefault("logged_strava_files", set())
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in logged_files:
            log_strava_upload(st.session_state.participant_id, uploaded_file.name)
            logged_files.add(uploaded_file.name)

    st.session_state.strava_uploaded = True
    st.session_state.strava_df = df

    render_strava_kpis(df)
    render_strava_charts(df)

    st.divider()
    if st.button("Next: View Combined Insights", type="primary", use_container_width=True):
        st.session_state.current_page = "Combined Insights"
        st.rerun()
