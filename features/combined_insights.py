import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


GREEN = "#1DB954"
ORANGE = "#FC4C02"


def inject_combined_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                radial-gradient(circle at top left, rgba(29,185,84,0.20), transparent 34%),
                radial-gradient(circle at top right, rgba(252,76,2,0.18), transparent 32%),
                linear-gradient(135deg, #05070a, #101318 56%, #090b0f);
            color: #f8fafc;
        }}
        .combined-hero {{
            min-height: 250px;
            padding: 56px 54px;
            border-radius: 18px;
            background:
                linear-gradient(135deg, rgba(29,185,84,0.18), rgba(252,76,2,0.16)),
                url("https://images.unsplash.com/photo-1517963628607-235ccdd5476c?auto=format&fit=crop&w=1800&q=80");
            background-size: cover;
            background-position: center;
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 24px 80px rgba(0,0,0,0.45);
            margin-bottom: 28px;
        }}
        .combined-hero h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 52px;
            font-weight: 850;
            letter-spacing: 0;
        }}
        .combined-hero p {{
            max-width: 780px;
            color: #e2e8f0;
            font-size: 18px;
            line-height: 1.6;
        }}
        div[data-testid="stMetric"] {{
            background: rgba(15,23,42,0.80);
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 14px;
            padding: 18px;
        }}
        div[data-testid="stMetricValue"] {{
            color: {GREEN};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def merge_tracks_into_workouts(spotify_df: pd.DataFrame, strava_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match Spotify tracks to Strava workout windows using exact timestamps.

    For each Strava row:
    - start_time = Activity Date
    - end_time = Activity Date + Elapsed Time seconds
    - matched Spotify rows satisfy start_time <= ts <= end_time
    """
    spotify = spotify_df.copy()
    strava = strava_df.copy().sort_values("Activity Date").reset_index(drop=True)
    spotify["ts"] = pd.to_datetime(spotify["ts"], errors="coerce")
    strava["Activity Date"] = pd.to_datetime(strava["Activity Date"], errors="coerce")
    strava["Elapsed Time"] = pd.to_numeric(strava["Elapsed Time"], errors="coerce")

    if getattr(spotify["ts"].dt, "tz", None) is not None:
        spotify["ts"] = spotify["ts"].dt.tz_convert(None)
    if getattr(strava["Activity Date"].dt, "tz", None) is not None:
        strava["Activity Date"] = strava["Activity Date"].dt.tz_convert(None)

    workout_rows = []
    track_rows = []
    for idx, workout in strava.iterrows():
        start_time = workout["Activity Date"]
        end_time = start_time + pd.to_timedelta(workout["Elapsed Time"], unit="s")
        workout_label = f"{workout['Activity Name']} ({start_time:%Y-%m-%d %H:%M})"

        matched_tracks = spotify[(spotify["ts"] >= start_time) & (spotify["ts"] <= end_time)].copy()
        tracklist = [
            f"{row['master_metadata_track_name']} - {row['master_metadata_album_artist_name']}"
            for _, row in matched_tracks.iterrows()
        ]

        workout_rows.append(
            {
                "workout_id": idx + 1,
                "Workout": workout_label,
                "Activity Name": workout["Activity Name"],
                "Activity Type": workout["Activity Type"],
                "Start": start_time,
                "End": end_time,
                "Duration Minutes": workout["Elapsed Time"] / 60,
                "Tracks Played": len(matched_tracks),
                "Tracklist": ", ".join(tracklist) if tracklist else "No Spotify tracks during workout",
            }
        )

        for _, track in matched_tracks.iterrows():
            track_rows.append(
                {
                    "workout_id": idx + 1,
                    "Workout": workout_label,
                    "Activity Type": workout["Activity Type"],
                    "Track Time": track["ts"],
                    "Track": track["master_metadata_track_name"],
                    "Artist": track["master_metadata_album_artist_name"],
                    "ms_played": track["ms_played"],
                }
            )

    return pd.DataFrame(workout_rows), pd.DataFrame(track_rows)


def render_timeline(workouts_df: pd.DataFrame, tracks_df: pd.DataFrame) -> None:
    fig = px.timeline(
        workouts_df,
        x_start="Start",
        x_end="End",
        y="Workout",
        color="Activity Type",
        hover_data=["Duration Minutes", "Tracks Played"],
        title="Workout Timeline with Spotify Track Markers",
        color_discrete_sequence=[ORANGE, GREEN, "#2563EB", "#9333EA", "#F59E0B"],
    )
    fig.update_yaxes(autorange="reversed")

    if not tracks_df.empty:
        fig.add_trace(
            go.Scatter(
                x=tracks_df["Track Time"],
                y=tracks_df["Workout"],
                mode="markers",
                name="Spotify track",
                marker=dict(color=GREEN, size=9, symbol="diamond", line=dict(color="#ffffff", width=1)),
                customdata=tracks_df[["Track", "Artist"]],
                hovertemplate="Track: %{customdata[0]}<br>Artist: %{customdata[1]}<br>Time: %{x}<extra></extra>",
            )
        )

    fig.update_layout(template="plotly_dark", height=620, margin=dict(l=10, r=10, t=70, b=10))
    st.plotly_chart(fig, use_container_width=True)


def render_artist_bar(tracks_df: pd.DataFrame) -> None:
    if tracks_df.empty:
        st.info("No Spotify artists were found inside the uploaded workout windows.")
        return

    artist_counts = (
        tracks_df.groupby(["Artist", "Activity Type"], as_index=False)
        .size()
        .sort_values("size", ascending=False)
    )
    top_artists = artist_counts.groupby("Artist")["size"].sum().nlargest(10).index
    artist_counts = artist_counts[artist_counts["Artist"].isin(top_artists)]

    fig = px.bar(
        artist_counts,
        x="Artist",
        y="size",
        color="Activity Type",
        barmode="group",
        labels={"size": "Tracks played during workouts"},
        title="Most Listened to Artists During Workouts",
        color_discrete_sequence=[GREEN, ORANGE, "#2563EB", "#9333EA", "#F59E0B"],
    )
    fig.update_layout(template="plotly_dark", height=480, margin=dict(l=10, r=10, t=70, b=10))
    st.plotly_chart(fig, use_container_width=True)


def render_workout_track_table(workouts_df: pd.DataFrame) -> None:
    display_df = workouts_df[
        ["Activity Name", "Activity Type", "Start", "End", "Duration Minutes", "Tracks Played", "Tracklist"]
    ].copy()
    display_df["Start"] = display_df["Start"].dt.strftime("%Y-%m-%d %H:%M")
    display_df["End"] = display_df["End"].dt.strftime("%Y-%m-%d %H:%M")
    display_df["Duration Minutes"] = display_df["Duration Minutes"].round(1)
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_combined_insights() -> None:
    inject_combined_css()
    st.markdown(
        """
        <section class="combined-hero">
            <h1>Combined Music x Workout Insights</h1>
            <p>Spotify tracks are matched into exact Strava workout time windows using uploaded participant data only.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    spotify_df = st.session_state.get("spotify_df")
    strava_df = st.session_state.get("strava_df")
    if spotify_df is None or strava_df is None or spotify_df.empty or strava_df.empty:
        st.warning("Spotify and Strava uploads are both required before combined insights can be generated.")
        cols = st.columns(2)
        if cols[0].button("Go to Spotify Upload", use_container_width=True):
            st.session_state.current_page = "Spotify Upload"
            st.session_state.participant_nav = "Spotify Upload"
            st.rerun()
        if cols[1].button("Go to Strava Upload", use_container_width=True):
            st.session_state.current_page = "Strava Upload"
            st.session_state.participant_nav = "Strava Upload"
            st.rerun()
        return

    workouts_df, tracks_df = merge_tracks_into_workouts(spotify_df, strava_df)

    metric_cols = st.columns(3)
    metric_cols[0].metric("Workouts Analyzed", f"{len(workouts_df):,}")
    metric_cols[1].metric("Workout Tracks Found", f"{len(tracks_df):,}")
    metric_cols[2].metric("Workouts with Music", f"{(workouts_df['Tracks Played'] > 0).sum():,}")

    render_timeline(workouts_df, tracks_df)
    render_artist_bar(tracks_df)

    st.subheader("Exact Tracklist by Workout")
    render_workout_track_table(workouts_df)
