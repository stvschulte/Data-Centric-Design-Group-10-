import pandas as pd
import streamlit as st

from utils.db_handler import log_strava_upload


def _mock_strava_dataframe() -> pd.DataFrame:
    """Replace this later with project-specific Strava data cleaning."""
    return pd.DataFrame(
        {
            "day": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "distance_km": [4.2, 0.0, 6.1, 5.0, 8.3],
            "average_heartrate": [142, 0, 151, 147, 158],
        }
    )


def render_strava_feature() -> None:
    st.title("Strava Upload")
    st.write("Upload exported Strava CSV files. No Strava OAuth or external API is used.")

    uploaded_files = st.file_uploader(
        "Strava CSV files",
        type=["csv"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload a CSV file to preview placeholder Strava insights.")
        return

    participant_id = st.session_state.participant_id
    for uploaded_file in uploaded_files:
        log_strava_upload(participant_id, uploaded_file.name)

    st.session_state.strava_uploaded = True

    mock_df = _mock_strava_dataframe()
    st.subheader("Mock Strava Preview")
    st.dataframe(mock_df, use_container_width=True, hide_index=True)
    st.line_chart(mock_df.set_index("day")[["distance_km", "average_heartrate"]])

    st.success("Strava upload logged. Add real data-cleaning logic in `features/strava_feature.py`.")
