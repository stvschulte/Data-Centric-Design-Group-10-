from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from utils.db_handler import create_participant


def render_consent_page() -> None:
    st.title("Informed Consent")
    st.write(
        "Please read each section carefully. You can only continue after all consent "
        "items have been checked."
    )

    with st.expander("Purpose", expanded=True):
        st.write(
            "This study explores relationships between personal activity data, music "
            "listening behavior, and participant reflections in a data-centric design context."
        )

    with st.expander("Procedures"):
        st.write(
            "You may be asked to upload exported Spotify and Strava files. The app uses "
            "placeholder analysis in this boilerplate; project-specific cleaning scripts "
            "can be added later inside the relevant feature modules."
        )

    with st.expander("Data Privacy"):
        st.write(
            "Uploaded files are processed locally by this app. The local database stores "
            "participant IDs and upload logs only. The `/data/` folder is ignored by Git."
        )

    with st.expander("Right to Withdraw"):
        st.write(
            "Participation is voluntary. You may stop using the application at any time "
            "without giving a reason."
        )

    understands_purpose = st.checkbox("I have read and understood the study purpose.")
    understands_data = st.checkbox("I understand how my uploaded data will be handled.")
    understands_withdrawal = st.checkbox("I understand that I can withdraw at any time.")

    if understands_purpose and understands_data and understands_withdrawal:
        if st.button("I Agree & Start", type="primary"):
            participant_id = f"P-{uuid4().hex[:12]}"
            consent_timestamp = datetime.now(timezone.utc).isoformat()
            create_participant(
                participant_id=participant_id,
                consent_timestamp=consent_timestamp,
                status="consented",
            )
            st.session_state.participant_id = participant_id
            st.session_state.consent_given = True
            st.session_state.current_page = "Spotify Upload"
            st.rerun()
    else:
        st.info("Check all three consent items to continue.")
