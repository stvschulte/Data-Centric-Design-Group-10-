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


def init_db() -> None:
    """Create local SQLite tables used by participant and researcher flows."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS participants (
                id TEXT PRIMARY KEY,
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
                FOREIGN KEY (participant_id) REFERENCES participants (id)
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
                FOREIGN KEY (participant_id) REFERENCES participants (id)
            )
            """
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_participant(participant_id: str, consent_timestamp: str, status: str = "consented") -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO participants (id, consent_timestamp, status)
            VALUES (?, ?, ?)
            """,
            (participant_id, consent_timestamp, status),
        )


def log_spotify_upload(participant_id: str, filename: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO spotify_uploads (participant_id, file_name, upload_timestamp)
            VALUES (?, ?, ?)
            """,
            (participant_id, filename, utc_now()),
        )


def log_strava_upload(participant_id: str, filename: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO strava_uploads (participant_id, file_name, upload_timestamp)
            VALUES (?, ?, ?)
            """,
            (participant_id, filename, utc_now()),
        )


def get_participants() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT id, consent_timestamp, status FROM participants ORDER BY consent_timestamp DESC",
            conn,
        )


def get_summary_metrics() -> dict:
    with get_connection() as conn:
        total_participants = conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
        spotify_uploads = conn.execute("SELECT COUNT(*) FROM spotify_uploads").fetchone()[0]
        strava_uploads = conn.execute("SELECT COUNT(*) FROM strava_uploads").fetchone()[0]
    return {
        "total_participants": total_participants,
        "spotify_uploads": spotify_uploads,
        "strava_uploads": strava_uploads,
    }


def get_participant_upload_logs(participant_id: str) -> dict[str, pd.DataFrame]:
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
