import pandas as pd
import streamlit as st

from utils.db_handler import log_spotify_upload


def _mock_spotify_dataframe() -> pd.DataFrame:
    """Replace this later with project-specific Spotify data cleaning."""
    return pd.DataFrame(
        {
            "track": ["Track A", "Track B", "Track C", "Track D"],
            "minutes_played": [12, 25, 7, 19],
        }
    )


def render_spotify_feature() -> None:
    st.title("Spotify Upload")
    st.write("Upload exported Spotify CSV or JSON files. No external API is used.")

    uploaded_files = st.file_uploader(
        "Spotify files",
        type=["csv", "json"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload a CSV or JSON file to preview placeholder Spotify insights.")
        return

    participant_id = st.session_state.participant_id
    for uploaded_file in uploaded_files:
        log_spotify_upload(participant_id, uploaded_file.name)

    st.session_state.spotify_uploaded = True

    mock_df = _mock_spotify_dataframe()
    st.subheader("Mock Spotify Preview")
    st.dataframe(mock_df, use_container_width=True, hide_index=True)
    st.bar_chart(mock_df.set_index("track"))

    st.success("Spotify upload logged. Add real data-cleaning logic in `features/spotify_feature.py`.")
