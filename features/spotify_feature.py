import json

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db_handler import log_spotify_upload


SPOTIFY_GREEN = "#1DB954"
REQUIRED_SPOTIFY_COLUMNS = [
    "ts",
    "master_metadata_track_name",
    "master_metadata_album_artist_name",
    "ms_played",
]


def inject_spotify_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                linear-gradient(90deg, rgba(4, 8, 6, 0.96), rgba(7, 20, 12, 0.90)),
                url("https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=1800&q=80");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .spotify-hero {{
            min-height: 250px;
            padding: 56px 54px;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(29,185,84,0.26), rgba(0,0,0,0.78));
            border: 1px solid rgba(29,185,84,0.35);
            box-shadow: 0 24px 80px rgba(0,0,0,0.38);
            margin-bottom: 28px;
        }}
        .spotify-hero h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 52px;
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
            background: rgba(8, 13, 10, 0.88);
            border: 1px solid rgba(29,185,84,0.32);
            border-radius: 14px;
            padding: 18px;
        }}
        div[data-testid="stMetricValue"] {{
            color: {SPOTIFY_GREEN};
        }}
        .stButton > button, [data-testid="stFileUploader"] button {{
            border-color: {SPOTIFY_GREEN} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def parse_spotify_json(uploaded_files) -> pd.DataFrame:
    """Parse Spotify Extended Streaming History JSON using the exact export schema.

    Expected source columns:
    - ts: track timestamp
    - master_metadata_track_name: track title
    - master_metadata_album_artist_name: artist
    - ms_played: listening duration in milliseconds
    """
    rows = []
    for uploaded_file in uploaded_files:
        try:
            payload = json.load(uploaded_file)
        except Exception as exc:
            st.error(f"Could not read `{uploaded_file.name}` as JSON: {exc}")
            continue

        if isinstance(payload, list):
            rows.extend(payload)
        elif isinstance(payload, dict):
            # Some exports wrap records in a top-level key. We only accept list-like records.
            for value in payload.values():
                if isinstance(value, list):
                    rows.extend(value)
                    break

    if not rows:
        return pd.DataFrame(columns=REQUIRED_SPOTIFY_COLUMNS)

    raw_df = pd.DataFrame(rows)
    missing = [column for column in REQUIRED_SPOTIFY_COLUMNS if column not in raw_df.columns]
    if missing:
        st.error(f"Spotify JSON is missing required columns: {', '.join(missing)}")
        return pd.DataFrame(columns=REQUIRED_SPOTIFY_COLUMNS)

    df = raw_df[REQUIRED_SPOTIFY_COLUMNS].copy()
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    if getattr(df["ts"].dt, "tz", None) is not None:
        df["ts"] = df["ts"].dt.tz_convert(None)

    # Drop podcasts, ads, local files, and malformed rows with no actual track title.
    df = df.dropna(subset=["ts", "master_metadata_track_name"])
    df = df[df["master_metadata_track_name"].astype(str).str.strip() != ""]

    df["master_metadata_album_artist_name"] = (
        df["master_metadata_album_artist_name"].fillna("Unknown").replace("", "Unknown")
    )
    df["ms_played"] = pd.to_numeric(df["ms_played"], errors="coerce").fillna(0)
    df = df[df["ms_played"] > 0]
    return df.reset_index(drop=True)


def render_spotify_kpis(df: pd.DataFrame) -> None:
    total_hours = df["ms_played"].sum() / 3_600_000
    top_artist = df.groupby("master_metadata_album_artist_name")["ms_played"].sum().idxmax()
    total_tracks = len(df)

    cols = st.columns(3)
    cols[0].metric("Total Hours Listened", f"{total_hours:,.1f}")
    cols[1].metric("Top Artist", top_artist)
    cols[2].metric("Track Plays", f"{total_tracks:,}")


def render_spotify_charts(df: pd.DataFrame) -> None:
    artist_totals = (
        df.groupby("master_metadata_album_artist_name", as_index=False)["ms_played"]
        .sum()
        .assign(hours=lambda data: data["ms_played"] / 3_600_000)
        .sort_values("hours", ascending=False)
        .head(10)
    )
    fig_artists = px.bar(
        artist_totals.sort_values("hours"),
        x="hours",
        y="master_metadata_album_artist_name",
        orientation="h",
        color_discrete_sequence=[SPOTIFY_GREEN],
        labels={"hours": "Hours listened", "master_metadata_album_artist_name": ""},
        title="Top 10 Artists",
    )
    fig_artists.update_layout(template="plotly_dark", height=430, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig_artists, use_container_width=True)

    track_totals = (
        df.groupby("master_metadata_track_name", as_index=False)["ms_played"]
        .sum()
        .assign(hours=lambda data: data["ms_played"] / 3_600_000)
        .sort_values("hours", ascending=False)
        .head(10)
    )
    fig_tracks = px.bar(
        track_totals.sort_values("hours"),
        x="hours",
        y="master_metadata_track_name",
        orientation="h",
        color_discrete_sequence=["#7AE582"],
        labels={"hours": "Hours listened", "master_metadata_track_name": ""},
        title="Top 10 Tracks",
    )
    fig_tracks.update_layout(template="plotly_dark", height=430, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig_tracks, use_container_width=True)

    hourly = df.assign(hour=df["ts"].dt.hour).groupby("hour", as_index=False).size()
    fig_hourly = px.line(
        hourly,
        x="hour",
        y="size",
        markers=True,
        labels={"hour": "Hour of day", "size": "Track plays"},
        title="Listening Activity per Hour",
    )
    fig_hourly.update_traces(line=dict(color=SPOTIFY_GREEN, width=4), marker=dict(size=8))
    fig_hourly.update_layout(template="plotly_dark", height=430, xaxis=dict(dtick=1))
    st.plotly_chart(fig_hourly, use_container_width=True)


def render_spotify_feature() -> None:
    inject_spotify_css()
    st.markdown(
        """
        <section class="spotify-hero">
            <h1>Upload Spotify History</h1>
            <p>Use your Spotify Extended Streaming History JSON export. Charts appear only after a valid file is uploaded.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Spotify Extended Streaming History JSON",
        type=["json"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload one or more Spotify JSON files to continue.")
        return

    df = parse_spotify_json(uploaded_files)
    if df.empty:
        st.warning("No valid Spotify track rows were found after filtering null tracks and invalid timestamps.")
        return

    logged_files = st.session_state.setdefault("logged_spotify_files", set())
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in logged_files:
            log_spotify_upload(st.session_state.participant_id, uploaded_file.name)
            logged_files.add(uploaded_file.name)

    st.session_state.spotify_uploaded = True
    st.session_state.spotify_df = df

    render_spotify_kpis(df)
    render_spotify_charts(df)

    st.divider()
    if st.button("Next: Upload Strava Data", type="primary", use_container_width=True):
        st.session_state.current_page = "Strava Upload"
        st.rerun()
