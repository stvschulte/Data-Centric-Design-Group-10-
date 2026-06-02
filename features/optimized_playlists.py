from __future__ import annotations

import html
import textwrap

import pandas as pd
import streamlit as st


SPOTIFY_GREEN = "#1DB954"
ZONE_DEFINITIONS = [
    ("Zone 1", "Recovery", "< 110 BPM", 0, 110),
    ("Zone 2", "Endurance", "110-130 BPM", 110, 131),
    ("Zone 3", "Tempo", "131-150 BPM", 131, 151),
    ("Zone 4", "Threshold", "151-170 BPM", 151, 171),
    ("Zone 5", "Max", "> 170 BPM", 171, float("inf")),
]


def render_html(markup: str) -> None:
    cleaned_markup = textwrap.dedent(markup).strip()
    cleaned_markup = "\n".join(line.lstrip() for line in cleaned_markup.splitlines())
    st.markdown(cleaned_markup, unsafe_allow_html=True)


def inject_playlist_css() -> None:
    render_html(
        f"""
        <style>
        .stApp {{
            background: linear-gradient(135deg, #05070a 0%, #101318 60%, #090b0f 100%);
            color: #f8fafc;
        }}
        .playlist-hero {{
            padding: 46px;
            margin-bottom: 24px;
            border-radius: 18px;
            background:
                linear-gradient(135deg, rgba(29,185,84,0.22), rgba(252,76,2,0.15)),
                linear-gradient(135deg, #07110b, #17110d);
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 24px 80px rgba(0,0,0,0.44);
        }}
        .playlist-hero h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 46px;
            font-weight: 850;
            letter-spacing: 0;
        }}
        .playlist-hero p {{
            max-width: 820px;
            color: #d8f8e3;
            font-size: 18px;
            line-height: 1.6;
        }}
        .zone-card {{
            min-height: 470px;
            padding: 18px;
            border-radius: 16px;
            background: rgba(8, 13, 10, 0.90);
            border: 1px solid rgba(29,185,84,0.24);
            box-shadow: 0 18px 54px rgba(0,0,0,0.32);
        }}
        .zone-card h2 {{
            margin: 0;
            color: #ffffff;
            font-size: 1.24rem;
            font-weight: 850;
        }}
        .zone-target {{
            margin: 5px 0 16px;
            color: {SPOTIFY_GREEN};
            font-size: 0.94rem;
            font-weight: 800;
        }}
        .playlist-track {{
            padding: 12px 0;
            border-top: 1px solid rgba(255,255,255,0.10);
        }}
        .playlist-track:first-of-type {{
            border-top: 0;
        }}
        .track-name {{
            color: #ffffff;
            font-size: 0.98rem;
            font-weight: 800;
            line-height: 1.25;
        }}
        .track-meta {{
            margin-top: 4px;
            color: #94a3b8;
            font-size: 0.86rem;
            line-height: 1.35;
        }}
        .empty-zone {{
            color: #94a3b8;
            font-size: 0.92rem;
            line-height: 1.45;
            margin-top: 14px;
        }}
        </style>
        """
    )


def zone_for_bpm(bpm: float) -> str:
    if bpm < 110:
        return "Zone 1"
    if bpm <= 130:
        return "Zone 2"
    if bpm <= 150:
        return "Zone 3"
    if bpm <= 170:
        return "Zone 4"
    return "Zone 5"


def build_track_summary(df: pd.DataFrame) -> pd.DataFrame:
    usable = df.dropna(subset=["track_bpm"]).copy()
    if usable.empty:
        return pd.DataFrame()

    usable["playlist_zone"] = usable["track_bpm"].apply(zone_for_bpm)
    return (
        usable.groupby(["track_name", "artist_name", "playlist_zone"], as_index=False)
        .agg(total_ms_played=("ms_played", "sum"), real_bpm=("track_bpm", "mean"))
        .assign(total_minutes=lambda data: data["total_ms_played"] / 60000)
        .sort_values("total_ms_played", ascending=False)
    )


def render_zone_card(zone_name: str, label: str, target_bpm: str, tracks: pd.DataFrame) -> None:
    rows = []
    for _, row in tracks.head(5).iterrows():
        rows.append(
            f"""
            <div class="playlist-track">
                <div class="track-name">{html.escape(str(row["track_name"]))}</div>
                <div class="track-meta">
                    {html.escape(str(row["artist_name"]))}<br>
                    {row["real_bpm"]:.0f} BPM · {row["total_minutes"]:.1f} min listened
                </div>
            </div>
            """
        )

    if not rows:
        rows.append('<div class="empty-zone">No tracks with enough BPM data in this zone yet.</div>')

    render_html(
        f"""
        <div class="zone-card">
            <h2>{zone_name}: {label}</h2>
            <div class="zone-target">{target_bpm}</div>
            {''.join(rows)}
        </div>
        """
    )


def render_optimized_playlists() -> None:
    inject_playlist_css()
    render_html(
        """
        <section class="playlist-hero">
            <h1>Your Zone-Optimized Playlists</h1>
            <p>Top tracks from your own listening history, grouped by real BPM so each playlist matches a training zone.</p>
        </section>
        """
    )

    participant_id = st.session_state.get("participant_id")
    augmented_df = st.session_state.get("augmented_music_workout_df")
    augmented_participant_id = st.session_state.get("augmented_music_workout_participant_id")
    if participant_id != augmented_participant_id or not isinstance(augmented_df, pd.DataFrame) or augmented_df.empty:
        st.warning("Generate combined insights first so the app can fetch BPM and build your playlists.")
        if st.button("Go to Combined Insights", type="primary"):
            st.session_state.current_page = "Combined Insights"
            st.rerun()
        return

    track_summary = build_track_summary(augmented_df)
    if track_summary.empty:
        st.warning("No BPM-enriched tracks are available for playlist generation yet.")
        return

    columns = st.columns(5)
    for column, (zone_name, label, target_bpm, _, _) in zip(columns, ZONE_DEFINITIONS):
        zone_tracks = track_summary[track_summary["playlist_zone"] == zone_name]
        with column:
            render_zone_card(zone_name, label, target_bpm, zone_tracks)
