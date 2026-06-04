from __future__ import annotations

import os
import re
import time

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db_handler import log_strava_upload, save_strava_activities


STRAVA_ORANGE = "#FC4C02"
HR_ZONE_COLORS = {
    "Zone 1 (Recovery)": "#FFD7C2",
    "Zone 2 (Endurance)": "#FFB088",
    "Zone 3 (Tempo)": "#FC7A30",
    "Zone 4 (Threshold)": "#E04412",
    "Zone 5 (Anaerobic/Max)": "#A31312",
}
HR_ZONE_BACKGROUNDS = [
    ("Zone 1", 60, 110, "rgba(128, 128, 128, 0.15)"),
    ("Zone 2", 110, 130, "rgba(46, 204, 113, 0.15)"),
    ("Zone 3", 130, 150, "rgba(241, 196, 15, 0.15)"),
    ("Zone 4", 150, 170, "rgba(230, 126, 34, 0.15)"),
    ("Zone 5", 170, 220, "rgba(231, 76, 60, 0.15)"),
]

COLUMN_VARIANTS = {
    "standard_date": ["Activity Date", "activity date", "Date", "start_time"],
    "standard_duration": ["Elapsed Time", "elapsed time", "Duration", "Time", "Moving Time"],
    "standard_name": ["Activity Name", "activity name", "Name", "Title"],
    "standard_type": ["Activity Type", "activity type", "Type"],
    "standard_hr": ["Average Heart Rate", "average heart rate", "Heart Rate"],
    "Media": ["Media", "media"],
}
REQUIRED_STANDARD_COLUMNS = ["standard_date", "standard_duration", "standard_type"]
MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
UPLOAD_FILE_TYPES = ["csv", "jpg", "jpeg", "png", "gif", "webp", "heic", "heif"]


def inject_strava_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                linear-gradient(135deg, rgba(7, 10, 18, 0.96), rgba(18, 20, 28, 0.92)),
                url("https://images.unsplash.com/photo-1502904550040-7534597429ae?auto=format&fit=crop&w=1800&q=80");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #f8fafc;
        }}
        .strava-hero {{
            min-height: 220px;
            padding: 48px 46px;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(252,76,2,0.30), rgba(9,11,18,0.88));
            border: 1px solid rgba(252,76,2,0.38);
            box-shadow: 0 24px 80px rgba(0,0,0,0.40);
            margin-bottom: 24px;
        }}
        .strava-hero h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 48px;
            font-weight: 850;
            letter-spacing: 0;
        }}
        .strava-hero p {{
            max-width: 760px;
            color: #ffe6dc;
            font-size: 18px;
            line-height: 1.6;
        }}
        div[data-testid="stMetric"] {{
            background: rgba(9, 11, 18, 0.88);
            border: 1px solid rgba(252,76,2,0.30);
            border-radius: 14px;
            padding: 18px;
            box-shadow: 0 14px 42px rgba(0,0,0,0.26);
        }}
        div[data-testid="stMetricLabel"] {{
            color: #cbd5e1;
            font-weight: 700;
        }}
        div[data-testid="stMetricValue"] {{
            color: {STRAVA_ORANGE};
            font-weight: 850;
        }}
        .stButton > button, [data-testid="stFileUploader"] button {{
            border-color: {STRAVA_ORANGE} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def normalize_column_name(column_name: str) -> str:
    """Normalize headers so small Strava CSV naming differences do not break parsing."""
    return re.sub(r"[^a-z0-9]+", "", str(column_name).strip().lower())


def build_strava_column_mapping(columns: pd.Index) -> dict[str, str]:
    """Map Strava export headers onto internal standard_* column names."""
    cleaned_columns = [str(column).replace("\ufeff", "").strip() for column in columns]
    exact_lookup = {column: column for column in cleaned_columns}
    normalized_lookup = {normalize_column_name(column): column for column in cleaned_columns}

    mapping = {}
    for standard_name, variants in COLUMN_VARIANTS.items():
        for variant in variants:
            if variant in exact_lookup:
                mapping[exact_lookup[variant]] = standard_name
                break

            normalized_variant = normalize_column_name(variant)
            if normalized_variant in normalized_lookup:
                mapping[normalized_lookup[normalized_variant]] = standard_name
                break

    return mapping


def parse_duration_to_seconds(duration_series: pd.Series) -> pd.Series:
    """Convert numeric seconds or HH:MM:SS-style duration values to seconds."""
    numeric_duration = pd.to_numeric(duration_series, errors="coerce")
    needs_timedelta = numeric_duration.isna() & duration_series.notna()
    if needs_timedelta.any():
        timedelta_duration = pd.to_timedelta(duration_series[needs_timedelta], errors="coerce")
        numeric_duration.loc[needs_timedelta] = timedelta_duration.dt.total_seconds()
    return numeric_duration


def parse_strava_csv(csv_file, filename: str = "activities.csv") -> pd.DataFrame:
    try:
        # Strava CSVs can be comma- or semicolon-delimited depending on export locale.
        raw_df = pd.read_csv(csv_file, sep=None, engine="python")
    except Exception as exc:
        st.error(f"Could not read `{filename}` as CSV: {exc}")
        return pd.DataFrame()

    raw_df.columns = [str(column).replace("\ufeff", "").strip() for column in raw_df.columns]
    column_mapping = build_strava_column_mapping(raw_df.columns)
    mapped_standard_columns = set(column_mapping.values())

    if not set(REQUIRED_STANDARD_COLUMNS).issubset(mapped_standard_columns):
        st.error(
            "Could not find required columns in this CSV. Please ensure you are uploading the 'activities.csv' from your Strava export."
        )
        st.caption(f"Detected columns: {', '.join(raw_df.columns.astype(str).tolist())}")
        st.stop()

    df = raw_df.rename(columns=column_mapping).copy()
    selected_columns = list(dict.fromkeys(column_mapping.values()))
    df = df[selected_columns]

    if "standard_name" not in df.columns:
        df["standard_name"] = "Unnamed Strava Activity"
    if "standard_hr" not in df.columns:
        df["standard_hr"] = pd.NA
    if "Media" not in df.columns:
        df["Media"] = ""

    df["standard_date"] = pd.to_datetime(df["standard_date"], errors="coerce")
    if getattr(df["standard_date"].dt, "tz", None) is not None:
        df["standard_date"] = df["standard_date"].dt.tz_convert(None)

    df["standard_duration"] = parse_duration_to_seconds(df["standard_duration"])
    df["standard_hr"] = pd.to_numeric(df["standard_hr"], errors="coerce")
    df["standard_name"] = df["standard_name"].fillna("Unnamed Strava Activity").replace("", "Unnamed Strava Activity")
    df["standard_type"] = df["standard_type"].fillna("Unknown").replace("", "Unknown")
    df["Media"] = df["Media"].fillna("").astype(str)

    df = df.dropna(subset=["standard_date", "standard_duration", "standard_type"])
    df = df[df["standard_duration"] > 0]
    return df.sort_values("standard_date").reset_index(drop=True)


def normalized_upload_basename(file_name: str) -> str:
    return os.path.basename(file_name.replace("\\", "/")).strip().lower()


def find_activities_file(uploaded_files) -> object | None:
    csv_files = []
    for uploaded_file in uploaded_files:
        basename = normalized_upload_basename(uploaded_file.name)
        if not basename.endswith(".csv"):
            continue

        csv_files.append(uploaded_file)
        if basename == "activities.csv":
            return uploaded_file

    for uploaded_file in csv_files:
        basename = normalized_upload_basename(uploaded_file.name)
        if basename.startswith("activities") or "activities" in basename:
            return uploaded_file

    if len(csv_files) == 1:
        return csv_files[0]

    return None


def render_missing_activities_message(uploaded_files) -> None:
    uploaded_names = [uploaded_file.name for uploaded_file in uploaded_files]
    st.error("Could not find `activities.csv`. Upload the unzipped Strava export files, including activities.csv.")
    if uploaded_names:
        with st.expander("Files detected"):
            st.write(uploaded_names[:50])
            if len(uploaded_names) > 50:
                st.caption(f"Showing first 50 of {len(uploaded_names)} uploaded files.")


def is_uploaded_media_file(file_name: str) -> bool:
    normalized_name = file_name.replace("\\", "/")
    extension = os.path.splitext(normalized_name)[1].lower()
    return extension in MEDIA_EXTENSIONS and not normalized_name.endswith("/")


def safe_media_filename(file_name: str) -> str:
    filename = os.path.basename(file_name.replace("\\", "/"))
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", filename)


def save_uploaded_media_files(uploaded_files, participant_id: str) -> int:
    save_dir = f"data/strava_pictures/{participant_id}/"
    os.makedirs(save_dir, exist_ok=True)

    saved_count = 0
    for uploaded_file in uploaded_files:
        if not is_uploaded_media_file(uploaded_file.name):
            continue

        output_filename = safe_media_filename(uploaded_file.name)
        if not output_filename:
            continue

        output_path = os.path.join(save_dir, output_filename)
        with open(output_path, "wb") as output_file:
            output_file.write(uploaded_file.getbuffer())
        saved_count += 1

    return saved_count


def parse_strava_export_files(uploaded_files) -> tuple[pd.DataFrame, int, str]:
    activities_file = find_activities_file(uploaded_files)
    if activities_file is None:
        render_missing_activities_message(uploaded_files)
        return pd.DataFrame(), 0, ""

    activities_file.seek(0)
    df = parse_strava_csv(activities_file, filename=activities_file.name)
    participant_id = st.session_state.get("participant_id", "unknown_participant")
    media_count = save_uploaded_media_files(uploaded_files, participant_id)
    return df, media_count, activities_file.name


def render_strava_kpis(df: pd.DataFrame) -> None:
    total_activities = len(df)
    total_hours = df["standard_duration"].sum() / 3600
    most_common_type = df["standard_type"].mode().iloc[0] if not df.empty else "N/A"

    cols = st.columns(3)
    cols[0].metric("Total Activities", f"{total_activities:,}")
    cols[1].metric("Total Active Hours", f"{total_hours:,.1f}")
    cols[2].metric("Most Frequent Workout Type", most_common_type)


def apply_dark_plotly_layout(fig, top_margin: int = 62) -> None:
    # High-contrast Plotly styling: transparent backgrounds blend into the dark page,
    # while white 14px text keeps titles, ticks, and axis labels readable.
    fig.update_layout(
        font=dict(color="white", size=14),
        title_font=dict(color="white", size=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=top_margin, b=10),
        xaxis=dict(tickfont=dict(color="white", size=13), title_font=dict(color="white", size=14)),
        yaxis=dict(tickfont=dict(color="white", size=13), title_font=dict(color="white", size=14)),
    )


def render_workout_type_distribution(df: pd.DataFrame) -> None:
    type_counts = df["standard_type"].value_counts().reset_index()
    type_counts.columns = ["Activity Type", "Count"]

    fig = px.bar(
        type_counts,
        x="Activity Type",
        y="Count",
        title="Workout Types Distribution",
        height=400,
        text="Count",
        color_discrete_sequence=[STRAVA_ORANGE],
    )
    fig.update_traces(marker_color=STRAVA_ORANGE, textposition="auto", cliponaxis=False)
    apply_dark_plotly_layout(fig, top_margin=76)
    max_count = type_counts["Count"].max()
    fig.update_yaxes(range=[0, max_count * 1.18 if max_count else 1])
    st.plotly_chart(fig, use_container_width=True)


def assign_hr_zone(heart_rate: float) -> str:
    """Bucket average heart rate into standard training zones for participant-friendly insight."""
    if heart_rate < 110:
        return "Zone 1 (Recovery)"
    if heart_rate <= 130:
        return "Zone 2 (Endurance)"
    if heart_rate <= 150:
        return "Zone 3 (Tempo)"
    if heart_rate <= 170:
        return "Zone 4 (Threshold)"
    return "Zone 5 (Anaerobic/Max)"


def render_hr_zone_distribution(df: pd.DataFrame) -> None:
    # HR is optional in Strava exports. Check for usable values before plotting
    # so participants without heart-rate data see a clear message instead of an empty chart.
    if "standard_hr" not in df.columns or df["standard_hr"].dropna().empty:
        st.warning("No heart rate data found in your Strava export.")
        return

    hr_df = df.dropna(subset=["standard_hr"]).copy()
    hr_df["standard_date"] = pd.to_datetime(hr_df["standard_date"], errors="coerce")
    hr_df["standard_duration"] = pd.to_numeric(hr_df["standard_duration"], errors="coerce")
    hr_df = hr_df.dropna(subset=["standard_date", "standard_duration", "standard_hr"])
    if hr_df.empty:
        st.warning("No heart rate data found in your Strava export.")
        return

    hr_df["duration_minutes"] = hr_df["standard_duration"] / 60
    # Keep the HR zone label in the dataframe for hover context, while the visual
    # zone structure itself is drawn as infographic background bands.
    hr_df["HR_Zone"] = hr_df["standard_hr"].apply(assign_hr_zone)

    fig = px.scatter(
        hr_df,
        x="standard_date",
        y="standard_hr",
        color="standard_type",
        size="duration_minutes",
        size_max=25,
        title="Heart Rate Timeline by Zone",
        height=400,
        hover_data={
            "standard_name": True,
            "standard_hr": ":.0f",
            "HR_Zone": True,
            "duration_minutes": ":.1f",
            "standard_duration": False,
        },
        labels={
            "standard_date": "Workout Date",
            "standard_hr": "Average Heart Rate (BPM)",
            "standard_type": "Activity Type",
            "duration_minutes": "Duration (minutes)",
            "HR_Zone": "Heart Rate Zone",
            "standard_name": "Workout Name",
        },
    )
    fig.update_traces(
        marker=dict(opacity=0.86, line=dict(color="rgba(255,255,255,0.42)", width=1)),
    )

    # Draw the HR zone bands behind the scatter points. These soft horizontal
    # rectangles turn the chart into an infographic: users can read effort zones
    # by position without relying on extra grid lines.
    for zone_label, y0, y1, fillcolor in HR_ZONE_BACKGROUNDS:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=fillcolor, line_width=0, layer="below")
        fig.add_annotation(
            x=1.0,
            y=(y0 + y1) / 2,
            xref="paper",
            yref="y",
            text=zone_label,
            showarrow=False,
            xanchor="right",
            font=dict(color="rgba(255,255,255,0.62)", size=12),
            bgcolor="rgba(0,0,0,0)",
        )

    apply_dark_plotly_layout(fig, top_margin=76)
    # Explicit y-axis boundaries and BPM tick marks make the zone thresholds
    # legible, while hiding grid lines keeps the colored zone bands visually clean.
    fig.update_yaxes(
        range=[60, 200],
        tickvals=[60, 80, 100, 110, 130, 150, 170, 190, 200],
        showgrid=False,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_layout(
        legend_title_text="Activity Type",
        hoverlabel=dict(bgcolor="rgba(15,23,42,0.96)", font=dict(color="white")),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_strava_charts(df: pd.DataFrame) -> None:
    left_col, right_col = st.columns(2)
    with left_col:
        render_workout_type_distribution(df)
    with right_col:
        render_hr_zone_distribution(df)


def render_strava_feature() -> None:
    inject_strava_css()
    st.markdown(
        """
        <section class="strava-hero">
            <h1>Upload Strava Export</h1>
            <p>Drop the unzipped Strava export files here. We will extract your activity data and workout media automatically.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Drop all files from your Strava Export",
        type=UPLOAD_FILE_TYPES,
        accept_multiple_files="directory",
    )
    st.caption(
        "Upload the unzipped Strava export folder or select all relevant files at once. "
        "Make sure `activities.csv` and the workout media files are included."
    )

    if not uploaded_files:
        st.info("Drop the unzipped Strava export files to continue.")
        return

    df, media_count, source_file = parse_strava_export_files(uploaded_files)
    if df.empty:
        st.warning("No valid Strava workouts were found after parsing dates and elapsed time.")
        return

    logged_files = st.session_state.setdefault("logged_strava_files", set())
    participant_id = st.session_state.get("participant_id")
    upload_key = "|".join(sorted(uploaded_file.name for uploaded_file in uploaded_files))
    if participant_id and upload_key not in logged_files:
        log_strava_upload(participant_id, source_file or "unzipped_strava_export")
        logged_files.add(upload_key)

    if participant_id:
        save_strava_activities(participant_id, df, source_file=source_file or "unzipped_strava_export")

    st.session_state.strava_uploaded = True
    st.session_state.strava_df = df

    st.success(f"Strava export processed. Saved {media_count:,} workout media file(s) for this participant.")
    render_strava_kpis(df)
    render_strava_charts(df)

    st.divider()
    if st.button("Next: View Combined Insights", type="primary", use_container_width=True):
        with st.spinner("Processing data..."):
            st.info(
                "Combining Spotify and Strava data automatically. "
                "This may take a couple of minutes, please wait patiently..."
            )
            st.session_state.current_page = "Combined Insights"
            # Give Streamlit a brief moment to render the expectation-setting state
            # before the next page starts BPM enrichment and workout matching.
            time.sleep(2)
            st.rerun()
