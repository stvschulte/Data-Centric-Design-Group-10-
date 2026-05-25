from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from utils.db_handler import create_participant


def render_consent_page() -> None:
    st.markdown(
        """
        <style>
        .consent-shell {
            padding: 42px 44px;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(15,23,42,0.92), rgba(30,41,59,0.82));
            border: 1px solid rgba(148,163,184,0.22);
            color: #f8fafc;
            margin-bottom: 26px;
        }
        .consent-shell h1 {
            margin: 0;
            font-size: 48px;
            font-weight: 850;
            letter-spacing: 0;
        }
        .consent-shell p {
            max-width: 820px;
            color: #cbd5e1;
            font-size: 18px;
            line-height: 1.6;
        }
        </style>
        <section class="consent-shell">
            <h1>Informed Consent</h1>
            <p>Review the study information below. You can continue only after confirming each consent statement.</p>
        </section>
        """,
        unsafe_allow_html=True,
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
