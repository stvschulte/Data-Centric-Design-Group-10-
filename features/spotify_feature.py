import html
import json
import os
import textwrap
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db_handler import log_spotify_upload, save_spotify_tracks


SPOTIFY_GREEN = "#1DB954"
REQUIRED_SPOTIFY_COLUMNS = [
    "ts",
    "master_metadata_track_name",
    "master_metadata_album_artist_name",
    "ms_played",
]
OPTIONAL_SPOTIFY_COLUMNS = ["spotify_track_uri"]


def render_html(markup: str) -> None:
    """Render trusted local HTML/CSS without exposing the raw markup on screen."""
    cleaned_markup = textwrap.dedent(markup).strip()
    cleaned_markup = "\n".join(line.lstrip() for line in cleaned_markup.splitlines())
    st.markdown(cleaned_markup, unsafe_allow_html=True)


def inject_spotify_css() -> None:
    render_html(
        f"""
        <style>
        .stApp {{
            font-size: 18px;
            background:
                linear-gradient(90deg, rgba(4, 8, 6, 0.96), rgba(7, 20, 12, 0.90)),
                url("https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=1800&q=80");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #f8fafc;
        }}
        .stApp p, .stApp label, .stApp span, .stApp div {{
            font-size: 1.05rem;
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
            font-size: 56px;
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
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 16px 42px rgba(0,0,0,0.26);
        }}
        div[data-testid="stMetricLabel"] {{
            font-size: 1.08rem;
            color: #cbd5e1;
            font-weight: 700;
        }}
        div[data-testid="stMetricValue"] {{
            color: {SPOTIFY_GREEN};
            font-size: 2.35rem;
            font-weight: 850;
        }}
        .stButton > button, [data-testid="stFileUploader"] button {{
            border-color: {SPOTIFY_GREEN} !important;
            font-size: 1.05rem !important;
            font-weight: 750 !important;
        }}
        .spotify-section-title {{
            margin: 28px 0 14px;
            color: #ffffff;
            font-size: 1.55rem;
            font-weight: 850;
            letter-spacing: 0;
        }}
        .spotify-rankings-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 22px;
            margin: 22px 0 28px;
            width: 100%;
        }}
        .ranking-panel {{
            min-width: 0;
            padding: 22px;
            border-radius: 18px;
            background: rgba(5, 10, 7, 0.88);
            border: 1px solid rgba(29,185,84,0.24);
            box-shadow: 0 22px 64px rgba(0,0,0,0.36);
        }}
        .ranking-panel h2 {{
            margin: 0 0 18px;
            color: #ffffff;
            font-size: 1.45rem;
            font-weight: 850;
            letter-spacing: 0;
        }}
        .ranking-list {{
            display: flex;
            flex-direction: column;
            gap: 11px;
            align-items: stretch;
        }}
        .ranking-row {{
            position: relative;
            overflow: hidden;
            display: grid;
            grid-template-columns: 46px 58px minmax(0, 1fr) auto;
            align-items: center;
            gap: 14px;
            width: 91%;
            min-height: 74px;
            padding: 13px 16px;
            border-radius: 16px;
            background: rgba(15, 23, 18, 0.86);
            border: 1px solid rgba(255,255,255,0.08);
            transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
        }}
        .ranking-row::before {{
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: var(--bar-width);
            background: linear-gradient(90deg, rgba(29,185,84,0.18), rgba(29,185,84,0.02));
            pointer-events: none;
        }}
        .ranking-row > * {{
            position: relative;
            z-index: 1;
        }}
        .ranking-link {{
            display: contents;
            color: inherit;
            text-decoration: none;
        }}
        .ranking-link:hover {{
            color: inherit;
            text-decoration: none;
        }}
        .ranking-row:hover {{
            transform: translateX(4px);
            border-color: rgba(29,185,84,0.52);
            background: rgba(18, 32, 23, 0.92);
        }}
        .rank-number {{
            color: #ffffff;
            font-size: 1.18rem;
            font-weight: 850;
            text-align: center;
        }}
        .ranking-image {{
            width: 58px;
            height: 58px;
            border-radius: 14px;
            object-fit: cover;
            background: #0f172a;
            box-shadow: 0 10px 24px rgba(0,0,0,0.30);
        }}
        .artist-image {{
            border-radius: 50%;
        }}
        .ranking-copy {{
            min-width: 0;
        }}
        .ranking-name {{
            color: #ffffff;
            font-size: 1.05rem;
            font-weight: 800;
            line-height: 1.25;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .ranking-subtitle {{
            margin-top: 4px;
            color: #94a3b8;
            font-size: 0.92rem;
            font-weight: 650;
        }}
        .ranking-stat {{
            justify-self: end;
            color: #d8f8e3;
            font-size: 1rem;
            font-weight: 850;
            white-space: nowrap;
            text-align: right;
        }}
        .ranking-stat span {{
            display: block;
            color: #94a3b8;
            font-size: 0.82rem;
            font-weight: 650;
            margin-top: 3px;
        }}
        .ranking-row.rank-1 {{
            width: 100%;
            min-height: 104px;
            padding: 20px 20px;
            grid-template-columns: 58px 74px minmax(0, 1fr) auto;
            background: linear-gradient(135deg, rgba(29,185,84,0.24), rgba(234,179,8,0.18)), rgba(8, 13, 10, 0.96);
            border: 1px solid rgba(234,179,8,0.54);
            box-shadow: 0 0 34px rgba(29,185,84,0.20), inset 4px 0 0 rgba(234,179,8,0.92);
        }}
        .ranking-row.rank-1 .ranking-image {{
            width: 74px;
            height: 74px;
        }}
        .ranking-row.rank-1 .rank-number {{
            color: #facc15;
            font-size: 1.55rem;
        }}
        .ranking-row.rank-1 .ranking-name {{
            font-size: 1.3rem;
            font-weight: 900;
        }}
        .ranking-row.rank-1 .ranking-stat {{
            color: #ffffff;
            font-size: 1.15rem;
        }}
        .ranking-row.rank-2 {{
            width: 97%;
            min-height: 94px;
            padding: 18px 19px;
            grid-template-columns: 54px 68px minmax(0, 1fr) auto;
            background: linear-gradient(135deg, rgba(148,163,184,0.22), rgba(29,185,84,0.13)), rgba(9, 14, 11, 0.94);
            border: 1px solid rgba(203,213,225,0.40);
            box-shadow: inset 4px 0 0 rgba(203,213,225,0.82);
        }}
        .ranking-row.rank-2 .ranking-image {{
            width: 68px;
            height: 68px;
        }}
        .ranking-row.rank-2 .rank-number {{
            color: #e2e8f0;
            font-size: 1.42rem;
        }}
        .ranking-row.rank-2 .ranking-name {{
            font-size: 1.2rem;
            font-weight: 880;
        }}
        .ranking-row.rank-3 {{
            width: 94%;
            min-height: 86px;
            padding: 16px 18px;
            grid-template-columns: 50px 64px minmax(0, 1fr) auto;
            background: linear-gradient(135deg, rgba(180,83,9,0.22), rgba(29,185,84,0.10)), rgba(9, 14, 11, 0.92);
            border: 1px solid rgba(180,83,9,0.42);
            box-shadow: inset 4px 0 0 rgba(180,83,9,0.84);
        }}
        .ranking-row.rank-3 .ranking-image {{
            width: 64px;
            height: 64px;
        }}
        .ranking-row.rank-3 .rank-number {{
            color: #fb923c;
            font-size: 1.32rem;
        }}
        .ranking-row.rank-3 .ranking-name {{
            font-size: 1.13rem;
            font-weight: 850;
        }}
        @media (max-width: 1100px) {{
            .spotify-rankings-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        @media (max-width: 640px) {{
            .spotify-hero {{
                padding: 38px 24px;
            }}
            .spotify-hero h1 {{
                font-size: 38px;
            }}
            .ranking-panel {{
                padding: 16px;
            }}
            .ranking-row,
            .ranking-row.rank-1,
            .ranking-row.rank-2,
            .ranking-row.rank-3 {{
                width: 100%;
                grid-template-columns: 36px 52px minmax(0, 1fr);
                gap: 10px;
            }}
            .ranking-stat {{
                grid-column: 3;
                justify-self: start;
                margin-top: -4px;
            }}
            .ranking-row.rank-1 .ranking-image,
            .ranking-row.rank-2 .ranking-image,
            .ranking-row.rank-3 .ranking-image,
            .ranking-image {{
                width: 52px;
                height: 52px;
            }}
        }}
        </style>
        """
    )


def parse_spotify_json(uploaded_files) -> pd.DataFrame:
    """Parse Spotify history JSON and normalize it to the internal schema.

    Preferred Extended Streaming History source columns:
    - ts: track timestamp
    - master_metadata_track_name: track title
    - master_metadata_album_artist_name: artist
    - ms_played: listening duration in milliseconds

    Also supported: older StreamingHistory_music_*.json exports with:
    - endTime
    - trackName
    - artistName
    - msPlayed
    """
    rows = []
    for uploaded_file in uploaded_files:
        try:
            uploaded_file.seek(0)
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
    is_extended_history = set(REQUIRED_SPOTIFY_COLUMNS).issubset(raw_df.columns)
    legacy_columns = ["endTime", "trackName", "artistName", "msPlayed"]
    is_legacy_history = set(legacy_columns).issubset(raw_df.columns)

    if is_extended_history:
        columns = REQUIRED_SPOTIFY_COLUMNS + [
            column for column in OPTIONAL_SPOTIFY_COLUMNS if column in raw_df.columns
        ]
        df = raw_df[columns].copy()
    elif is_legacy_history:
        # Older Spotify exports use local endTime without timezone information.
        df = raw_df[legacy_columns].rename(
            columns={
                "endTime": "ts",
                "trackName": "master_metadata_track_name",
                "artistName": "master_metadata_album_artist_name",
                "msPlayed": "ms_played",
            }
        )
        st.info("Detected Spotify Streaming History format and converted it for analysis.")
    else:
        st.error(
            "Spotify JSON is missing required columns. Expected either Extended History "
            "`ts`, `master_metadata_track_name`, `master_metadata_album_artist_name`, `ms_played` "
            "or Streaming History `endTime`, `trackName`, `artistName`, `msPlayed`."
        )
        st.caption(f"Detected columns: {', '.join(raw_df.columns.astype(str).tolist())}")
        return pd.DataFrame(columns=REQUIRED_SPOTIFY_COLUMNS)

    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    if getattr(df["ts"].dt, "tz", None) is not None:
        df["ts"] = df["ts"].dt.tz_convert(None)

    # Drop podcasts, ads, local files, malformed rows, and very short plays/skips.
    df = df.dropna(subset=["ts", "master_metadata_track_name"])
    df = df[df["master_metadata_track_name"].astype(str).str.strip() != ""]

    df["master_metadata_album_artist_name"] = (
        df["master_metadata_album_artist_name"].fillna("Unknown").replace("", "Unknown")
    )
    if "spotify_track_uri" not in df.columns:
        df["spotify_track_uri"] = ""
    df["spotify_track_uri"] = df["spotify_track_uri"].fillna("").astype(str)
    df["ms_played"] = pd.to_numeric(df["ms_played"], errors="coerce").fillna(0)
    df = df[df["ms_played"] >= 30_000]
    return df.reset_index(drop=True)


def render_spotify_kpis(df: pd.DataFrame) -> None:
    total_hours = df["ms_played"].sum() / 3_600_000
    top_artist = df.groupby("master_metadata_album_artist_name")["ms_played"].sum().idxmax()
    total_tracks = len(df)

    cols = st.columns(3)
    cols[0].metric("Total Hours Listened", f"{total_hours:,.1f}")
    cols[1].metric("Top Artist", top_artist)
    cols[2].metric("Track Plays", f"{total_tracks:,}")


def format_hours(hours: float) -> str:
    return f"{hours:,.1f} hours"


def track_placeholder_url() -> str:
    return "https://img.icons8.com/fluency/96/vinyl.png"


def artist_placeholder_url(artist_name: str) -> str:
    encoded_name = quote_plus(artist_name or "Artist")
    return f"https://ui-avatars.com/api/?name={encoded_name}&background=1DB954&color=05070a&bold=true&size=128"


def get_spotify_secret(key: str) -> str:
    placeholder_values = {
        "",
        "jouw-client-id",
        "jouw-client-secret",
        "your-client-id",
        "your-client-secret",
    }
    value = os.getenv(key)
    if value and value.strip() not in placeholder_values:
        return value

    try:
        secret_value = st.secrets.get(key, "")
        return secret_value if secret_value.strip() not in placeholder_values else ""
    except Exception:
        return ""


@st.cache_resource(show_spinner=False)
def get_spotify_client(client_id: str, client_secret: str):
    """Create a Spotify Web API client when optional artwork credentials exist."""
    if not client_id or not client_secret:
        return None, "missing_credentials"

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ModuleNotFoundError:
        return None, "missing_spotipy"

    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    # Keep optional artwork lookups non-blocking. Spotipy's default retry behavior can
    # wait for very long Retry-After windows when Spotify rate-limits the app.
    return (
        spotipy.Spotify(
            auth_manager=auth_manager,
            requests_timeout=4,
            retries=0,
            status_retries=0,
        ),
        "ready",
    )


def get_artwork_cache() -> dict:
    return st.session_state.setdefault("spotify_artwork_cache", {"artists": {}, "tracks": {}, "deezer": {}})


def first_spotify_image(images: list) -> str:
    if not images:
        return ""
    return images[0].get("url", "")


def lookup_artist_artwork(spotify_client, artist_name: str) -> dict:
    cache = get_artwork_cache()["artists"]
    cache_key = artist_name.lower().strip()
    if cache_key in cache:
        return cache[cache_key]

    artwork = {"image_url": artist_placeholder_url(artist_name), "spotify_url": ""}
    if spotify_client is None:
        cache[cache_key] = artwork
        return artwork

    try:
        results = spotify_client.search(q=f"artist:{artist_name}", type="artist", limit=1)
        items = results.get("artists", {}).get("items", [])
        if items:
            artist = items[0]
            artwork = {
                "image_url": first_spotify_image(artist.get("images", [])) or artist_placeholder_url(artist_name),
                "spotify_url": artist.get("external_urls", {}).get("spotify", ""),
            }
    except Exception:
        pass

    cache[cache_key] = artwork
    return artwork


def deezer_get(endpoint: str, query: str) -> dict:
    cache = get_artwork_cache()["deezer"]
    cache_key = f"{endpoint}:{query.lower().strip()}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        url = f"https://api.deezer.com/{endpoint}?q={quote_plus(query)}&limit=1"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=3) as response:
            payload = json.load(response)
    except Exception:
        payload = {}

    cache[cache_key] = payload
    return payload


def lookup_deezer_artist_artwork(artist_name: str) -> dict:
    payload = deezer_get("search/artist", artist_name)
    items = payload.get("data", [])
    if not items:
        return {"image_url": artist_placeholder_url(artist_name), "spotify_url": ""}

    artist = items[0]
    return {
        "image_url": artist.get("picture_medium") or artist.get("picture_big") or artist_placeholder_url(artist_name),
        "spotify_url": artist.get("link", ""),
    }


def lookup_deezer_track_artwork(track_name: str, artist_name: str) -> dict:
    query = f'track:"{track_name}" artist:"{artist_name}"'
    payload = deezer_get("search/track", query)
    items = payload.get("data", [])
    if not items:
        payload = deezer_get("search/track", f"{track_name} {artist_name}")
        items = payload.get("data", [])
    if not items:
        return {"image_url": track_placeholder_url(), "spotify_url": ""}

    track = items[0]
    album = track.get("album", {})
    return {
        "image_url": album.get("cover_medium") or album.get("cover_big") or track_placeholder_url(),
        "spotify_url": track.get("link", ""),
    }


def lookup_track_artwork(spotify_client, track_name: str, artist_name: str) -> dict:
    cache = get_artwork_cache()["tracks"]
    cache_key = f"{track_name.lower().strip()}::{artist_name.lower().strip()}"
    if cache_key in cache:
        return cache[cache_key]

    artwork = {"image_url": track_placeholder_url(), "spotify_url": ""}
    if spotify_client is None:
        cache[cache_key] = artwork
        return artwork

    try:
        query = f'track:"{track_name}" artist:"{artist_name}"'
        results = spotify_client.search(q=query, type="track", limit=1)
        items = results.get("tracks", {}).get("items", [])
        if not items:
            results = spotify_client.search(q=f"{track_name} {artist_name}", type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
        if items:
            track = items[0]
            artwork = {
                "image_url": first_spotify_image(track.get("album", {}).get("images", [])) or track_placeholder_url(),
                "spotify_url": track.get("external_urls", {}).get("spotify", ""),
            }
    except Exception:
        pass

    cache[cache_key] = artwork
    return artwork


def add_spotify_artwork_columns(
    artist_totals: pd.DataFrame,
    track_totals: pd.DataFrame,
    load_artist_artwork: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    artists = artist_totals.copy()
    tracks = track_totals.copy()

    if not load_artist_artwork:
        artists["image_url"] = [
            artist_placeholder_url(str(row["master_metadata_album_artist_name"]))
            for _, row in artists.iterrows()
        ]
        artists["spotify_url"] = ""
        return artists, tracks, "skipped"

    client_id = get_spotify_secret("SPOTIPY_CLIENT_ID")
    client_secret = get_spotify_secret("SPOTIPY_CLIENT_SECRET")
    spotify_client, artwork_status = get_spotify_client(client_id, client_secret)
    if artwork_status != "ready":
        artwork_status = "deezer_fallback"

    artist_artwork = []
    for _, row in artists.iterrows():
        artist_name = str(row["master_metadata_album_artist_name"])
        artwork = lookup_artist_artwork(spotify_client, artist_name)
        if artwork["image_url"] == artist_placeholder_url(artist_name):
            artwork = lookup_deezer_artist_artwork(artist_name)
        artist_artwork.append(artwork)

    artists["image_url"] = [item["image_url"] for item in artist_artwork]
    artists["spotify_url"] = [item["spotify_url"] for item in artist_artwork]

    track_artwork = []
    for _, row in tracks.iterrows():
        track_name = str(row["master_metadata_track_name"])
        artist_name = str(row["master_metadata_album_artist_name"])
        # Deezer is used first for album covers because Spotify search is prone
        # to participant-facing 429 rate limits in Development Mode.
        artwork = lookup_deezer_track_artwork(track_name, artist_name)
        if artwork["image_url"] == track_placeholder_url():
            artwork = lookup_track_artwork(spotify_client, track_name, artist_name)
        track_artwork.append(artwork)

    tracks["image_url"] = [item["image_url"] for item in track_artwork]
    tracks["spotify_url"] = [item["spotify_url"] for item in track_artwork]
    return artists, tracks, artwork_status


def render_artwork_status(artwork_status: str) -> None:
    if artwork_status == "skipped":
        st.caption("Afbeeldingen zijn overgeslagen zodat uploaden en doorgaan snel blijft.")
    elif artwork_status == "ready":
        st.caption("Artist images en track covers worden standaard geladen. Track covers gebruiken eerst Deezer om Spotify rate limits te vermijden.")
    elif artwork_status == "deezer_fallback":
        st.caption("Artist images worden opgehaald via de publieke Deezer Search API. Als een match ontbreekt, gebruikt de app alsnog een placeholder.")
    elif artwork_status == "missing_spotipy":
        st.caption("Spotify artwork credentials zijn gevonden, maar de Python package `spotipy` ontbreekt. Installeer dependencies opnieuw met `python3 -m pip install -r requirements.txt`.")
    else:
        st.caption("Echte Spotify-afbeeldingen zijn optioneel. Zet `SPOTIPY_CLIENT_ID` en `SPOTIPY_CLIENT_SECRET` om album covers en artist images te laden.")


def render_ranking_rows(df: pd.DataFrame, name_column: str, image_type: str) -> str:
    rows_html = []
    max_hours = df["hours"].max() if not df.empty else 1

    for index, row in df.reset_index(drop=True).iterrows():
        rank = index + 1
        name = html.escape(str(row[name_column]))
        hours = float(row["hours"])
        plays = int(row["plays"])
        share_percent = max(20, min(100, int((hours / max_hours) * 100))) if max_hours else 20
        rank_class = f"rank-{rank}" if rank <= 3 else "rank-standard"
        image_url = html.escape(str(row.get("image_url", "")) or track_placeholder_url(), quote=True)
        spotify_url = html.escape(str(row.get("spotify_url", "")), quote=True)

        if image_type == "track":
            artist_name = html.escape(str(row.get("master_metadata_album_artist_name", "Unknown Artist")))
            subtitle = f"{artist_name} · {plays:,} plays"
            image_class = "ranking-image"
        else:
            subtitle = f"{plays:,} plays"
            image_class = "ranking-image artist-image"

        row_inner_html = f"""
            <div class="rank-number">#{rank}</div>
            <img class="{image_class}" src="{image_url}" alt="" loading="lazy" />
            <div class="ranking-copy">
                <div class="ranking-name">{name}</div>
                <div class="ranking-subtitle">{subtitle}</div>
            </div>
            <div class="ranking-stat">{format_hours(hours)}<span>{share_percent}% of top</span></div>
        """

        if spotify_url:
            row_inner_html = f'<a class="ranking-link" href="{spotify_url}" target="_blank" rel="noopener noreferrer">{row_inner_html}</a>'

        rows_html.append(
            f"""
            <div class="ranking-row {rank_class}" style="--bar-width: {share_percent}%;">
                {row_inner_html}
            </div>
            """
        )

    return "\n".join(rows_html)


def render_top_10_rankings(df: pd.DataFrame, load_artist_artwork: bool = True) -> None:
    artist_totals = (
        df.groupby("master_metadata_album_artist_name", as_index=False)
        .agg(total_ms=("ms_played", "sum"), plays=("ms_played", "size"))
        .assign(hours=lambda data: data["total_ms"] / 3_600_000)
        .sort_values("hours", ascending=False)
        .head(10)
    )

    track_totals = (
        df.groupby(["master_metadata_track_name", "master_metadata_album_artist_name"], as_index=False)
        .agg(total_ms=("ms_played", "sum"), plays=("ms_played", "size"))
        .assign(hours=lambda data: data["total_ms"] / 3_600_000)
        .sort_values("hours", ascending=False)
        .head(10)
    )
    artist_totals, track_totals, artwork_status = add_spotify_artwork_columns(
        artist_totals,
        track_totals,
        load_artist_artwork=load_artist_artwork,
    )

    artist_rows = render_ranking_rows(
        artist_totals,
        name_column="master_metadata_album_artist_name",
        image_type="artist",
    )
    track_rows = render_ranking_rows(
        track_totals,
        name_column="master_metadata_track_name",
        image_type="track",
    )

    render_html(
        f"""
        <div class="spotify-rankings-grid">
            <section class="ranking-panel">
                <h2>Top 10 Artists</h2>
                <div class="ranking-list">{artist_rows}</div>
            </section>
            <section class="ranking-panel">
                <h2>Top 10 Tracks</h2>
                <div class="ranking-list">{track_rows}</div>
            </section>
        </div>
        """
    )
    render_artwork_status(artwork_status)


def render_spotify_charts(df: pd.DataFrame, load_artist_artwork: bool = True) -> None:
    render_top_10_rankings(df, load_artist_artwork=load_artist_artwork)

    hourly = df.assign(hour=df["ts"].dt.hour).groupby("hour", as_index=False).size()
    render_html('<div class="spotify-section-title">Listening Activity per Hour</div>')
    fig_hourly = px.line(
        hourly,
        x="hour",
        y="size",
        markers=True,
        labels={"hour": "Hour of day", "size": "Track plays"},
        title="Listening Activity per Hour",
    )
    fig_hourly.update_traces(line=dict(color=SPOTIFY_GREEN, width=4), marker=dict(size=8))
    fig_hourly.update_layout(
        template="plotly_dark",
        height=460,
        font=dict(size=14),
        title_font=dict(size=22),
        xaxis=dict(dtick=1, title_font=dict(size=16), tickfont=dict(size=14)),
        yaxis=dict(title_font=dict(size=16), tickfont=dict(size=14)),
        margin=dict(l=10, r=10, t=70, b=10),
    )
    st.plotly_chart(fig_hourly, use_container_width=True)

    render_html('<div class="spotify-section-title">Listening Habits: Time of Day vs. Day of Week</div>')
    heatmap_df = df.copy()
    heatmap_df["hour"] = heatmap_df["ts"].dt.hour
    heatmap_df["day_of_week"] = pd.Categorical(
        heatmap_df["ts"].dt.day_name(),
        categories=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        ordered=True,
    )
    fig_heatmap = px.density_heatmap(
        heatmap_df,
        x="hour",
        y="day_of_week",
        nbinsx=24,
        category_orders={
            "day_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        },
        color_continuous_scale=[(0, "#03130A"), (0.45, "#0B3D1F"), (1, SPOTIFY_GREEN)],
        labels={"hour": "Hour of Day", "day_of_week": "Day of Week", "count": "Track Plays"},
        title="Listening Habits: Time of Day vs. Day of Week",
    )
    fig_heatmap.update_layout(
        template="plotly_dark",
        height=430,
        font=dict(size=14, color="white"),
        title_font=dict(size=22, color="white"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=70, b=10),
        xaxis=dict(dtick=1),
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)


def render_spotify_feature() -> None:
    inject_spotify_css()
    render_html(
        """
        <section class="spotify-hero">
            <h1>Upload Spotify History</h1>
            <p>Use your Spotify Extended Streaming History JSON export. Charts appear only after a valid file is uploaded.</p>
        </section>
        """
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
        st.warning("No valid Spotify track rows were found after filtering null tracks, short plays, and invalid timestamps.")
        return

    logged_files = st.session_state.setdefault("logged_spotify_files", set())
    participant_id = st.session_state.get("participant_id")
    for uploaded_file in uploaded_files:
        if participant_id and uploaded_file.name not in logged_files:
            log_spotify_upload(participant_id, uploaded_file.name)
            logged_files.add(uploaded_file.name)

    if participant_id:
        source_file = "|".join(uploaded_file.name for uploaded_file in uploaded_files)
        save_spotify_tracks(participant_id, df, source_file=source_file)

    st.session_state.spotify_uploaded = True
    st.session_state.spotify_df = df

    render_spotify_kpis(df)

    with st.spinner("Rendering Spotify summary..."):
        render_spotify_charts(df, load_artist_artwork=True)

    st.divider()
    if st.button("Next: Upload Strava Data", type="primary", use_container_width=True):
        st.session_state.current_page = "Strava Upload"
        st.rerun()
