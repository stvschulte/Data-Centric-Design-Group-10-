from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from bs4 import BeautifulSoup

from utils.db_handler import (
    fetch_spotify_tracks,
    fetch_strava_activities,
    save_participant_reflection,
)


SPOTIFY_GREEN = "#1DB954"
STRAVA_ORANGE = "#FC4C02"
PLACEHOLDER_CREDENTIALS = {
    "",
    "jouw-client-id",
    "jouw-client-secret",
    "your-client-id",
    "your-client-secret",
}
HR_ZONE_BANDS = [
    (60, 110, "rgba(128, 128, 128, 0.15)", "Z1 Recovery | music 60-95"),
    (110, 130, "rgba(46, 204, 113, 0.15)", "Z2 Endurance | music 90-120"),
    (130, 150, "rgba(241, 196, 15, 0.15)", "Z3 Tempo | music 115-135"),
    (150, 170, "rgba(230, 126, 34, 0.15)", "Z4 Threshold | music 125-150"),
    (170, 220, "rgba(231, 76, 60, 0.15)", "Z5 Max | music 140-170"),
]
GENRE_BPM_PRIORS = {
    # Practical genre tempo priors based on published DJ/production BPM ranges.
    # These are only used when a track-level BPM source is unavailable.
    "afro house": 122,
    "afrobeats": 115,
    "afrobeat": 115,
    "afro pop": 108,
    "afro fusion": 108,
    "amapiano": 113,
    "house": 124,
    "deep house": 122,
    "tech house": 126,
    "progressive house": 124,
    "melodic house": 123,
    "electro house": 128,
    "disco": 120,
    "dance": 124,
    "dance pop": 122,
    "edm": 128,
    "electronic": 124,
    "electronica": 120,
    "techno": 130,
    "melodic techno": 124,
    "trance": 138,
    "drum and bass": 174,
    "drum & bass": 174,
    "dnb": 174,
    "dubstep": 140,
    "garage": 130,
    "uk garage": 132,
    "hip hop": 98,
    "hip-hop": 98,
    "rap": 98,
    "drill": 145,
    "trap": 140,
    "lo fi": 82,
    "lo-fi": 82,
    "r&b": 92,
    "rnb": 92,
    "pop": 120,
    "rock": 120,
    "alternative": 118,
    "indie": 118,
    "metal": 130,
    "punk": 160,
    "reggaeton": 95,
    "latin": 100,
    "salsa": 100,
    "dancehall": 100,
    "funk": 105,
    "soul": 95,
    "jazz": 110,
    "classical": 90,
}


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
    """Read Spotify credentials from environment or Streamlit secrets."""
    client_id_keys = ("SPOTIPY_CLIENT_ID", "SPOTIFY_CLIENT_ID")
    client_secret_keys = ("SPOTIPY_CLIENT_SECRET", "SPOTIFY_CLIENT_SECRET")

    def clean_secret(value) -> str:
        value = str(value or "").strip().strip('"').strip("'")
        return "" if value in PLACEHOLDER_CREDENTIALS else value

    def read_dotenv_secret(key: str) -> str:
        dotenv_path = Path(".env")
        if not dotenv_path.exists():
            return ""

        for line in dotenv_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            dotenv_key, dotenv_value = stripped.split("=", 1)
            if dotenv_key.strip() == key:
                return clean_secret(dotenv_value)
        return ""

    def read_secret(key: str) -> str:
        value = os.getenv(key, "")
        if clean_secret(value):
            return clean_secret(value)

        try:
            secret_value = clean_secret(st.secrets.get(key, ""))
            if secret_value:
                return secret_value

            spotify_section = st.secrets.get("spotify", {})
            if isinstance(spotify_section, dict):
                section_key = key.replace("SPOTIPY_", "").replace("SPOTIFY_", "").lower()
                section_value = clean_secret(spotify_section.get(section_key, ""))
                if section_value:
                    return section_value
        except Exception:
            pass

        return read_dotenv_secret(key)

    def read_first(keys: tuple[str, ...]) -> str:
        for key in keys:
            value = read_secret(key)
            if value:
                return value
        return ""

    return read_first(client_id_keys), read_first(client_secret_keys)


def spotify_credentials_status(client_id: str, client_secret: str) -> str:
    if client_id and client_secret:
        return (
            "Spotify credentials detected. The app uses Spotify metadata when available, "
            "but BPM/audio_features may be blocked for Development Mode apps."
        )
    return (
        "Spotify credentials are missing or still set to placeholder values. "
        "Update `.streamlit/secrets.toml` with real values and restart Streamlit."
    )


def normalize_spotify_uri(value: str) -> str:
    value = str(value or "").strip()
    if value.startswith("spotify:track:"):
        return value
    if "open.spotify.com/track/" in value:
        track_id = value.split("/track/", 1)[1].split("?", 1)[0].strip()
        return f"spotify:track:{track_id}" if track_id else ""
    return ""


def to_utc_naive(series: pd.Series) -> pd.Series:
    # Timezone fix: Spotify timestamps are usually UTC and Strava exports can be
    # timezone-aware or timezone-naive. Parsing with utc=True aligns both onto
    # the same timeline, then tz_localize(None) avoids aware/naive comparisons.
    return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert("UTC").dt.tz_localize(None)


def prepare_valid_workout_windows(strava_df: pd.DataFrame) -> pd.DataFrame:
    strava = strava_df.copy()
    for column in ["standard_date", "standard_duration", "standard_hr", "standard_name", "standard_type"]:
        if column not in strava.columns:
            strava[column] = pd.NA

    strava["start_time"] = to_utc_naive(strava["standard_date"])
    strava["standard_duration"] = pd.to_numeric(strava["standard_duration"], errors="coerce")
    strava["standard_hr"] = pd.to_numeric(strava["standard_hr"], errors="coerce")

    # Track-level analysis needs a valid workout window and a valid average HR,
    # because that HR is assigned to every individual track played in the window.
    strava = strava.dropna(subset=["start_time", "standard_duration", "standard_hr"]).copy()
    strava = strava[strava["standard_duration"] > 0].copy()
    strava["end_time"] = strava["start_time"] + pd.to_timedelta(strava["standard_duration"], unit="s")
    strava["workout_id"] = range(1, len(strava) + 1)
    return strava.sort_values("start_time").reset_index(drop=True)


def workout_calendar_dates(workouts: pd.DataFrame) -> set:
    dates = set()
    for _, workout in workouts.iterrows():
        for day in pd.date_range(workout["start_time"].normalize(), workout["end_time"].normalize(), freq="D"):
            dates.add(day.date())
    return dates


def prepare_spotify_tracks(spotify_df: pd.DataFrame, workouts: pd.DataFrame) -> pd.DataFrame:
    spotify = spotify_df.copy()
    for column in ["ts", "track_name", "artist_name", "spotify_track_uri"]:
        if column not in spotify.columns:
            spotify[column] = pd.NA

    spotify["ts"] = to_utc_naive(spotify["ts"])
    spotify["track_name"] = spotify["track_name"].fillna("Unknown Track").replace("", "Unknown Track")
    spotify["artist_name"] = spotify["artist_name"].fillna("Unknown Artist").replace("", "Unknown Artist")
    spotify["spotify_track_uri"] = spotify["spotify_track_uri"].fillna("").apply(normalize_spotify_uri)
    spotify = spotify.dropna(subset=["ts", "track_name"]).copy()

    # Performance optimization: keep only Spotify rows from days where a workout
    # exists before doing interval matching or fetching any BPM data.
    workout_dates = workout_calendar_dates(workouts)
    if not workout_dates:
        return spotify.iloc[0:0].copy()

    spotify = spotify[spotify["ts"].dt.date.isin(workout_dates)].copy()
    return spotify.sort_values("ts").reset_index(drop=True)


def merge_tracks_into_workouts(spotify_df: pd.DataFrame, strava_df: pd.DataFrame) -> pd.DataFrame:
    workouts = prepare_valid_workout_windows(strava_df)
    if workouts.empty:
        return pd.DataFrame()

    spotify = prepare_spotify_tracks(spotify_df, workouts)
    if spotify.empty:
        return pd.DataFrame()

    spotify_times = spotify["ts"].to_numpy()
    rows = []
    for _, workout in workouts.iterrows():
        # Optimized interval merge: Spotify is sorted once, then searchsorted
        # finds the slice inside each workout window without scanning the full
        # listening history for every workout.
        start_idx = spotify_times.searchsorted(workout["start_time"].to_datetime64(), side="left")
        end_idx = spotify_times.searchsorted(workout["end_time"].to_datetime64(), side="right")
        matched_tracks = spotify.iloc[start_idx:end_idx]
        if matched_tracks.empty:
            continue

        for _, track in matched_tracks.iterrows():
            rows.append(
                {
                    "track_name": track.get("track_name", "Unknown Track"),
                    "artist_name": track.get("artist_name", "Unknown Artist"),
                    "spotify_track_uri": track.get("spotify_track_uri", ""),
                    "workout_name": workout.get("standard_name", "Unnamed Workout"),
                    "workout_type": workout.get("standard_type", "Unknown"),
                    "workout_start": workout["start_time"],
                    "track_time": track["ts"],
                    "standard_hr": workout["standard_hr"],
                    "standard_duration": workout["standard_duration"],
                    "ms_played": track.get("ms_played", 0),
                }
            )

    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def fetch_audio_features(track_uris: tuple[str, ...], client_id: str, client_secret: str) -> tuple[dict[str, float], str]:
    """Fetch Spotify tempo values in batches of 100 and cache by URI + credentials."""
    if not track_uris:
        return {}, ""
    if not client_id or not client_secret:
        return {}, "Spotify client credentials are not configured, so BPM values cannot be fetched."

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials

        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        spotify_client = spotipy.Spotify(
            client_credentials_manager=auth_manager,
            requests_timeout=10,
            retries=0,
            status_retries=0,
        )

        tempo_by_uri = {}
        for start in range(0, len(track_uris), 100):
            batch = list(track_uris[start : start + 100])
            features = spotify_client.audio_features(batch)
            for uri, feature in zip(batch, features):
                if feature and feature.get("tempo") is not None:
                    tempo_by_uri[uri] = float(feature["tempo"])
        return tempo_by_uri, ""
    except Exception as exc:
        error_text = str(exc)
        if "403" in error_text and "audio-features" in error_text:
            return {}, (
                "Spotify returned 403 for audio_features. This app can search tracks, "
                "but Spotify does not allow this Development Mode app to read BPM/audio features."
            )
        return {}, error_text.splitlines()[0][:240]


def normalize_match_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", value)
    value = re.sub(r"\b(feat|featuring|ft|explicit|clean)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def run_pair_lookups_in_parallel(
    pairs: list[tuple[str, str]],
    lookup_func,
    max_workers: int = 8,
) -> dict[tuple[str, str], object]:
    if not pairs:
        return {}

    results = {}
    worker_count = max(1, min(max_workers, len(pairs)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_by_pair = {executor.submit(lookup_func, pair): pair for pair in pairs}
        for future in as_completed(future_by_pair):
            pair = future_by_pair[future]
            try:
                results[pair] = future.result()
            except Exception:
                results[pair] = None
    return results


def songbpm_slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    value = value.replace("&", " and ")
    value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", value)
    value = re.sub(r"['’]", "", value)
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def match_genre_bpm_values(genres: list[str]) -> list[tuple[str, float]]:
    matches = []
    for genre in genres or []:
        normalized_genre = normalize_match_text(genre)
        for genre_key, bpm in sorted(GENRE_BPM_PRIORS.items(), key=lambda item: len(item[0]), reverse=True):
            if normalize_match_text(genre_key) in normalized_genre:
                matches.append((genre_key, float(bpm)))
    return matches


def normalize_genre_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return [part.strip() for part in re.split(r"[,;/|]", stripped) if part.strip()]
    return []


def genre_derived_bpm(genres: list[str], max_genres: int = 3) -> tuple[float | None, str]:
    clean_genres = normalize_genre_list(genres)
    matches = match_genre_bpm_values(clean_genres)
    if not matches:
        return None, ""

    deduped = []
    seen = set()
    for genre_key, bpm in matches:
        if genre_key in seen:
            continue
        seen.add(genre_key)
        deduped.append((genre_key, bpm))
        if len(deduped) >= max_genres:
            break

    bpm_value = float(np.mean([bpm for _, bpm in deduped]))
    label = ", ".join(genre for genre, _ in deduped)
    source_label = ", ".join(clean_genres[:max_genres])
    return bpm_value, f"Genre-derived BPM ({label}) from genre metadata: {source_label}"


def best_match_score(left: str, right: str) -> float:
    left_clean = normalize_match_text(left)
    right_clean = normalize_match_text(right)
    if not left_clean or not right_clean:
        return 0.0
    score = SequenceMatcher(None, left_clean, right_clean).ratio()
    if left_clean in right_clean or right_clean in left_clean:
        score = max(score, 0.92)
    return score


@st.cache_data(show_spinner=False)
def fetch_itunes_track_genres(track_name: str, artist_name: str) -> tuple[list[str], str]:
    """Fetch track genre metadata from the public iTunes Search API.

    This gives us a non-Spotify genre source when Spotify search is rate-limited
    and audio_features are unavailable. The returned genre is still metadata,
    not a guessed BPM from the title.
    """
    clean_track = str(track_name or "").strip()
    clean_artist = str(artist_name or "").strip()
    if not clean_track:
        return [], ""

    query = f"{clean_track} {clean_artist}".strip()
    try:
        url = f"https://itunes.apple.com/search?term={quote_plus(query)}&entity=song&limit=5"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=3) as response:
            payload = json.load(response)
    except Exception:
        return [], ""

    best_item = None
    best_score = 0.0
    for item in payload.get("results", []):
        track_score = best_match_score(clean_track, item.get("trackName", ""))
        artist_score = best_match_score(clean_artist, item.get("artistName", "")) if clean_artist else 0.9
        score = (track_score * 0.68) + (artist_score * 0.32)
        if score > best_score:
            best_score = score
            best_item = item

    if not best_item or best_score < 0.72:
        return [], ""

    genres = []
    primary_genre = str(best_item.get("primaryGenreName") or "").strip()
    if primary_genre:
        genres.append(primary_genre)

    return genres, f"iTunes genre metadata: {primary_genre}" if genres else ""


def song_title_variants(track_name: str) -> list[str]:
    variants = []

    def add(value: str) -> None:
        value = str(value or "").strip()
        if value and value not in variants:
            variants.append(value)

    add(track_name)
    add(re.sub(r"\([^)]*\)|\[[^]]*\]", "", str(track_name)))
    if " - " in str(track_name):
        parts = [part.strip() for part in str(track_name).split(" - ") if part.strip()]
        add("-".join(parts))
        add(parts[0])
    add(re.sub(r"\s+-\s+", " ", str(track_name)))
    return variants


@st.cache_data(show_spinner=False)
def fetch_songbpm_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=3) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_songbpm_detail_page(html: str, track_name: str, artist_name: str) -> tuple[float, str] | None:
    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    match = re.search(r"BPM and key for (.*?) by (.*?) \|", page_title)
    page_track = match.group(1) if match else page_title
    page_artist = match.group(2) if match else ""

    track_score = SequenceMatcher(None, normalize_match_text(track_name), normalize_match_text(page_track)).ratio()
    artist_score = (
        SequenceMatcher(None, normalize_match_text(artist_name), normalize_match_text(page_artist)).ratio()
        if page_artist
        else 1
    )
    if track_score < 0.78 or artist_score < 0.65:
        return None

    text = soup.get_text("\n", strip=True)
    canonical_match = re.search(r"is a\s*\n?(\d+(?:\.\d+)?)\s*BPM", text, re.IGNORECASE)
    if canonical_match:
        bpm = float(canonical_match.group(1))
        return bpm, f"SongBPM detail page: {page_track}"

    bpm_values = [float(value) for value in re.findall(r"(?<!\d)(\d{2,3}(?:\.\d+)?)\s*BPM", text)]
    bpm_values = [value for value in bpm_values if 40 <= value <= 220]
    if bpm_values:
        return bpm_values[0], f"SongBPM detail page: {page_track}"
    return None


def parse_songbpm_artist_rows(html: str, artist_name: str) -> tuple[list[dict], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    artist_clean = normalize_match_text(artist_name)
    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True)
        bpm_match = re.search(r"\bBPM\s+(\d+(?:\.\d+)?)\b", text)
        if not bpm_match:
            continue

        title = text
        if normalize_match_text(title).startswith(artist_clean):
            title = title[len(str(artist_name)) :].strip()
        title = re.split(r"\bKey\b|\bDuration\b|\bBPM\b", title)[0].strip()
        rows.append(
            {
                "title": title,
                "clean_title": normalize_match_text(title),
                "bpm": float(bpm_match.group(1)),
                "url": anchor.get("href", ""),
            }
        )

    next_link = None
    for anchor in soup.find_all("a", href=True):
        if anchor.get_text(" ", strip=True).lower() == "next":
            next_link = anchor["href"]
            break

    return rows, next_link


@st.cache_data(show_spinner=False)
def fetch_songbpm_bpm(track_name: str, artist_name: str, max_artist_pages: int = 1) -> tuple[float | None, str]:
    artist_slug = songbpm_slug(artist_name)
    if not artist_slug:
        return None, ""

    for variant in song_title_variants(track_name):
        title_slug = songbpm_slug(variant)
        if not title_slug:
            continue
        url = f"https://songbpm.com/@{artist_slug}/{title_slug}"
        try:
            parsed = parse_songbpm_detail_page(fetch_songbpm_html(url), track_name, artist_name)
        except Exception:
            parsed = None
        if parsed:
            bpm, source = parsed
            return bpm, source

    target = normalize_match_text(track_name)
    if not target:
        return None, ""

    best_match = None
    best_score = 0.0
    current_url = f"https://songbpm.com/@{artist_slug}"
    for _ in range(max_artist_pages):
        try:
            rows, next_link = parse_songbpm_artist_rows(fetch_songbpm_html(current_url), artist_name)
        except Exception:
            break

        for row in rows:
            row_title = row["clean_title"]
            score = SequenceMatcher(None, target, row_title).ratio()
            if len(target) >= 6 and len(row_title) >= 6 and (target in row_title or row_title in target):
                score = max(score, 0.93)
            if score > best_score:
                best_match = row
                best_score = score

        if best_match and best_score >= 0.86:
            return best_match["bpm"], f"SongBPM artist page: {best_match['title']}"
        if not next_link:
            break
        current_url = urljoin(current_url, next_link)

    if best_match and best_score >= 0.84:
        return best_match["bpm"], f"SongBPM artist page: {best_match['title']}"
    return None, ""


def fill_missing_tempos_from_songbpm(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    enriched = df.copy()
    if "bpm_source" not in enriched.columns:
        enriched["bpm_source"] = ""

    missing_mask = enriched["tempo"].isna()
    if not missing_mask.any():
        return enriched, ""

    pairs_df = enriched.loc[missing_mask, ["track_name", "artist_name"]].drop_duplicates()
    pairs = [(str(row.track_name), str(row.artist_name)) for row in pairs_df.itertuples(index=False)]

    def lookup(pair: tuple[str, str]) -> tuple[float | None, str]:
        return fetch_songbpm_bpm(pair[0], pair[1])

    lookup_results = run_pair_lookups_in_parallel(pairs, lookup)
    bpm_by_pair = {}
    source_by_pair = {}
    for pair_key, result in lookup_results.items():
        bpm, source = result if result else (None, "")
        bpm_by_pair[pair_key] = bpm
        source_by_pair[pair_key] = source

    for idx, row in enriched.loc[missing_mask].iterrows():
        pair_key = (str(row["track_name"]), str(row["artist_name"]))
        bpm = bpm_by_pair.get(pair_key)
        if bpm:
            enriched.at[idx, "tempo"] = bpm
            enriched.at[idx, "bpm_source"] = source_by_pair.get(pair_key, "SongBPM")

    found_count = sum(1 for bpm in bpm_by_pair.values() if bpm)
    if found_count:
        return enriched, f"SongBPM found BPM for {found_count:,} unique matched track(s)."
    return enriched, "SongBPM did not return BPM for the matched tracks."


@st.cache_data(show_spinner=False)
def fetch_deezer_bpm(track_name: str, artist_name: str) -> float | None:
    """Best-effort public BPM fallback.

    Deezer does not expose BPM for every commercial track, so this is only used
    after Spotify audio_features fails or returns no tempo values.
    """
    clean_track = str(track_name or "").strip()
    clean_artist = str(artist_name or "").strip()
    if not clean_track:
        return None

    queries = [f'track:"{clean_track}" artist:"{clean_artist}"']
    if clean_artist and clean_artist != "Unknown":
        queries.append(f"{clean_track} {clean_artist}")
    else:
        queries.append(clean_track)

    for query in queries:
        try:
            search_url = f"https://api.deezer.com/search/track?q={quote_plus(query)}&limit=1"
            request = Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=3) as response:
                payload = json.load(response)

            items = payload.get("data", [])
            if not items:
                continue

            track_id = items[0].get("id")
            if not track_id:
                continue

            detail_request = Request(f"https://api.deezer.com/track/{track_id}", headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(detail_request, timeout=3) as response:
                detail = json.load(response)

            bpm = float(detail.get("bpm") or 0)
            if bpm > 0:
                return bpm
        except Exception:
            continue

    return None


def fill_missing_tempos_from_deezer(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    enriched = df.copy()
    if "bpm_source" not in enriched.columns:
        enriched["bpm_source"] = ""

    missing_mask = enriched["tempo"].isna()
    if not missing_mask.any():
        return enriched, ""

    pairs_df = enriched.loc[missing_mask, ["track_name", "artist_name"]].drop_duplicates()
    pairs = [(str(row.track_name), str(row.artist_name)) for row in pairs_df.itertuples(index=False)]

    def lookup(pair: tuple[str, str]) -> float | None:
        return fetch_deezer_bpm(pair[0], pair[1])

    bpm_by_pair = run_pair_lookups_in_parallel(pairs, lookup)

    for idx, row in enriched.loc[missing_mask].iterrows():
        bpm = bpm_by_pair.get((str(row["track_name"]), str(row["artist_name"])))
        if bpm:
            enriched.at[idx, "tempo"] = bpm
            enriched.at[idx, "bpm_source"] = "Deezer"

    found_count = sum(1 for bpm in bpm_by_pair.values() if bpm)
    if found_count:
        return enriched, f"Deezer fallback found BPM for {found_count:,} unique matched track(s)."
    return enriched, "Deezer fallback did not return BPM for the matched tracks."


@st.cache_data(show_spinner=False)
def fetch_spotify_track_metadata(
    track_uris: tuple[str, ...],
    client_id: str,
    client_secret: str,
) -> tuple[dict[str, dict], str]:
    """Fetch metadata that is still available to this Development Mode app.

    The bulk /tracks endpoint returns 403 for this app, but individual /track/{id}
    calls are currently allowed. Cache the result so the 70 unique matched tracks
    are only resolved once.
    """
    if not track_uris:
        return {}, ""
    if not client_id or not client_secret:
        return {}, "Spotify client credentials are not configured, so track metadata cannot be fetched."

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials

        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        spotify_client = spotipy.Spotify(
            client_credentials_manager=auth_manager,
            requests_timeout=10,
            retries=0,
            status_retries=0,
        )

        metadata_by_uri = {}
        for uri in track_uris:
            track_id = uri.rsplit(":", 1)[-1]
            track = spotify_client.track(track_id)
            album = track.get("album", {}) or {}
            release_year = pd.to_datetime(album.get("release_date"), errors="coerce")
            artist_genres = []
            artist_items = track.get("artists", []) or []
            if artist_items:
                artist_id = artist_items[0].get("id")
                if artist_id:
                    try:
                        artist_genres = spotify_client.artist(artist_id).get("genres", []) or []
                    except Exception:
                        artist_genres = []
            metadata_by_uri[uri] = {
                "spotify_popularity": track.get("popularity"),
                "spotify_duration_ms": track.get("duration_ms"),
                "spotify_release_year": None if pd.isna(release_year) else release_year.year,
                "spotify_album": album.get("name", ""),
                "spotify_explicit": bool(track.get("explicit", False)),
                "spotify_artist_genres": artist_genres,
            }
        return metadata_by_uri, ""
    except Exception as exc:
        return {}, str(exc).splitlines()[0][:240]


def add_spotify_metadata(df: pd.DataFrame, client_id: str, client_secret: str) -> tuple[pd.DataFrame, str]:
    enriched = df.copy()
    unique_uris = tuple(sorted(uri for uri in enriched["spotify_track_uri"].dropna().unique() if uri))
    metadata_by_uri, error_message = fetch_spotify_track_metadata(unique_uris, client_id, client_secret)

    enriched["spotify_popularity"] = enriched["spotify_track_uri"].map(
        lambda uri: metadata_by_uri.get(uri, {}).get("spotify_popularity")
    )
    enriched["spotify_duration_ms"] = enriched["spotify_track_uri"].map(
        lambda uri: metadata_by_uri.get(uri, {}).get("spotify_duration_ms")
    )
    enriched["spotify_release_year"] = enriched["spotify_track_uri"].map(
        lambda uri: metadata_by_uri.get(uri, {}).get("spotify_release_year")
    )
    enriched["spotify_album"] = enriched["spotify_track_uri"].map(
        lambda uri: metadata_by_uri.get(uri, {}).get("spotify_album", "")
    )
    enriched["spotify_explicit"] = enriched["spotify_track_uri"].map(
        lambda uri: metadata_by_uri.get(uri, {}).get("spotify_explicit")
    )
    enriched["spotify_artist_genres"] = enriched["spotify_track_uri"].map(
        lambda uri: metadata_by_uri.get(uri, {}).get("spotify_artist_genres", [])
    )
    enriched["genre_labels"] = enriched["spotify_artist_genres"].apply(normalize_genre_list)
    enriched["genre_source"] = enriched["genre_labels"].apply(lambda genres: "Spotify artist genres" if genres else "")
    enriched["spotify_popularity"] = pd.to_numeric(enriched["spotify_popularity"], errors="coerce")
    enriched["spotify_duration_minutes"] = pd.to_numeric(enriched["spotify_duration_ms"], errors="coerce") / 60000
    enriched["spotify_release_year"] = pd.to_numeric(enriched["spotify_release_year"], errors="coerce")

    if metadata_by_uri:
        return enriched, f"Fetched Spotify metadata for {len(metadata_by_uri):,} unique track(s)."
    if error_message:
        return enriched, f"Spotify metadata lookup failed: {error_message}"
    return enriched, "No Spotify metadata could be fetched."


def fill_missing_genres_from_itunes(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    enriched = df.copy()
    if "genre_labels" not in enriched.columns:
        enriched["genre_labels"] = [[] for _ in range(len(enriched))]
    if "genre_source" not in enriched.columns:
        enriched["genre_source"] = ""

    missing_genre_mask = (
        enriched["genre_labels"].apply(lambda value: len(normalize_genre_list(value)) == 0)
        & enriched["tempo"].isna()
    )
    if not missing_genre_mask.any():
        return enriched, ""

    pairs_df = enriched.loc[missing_genre_mask, ["track_name", "artist_name"]].drop_duplicates()
    pairs = [(str(row.track_name), str(row.artist_name)) for row in pairs_df.itertuples(index=False)]

    def lookup(pair: tuple[str, str]) -> tuple[list[str], str]:
        return fetch_itunes_track_genres(pair[0], pair[1])

    lookup_results = run_pair_lookups_in_parallel(pairs, lookup)
    genres_by_pair = {}
    source_by_pair = {}
    for pair_key, result in lookup_results.items():
        genres, source = result if result else ([], "")
        genres_by_pair[pair_key] = genres
        source_by_pair[pair_key] = source

    filled_pairs = set()
    for idx, row in enriched.loc[missing_genre_mask].iterrows():
        pair_key = (str(row["track_name"]), str(row["artist_name"]))
        genres = genres_by_pair.get(pair_key, [])
        if genres:
            enriched.at[idx, "genre_labels"] = genres
            enriched.at[idx, "genre_source"] = source_by_pair.get(pair_key, "iTunes genre metadata")
            filled_pairs.add(pair_key)

    if filled_pairs:
        return enriched, f"iTunes/Apple genre metadata found genres for {len(filled_pairs):,} unique matched track(s)."
    return enriched, "iTunes/Apple genre metadata did not find usable genres for the remaining matched tracks."


def fill_missing_tempos_from_genres(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    enriched = df.copy()
    if "bpm_source" not in enriched.columns:
        enriched["bpm_source"] = ""
    if "genre_labels" not in enriched.columns:
        enriched["genre_labels"] = [[] for _ in range(len(enriched))]

    missing_mask = enriched["tempo"].isna()
    if not missing_mask.any():
        return enriched, ""

    filled_pairs = set()
    for idx, row in enriched.loc[missing_mask].iterrows():
        genre_labels = normalize_genre_list(row.get("genre_labels", []))
        if not genre_labels:
            genre_labels = normalize_genre_list(row.get("spotify_artist_genres", []))

        bpm, source = genre_derived_bpm(genre_labels)
        if bpm:
            enriched.at[idx, "tempo"] = bpm
            genre_source = str(row.get("genre_source") or "genre metadata")
            enriched.at[idx, "bpm_source"] = f"{source} [{genre_source}]"
            filled_pairs.add((str(row.get("track_name")), str(row.get("artist_name"))))

    if filled_pairs:
        return enriched, f"Genre-derived fallback assigned BPM for {len(filled_pairs):,} unique matched track(s)."
    return enriched, "Genre-derived fallback did not match available genre metadata to known BPM priors."


@st.cache_data(show_spinner=False)
def resolve_spotify_track_uris(
    track_artist_pairs: tuple[tuple[str, str], ...],
    client_id: str,
    client_secret: str,
) -> tuple[dict[tuple[str, str], str], str]:
    """Resolve missing Spotify URIs for matched workout tracks only.

    Many Spotify history exports do not include spotify_track_uri. Searching the
    full listening history would be slow, so this cached fallback only searches
    unique track/artist pairs that were actually played during workouts.
    """
    if not track_artist_pairs:
        return {}, ""
    if not client_id or not client_secret:
        return {}, "Spotify client credentials are not configured, so track URIs and BPM values cannot be fetched."

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials

        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        spotify_client = spotipy.Spotify(
            client_credentials_manager=auth_manager,
            requests_timeout=10,
            retries=0,
            status_retries=0,
        )

        uri_by_pair = {}
        for track_name, artist_name in track_artist_pairs:
            clean_track = str(track_name or "").strip()
            clean_artist = str(artist_name or "").strip()
            if not clean_track:
                uri_by_pair[(track_name, artist_name)] = ""
                continue

            queries = [f'track:"{clean_track}" artist:"{clean_artist}"']
            if clean_artist and clean_artist != "Unknown":
                queries.append(f"{clean_track} {clean_artist}")
            else:
                queries.append(clean_track)

            resolved_uri = ""
            for query in queries:
                result = spotify_client.search(q=query, type="track", limit=1)
                items = result.get("tracks", {}).get("items", [])
                if items:
                    resolved_uri = items[0].get("uri", "")
                    break
            uri_by_pair[(track_name, artist_name)] = resolved_uri

        return uri_by_pair, ""
    except Exception as exc:
        return {}, str(exc)


def fill_missing_spotify_uris(df: pd.DataFrame, client_id: str, client_secret: str) -> tuple[pd.DataFrame, str]:
    resolved = df.copy()
    missing_uri_mask = resolved["spotify_track_uri"].fillna("").astype(str).str.strip().eq("")
    if not missing_uri_mask.any():
        return resolved, ""

    pairs_df = resolved.loc[missing_uri_mask, ["track_name", "artist_name"]].drop_duplicates()
    track_artist_pairs = tuple((str(row.track_name), str(row.artist_name)) for row in pairs_df.itertuples(index=False))
    uri_by_pair, error_message = resolve_spotify_track_uris(track_artist_pairs, client_id, client_secret)
    if uri_by_pair:
        for idx, row in resolved.loc[missing_uri_mask].iterrows():
            resolved.at[idx, "spotify_track_uri"] = uri_by_pair.get((str(row["track_name"]), str(row["artist_name"])), "")

    resolved_count = sum(1 for uri in uri_by_pair.values() if uri)
    if resolved_count:
        return resolved, f"Resolved Spotify URIs for {resolved_count:,} matched track(s)."
    if error_message:
        return resolved, f"Spotify URI lookup failed: {error_message}"
    return resolved, "No Spotify URIs could be resolved for the matched tracks."


def add_track_tempos(track_df: pd.DataFrame, client_id: str, client_secret: str) -> tuple[pd.DataFrame, str]:
    df = track_df.copy()
    if "spotify_track_uri" not in df.columns:
        df["spotify_track_uri"] = ""
    df["spotify_track_uri"] = df["spotify_track_uri"].fillna("").astype(str)
    has_exported_uris = df["spotify_track_uri"].str.strip().ne("").any()
    uri_status = (
        "Using Spotify track URIs from the uploaded listening history."
        if has_exported_uris
        else "Spotify URI search skipped to avoid rate-limit blocking; no Spotify URIs were present in the upload."
    )
    df, metadata_status = add_spotify_metadata(df, client_id, client_secret)
    unique_uris = tuple(sorted(uri for uri in df["spotify_track_uri"].unique() if uri))

    tempo_by_uri, error_message = fetch_audio_features(unique_uris, client_id, client_secret)
    df["tempo"] = df["spotify_track_uri"].map(tempo_by_uri)
    df["tempo"] = pd.to_numeric(df["tempo"], errors="coerce")
    df["bpm_source"] = ""
    df.loc[df["tempo"].notna(), "bpm_source"] = "Spotify audio_features"
    df, songbpm_status = fill_missing_tempos_from_songbpm(df)
    df, deezer_status = fill_missing_tempos_from_deezer(df)
    df, itunes_genre_status = fill_missing_genres_from_itunes(df)
    df, genre_status = fill_missing_tempos_from_genres(df)
    df["track_bpm"] = df["tempo"]
    if "standard_hr" in df.columns:
        df["standard_hr"] = pd.to_numeric(df["standard_hr"], errors="coerce")

    status_parts = [
        status
        for status in [uri_status, metadata_status, songbpm_status, deezer_status, itunes_genre_status, genre_status]
        if status
    ]
    if tempo_by_uri:
        status_parts.append(f"Fetched BPM for {len(tempo_by_uri):,} unique Spotify tracks.")
    elif error_message:
        status_parts.append(f"Spotify BPM lookup failed: {error_message}")
    else:
        status_parts.append("No Spotify track URIs were available for BPM lookup.")
    return df, " ".join(status_parts)


def pearson_insight(
    track_df: pd.DataFrame,
    x_column: str = "tempo",
    x_label: str = "the BPM of your music",
) -> tuple[float | None, str]:
    paired = track_df[[x_column, "standard_hr"]].dropna()
    if len(paired) < 3 or paired[x_column].nunique() < 2 or paired["standard_hr"].nunique() < 2:
        return None, f"Based on {len(paired):,} tracks analyzed, there is not enough variation to calculate a reliable correlation."

    correlation = paired[x_column].corr(paired["standard_hr"])
    if pd.isna(correlation):
        return None, f"Based on {len(paired):,} tracks analyzed, there is not enough variation to calculate a reliable correlation."

    abs_corr = abs(correlation)
    if abs_corr < 0.2:
        strength = "very weak"
    elif abs_corr < 0.4:
        strength = "weak"
    elif abs_corr < 0.6:
        strength = "moderate"
    elif abs_corr < 0.8:
        strength = "strong"
    else:
        strength = "very strong"

    direction = "positive" if correlation > 0 else "negative"
    return (
        float(correlation),
        f"Based on {len(paired):,} tracks analyzed, there is a {strength} {direction} correlation ({correlation:+.2f}) between {x_label} and your average heart rate.",
    )


def compact_bpm_source(source: str) -> str:
    source = str(source or "Unknown")
    if source.startswith("Spotify audio_features"):
        return "Spotify audio_features"
    if source.startswith("SongBPM"):
        return "SongBPM"
    if source.startswith("Deezer"):
        return "Deezer"
    if source.startswith("Genre-derived BPM"):
        return "Genre-derived BPM"
    return source


def tempo_axis_range(track_df: pd.DataFrame) -> list[float]:
    tempo = pd.to_numeric(track_df["tempo"], errors="coerce").dropna()
    if tempo.empty:
        return [80, 180]
    return [float(max(0, min(80, tempo.min() - 8))), float(max(180, tempo.max() + 8))]


def add_ols_trendline(fig: go.Figure, track_df: pd.DataFrame, x_column: str) -> None:
    paired = track_df[[x_column, "standard_hr"]].dropna().sort_values(x_column)
    if len(paired) < 3 or paired[x_column].nunique() < 2 or paired["standard_hr"].nunique() < 2:
        return

    slope, intercept = np.polyfit(paired[x_column], paired["standard_hr"], 1)
    x_values = paired[x_column]
    y_values = slope * x_values + intercept
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines",
            name="OLS trendline",
            line=dict(color="#ffffff", width=3),
            hoverinfo="skip",
        )
    )


def render_track_level_scatter(track_df: pd.DataFrame) -> None:
    plot_df = track_df.copy()
    plot_df["bpm_source_display"] = plot_df["bpm_source"].apply(compact_bpm_source)

    fig = go.Figure()
    for y0, y1, fillcolor, annotation_text in HR_ZONE_BANDS:
        fig.add_hrect(
            y0=y0,
            y1=y1,
            fillcolor=fillcolor,
            line_width=0,
            layer="below",
            annotation_text=annotation_text,
            annotation_position="right",
            annotation_font_color="rgba(255,255,255,0.70)",
            annotation_font_size=12,
        )

    fig.add_trace(
        go.Scatter(
            x=plot_df["tempo"],
            y=plot_df["standard_hr"],
            mode="markers",
            name="Workout tracks",
            marker=dict(
                color=SPOTIFY_GREEN,
                size=8,
                opacity=0.7,
                line=dict(color="rgba(255,255,255,0.28)", width=1),
            ),
            customdata=plot_df[["track_name", "artist_name", "tempo", "workout_name", "bpm_source_display"]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]}<br>"
                "Track BPM: %{customdata[2]:.0f}<br>"
                "BPM source: %{customdata[4]}<br>"
                "Workout: %{customdata[3]}<br>"
                "Workout Avg HR: %{y:.0f} BPM"
                "<extra></extra>"
            ),
        )
    )
    add_ols_trendline(fig, plot_df, "tempo")

    fig.update_layout(
        template="plotly_dark",
        height=560,
        title="Track BPM vs Workout Average Heart Rate",
        font=dict(color="white", size=14),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=74, b=10),
        hoverlabel=dict(bgcolor="rgba(15,23,42,0.96)", font=dict(color="white")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(
        title="Track BPM",
        range=tempo_axis_range(plot_df),
        showgrid=True,
        gridcolor="rgba(255,255,255,0.10)",
    )
    fig.update_yaxes(
        title="Workout Average Heart Rate",
        range=[60, 220],
        showgrid=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def metadata_axis_range(track_df: pd.DataFrame, x_column: str) -> list[float]:
    values = pd.to_numeric(track_df[x_column], errors="coerce").dropna()
    if values.empty:
        return [0, 100]
    if x_column == "spotify_popularity":
        return [0, 100]
    return [float(max(0, values.min() - 1)), float(values.max() + 1)]


def render_metadata_scatter(track_df: pd.DataFrame, x_column: str, x_title: str, chart_title: str) -> None:
    plot_df = track_df.dropna(subset=[x_column, "standard_hr"]).copy()
    fig = go.Figure()
    for y0, y1, fillcolor, annotation_text in HR_ZONE_BANDS:
        fig.add_hrect(
            y0=y0,
            y1=y1,
            fillcolor=fillcolor,
            line_width=0,
            layer="below",
            annotation_text=annotation_text,
            annotation_position="right",
            annotation_font_color="rgba(255,255,255,0.70)",
            annotation_font_size=12,
        )

    fig.add_trace(
        go.Scatter(
            x=plot_df[x_column],
            y=plot_df["standard_hr"],
            mode="markers",
            name="Workout tracks",
            marker=dict(
                color=STRAVA_ORANGE,
                size=8,
                opacity=0.7,
                line=dict(color="rgba(255,255,255,0.28)", width=1),
            ),
            customdata=plot_df[["track_name", "artist_name", x_column, "workout_name"]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]}<br>"
                f"{x_title}: %{{customdata[2]}}<br>"
                "Workout: %{customdata[3]}<br>"
                "Workout Avg HR: %{y:.0f} BPM"
                "<extra></extra>"
            ),
        )
    )
    add_ols_trendline(fig, plot_df, x_column)
    fig.update_layout(
        template="plotly_dark",
        height=560,
        title=chart_title,
        font=dict(color="white", size=14),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=74, b=10),
        hoverlabel=dict(bgcolor="rgba(15,23,42,0.96)", font=dict(color="white")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(
        title=x_title,
        range=metadata_axis_range(plot_df, x_column),
        showgrid=True,
        gridcolor="rgba(255,255,255,0.10)",
    )
    fig.update_yaxes(
        title="Workout Average Heart Rate",
        range=[60, 220],
        showgrid=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def choose_metadata_fallback(enriched_df: pd.DataFrame) -> tuple[str, str, str, str] | None:
    candidates = [
        (
            "spotify_popularity",
            "Spotify Track Popularity",
            "Spotify Track Popularity vs Workout Average Heart Rate",
            "Spotify track popularity",
        ),
        (
            "spotify_duration_minutes",
            "Track Duration (minutes)",
            "Spotify Track Duration vs Workout Average Heart Rate",
            "Spotify track duration",
        ),
        (
            "spotify_release_year",
            "Track Release Year",
            "Spotify Track Release Year vs Workout Average Heart Rate",
            "Spotify track release year",
        ),
    ]
    for x_column, x_title, chart_title, insight_label in candidates:
        if x_column not in enriched_df.columns:
            continue
        valid = enriched_df[[x_column, "standard_hr"]].dropna()
        if len(valid) >= 3 and valid[x_column].nunique() >= 2:
            return x_column, x_title, chart_title, insight_label
    return None


def render_combined_insights() -> None:
    inject_combined_css()
    st.markdown(
        """
        <section class="combined-hero">
            <h1>Combined Music x Workout Insights</h1>
            <p>Every song played inside a Strava workout window is mapped to that workout's average heart rate.</p>
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

    with st.spinner("Matching workout tracks and fetching BPM values..."):
        merged_df = merge_tracks_into_workouts(spotify_df, strava_df)
        if merged_df.empty:
            st.warning(
                "No Spotify tracks were found inside Strava workout windows with valid average heart-rate data. "
                "Check whether the Spotify and Strava export dates overlap."
            )
            return

        client_id, client_secret = get_configured_spotify_credentials()
        credential_status = spotify_credentials_status(client_id, client_secret)
        enriched_df, bpm_status = add_track_tempos(merged_df, client_id, client_secret)

    st.session_state.augmented_music_workout_df = enriched_df
    st.session_state.augmented_music_workout_participant_id = participant_id
    st.caption(credential_status)
    st.caption(bpm_status)

    if enriched_df.empty or enriched_df["standard_hr"].dropna().empty:
        st.warning(
            "Tracks were matched to workouts, but no usable Spotify metadata or heart-rate values were available for charting."
        )
        st.metric("Matched Workout Tracks", f"{len(merged_df):,}")
        return

    bpm_df = enriched_df.dropna(subset=["tempo", "standard_hr"]).copy()
    metadata_fallback = choose_metadata_fallback(enriched_df)
    if len(bpm_df) < 3 and metadata_fallback is None:
        st.warning(
            "Tracks were matched to workouts, but the available Spotify endpoints did not return enough chartable BPM or metadata values."
        )
        st.metric("Matched Workout Tracks", f"{len(merged_df):,}")
        return

    col_tracks, col_workouts, col_bpm = st.columns(3)
    col_tracks.metric("Matched Workout Tracks", f"{len(merged_df):,}")
    col_workouts.metric("Workouts With Music", f"{enriched_df['workout_name'].nunique():,}")
    if len(bpm_df) >= 3:
        col_bpm.metric("Tracks With BPM", f"{len(bpm_df):,}")
        source_counts = bpm_df["bpm_source"].fillna("Unknown").apply(compact_bpm_source).value_counts().to_dict()
        st.caption(
            "BPM sources used: "
            + "; ".join(f"{source}: {count}" for source, count in list(source_counts.items())[:6])
        )
        if source_counts.get("Genre-derived BPM"):
            st.caption(
                "Genre-derived BPM uses metadata genres first, then averages up to three matching genre tempo priors for that track."
            )
        render_track_level_scatter(bpm_df)
        correlation, insight_text = pearson_insight(bpm_df)
    else:
        x_column, x_title, chart_title, insight_label = metadata_fallback
        metadata_df = enriched_df.dropna(subset=[x_column, "standard_hr"]).copy()
        col_bpm.metric("Tracks With BPM", f"{len(bpm_df):,}")
        st.warning(
            "Spotify blocks BPM/audio_features for this Development Mode app, and the configured BPM fallbacks only found "
            f"{len(bpm_df):,} BPM-backed track(s). The chart below uses {x_title.lower()}, which this app can fetch."
        )
        render_metadata_scatter(
            metadata_df,
            x_column=x_column,
            x_title=x_title,
            chart_title=chart_title,
        )
        correlation, insight_text = pearson_insight(
            metadata_df,
            x_column=x_column,
            x_label=insight_label,
        )
    st.info(insight_text)

    st.divider()
    reflection_text = st.text_area("What is your opinion on these data insights?")
    if st.button("Submit Reflection & Generate Playlists", type="primary"):
        save_participant_reflection(participant_id, reflection_text, correlation=correlation)
        st.session_state.current_page = "Optimized Playlists"
        st.rerun()
