from __future__ import annotations

import json
import os
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db_handler import (
    fetch_spotify_tracks,
    fetch_strava_activities,
    save_participant_reflection,
)


SPOTIFY_GREEN = "#1DB954"
STRAVA_ORANGE = "#FC4C02"


def inject_combined_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: linear-gradient(135deg, #05070a 0%, #101318 58%, #090b0f 100%);
            color: #f8fafc;
        }}
        .combined-hero {{
            padding: 52px 46px;
            border-radius: 18px;
            background:
                linear-gradient(135deg, rgba(29,185,84,0.24), rgba(252,76,2,0.18)),
                linear-gradient(135deg, #07110b, #17110d);
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 24px 80px rgba(0,0,0,0.44);
            margin-bottom: 26px;
        }}
        .combined-hero h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 48px;
            font-weight: 850;
            letter-spacing: 0;
        }}
        .combined-hero p {{
            max-width: 840px;
            color: #dbeafe;
            font-size: 18px;
            line-height: 1.6;
        }}
        div[data-testid="stMetric"] {{
            background: rgba(15,23,42,0.86);
            border: 1px solid rgba(255,255,255,0.13);
            border-radius: 12px;
            padding: 18px;
        }}
        div[data-testid="stMetricValue"] {{
            color: {SPOTIFY_GREEN};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_configured_spotify_credentials() -> tuple[str, str]:
    """Read Spotify credentials from environment or Streamlit secrets, never from participant UI."""
    placeholder_values = {
        "",
        "jouw-client-id",
        "jouw-client-secret",
        "your-client-id",
        "your-client-secret",
    }

    def read_secret(key: str) -> str:
        value = os.getenv(key, "")
        if value.strip() and value.strip() not in placeholder_values:
            return value.strip()
        try:
            secret_value = st.secrets.get(key, "")
            return secret_value.strip() if secret_value.strip() not in placeholder_values else ""
        except Exception:
            return ""

    return read_secret("SPOTIPY_CLIENT_ID"), read_secret("SPOTIPY_CLIENT_SECRET")


def create_spotify_client(client_id: str, client_secret: str):
    if not client_id or not client_secret:
        return None

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ModuleNotFoundError:
        return None

    try:
        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        return spotipy.Spotify(auth_manager=auth_manager, requests_timeout=8, retries=2)
    except Exception:
        return None


def normalize_spotify_uri(value: str) -> str:
    value = str(value or "").strip()
    if value.startswith("spotify:track:"):
        return value
    if "open.spotify.com/track/" in value:
        track_id = value.split("/track/", 1)[1].split("?", 1)[0].strip()
        return f"spotify:track:{track_id}" if track_id else ""
    return ""


def merge_tracks_into_workouts(spotify_df: pd.DataFrame, strava_df: pd.DataFrame) -> pd.DataFrame:
    spotify = spotify_df.copy()
    strava = strava_df.copy()
    spotify["ts"] = pd.to_datetime(spotify["ts"], errors="coerce")
    strava["standard_date"] = pd.to_datetime(strava["standard_date"], errors="coerce")
    strava["standard_duration"] = pd.to_numeric(strava["standard_duration"], errors="coerce")
    spotify = spotify.dropna(subset=["ts", "track_name"])
    strava = strava.dropna(subset=["standard_date", "standard_duration"])

    rows = []
    for workout_index, workout in strava.reset_index(drop=True).iterrows():
        start_time = workout["standard_date"]
        end_time = start_time + pd.to_timedelta(workout["standard_duration"], unit="s")
        matched_tracks = spotify[(spotify["ts"] >= start_time) & (spotify["ts"] <= end_time)].copy()
        if matched_tracks.empty:
            continue

        for _, track in matched_tracks.iterrows():
            rows.append(
                {
                    "participant_workout_id": workout_index + 1,
                    "workout_name": workout.get("standard_name", "Unnamed Workout"),
                    "workout_type": workout.get("standard_type", "Unknown"),
                    "workout_start": start_time,
                    "workout_duration_minutes": workout["standard_duration"] / 60,
                    "average_heart_rate": workout.get("standard_hr"),
                    "track_time": track["ts"],
                    "track_name": track.get("track_name", "Unknown Track"),
                    "artist_name": track.get("artist_name", "Unknown Artist"),
                    "ms_played": track.get("ms_played", 0),
                    "spotify_track_uri": normalize_spotify_uri(track.get("spotify_track_uri", "")),
                }
            )

    return pd.DataFrame(rows)


def resolve_missing_track_uris(sp, merged_df: pd.DataFrame) -> pd.DataFrame:
    df = merged_df.copy()
    if sp is None:
        return df

    missing_mask = df["spotify_track_uri"].fillna("").eq("")
    if not missing_mask.any():
        return df

    resolved_cache = {}
    for idx, row in df[missing_mask].iterrows():
        cache_key = (row["track_name"], row["artist_name"])
        if cache_key not in resolved_cache:
            try:
                query = f'track:"{row["track_name"]}" artist:"{row["artist_name"]}"'
                result = sp.search(q=query, type="track", limit=1)
                items = result.get("tracks", {}).get("items", [])
                resolved_cache[cache_key] = items[0].get("uri", "") if items else ""
            except Exception:
                resolved_cache[cache_key] = ""
        df.at[idx, "spotify_track_uri"] = resolved_cache[cache_key]

    return df


@st.cache_data(show_spinner=False)
def fetch_audio_features_cached(track_uris: tuple[str, ...], client_id: str, client_secret: str) -> tuple[dict, str]:
    """Fetch Spotify audio features in API-sized batches and return URI -> tempo."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials

        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        sp = spotipy.Spotify(auth_manager=auth_manager, requests_timeout=8, retries=2)
        tempo_by_uri = {}
        for start in range(0, len(track_uris), 100):
            batch = list(track_uris[start : start + 100])
            features = sp.audio_features(batch)
            for uri, feature in zip(batch, features):
                if feature and feature.get("tempo") is not None:
                    tempo_by_uri[uri] = float(feature["tempo"])
        return tempo_by_uri, ""
    except Exception as exc:
        return {}, str(exc)


@st.cache_data(show_spinner=False)
def fetch_deezer_bpm_cached(track_name: str, artist_name: str) -> float | None:
    """Best-effort no-credential BPM fallback via Deezer's public track endpoint."""
    try:
        query = f'track:"{track_name}" artist:"{artist_name}"'
        search_url = f"https://api.deezer.com/search/track?q={quote_plus(query)}&limit=1"
        request = Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=6) as response:
            payload = json.load(response)
        items = payload.get("data", [])
        if not items:
            fallback_url = f"https://api.deezer.com/search/track?q={quote_plus(track_name + ' ' + artist_name)}&limit=1"
            request = Request(fallback_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=6) as response:
                payload = json.load(response)
            items = payload.get("data", [])
        if not items:
            return None

        track_id = items[0].get("id")
        if not track_id:
            return None
        detail_request = Request(f"https://api.deezer.com/track/{track_id}", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(detail_request, timeout=6) as response:
            detail = json.load(response)
        bpm = float(detail.get("bpm") or 0)
        return bpm if bpm > 0 else None
    except Exception:
        return None


def add_bpm_values(merged_df: pd.DataFrame, spotify_client, client_id: str, client_secret: str) -> tuple[pd.DataFrame, str]:
    df = merged_df.copy()
    tempo_by_uri = {}
    spotify_error = ""

    if spotify_client is not None:
        df = resolve_missing_track_uris(spotify_client, df)
        track_uris = tuple(sorted(uri for uri in df["spotify_track_uri"].dropna().unique() if uri))
        if track_uris and client_id and client_secret:
            tempo_by_uri, spotify_error = fetch_audio_features_cached(track_uris, client_id, client_secret)

    df["track_bpm"] = df["spotify_track_uri"].map(tempo_by_uri) if tempo_by_uri else pd.NA

    missing_bpm_mask = df["track_bpm"].isna()
    deezer_matches = 0
    if missing_bpm_mask.any():
        bpm_cache = {}
        for idx, row in df[missing_bpm_mask].iterrows():
            cache_key = (str(row["track_name"]), str(row["artist_name"]))
            if cache_key not in bpm_cache:
                bpm_cache[cache_key] = fetch_deezer_bpm_cached(cache_key[0], cache_key[1])
            if bpm_cache[cache_key] is not None:
                df.at[idx, "track_bpm"] = bpm_cache[cache_key]
                deezer_matches += 1

    df["track_bpm"] = pd.to_numeric(df["track_bpm"], errors="coerce")
    if tempo_by_uri:
        status = "BPM values loaded automatically from configured Spotify credentials."
    elif deezer_matches:
        status = "BPM values loaded automatically with a public Deezer fallback where available."
    elif spotify_error:
        status = "Music and workout data were combined, but Spotify did not return BPM audio features for this app."
    else:
        status = "Music and workout data were combined, but no BPM source is configured or available for these tracks."
    return df, status


def build_workout_summary(merged_df: pd.DataFrame) -> pd.DataFrame:
    usable = merged_df.dropna(subset=["track_bpm"]).copy()
    if usable.empty:
        return pd.DataFrame()

    return (
        usable.groupby(
            [
                "participant_workout_id",
                "workout_name",
                "workout_type",
                "workout_start",
                "workout_duration_minutes",
                "average_heart_rate",
            ],
            as_index=False,
        )
        .agg(
            average_track_bpm=("track_bpm", "mean"),
            tracks_matched=("track_name", "count"),
            music_minutes=("ms_played", lambda value: value.sum() / 60000),
        )
        .dropna(subset=["average_track_bpm"])
    )


def correlation_sentence(df: pd.DataFrame, x_column: str, y_column: str, subject: str) -> tuple[float | None, str]:
    paired = df[[x_column, y_column]].dropna()
    if len(paired) < 2 or paired[x_column].nunique() < 2 or paired[y_column].nunique() < 2:
        return None, f"There is not enough variation yet to determine how {subject} relates to your music tempo."

    correlation = paired[x_column].corr(paired[y_column])
    if pd.isna(correlation):
        return None, f"There is not enough variation yet to determine how {subject} relates to your music tempo."

    direction = "positive" if correlation > 0 else "negative"
    if abs(correlation) < 0.2:
        return correlation, f"Your {subject} shows only a minimal relationship ({correlation:+.2f}) with average track BPM."
    return correlation, f"Your {subject} shows a {direction} correlation ({correlation:+.2f}) with average track BPM."


def apply_chart_style(fig) -> None:
    fig.update_layout(
        template="plotly_dark",
        height=470,
        font=dict(color="white", size=14),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=70, b=10),
    )


def render_combined_insights() -> None:
    inject_combined_css()
    st.markdown(
        """
        <section class="combined-hero">
            <h1>Combined Music x Workout Insights</h1>
            <p>Your Spotify and Strava rows are loaded only for your Participant ID and matched by workout time windows.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    participant_id = st.session_state.get("participant_id")
    if not participant_id:
        st.warning("No Participant ID found. Please complete consent first.")
        return

    spotify_df = fetch_spotify_tracks(participant_id)
    strava_df = fetch_strava_activities(participant_id)
    if spotify_df.empty or strava_df.empty:
        st.warning("Spotify and Strava uploads are both required before combined insights can be generated.")
        return

    merged_df = merge_tracks_into_workouts(spotify_df, strava_df)
    if merged_df.empty:
        st.warning("No Spotify tracks were found inside your Strava workout windows.")
        return

    client_id, client_secret = get_configured_spotify_credentials()
    spotify_client = create_spotify_client(client_id, client_secret)
    with st.spinner("Combining Spotify and Strava data automatically..."):
        merged_df, bpm_status = add_bpm_values(merged_df, spotify_client, client_id, client_secret)
    st.session_state.augmented_music_workout_df = merged_df
    st.session_state.augmented_music_workout_participant_id = participant_id
    st.caption(bpm_status)

    workout_summary = build_workout_summary(merged_df)
    if workout_summary.empty:
        st.warning("Your Spotify and Strava data were combined, but no BPM values could be found for the matched tracks yet.")
        st.metric("Matched Workout Tracks", f"{len(merged_df):,}")
        return

    st.session_state.workout_bpm_summary_df = workout_summary

    hr_corr, hr_insight = correlation_sentence(
        workout_summary,
        x_column="average_track_bpm",
        y_column="average_heart_rate",
        subject="heart rate",
    )
    st.info(hr_insight)

    fig_hr = px.scatter(
        workout_summary,
        x="average_track_bpm",
        y="average_heart_rate",
        color="workout_type",
        trendline="ols" if len(workout_summary.dropna(subset=["average_track_bpm", "average_heart_rate"])) >= 2 else None,
        hover_data=["workout_name", "tracks_matched", "music_minutes"],
        title="Heart Rate vs Average Track BPM",
        labels={"average_track_bpm": "Average Track BPM", "average_heart_rate": "Average Heart Rate"},
        color_discrete_sequence=[STRAVA_ORANGE, SPOTIFY_GREEN, "#60A5FA", "#F59E0B", "#A78BFA"],
    )
    apply_chart_style(fig_hr)
    st.plotly_chart(fig_hr, use_container_width=True)

    duration_corr, duration_insight = correlation_sentence(
        workout_summary,
        x_column="average_track_bpm",
        y_column="workout_duration_minutes",
        subject="workout duration",
    )
    st.info(duration_insight)

    fig_duration = px.scatter(
        workout_summary,
        x="average_track_bpm",
        y="workout_duration_minutes",
        size="average_heart_rate",
        color="workout_type",
        hover_data=["workout_name", "average_heart_rate", "tracks_matched"],
        title="Workout Duration vs Average Track BPM",
        labels={"average_track_bpm": "Average Track BPM", "workout_duration_minutes": "Workout Duration (minutes)"},
        color_discrete_sequence=[SPOTIFY_GREEN, STRAVA_ORANGE, "#60A5FA", "#F59E0B", "#A78BFA"],
    )
    apply_chart_style(fig_duration)
    st.plotly_chart(fig_duration, use_container_width=True)

    st.divider()
    reflection_text = st.text_area("What is your opinion on these data insights?")
    if st.button("Submit Reflection & Generate Playlists", type="primary"):
        save_participant_reflection(participant_id, reflection_text, correlation=hr_corr)
        st.session_state.current_page = "Optimized Playlists"
        st.rerun()
