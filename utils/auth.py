import streamlit as st


RESEARCHER_PASSWORD = "0000"


def require_researcher_auth() -> bool:
    """Hardcoded boilerplate auth. Replace before real deployment."""
    if st.session_state.get("researcher_authenticated"):
        return True

    password = st.text_input("Researcher password", type="password")
    if password == RESEARCHER_PASSWORD:
        st.session_state.researcher_authenticated = True
        st.success("Researcher access granted.")
        return True

    return False
