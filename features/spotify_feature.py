import json

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db_handler import log_spotify_upload


SPOTIFY_GREEN = "#1DB954"


def inject_spotify_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                linear-gradient(90deg, rgba(7, 10, 12, 0.94), rgba(9, 20, 16, 0.88)),
                url("https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=1800&q=80");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .spotify-hero {{
            min-height: 260px;
            padding: 56px 54px;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(29,185,84,0.24), rgba(0,0,0,0.76));
            border: 1px solid rgba(29,185,84,0.34);
            box-shadow: 0 24px 80px rgba(0,0,0,0.35);
            margin-bottom: 28px;
        }}
        .spotify-hero h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 54px;
            font-weight: 850;
            letter-spacing: 0;
        }}
        .spotify-hero p {{
            max-width: 760px;
            color: #d8f8e3;
            font-size: 18px;
            line-height: 1.6;
        }}
        div[data-testid="stMetric"] {{
            background: rgba(10, 15, 12, 0.84);
            border: 1px solid rgba(29,185,84,0.32);
            border-radius: 14px;
            padding: 18px;
        }}
        div[data-testid="stMetricValue"] {{
            color: {SPOTIFY_GREEN};
        }}
        .stButton > button, [data-testid="stFileUploader"] button {{
            border-color: {SPOTIFY_GREEN} !important;
            color: #ffffff !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def generate_mock_spotify_dataframe() -> pd.DataFrame:
    """Junior devs: replace this with Spotify Extended Streaming History cleaning later."""
    artists = ["Nia Archives", "Fred again..", "Bicep", "Rosalia", "Kendrick Lamar", "SZA"]
    tracks = ["Night Run", "Pulse Check", "Afterglow", "Hill Sprint", "Warm Up", "Last Rep"]
    timestamps = pd.date_range("2026-04-01 06:20", periods=240, freq="3h")

    rows = []
    for idx, timestamp in enumerate(timestamps):
        artist = artists[idx % len(artists)]
        track = tracks[(idx * 3) % len(tracks)]
        rows.append(
            {
                "timestamp": timestamp,
                "track_name": track,
                "artist_name": artist,
                "ms_played": 90_000 + ((idx * 37_000) % 210_000),
                "estimated_bpm": 92 + ((idx * 11) % 78),
            }
        )
    return pd.DataFrame(rows)


def parse_spotify_json(uploaded_files) -> pd.DataFrame:
    rows = []
    for uploaded_file in uploaded_files:
        try:
            payload = json.load(uploaded_file)
        except Exception:
            continue
        if isinstance(payload, dict):
            payload = payload.get("items", payload.get("endsong", []))
        if isinstance(payload, list):
            rows.extend(payload)

    if not rows:
        return generate_mock_spotify_dataframe()

    df = pd.DataFrame(rows)
    timestamp_col = "ts" if "ts" in df.columns else ("timestamp" if "timestamp" in df.columns else None)
    track_col = "master_metadata_track_name" if "master_metadata_track_name" in df.columns else ("track_name" if "track_name" in df.columns else None)
    artist_col = "master_metadata_album_artist_name" if "master_metadata_album_artist_name" in df.columns else ("artist_name" if "artist_name" in df.columns else None)
    ms_col = "ms_played" if "ms_played" in df.columns else ("msPlayed" if "msPlayed" in df.columns else None)

    cleaned = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(df[timestamp_col], errors="coerce") if timestamp_col else pd.Timestamp.now(),
            "track_name": df[track_col].fillna("Unknown Track") if track_col else "Unknown Track",
            "artist_name": df[artist_col].fillna("Unknown Artist") if artist_col else "Unknown Artist",
            "ms_played": pd.to_numeric(df[ms_col], errors="coerce").fillna(0) if ms_col else 0,
        }
    )
    cleaned = cleaned.dropna(subset=["timestamp"])
    cleaned["estimated_bpm"] = 88 + (pd.util.hash_pandas_object(cleaned["track_name"], index=False) % 86)
    return cleaned


def render_kpis(df: pd.DataFrame) -> None:
    total_hours = df["ms_played"].sum() / 3_600_000
    top_artist = df.groupby("artist_name")["ms_played"].sum().idxmax()
    avg_bpm = df["estimated_bpm"].mean()

    cols = st.columns(3)
    cols[0].metric("Total Hours Listened", f"{total_hours:,.1f}")
    cols[1].metric("Top Artist", top_artist)
    cols[2].metric("Average BPM", f"{avg_bpm:,.0f}")


def render_visualizations(df: pd.DataFrame) -> None:
    track_totals = (
        df.groupby(["track_name", "artist_name"], as_index=False)["ms_played"]
        .sum()
        .assign(hours=lambda data: data["ms_played"] / 3_600_000)
        .sort_values("hours", ascending=False)
        .head(10)
    )
    track_totals["label"] = track_totals["track_name"] + " - " + track_totals["artist_name"]

    artist_totals = (
        df.groupby("artist_name", as_index=False)["ms_played"]
        .sum()
        .assign(hours=lambda data: data["ms_played"] / 3_600_000)
        .sort_values("hours", ascending=False)
        .head(10)
    )

    left, right = st.columns(2)
    with left:
        fig_tracks = px.bar(
            track_totals.sort_values("hours"),
            x="hours",
            y="label",
            orientation="h",
            color_discrete_sequence=[SPOTIFY_GREEN],
            labels={"hours": "Hours listened", "label": ""},
            title="Top 10 Tracks",
        )
        fig_tracks.update_layout(template="plotly_dark", height=430, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig_tracks, use_container_width=True)

    with right:
        fig_artists = px.bar(
            artist_totals.sort_values("hours"),
            x="hours",
            y="artist_name",
            orientation="h",
            color_discrete_sequence=["#7AE582"],
            labels={"hours": "Hours listened", "artist_name": ""},
            title="Top 10 Artists",
        )
        fig_artists.update_layout(template="plotly_dark", height=430, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig_artists, use_container_width=True)

    hourly = df.assign(hour=df["timestamp"].dt.hour).groupby("hour", as_index=False).size()
    fig_hourly = px.line(
        hourly,
        x="hour",
        y="size",
        markers=True,
        labels={"hour": "Hour of day", "size": "Listening events"},
        title="Listening Habits Over the Day",
    )
    fig_hourly.update_traces(line=dict(color=SPOTIFY_GREEN, width=4), marker=dict(size=8))
    fig_hourly.update_layout(template="plotly_dark", height=420)
    st.plotly_chart(fig_hourly, use_container_width=True)

    fig_bpm = px.histogram(
        df,
        x="estimated_bpm",
        nbins=28,
        color_discrete_sequence=[SPOTIFY_GREEN],
        labels={"estimated_bpm": "Estimated BPM"},
        title="BPM Distribution",
    )
    fig_bpm.update_layout(template="plotly_dark", height=420)
    st.plotly_chart(fig_bpm, use_container_width=True)


def render_spotify_feature() -> None:
    inject_spotify_css()
    st.markdown(
        """
        <section class="spotify-hero">
            <h1>Spotify Listening Profile</h1>
            <p>Explore listening intensity, artist patterns, daily rhythm, and estimated tempo before merging with workout data.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader("Upload Spotify Extended Streaming History JSON", type=["json"], accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            log_spotify_upload(st.session_state.participant_id, uploaded_file.name)
        df = parse_spotify_json(uploaded_files)
        st.session_state.spotify_uploaded = True
        st.success("Spotify JSON uploaded and logged.")
    else:
        df = generate_mock_spotify_dataframe()
        st.info("No JSON uploaded yet, showing a high-fidelity mock Spotify dataset.")

    st.session_state.spotify_mock_df = df
    render_kpis(df)
    render_visualizations(df)
