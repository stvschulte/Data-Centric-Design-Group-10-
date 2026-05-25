import streamlit as st

from features.combined_insights import render_combined_insights
from features.consent_page import render_consent_page
from features.researcher_dashboard import render_researcher_dashboard
from features.spotify_feature import render_spotify_feature
from features.strava_feature import render_strava_feature
from utils.db_handler import init_db


PARTICIPANT_PAGES = {
    "Consent": render_consent_page,
    "Spotify Upload": render_spotify_feature,
    "Strava Upload": render_strava_feature,
    "Combined Insights": render_combined_insights,
}

RESEARCHER_PAGES = {
    "Researcher Dashboard": render_researcher_dashboard,
}


def init_session_state() -> None:
    """Initialize every shared state key in one place."""
    defaults = {
        "participant_id": None,
        "consent_given": False,
        "current_page": "Consent",
        "spotify_uploaded": False,
        "strava_uploaded": False,
        "researcher_authenticated": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sidebar() -> str:
    st.sidebar.title("Navigation")
    current_page = st.session_state.current_page
    participant_options = list(PARTICIPANT_PAGES.keys())
    researcher_options = ["None"] + list(RESEARCHER_PAGES.keys())
    participant_index = participant_options.index(current_page) if current_page in participant_options else 0
    researcher_index = researcher_options.index(current_page) if current_page in researcher_options else 0

    st.sidebar.header("Participants Flow")
    participant_choice = st.sidebar.radio(
        "Participant pages",
        participant_options,
        index=participant_index,
        label_visibility="collapsed",
    )

    st.sidebar.header("Researcher Area")
    researcher_choice = st.sidebar.radio(
        "Researcher pages",
        researcher_options,
        index=researcher_index,
        label_visibility="collapsed",
    )

    selected_page = researcher_choice if researcher_choice != "None" else participant_choice

    if selected_page in PARTICIPANT_PAGES and not st.session_state.consent_given:
        selected_page = "Consent"
        st.sidebar.warning("Consent is required before continuing.")

    st.session_state.current_page = selected_page
    return selected_page


def main() -> None:
    st.set_page_config(
        page_title="Data-Centric Research App",
        page_icon="📊",
        layout="wide",
    )

    init_session_state()
    init_db()

    selected_page = render_sidebar()

    if selected_page in RESEARCHER_PAGES:
        RESEARCHER_PAGES[selected_page]()
    else:
        PARTICIPANT_PAGES[selected_page]()


if __name__ == "__main__":
    main()
