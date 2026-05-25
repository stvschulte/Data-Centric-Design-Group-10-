import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.db_handler import log_strava_upload


STRAVA_ORANGE = "#FC4C02"


def inject_strava_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                linear-gradient(90deg, rgba(255,255,255,0.96), rgba(255,246,241,0.9)),
                url("https://images.unsplash.com/photo-1502904550040-7534597429ae?auto=format&fit=crop&w=1800&q=80");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #18181b;
        }}
        .strava-hero {{
            min-height: 260px;
            padding: 56px 54px;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(252,76,2,0.18), rgba(255,255,255,0.86));
            border: 1px solid rgba(252,76,2,0.34);
            box-shadow: 0 24px 80px rgba(35,24,18,0.18);
            margin-bottom: 28px;
        }}
        .strava-hero h1 {{
            margin: 0;
            color: #111827;
            font-size: 54px;
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
            background: rgba(255,255,255,0.92);
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


def generate_mock_strava_dataframe() -> pd.DataFrame:
    """Junior devs: replace this with Strava export cleaning later."""
    workout_types = ["Run", "Ride", "Strength", "Walk", "Yoga"]
    start_times = pd.date_range("2026-01-05 07:30", periods=92, freq="4D")

    rows = []
    for idx, start_time in enumerate(start_times):
        duration = 28 + ((idx * 9) % 82)
        workout_type = workout_types[(idx * 2) % len(workout_types)]
        rows.append(
            {
                "start_time": start_time,
                "end_time": start_time + pd.Timedelta(minutes=duration),
                "duration_minutes": duration,
                "workout_type": workout_type,
                "frequency_id": start_time.date().isoformat(),
            }
        )
    return pd.DataFrame(rows)


def parse_strava_csv(uploaded_files) -> pd.DataFrame:
    frames = []
    for uploaded_file in uploaded_files:
        try:
            frames.append(pd.read_csv(uploaded_file))
        except Exception:
            continue

    if not frames:
        return generate_mock_strava_dataframe()

    raw = pd.concat(frames, ignore_index=True)
    column_lookup = {str(col).strip().lower(): col for col in raw.columns}
    start_col = column_lookup.get("activity date") or column_lookup.get("start_time") or column_lookup.get("start time")
    elapsed_col = column_lookup.get("elapsed time") or column_lookup.get("duration_minutes") or column_lookup.get("duration")
    type_col = column_lookup.get("activity type") or column_lookup.get("workout_type") or column_lookup.get("type")

    if start_col is None or elapsed_col is None:
        return generate_mock_strava_dataframe()

    start_time = pd.to_datetime(raw[start_col], errors="coerce")
    duration_raw = raw[elapsed_col]
    duration_minutes = pd.to_numeric(duration_raw, errors="coerce")
    if duration_minutes.max(skipna=True) and duration_minutes.max(skipna=True) > 300:
        duration_minutes = duration_minutes / 60
    duration_minutes = duration_minutes.fillna(pd.to_timedelta(duration_raw.astype(str), errors="coerce").dt.total_seconds() / 60)

    df = pd.DataFrame(
        {
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "workout_type": raw[type_col].fillna("Workout") if type_col else "Workout",
        }
    ).dropna(subset=["start_time", "duration_minutes"])
    df["end_time"] = df["start_time"] + pd.to_timedelta(df["duration_minutes"], unit="m")
    df["frequency_id"] = df["start_time"].dt.date.astype(str)
    return df[["start_time", "end_time", "duration_minutes", "workout_type", "frequency_id"]]


def render_kpis(df: pd.DataFrame) -> None:
    total_workouts = len(df)
    total_hours = df["duration_minutes"].sum() / 60
    most_common_type = df["workout_type"].mode().iloc[0] if not df.empty else "N/A"

    cols = st.columns(3)
    cols[0].metric("Total Workouts", f"{total_workouts:,}")
    cols[1].metric("Total Active Hours", f"{total_hours:,.1f}")
    cols[2].metric("Most Frequent Type", most_common_type)


def render_calendar_heatmap(df: pd.DataFrame) -> None:
    calendar = df.groupby(df["start_time"].dt.date).size().reset_index(name="workouts")
    calendar["date"] = pd.to_datetime(calendar["start_time"])
    calendar["week"] = calendar["date"].dt.isocalendar().week.astype(int)
    calendar["weekday"] = calendar["date"].dt.day_name()
    calendar["month"] = calendar["date"].dt.strftime("%b")

    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pivot = calendar.pivot_table(index="weekday", columns="week", values="workouts", aggfunc="sum").reindex(weekday_order)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.fillna(0).values,
            x=pivot.columns.astype(str),
            y=pivot.index,
            colorscale=[[0, "#fff7ed"], [0.35, "#fdba74"], [1, STRAVA_ORANGE]],
            hovertemplate="Week %{x}<br>%{y}<br>Workouts: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Workout Frequency Calendar Heatmap",
        height=420,
        paper_bgcolor="rgba(255,255,255,0.92)",
        plot_bgcolor="rgba(255,255,255,0.92)",
        margin=dict(l=20, r=20, t=70, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_duration_chart(df: pd.DataFrame) -> None:
    daily = df.sort_values("start_time")
    fig = px.area(
        daily,
        x="start_time",
        y="duration_minutes",
        color="workout_type",
        labels={"start_time": "Date", "duration_minutes": "Duration minutes", "workout_type": "Workout type"},
        title="Workout Duration Over Time",
        color_discrete_sequence=[STRAVA_ORANGE, "#111827", "#2563eb", "#16a34a", "#9333ea"],
    )
    fig.update_layout(height=430, paper_bgcolor="rgba(255,255,255,0.92)", plot_bgcolor="rgba(255,255,255,0.92)")
    st.plotly_chart(fig, use_container_width=True)


def render_strava_feature() -> None:
    inject_strava_css()
    st.markdown(
        """
        <section class="strava-hero">
            <h1>Strava Activity Profile</h1>
            <p>Review training volume, workout rhythm, and activity consistency before combining exercise sessions with music behavior.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader("Upload Strava CSV files", type=["csv"], accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            log_strava_upload(st.session_state.participant_id, uploaded_file.name)
        df = parse_strava_csv(uploaded_files)
        st.session_state.strava_uploaded = True
        st.success("Strava CSV uploaded and logged.")
    else:
        df = generate_mock_strava_dataframe()
        st.info("No CSV uploaded yet, showing a high-fidelity mock Strava dataset.")

    st.session_state.strava_mock_df = df
    render_kpis(df)
    render_calendar_heatmap(df)
    render_duration_chart(df)
