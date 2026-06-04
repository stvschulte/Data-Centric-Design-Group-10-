from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "research_app.sqlite"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """Create participant-scoped local SQLite tables.

    Every participant-facing table stores participant_id explicitly so uploads,
    parsed rows, reflections, and later queries cannot overwrite another
    participant's local data.
    """
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS participants (
                participant_id TEXT PRIMARY KEY,
                consent_timestamp TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spotify_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                upload_timestamp TEXT NOT NULL,
                FOREIGN KEY (participant_id) REFERENCES participants (participant_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strava_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                upload_timestamp TEXT NOT NULL,
                FOREIGN KEY (participant_id) REFERENCES participants (participant_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spotify_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL,
                ts TEXT,
                track_name TEXT,
                artist_name TEXT,
                ms_played REAL,
                spotify_track_uri TEXT,
                source_file TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (participant_id) REFERENCES participants (participant_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strava_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL,
                standard_date TEXT,
                standard_duration REAL,
                standard_name TEXT,
                standard_type TEXT,
                standard_hr REAL,
                media TEXT,
                source_file TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (participant_id) REFERENCES participants (participant_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS participant_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL,
                reflection_text TEXT NOT NULL,
                correlation REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (participant_id) REFERENCES participants (participant_id)
            )
            """
        )

        _migrate_legacy_participants(conn)
        _ensure_column(conn, "strava_activities", "media", "TEXT")


def _migrate_legacy_participants(conn: sqlite3.Connection) -> None:
    """Best-effort migration from the earlier participants(id, ...) schema."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(participants)").fetchall()}
    if "participant_id" in columns:
        return

    conn.execute("ALTER TABLE participants RENAME TO participants_legacy")
    conn.execute(
        """
        CREATE TABLE participants (
            participant_id TEXT PRIMARY KEY,
            consent_timestamp TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )
    legacy_columns = {row[1] for row in conn.execute("PRAGMA table_info(participants_legacy)").fetchall()}
    id_column = "id" if "id" in legacy_columns else "participant_id"
    conn.execute(
        f"""
        INSERT OR IGNORE INTO participants (participant_id, consent_timestamp, status)
        SELECT {id_column}, consent_timestamp, status FROM participants_legacy
        """
    )


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def require_participant_id(participant_id: str) -> str:
    if not participant_id:
        raise ValueError("participant_id is required for all database operations")
    return str(participant_id)


def create_participant(participant_id: str, consent_timestamp: str | None = None, status: str = "consented") -> None:
    participant_id = require_participant_id(participant_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO participants (participant_id, consent_timestamp, status)
            VALUES (?, ?, ?)
            """,
            (participant_id, consent_timestamp or utc_now(), status),
        )


def log_spotify_upload(participant_id: str, filename: str) -> None:
    participant_id = require_participant_id(participant_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO spotify_uploads (participant_id, file_name, upload_timestamp)
            VALUES (?, ?, ?)
            """,
            (participant_id, filename, utc_now()),
        )


def log_strava_upload(participant_id: str, filename: str) -> None:
    participant_id = require_participant_id(participant_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO strava_uploads (participant_id, file_name, upload_timestamp)
            VALUES (?, ?, ?)
            """,
            (participant_id, filename, utc_now()),
        )


def save_spotify_tracks(participant_id: str, df: pd.DataFrame, source_file: str = "") -> None:
    participant_id = require_participant_id(participant_id)
    if df.empty:
        return

    rows = []
    for _, row in df.iterrows():
        ts = pd.to_datetime(row.get("ts"), errors="coerce")
        rows.append(
            (
                participant_id,
                None if pd.isna(ts) else ts.isoformat(),
                row.get("master_metadata_track_name"),
                row.get("master_metadata_album_artist_name"),
                row.get("ms_played"),
                row.get("spotify_track_uri", ""),
                source_file,
                utc_now(),
            )
        )

    with get_connection() as conn:
        if source_file:
            conn.execute(
                "DELETE FROM spotify_tracks WHERE participant_id = ? AND source_file = ?",
                (participant_id, source_file),
            )
        conn.executemany(
            """
            INSERT INTO spotify_tracks (
                participant_id, ts, track_name, artist_name, ms_played,
                spotify_track_uri, source_file, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def save_strava_activities(participant_id: str, df: pd.DataFrame, source_file: str = "") -> None:
    participant_id = require_participant_id(participant_id)
    if df.empty:
        return

    rows = []
    for _, row in df.iterrows():
        activity_date = pd.to_datetime(row.get("standard_date"), errors="coerce")
        rows.append(
            (
                participant_id,
                None if pd.isna(activity_date) else activity_date.isoformat(),
                row.get("standard_duration"),
                row.get("standard_name"),
                row.get("standard_type"),
                row.get("standard_hr"),
                row.get("Media", row.get("media", "")),
                source_file,
                utc_now(),
            )
        )

    with get_connection() as conn:
        if source_file:
            conn.execute(
                "DELETE FROM strava_activities WHERE participant_id = ? AND source_file = ?",
                (participant_id, source_file),
            )
        conn.executemany(
            """
            INSERT INTO strava_activities (
                participant_id, standard_date, standard_duration, standard_name,
                standard_type, standard_hr, media, source_file, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def save_participant_reflection(participant_id: str, reflection_text: str, correlation: float | None = None) -> None:
    participant_id = require_participant_id(participant_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO participant_reflections (participant_id, reflection_text, correlation, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (participant_id, reflection_text, correlation, utc_now()),
        )


def fetch_spotify_tracks(participant_id: str) -> pd.DataFrame:
    participant_id = require_participant_id(participant_id)
    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT ts, track_name, artist_name, ms_played, spotify_track_uri, source_file, created_at
            FROM spotify_tracks
            WHERE participant_id = ?
            ORDER BY ts
            """,
            conn,
            params=(participant_id,),
        )
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    return df


def fetch_strava_activities(participant_id: str) -> pd.DataFrame:
    participant_id = require_participant_id(participant_id)
    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT standard_date, standard_duration, standard_name, standard_type, standard_hr, media, source_file, created_at
            FROM strava_activities
            WHERE participant_id = ?
            ORDER BY standard_date
            """,
            conn,
            params=(participant_id,),
        )
    if not df.empty:
        df["standard_date"] = pd.to_datetime(df["standard_date"], errors="coerce")
        df["standard_duration"] = pd.to_numeric(df["standard_duration"], errors="coerce")
        df["standard_hr"] = pd.to_numeric(df["standard_hr"], errors="coerce")
    return df


def fetch_participant_reflections(participant_id: str) -> pd.DataFrame:
    participant_id = require_participant_id(participant_id)
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT reflection_text, correlation, created_at
            FROM participant_reflections
            WHERE participant_id = ?
            ORDER BY created_at DESC
            """,
            conn,
            params=(participant_id,),
        )


def get_participants() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT participant_id, consent_timestamp, status FROM participants ORDER BY consent_timestamp DESC",
            conn,
        )


def get_summary_metrics(participant_id: str | None = None) -> dict:
    with get_connection() as conn:
        if participant_id:
            total_participants = 1
            spotify_uploads = conn.execute(
                "SELECT COUNT(*) FROM spotify_uploads WHERE participant_id = ?",
                (participant_id,),
            ).fetchone()[0]
            strava_uploads = conn.execute(
                "SELECT COUNT(*) FROM strava_uploads WHERE participant_id = ?",
                (participant_id,),
            ).fetchone()[0]
        else:
            total_participants = conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
            spotify_uploads = conn.execute("SELECT COUNT(*) FROM spotify_uploads").fetchone()[0]
            strava_uploads = conn.execute("SELECT COUNT(*) FROM strava_uploads").fetchone()[0]
    return {
        "total_participants": total_participants,
        "spotify_uploads": spotify_uploads,
        "strava_uploads": strava_uploads,
    }


def get_participant_upload_logs(participant_id: str) -> dict[str, pd.DataFrame]:
    participant_id = require_participant_id(participant_id)
    with get_connection() as conn:
        spotify = pd.read_sql_query(
            """
            SELECT file_name, upload_timestamp
            FROM spotify_uploads
            WHERE participant_id = ?
            ORDER BY upload_timestamp DESC
            """,
            conn,
            params=(participant_id,),
        )
        strava = pd.read_sql_query(
            """
            SELECT file_name, upload_timestamp
            FROM strava_uploads
            WHERE participant_id = ?
            ORDER BY upload_timestamp DESC
            """,
            conn,
            params=(participant_id,),
        )
    return {"spotify": spotify, "strava": strava}
