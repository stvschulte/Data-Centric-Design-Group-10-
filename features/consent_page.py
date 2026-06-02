import streamlit as st

from utils.db_handler import create_participant


def render_consent_page() -> None:
    st.markdown(
        """
        <style>
        .consent-hero {
            padding: 56px 36px;
            margin-bottom: 24px;
            border-radius: 18px;
            background:
                linear-gradient(135deg, rgba(8, 18, 38, 0.98), rgba(13, 40, 57, 0.94) 54%, rgba(252, 76, 2, 0.72));
            border: 1px solid rgba(255, 255, 255, 0.14);
            box-shadow: 0 24px 80px rgba(2, 6, 23, 0.32);
            color: #ffffff;
            text-align: center;
        }
        .consent-hero h1 {
            margin: 0;
            color: #ffffff;
            font-size: 48px;
            font-weight: 850;
            letter-spacing: 0;
        }
        .consent-intro {
            max-width: 900px;
            margin: 0 auto 26px auto;
            color: #334155;
            font-size: 18px;
            line-height: 1.65;
            text-align: center;
        }
        </style>
        <section class="consent-hero">
            <h1>Data-Centric Workout Analyzer</h1>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <p class="consent-intro">
            Welcome. This tool explores the relationship between your music tempo and physical exertion.
            Before we begin, please review the informed consent below.
        </p>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Purpose of the Study"):
        st.write(
            "The purpose of this project, conducted as part of the Data-Centric Design for Connected Products (IDEM2213) course at Delft University of Technology, is to investigate the correlation between musical tempo (BPM) and physical exertion during exercise. By analyzing your donated Spotify listening history alongside your Strava workout data, we aim to uncover behavioral patterns regarding how music influences workout intensity."
        )

    with st.expander("Study Procedures"):
        st.write(
            "If you agree to participate, you will be asked to upload two personal datasets: an export of your Spotify Extended Streaming History (JSON format) and an export of your Strava Activity History (CSV format). The application will process these files to extract timestamps, workout durations, heart rate (if available), and track metadata (including BPM). You will then be presented with a personal dashboard visualizing your combined data. Finally, you will be asked to provide qualitative feedback reflecting on the generated insights."
        )

    with st.expander("Data Privacy & Storage"):
        st.write(
            "Your privacy is paramount. This application operates entirely within your local environment; no personal data is transmitted to external servers or third-party AI tools. The data you upload is temporarily stored in a local SQLite database for the duration of the analysis. In accordance with TU Delft Human Research Ethics guidelines, all data will be permanently deleted upon the completion of this course. Only the anonymized, aggregated findings and your qualitative reflections will be used in the final DCD Process Log deliverable."
        )

    with st.expander("Right to Withdraw"):
        st.write(
            "Your participation in this data donation is entirely voluntary. You have the right to withdraw your consent and cease participation at any time without providing a reason. Refusing to participate or withdrawing your data will have no negative consequences, nor will it impact the assessment of any group member. If you choose to withdraw, simply close the application; any locally cached data will not be preserved beyond your active session."
        )

    understands_study = st.checkbox(
        "I have read and understood the purpose, procedures, and privacy measures of this study."
    )
    understands_voluntary = st.checkbox(
        "I understand that my participation is voluntary and that I may withdraw at any time."
    )
    explicitly_consents = st.checkbox(
        "I explicitly consent to the local processing of my personal Spotify and Strava data for this project."
    )

    # The start button is intentionally hidden until every active-consent item is checked.
    if understands_study and understands_voluntary and explicitly_consents:
        if st.button("I Agree & Start Uploading", type="primary"):
            # Routing logic starts by generating a participant-scoped ID before any upload can happen.
            import uuid
            st.session_state.participant_id = str(uuid.uuid4())[:8]
            create_participant(participant_id=st.session_state.participant_id, status="consented")
            st.session_state.consent_given = True
            st.session_state.current_page = 'Spotify Upload'
            st.rerun()
