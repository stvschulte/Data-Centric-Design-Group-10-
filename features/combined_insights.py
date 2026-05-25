import pandas as pd
import streamlit as st


def _mock_combined_dataframe() -> pd.DataFrame:
    """Replace this later with merged Spotify + Strava analysis outputs."""
    return pd.DataFrame(
        {
            "session": ["Workout 1", "Workout 2", "Workout 3", "Workout 4"],
            "music_minutes": [35, 28, 42, 31],
            "activity_minutes": [40, 30, 45, 34],
            "mock_alignment_score": [0.82, 0.67, 0.91, 0.74],
        }
    )


def render_combined_insights() -> None:
    st.title("Combined Insights")

    if not st.session_state.spotify_uploaded or not st.session_state.strava_uploaded:
        st.warning("Upload both Spotify and Strava files before interpreting combined insights.")

    mock_df = _mock_combined_dataframe()

    st.subheader("Mock Combined Dataset")
    st.dataframe(mock_df, use_container_width=True, hide_index=True)

    st.subheader("Placeholder Alignment Chart")
    st.line_chart(mock_df.set_index("session")[["music_minutes", "activity_minutes"]])

    st.subheader("Placeholder Score Chart")
    st.bar_chart(mock_df.set_index("session")[["mock_alignment_score"]])

    st.info("Add merged-data logic in `features/combined_insights.py` after upload cleaning is stable.")
