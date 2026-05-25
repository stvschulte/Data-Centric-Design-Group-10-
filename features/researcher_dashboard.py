import streamlit as st

from utils.auth import require_researcher_auth
from utils.db_handler import (
    get_participant_upload_logs,
    get_participants,
    get_summary_metrics,
)


def render_researcher_dashboard() -> None:
    st.title("Researcher Dashboard")

    if not require_researcher_auth():
        st.error("Researcher authentication required.")
        st.stop()

    summary = get_summary_metrics()
    metric_cols = st.columns(3)
    metric_cols[0].metric("Total Participants", summary["total_participants"])
    metric_cols[1].metric("Spotify Uploads", summary["spotify_uploads"])
    metric_cols[2].metric("Strava Uploads", summary["strava_uploads"])

    participants_df = get_participants()
    st.subheader("Participants")

    if participants_df.empty:
        st.info("No participant records found yet.")
        return

    st.dataframe(participants_df, use_container_width=True, hide_index=True)

    participant_options = participants_df["id"].tolist()
    selected_participant = st.selectbox("Inspect participant logs", participant_options)

    logs = get_participant_upload_logs(selected_participant)
    st.write(f"Upload logs for `{selected_participant}`")

    st.markdown("**Spotify uploads**")
    st.dataframe(logs["spotify"], use_container_width=True, hide_index=True)

    st.markdown("**Strava uploads**")
    st.dataframe(logs["strava"], use_container_width=True, hide_index=True)
