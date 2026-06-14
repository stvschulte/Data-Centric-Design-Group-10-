from __future__ import annotations

import uuid

import pandas as pd
import plotly.express as px
import streamlit as st

from features.combined_insights import (
    add_track_tempos,
    get_configured_spotify_credentials,
    merge_tracks_into_workouts,
)
from features.spotify_feature import parse_spotify_json
from features.strava_feature import (
    UPLOAD_FILE_TYPES,
    find_activities_file,
    parse_strava_csv,
    save_uploaded_media_files,
)
from utils.db_handler import (
    create_participant,
    fetch_spotify_tracks,
    fetch_strava_activities,
    log_spotify_upload,
    log_strava_upload,
    save_spotify_tracks,
    save_strava_activities,
)


def inject_researcher_area_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(135deg, #05070a 0%, #101318 54%, #080b10 100%);
            color: #f8fafc;
        }
        .researcher-area-hero {
            padding: 42px 44px;
            border: 1px solid rgba(255,255,255,0.13);
            border-radius: 14px;
            background:
                linear-gradient(135deg, rgba(29,185,84,0.18), rgba(252,76,2,0.16)),
                linear-gradient(135deg, rgba(15,23,42,0.92), rgba(9,12,18,0.96));
            box-shadow: 0 24px 80px rgba(0,0,0,0.38);
            margin-bottom: 24px;
        }
        .researcher-area-hero h1 {
            margin: 0;
            font-size: 42px;
            line-height: 1.08;
            font-weight: 850;
            letter-spacing: 0;
            color: #ffffff;
        }
        .researcher-area-hero p {
            margin: 14px 0 0;
            max-width: 860px;
            color: #dbeafe;
            font-size: 17px;
            line-height: 1.55;
        }
        div[data-testid="stMetric"] {
            background: rgba(15,23,42,0.82);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 10px;
            padding: 16px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_researcher_area_state() -> None:
    # Session state keeps the dynamic participant block list alive across Streamlit reruns.
    if "research_participants" not in st.session_state:
        st.session_state.research_participants = []
    if "show_cohort_analysis" not in st.session_state:
        st.session_state.show_cohort_analysis = False
    if "research_processed_uploads" not in st.session_state:
        st.session_state.research_processed_uploads = set()
    if "research_participant_uploads" not in st.session_state:
        st.session_state.research_participant_uploads = {}


def uploaded_files_signature(uploaded_files) -> str:
    parts = []
    for uploaded_file in uploaded_files or []:
        size = getattr(uploaded_file, "size", None)
        parts.append(f"{uploaded_file.name}:{size}")
    return "|".join(sorted(parts))


def update_participant_upload_presence(p_id: str, data_type: str, has_files: bool) -> None:
    """Track which visible participant blocks currently contain uploaded files."""
    upload_state = st.session_state.research_participant_uploads.setdefault(p_id, {"spotify": False, "strava": False})
    upload_state[data_type] = has_files


def get_analysis_participant_ids() -> list[str]:
    """Analyze only current participant blocks that have both Spotify and Strava uploads present."""
    upload_state = st.session_state.get("research_participant_uploads", {})
    return [
        p_id
        for p_id in st.session_state.get("research_participants", [])
        if upload_state.get(p_id, {}).get("spotify") and upload_state.get(p_id, {}).get("strava")
    ]


def process_spotify_uploads(p_id: str, uploaded_files) -> pd.DataFrame:
    if not uploaded_files:
        return pd.DataFrame()

    signature = uploaded_files_signature(uploaded_files)
    processed_key = f"spotify:{p_id}:{signature}"
    if processed_key in st.session_state.research_processed_uploads:
        return pd.DataFrame()

    df = parse_spotify_json(uploaded_files)
    if df.empty:
        st.warning("No valid Spotify tracks found for this participant.")
        return pd.DataFrame()

    create_participant(p_id, status="researcher_uploaded")
    source_file = "|".join(uploaded_file.name for uploaded_file in uploaded_files)
    save_spotify_tracks(p_id, df, source_file=source_file)
    for uploaded_file in uploaded_files:
        log_spotify_upload(p_id, uploaded_file.name)

    st.session_state.research_processed_uploads.add(processed_key)
    return df


def process_strava_uploads(p_id: str, uploaded_files) -> tuple[pd.DataFrame, int, str]:
    if not uploaded_files:
        return pd.DataFrame(), 0, ""

    signature = uploaded_files_signature(uploaded_files)
    processed_key = f"strava:{p_id}:{signature}"
    if processed_key in st.session_state.research_processed_uploads:
        return pd.DataFrame(), 0, ""

    activities_file = find_activities_file(uploaded_files)
    if activities_file is None:
        st.warning("Could not find activities.csv in this participant block.")
        return pd.DataFrame(), 0, ""

    activities_file.seek(0)
    df = parse_strava_csv(activities_file, filename=activities_file.name)
    if df.empty:
        st.warning("No valid Strava activities found for this participant.")
        return pd.DataFrame(), 0, activities_file.name

    create_participant(p_id, status="researcher_uploaded")
    save_strava_activities(p_id, df, source_file=activities_file.name)
    log_strava_upload(p_id, activities_file.name)
    media_count = save_uploaded_media_files(uploaded_files, p_id)

    st.session_state.research_processed_uploads.add(processed_key)
    return df, media_count, activities_file.name


def render_participant_block(p_id: str, index: int) -> None:
    with st.expander(f"Participant {index + 1} (ID: {p_id})", expanded=True):
        st.caption("Drop this participant's Spotify and Strava exports in this block.")
        left_col, right_col = st.columns(2)

        with left_col:
            spotify_files = st.file_uploader(
                "Spotify Extended Streaming History JSON",
                type=["json"],
                accept_multiple_files=True,
                # Unique widget keys bind uploaded files to the correct dynamic participant block.
                key=f"spotify_{p_id}",
            )
            if spotify_files:
                update_participant_upload_presence(p_id, "spotify", True)
                spotify_df = process_spotify_uploads(p_id, spotify_files)
                if not spotify_df.empty:
                    st.success(f"Saved {len(spotify_df):,} Spotify track rows for participant {p_id}.")
            else:
                update_participant_upload_presence(p_id, "spotify", False)

        with right_col:
            strava_files = st.file_uploader(
                "Strava export files",
                type=UPLOAD_FILE_TYPES,
                accept_multiple_files="directory",
                # Unique widget keys prevent Streamlit duplication and cross-participant file mixing.
                key=f"strava_{p_id}",
            )
            if strava_files:
                update_participant_upload_presence(p_id, "strava", True)
                strava_df, media_count, source_file = process_strava_uploads(p_id, strava_files)
                if not strava_df.empty:
                    st.success(
                        f"Saved {len(strava_df):,} Strava activities from {source_file}. "
                        f"Media files: {media_count:,}."
                    )
            else:
                update_participant_upload_presence(p_id, "strava", False)

        spotify_saved = fetch_spotify_tracks(p_id)
        strava_saved = fetch_strava_activities(p_id)
        metric_cols = st.columns(3)
        metric_cols[0].metric("Spotify Rows", f"{len(spotify_saved):,}")
        metric_cols[1].metric("Strava Activities", f"{len(strava_saved):,}")
        metric_cols[2].metric("Avg HR Rows", f"{strava_saved['standard_hr'].notna().sum():,}" if not strava_saved.empty else "0")


def normalize_participant_scope(participant_ids: list[str]) -> list[str]:
    """Keep cohort analysis scoped to the participant blocks in the current researcher session."""
    return list(dict.fromkeys(str(participant_id).strip() for participant_id in participant_ids if str(participant_id).strip()))


def build_cohort_dataset(participant_ids: list[str]) -> tuple[pd.DataFrame, str]:
    participant_ids = normalize_participant_scope(participant_ids)
    if not participant_ids:
        return pd.DataFrame(), "No participant blocks are active in this researcher session."

    matched_parts = []
    skipped_participants = []
    for participant_id in participant_ids:
        spotify_df = fetch_spotify_tracks(participant_id)
        strava_df = fetch_strava_activities(participant_id)
        if spotify_df.empty or strava_df.empty:
            skipped_participants.append(participant_id)
            continue

        merged = merge_tracks_into_workouts(spotify_df, strava_df)
        if merged.empty:
            skipped_participants.append(participant_id)
            continue

        merged["participant_id"] = participant_id
        matched_parts.append(merged)

    if not matched_parts:
        return pd.DataFrame(), "No Spotify tracks were found inside Strava workout windows for the active participant blocks."

    cohort_df = pd.concat(matched_parts, ignore_index=True)
    client_id, client_secret = get_configured_spotify_credentials()
    enriched_df, bpm_status = add_track_tempos(cohort_df, client_id, client_secret)
    enriched_df["standard_duration"] = pd.to_numeric(enriched_df["standard_duration"], errors="coerce")
    enriched_df["standard_hr"] = pd.to_numeric(enriched_df["standard_hr"], errors="coerce")
    enriched_df["tempo"] = pd.to_numeric(enriched_df["tempo"], errors="coerce")

    scope_status = f"Analysis scoped to current participant blocks: {', '.join(participant_ids)}."
    if skipped_participants:
        scope_status += f" Skipped incomplete/unmatched participant block(s): {', '.join(skipped_participants)}."
    return enriched_df, " ".join(status for status in [scope_status, bpm_status] if status)


def interpret_pearson_r(correlation: float) -> tuple[str, str]:
    """Classify Pearson's r by direction and common practical strength thresholds."""
    if pd.isna(correlation):
        return "", "Not enough paired numeric data is available to calculate a reliable linear correlation."

    absolute_correlation = abs(correlation)
    if absolute_correlation > 0.5:
        strength = "Strong"
    elif absolute_correlation > 0.3:
        strength = "Moderate"
    elif absolute_correlation > 0:
        strength = "Weak"
    else:
        return "No linear correlation", "This indicates no linear relationship across the cohort."

    direction = "positive" if correlation > 0 else "negative"
    return f"{strength} {direction} correlation", f"This indicates a {strength.lower()} {direction} relationship across the cohort"


def render_correlation_summary(correlation: float, positive_text: str, negative_text: str) -> None:
    """Show Pearson's r with a short interpretation below the matching scatter plot."""
    if pd.isna(correlation):
        st.info("Statistical Value: Pearson's r could not be calculated. Not enough paired numeric data is available.")
        return

    sign = "+" if correlation >= 0 else ""
    relationship_label, interpretation = interpret_pearson_r(correlation)
    direction_text = positive_text if correlation > 0 else negative_text if correlation < 0 else "meaning the variables do not move together in a clear linear way."
    st.info(
        f"Statistical Value: Pearson's r = {sign}{correlation:.2f}. "
        f"{relationship_label}. {interpretation}, {direction_text}"
    )


def render_cohort_chart(df: pd.DataFrame, y_column: str, title: str, y_label: str) -> None:
    plot_df = df.dropna(subset=["tempo", y_column, "participant_id"]).copy()
    if len(plot_df) < 3:
        st.warning(f"Not enough rows with BPM and {y_label.lower()} for `{title}`.")
        return

    fig = px.scatter(
        plot_df,
        x="tempo",
        y=y_column,
        color="participant_id",
        trendline="ols",
        trendline_scope="overall",
        template="plotly_dark",
        title=title,
        hover_data={
            "participant_id": True,
            "track_name": True,
            "artist_name": True,
            "workout_name": True,
            "workout_type": True,
            "tempo": ":.0f",
            "standard_hr": ":.0f",
            "standard_duration": ":.0f",
        },
        labels={
            "tempo": "Track BPM",
            "standard_hr": "Heart Rate (BPM)",
            "standard_duration": "Workout Duration (seconds)",
            "participant_id": "Participant",
        },
        height=520,
    )
    fig.update_traces(marker=dict(size=9, opacity=0.76, line=dict(width=0.5, color="rgba(255,255,255,0.38)")))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        margin=dict(l=10, r=10, t=74, b=10),
        legend_title_text="Participant",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_cohort_analysis() -> None:
    st.divider()

    with st.spinner("Matching Spotify tracks to Strava workouts and enriching BPM data..."):
        cohort_df, status = build_cohort_dataset(get_analysis_participant_ids())

    if status:
        st.caption(status)
    if cohort_df.empty:
        st.warning("No cohort analysis could be generated yet.")
        return

    num_participants = cohort_df["participant_id"].nunique()
    total_points = len(cohort_df)
    st.subheader(f"📊 Cohort Analysis Results ({num_participants} Participants, {total_points} Data Points Analyzed)")

    # Pearson's r measures linear association between two numeric variables.
    # Pandas automatically ignores rows where either side of the pair is missing.
    hr_bpm_corr = cohort_df["tempo"].corr(cohort_df["standard_hr"])
    dur_bpm_corr = cohort_df["tempo"].corr(cohort_df["standard_duration"])

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Participants", f"{num_participants:,}")
    kpi_cols[1].metric("Data Points", f"{total_points:,}")
    kpi_cols[2].metric("Workouts", f"{cohort_df['workout_name'].nunique():,}")
    kpi_cols[3].metric("Rows With BPM", f"{cohort_df['tempo'].notna().sum():,}")

    render_cohort_chart(
        cohort_df,
        y_column="standard_hr",
        title="Heart Rate vs Track BPM (Cohort View)",
        y_label="heart rate",
    )
    render_correlation_summary(
        hr_bpm_corr,
        "meaning higher music tempos generally correlate with higher average heart rates during exercise.",
        "meaning higher music tempos generally correlate with lower average heart rates during exercise.",
    )

    render_cohort_chart(
        cohort_df,
        y_column="standard_duration",
        title="Workout Duration vs Track BPM (Cohort View)",
        y_label="workout duration",
    )
    render_correlation_summary(
        dur_bpm_corr,
        "meaning higher music tempos generally correlate with longer workout durations.",
        "meaning higher music tempos generally correlate with shorter workout durations.",
    )


def render_researcher_area() -> None:
    inject_researcher_area_css()
    init_researcher_area_state()

    st.markdown(
        """
        <section class="researcher-area-hero">
            <h1>Researcher Ingestion Workspace</h1>
            <p>Add participants vertically, upload each participant's Spotify and Strava exports in-place, then run one cohort analysis across all saved participant data.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    if st.button("➕ Add New Participant"):
        st.session_state.research_participants.append(str(uuid.uuid4())[:8])
        st.session_state.show_cohort_analysis = False
        st.rerun()

    if not st.session_state.research_participants:
        st.info("Add a participant to start uploading data.")

    for index, p_id in enumerate(st.session_state.research_participants):
        render_participant_block(p_id, index)

    st.divider()
    if st.button("Voer analyse uit (Execute Cohort Analysis)", type="primary", use_container_width=True):
        st.session_state.show_cohort_analysis = True

    if st.session_state.show_cohort_analysis:
        render_cohort_analysis()
