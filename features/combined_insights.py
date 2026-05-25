import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from features.spotify_feature import generate_mock_spotify_dataframe
from features.strava_feature import generate_mock_strava_dataframe


GREEN = "#1DB954"
ORANGE = "#FC4C02"


def inject_combined_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                radial-gradient(circle at top left, rgba(29,185,84,0.20), transparent 34%),
                radial-gradient(circle at top right, rgba(252,76,2,0.18), transparent 32%),
                linear-gradient(135deg, #05070a, #101318 56%, #090b0f);
            color: #f8fafc;
        }}
        .combined-hero {{
            min-height: 250px;
            padding: 56px 54px;
            border-radius: 18px;
            background:
                linear-gradient(135deg, rgba(29,185,84,0.18), rgba(252,76,2,0.16)),
                url("https://images.unsplash.com/photo-1517963628607-235ccdd5476c?auto=format&fit=crop&w=1800&q=80");
            background-size: cover;
            background-position: center;
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 24px 80px rgba(0,0,0,0.45);
            margin-bottom: 28px;
        }}
        .combined-hero h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 54px;
            font-weight: 850;
            letter-spacing: 0;
        }}
        .combined-hero p {{
            max-width: 780px;
            color: #e2e8f0;
            font-size: 18px;
            line-height: 1.6;
        }}
        div[data-testid="stMetric"] {{
            background: rgba(15,23,42,0.80);
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 14px;
            padding: 18px;
        }}
        div[data-testid="stMetricValue"] {{
            color: {GREEN};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def prepare_mock_merge(spotify_df: pd.DataFrame, strava_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    spotify = spotify_df.copy()
    strava = strava_df.copy().sort_values("start_time").reset_index(drop=True)
    spotify["timestamp"] = pd.to_datetime(spotify["timestamp"])
    strava["start_time"] = pd.to_datetime(strava["start_time"])
    strava["end_time"] = pd.to_datetime(strava["end_time"])

    # Keep the mock timelines aligned so each workout has tracks inside its window.
    aligned_timestamps = []
    for idx in range(len(spotify)):
        workout = strava.iloc[idx % len(strava)]
        offset_minutes = (idx % 10) * 4
        timestamp = workout["start_time"] + pd.Timedelta(minutes=offset_minutes)
        if timestamp > workout["end_time"]:
            timestamp = workout["start_time"] + pd.Timedelta(minutes=1)
        aligned_timestamps.append(timestamp)
    spotify["timestamp"] = aligned_timestamps

    workout_rows = []
    track_rows = []
    for idx, workout in strava.iterrows():
        tracks = spotify[
            (spotify["timestamp"] >= workout["start_time"])
            & (spotify["timestamp"] <= workout["end_time"])
        ].copy()

        if tracks.empty:
            avg_bpm = None
        else:
            avg_bpm = tracks["estimated_bpm"].mean()

        workout_id = f"Workout {idx + 1}"
        workout_rows.append(
            {
                "workout_id": workout_id,
                "start_time": workout["start_time"],
                "duration_minutes": workout["duration_minutes"],
                "workout_type": workout["workout_type"],
                "tracks_played": len(tracks),
                "average_bpm": avg_bpm,
            }
        )

        for _, track in tracks.iterrows():
            track_rows.append(
                {
                    "workout_id": workout_id,
                    "workout_type": workout["workout_type"],
                    "workout_start": workout["start_time"],
                    "duration_minutes": workout["duration_minutes"],
                    "track_time": track["timestamp"],
                    "track_name": track["track_name"],
                    "artist_name": track["artist_name"],
                    "estimated_bpm": track["estimated_bpm"],
                }
            )

    return pd.DataFrame(workout_rows), pd.DataFrame(track_rows)


def render_music_during_workouts(workouts_df: pd.DataFrame, tracks_df: pd.DataFrame) -> None:
    st.subheader("Music During Workouts")
    workout_options = workouts_df["workout_id"].tolist()
    selected_workout = st.selectbox("Select workout session", workout_options)
    workout_tracks = tracks_df[tracks_df["workout_id"] == selected_workout]

    if workout_tracks.empty:
        st.info("No tracks were matched to this workout window.")
        return

    display_df = workout_tracks[["track_time", "track_name", "artist_name", "estimated_bpm"]].copy()
    display_df["track_time"] = display_df["track_time"].dt.strftime("%H:%M")
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_bpm_scatter(workouts_df: pd.DataFrame) -> None:
    scored = workouts_df.dropna(subset=["average_bpm"])
    fig = go.Figure()
    for workout_type, data in scored.groupby("workout_type"):
        fig.add_trace(
            go.Scatter(
                x=data["duration_minutes"],
                y=data["average_bpm"],
                mode="markers",
                name=workout_type,
                marker=dict(size=data["tracks_played"].clip(lower=1) * 2 + 10, opacity=0.82),
                customdata=data[["workout_id", "tracks_played"]],
                hovertemplate=(
                    "Workout: %{customdata[0]}<br>"
                    "Type: " + workout_type + "<br>"
                    "Duration: %{x:.0f} min<br>"
                    "Avg BPM: %{y:.0f}<br>"
                    "Tracks: %{customdata[1]}<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title="BPM vs. Workout Duration and Type",
        xaxis_title="Workout duration minutes",
        yaxis_title="Average listening BPM",
        template="plotly_dark",
        height=460,
        margin=dict(l=20, r=20, t=70, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_overlay_chart(workouts_df: pd.DataFrame) -> None:
    ordered = workouts_df.sort_values("start_time")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=ordered["start_time"],
            y=ordered["duration_minutes"],
            name="Workout duration",
            marker_color=ORANGE,
            opacity=0.82,
            yaxis="y",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ordered["start_time"],
            y=ordered["average_bpm"],
            name="Average listening BPM",
            mode="lines+markers",
            line=dict(color=GREEN, width=4),
            marker=dict(size=9),
            yaxis="y2",
        )
    )
    fig.update_layout(
        title="Workout Duration Overlaid with Average Listening BPM",
        template="plotly_dark",
        height=480,
        yaxis=dict(title="Duration minutes", side="left"),
        yaxis2=dict(title="Average BPM", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=20, r=20, t=80, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_combined_insights() -> None:
    inject_combined_css()
    st.markdown(
        """
        <section class="combined-hero">
            <h1>Music x Movement Dashboard</h1>
            <p>A unified view of workout windows and listening tempo, designed to reveal how training sessions line up with music behavior.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.spotify_uploaded or not st.session_state.strava_uploaded:
        st.warning("Upload both Spotify and Strava files to replace this demo with participant-specific data.")

    spotify_df = st.session_state.get("spotify_mock_df", generate_mock_spotify_dataframe())
    strava_df = st.session_state.get("strava_mock_df", generate_mock_strava_dataframe())
    workouts_df, tracks_df = prepare_mock_merge(spotify_df, strava_df)

    cols = st.columns(3)
    cols[0].metric("Matched Workouts", f"{len(workouts_df):,}")
    cols[1].metric("Tracks During Workouts", f"{len(tracks_df):,}")
    cols[2].metric("Average Workout BPM", f"{workouts_df['average_bpm'].mean():.0f}" if workouts_df["average_bpm"].notna().any() else "N/A")

    render_music_during_workouts(workouts_df, tracks_df)
    render_bpm_scatter(workouts_df)
    render_overlay_chart(workouts_df)
