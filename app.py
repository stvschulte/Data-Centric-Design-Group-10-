import streamlit as st
import pandas as pd
import json
import altair as alt
import hashlib
import xml.etree.ElementTree as ET

# -----------------------------------------------------------------------------
# Configuration & State Management
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Spotify x Strava Analyzer", layout="wide", page_icon="⚡")

def init_session_state():
    if 'step' not in st.session_state:
        st.session_state.step = 1
    if 'spotify_data' not in st.session_state:
        st.session_state.spotify_data = None
    if 'workout_data' not in st.session_state:
        st.session_state.workout_data = None

def next_step():
    st.session_state.step += 1

def reset_app():
    st.session_state.step = 1
    st.session_state.spotify_data = None
    st.session_state.workout_data = None
    st.rerun()

# -----------------------------------------------------------------------------
# Custom Theming Engine
# -----------------------------------------------------------------------------
def apply_theme(step):
    """Injects custom CSS based on the current step to match brand identities."""
    if step == 1:
        # Home Page Theme (Deep Space / Purple)
        bg1, bg2, bg3 = "#0F0C29", "#302B63", "#0F0C29"
        accent_light, accent_dark = "#D8B4FE", "#8A2BE2"
    elif step == 2:
        # Spotify Theme (Deep Emerald)
        bg1, bg2, bg3 = "#051A0F", "#114022", "#051A0F"
        accent_light, accent_dark = "#4ADE80", "#1DB954"
    elif step == 3:
        # Apple Health Theme (Activity Rings / Deep Red)
        bg1, bg2, bg3 = "#1C0000", "#4A0005", "#1C0000"
        accent_light, accent_dark = "#FF2D55", "#D70015"
    else:
        # Combined Analysis Theme (Deep Ocean)
        bg1, bg2, bg3 = "#0A131F", "#0F2D54", "#0A131F"
        accent_light, accent_dark = "#93C5FD", "#3B82F6"
        
    custom_css = f"""
    <style>
    /* Hide default Streamlit clutter for a native app feel */
    [data-testid="stHeader"] {{ visibility: hidden !important; }}
    #MainMenu {{ visibility: hidden !important; }}
    footer {{ visibility: hidden !important; }}
    
    /* Fluid Gradient Background */
    [data-testid="stAppViewContainer"] {{
        background: linear-gradient(135deg, {bg1}, {bg2}, {bg3}) !important;
        background-size: 200% 200% !important;
        animation: gradientBG 15s ease infinite !important;
    }}
    @keyframes gradientBG {{
        0% {{background-position: 0% 50%;}}
        50% {{background-position: 100% 50%;}}
        100% {{background-position: 0% 50%;}}
    }}
    
    /* Adjust padding to center content beautifully */
    .block-container {{
        padding-top: 3rem !important;
        padding-bottom: 3rem !important;
        max-width: 1050px !important;
    }}

    /* Typography & Hierarchy */
    h1, h2, h3 {{ font-family: 'Inter', 'Helvetica Neue', sans-serif; }}
    h1 {{
        background: -webkit-linear-gradient(45deg, {accent_light}, {accent_dark});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-weight: 900 !important;
        font-size: 3.5rem !important;
        letter-spacing: -1.5px !important;
        margin-bottom: 2rem !important;
        padding-bottom: 0.5rem;
    }}
    h2, h3 {{ color: #FFFFFF !important; font-weight: 700; letter-spacing: -0.5px; }}
    p, li, label {{ color: #E2E8F0 !important; font-family: 'Inter', 'Helvetica Neue', sans-serif; font-size: 1.15rem; line-height: 1.7; }}
    
    /* Frosted Glassmorphism Cards for Metrics & Data */
    div[data-testid="stMetric"] {{
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
        transition: transform 0.3s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-5px);
    }}
    div[data-testid="stMetricValue"] {{ color: {accent_light} !important; font-weight: 800; font-size: 2.5rem; }}
    div[data-testid="stMetricLabel"] {{ color: #CBD5E1 !important; font-size: 1.1rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }}
    
    /* Tactile, Illuminated Primary Buttons */
    div.stButton > button:first-child {{
        background: linear-gradient(135deg, {accent_dark}, {accent_light}) !important;
        color: #000000 !important;
        border: none;
        border-radius: 50px;
        padding: 0.75rem 3rem;
        font-size: 1.25rem;
        font-weight: 800;
        letter-spacing: 0.5px;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        box-shadow: 0 8px 25px rgba(0,0,0,0.4);
        display: block;
        margin: 2rem auto;
    }}
    div.stButton > button:first-child:hover {{
        transform: translateY(-5px) scale(1.02);
        box-shadow: 0 15px 35px {accent_dark}88;
        color: #FFFFFF !important;
    }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Data Processing & Caching
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner="Processing Spotify Data...")
def process_spotify_files(uploaded_files) -> pd.DataFrame:
    all_data = []
    for file in uploaded_files:
        data = json.load(file)
        all_data.extend(data)
        
    df = pd.DataFrame(all_data)
    
    if df.empty:
        return df

    if 'ts' in df.columns:
        df['endTime'] = pd.to_datetime(df['ts'])
        df['trackName'] = df.get('master_metadata_track_name', 'Unknown Track')
        df['artistName'] = df.get('master_metadata_album_artist_name', 'Unknown Artist')
        df['msPlayed'] = df.get('ms_played', 0)
    elif 'endTime' in df.columns:
        df['endTime'] = pd.to_datetime(df['endTime'])
    
    if df['endTime'].dt.tz is not None:
        df['endTime'] = df['endTime'].dt.tz_localize(None)
    
    df = df.dropna(subset=['trackName'])
    return df

@st.cache_data(show_spinner="Processing Apple Health Data (This may take a moment)...")
def process_apple_health_files(uploaded_files) -> pd.DataFrame:
    """Parses massive Apple Health XML exports using a memory-efficient iterparse."""
    workouts = []
    for file in uploaded_files:
        context = ET.iterparse(file, events=("start", "end"))
        for event, elem in context:
            if event == "end" and elem.tag == "Workout":
                workout_type = elem.attrib.get('workoutActivityType', '').replace('HKWorkoutActivityType', '')
                start_date = elem.attrib.get('startDate')
                end_date = elem.attrib.get('endDate')
                duration_mins = float(elem.attrib.get('duration', 0))
                
                avg_hr = 0
                for stat in elem.findall('WorkoutStatistics'):
                    if stat.attrib.get('type') == 'HKQuantityTypeIdentifierHeartRate':
                        avg_hr = float(stat.attrib.get('average', 0))
                        
                if start_date and end_date:
                    workouts.append({
                        'Activity Name': f"{workout_type} Workout",
                        'Activity Type': workout_type,
                        'Activity Date': pd.to_datetime(start_date),
                        'End Date': pd.to_datetime(end_date),
                        'Elapsed Time': duration_mins * 60, # Stored in seconds for downstream math
                        'Average Heart Rate': avg_hr
                    })
                elem.clear() # Critically important: frees memory line-by-line
                
    df = pd.DataFrame(workouts)
    
    if not df.empty:
        if df['Activity Date'].dt.tz is not None:
            df['Activity Date'] = df['Activity Date'].dt.tz_localize(None)
        
        df['End Date'] = df['Activity Date'] + pd.to_timedelta(df['Elapsed Time'], unit='s')
    return df

def get_mock_bpm(track_name: str) -> int:
    if not isinstance(track_name, str):
        return 120
    hash_val = int(hashlib.md5(track_name.encode('utf-8')).hexdigest(), 16)
    return (hash_val % 80) + 100

# -----------------------------------------------------------------------------
# UI Pages
# -----------------------------------------------------------------------------
def home_page():
    st.title("🎧 Sync & Sweat")
    st.markdown("### Discover the rhythm behind your runner's high.")
    
    st.write("---")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        Have you ever wondered if the tempo of your music drives your pace, or if you naturally gravitate towards faster songs when your heart rate spikes? **Sync & Sweat** bridges the gap between your music library and your workout logs.
        
        By merging your Spotify streaming history with your Apple Health workout logs, this tool provides deep, visual insights into your training habits and your ultimate workout soundtracks.
        
        **How it works:**
        1. **Spotify Data:** Upload your listening history to map out your musical journey.
        2. **Apple Health Data:** Upload your `export.xml` to map out your physical performance.
        3. **Analyze:** We sync the timestamps and visualize exactly what you listened to during your hardest efforts.
        """)
        st.button("Get Started 🚀", on_click=next_step, type="primary")
        
    with col2:
        # A placeholder for an aesthetic image/graphic
        st.image("https://images.unsplash.com/photo-1605296867304-46d5465a13f1?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80", 
                 caption="Find your rhythm.", use_container_width=True)


def spotify_page():
    st.title("🟢 Step 1: Your Spotify Data")
    st.markdown("Let's grab your music history. Upload your Spotify `StreamingHistory_music_0.json` file below.")
    
    spotify_files = st.file_uploader("Upload Spotify JSON files", type=['json'], accept_multiple_files=True)
    
    if spotify_files:
        df_spotify = process_spotify_files(spotify_files)
        
        if not df_spotify.empty and 'msPlayed' in df_spotify.columns:
            st.success("Spotify data successfully processed!")
            
            total_hours = df_spotify['msPlayed'].sum() / (1000 * 60 * 60)
            st.metric(label="Total Hours Listened", value=f"{total_hours:,.2f} hrs")
            
            st.subheader("Top 10 Most Played Tracks")
            top_tracks = df_spotify.groupby(['trackName', 'artistName']).size().reset_index(name='play_count')
            top_tracks = top_tracks.sort_values(by='play_count', ascending=False).head(10)
            
            # Appealing table with progress bars
            st.dataframe(
                top_tracks,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "trackName": "Track",
                    "artistName": "Artist",
                    "play_count": st.column_config.ProgressColumn("Play Count", format="%d", min_value=0, max_value=int(top_tracks['play_count'].max()))
                }
            )
            
            st.session_state.spotify_data = df_spotify
            st.button("Continue to Strava Upload ➡️", on_click=next_step, type="primary")
        else:
            st.error("Could not parse Spotify data. Ensure it is a valid streaming history JSON.")

def apple_health_page():
    st.title("🔴 Step 2: Your Apple Health Data")
    st.markdown("""
    Now let's get your workouts. Upload your Apple Health `export.xml` file below. 
    *(Note: If you still see a 200MB limit on the uploader, restart your app in the terminal using: `streamlit run app.py --server.maxUploadSize=2000`)*
    """)
    
    health_files = st.file_uploader("Upload Apple Health XML file(s)", type=['xml'], accept_multiple_files=True)
    
    if health_files:
        df_health = process_apple_health_files(health_files)
        
        if not df_health.empty and 'Activity Date' in df_health.columns:
            st.success("Apple Health data successfully processed!")
            
            st.metric(label="Total Logged Workouts", value=len(df_health))
            
            st.subheader("Activities by Type")
            if 'Activity Type' in df_health.columns:
                st.bar_chart(df_health['Activity Type'].value_counts())
            
            st.session_state.workout_data = df_health
            st.button("Continue to Combined Analysis ➡️", on_click=next_step, type="primary")
        else:
            st.error("Uploaded XML does not appear to contain valid Apple Health Workout data.")

def combined_analysis_page():
    st.title("⚡ Step 3: Combined Analysis")
    
    df_spotify = st.session_state.spotify_data
    df_workout = st.session_state.workout_data
    
    if df_spotify is not None and df_workout is not None:
        
        combined_data = []
        
        with st.spinner("Matching music to workouts..."):
            for _, row in df_workout.iterrows():
                start_time = row['Activity Date']
                end_time = row['End Date']
                
                mask = (df_spotify['endTime'] >= start_time) & (df_spotify['endTime'] <= end_time)
                workout_songs = df_spotify.loc[mask].copy()
                
                avg_hr = row.get('Average Heart Rate', 0)
                if pd.isna(avg_hr):
                    avg_hr = 0

                if not workout_songs.empty:
                    workout_songs['BPM'] = workout_songs['trackName'].apply(get_mock_bpm)
                    avg_bpm = workout_songs['BPM'].mean()
                    songs_played = len(workout_songs)
                    tracklist = ", ".join(workout_songs['trackName'].tolist())
                else:
                    avg_bpm = 0
                    songs_played = 0
                    tracklist = "No music matched"
                    
                combined_data.append({
                    'Activity Name': row.get('Activity Name', 'Workout'),
                    'Activity Type': row.get('Activity Type', 'Unknown'),
                    'Date': start_time.strftime('%Y-%m-%d'),
                    'Elapsed Time (Mins)': round(row['Elapsed Time'] / 60, 2),
                    'Average Heart Rate': avg_hr,
                    'Average Track BPM': round(avg_bpm, 1),
                    'Songs Played': songs_played,
                    'Tracklist': tracklist
                })
        
        if combined_data:
            df_combined = pd.DataFrame(combined_data)
            st.success(f"Successfully matched music to {len(df_combined)} workouts!")
            st.divider()
            
            st.subheader("❤️ Heart Rate vs. 🎵 Average Track BPM")
            if df_combined['Average Heart Rate'].sum() > 0 and df_combined['Songs Played'].sum() > 0:
                chart_hr = alt.Chart(df_combined[(df_combined['Average Heart Rate'] > 0) & (df_combined['Songs Played'] > 0)]).mark_circle(size=80, opacity=0.8).encode(
                    x=alt.X('Average Heart Rate', scale=alt.Scale(zero=False), title='Average Heart Rate (bpm)'),
                    y=alt.Y('Average Track BPM', scale=alt.Scale(zero=False), title='Average Music BPM'),
                    color=alt.Color('Activity Type', legend=alt.Legend(title="Activity")),
                    tooltip=['Activity Name', 'Date', 'Average Heart Rate', 'Average Track BPM', 'Songs Played']
                ).interactive()
                st.altair_chart(chart_hr, use_container_width=True)
            else:
                st.warning("Not enough Heart Rate or matched music data to chart.")

            st.subheader("⏱️ Workout Duration vs. 🎵 Average Track BPM")
            chart_dur = alt.Chart(df_combined[df_combined['Songs Played'] > 0]).mark_circle(size=80, opacity=0.8).encode(
                x=alt.X('Elapsed Time (Mins)', title='Workout Duration (Minutes)'),
                y=alt.Y('Average Track BPM', scale=alt.Scale(zero=False), title='Average Music BPM'),
                color=alt.Color('Activity Type', legend=alt.Legend(title="Activity")),
                size=alt.Size('Songs Played', legend=None),
                tooltip=['Activity Name', 'Elapsed Time (Mins)', 'Average Track BPM', 'Songs Played', 'Tracklist']
            ).interactive()
            st.altair_chart(chart_dur, use_container_width=True)
            
            st.subheader("📋 Workout & Playlist Breakdown")
            st.dataframe(
                df_combined[['Date', 'Activity Name', 'Activity Type', 'Average Heart Rate', 'Average Track BPM', 'Songs Played', 'Tracklist']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Average Heart Rate": st.column_config.NumberColumn("Avg HR (bpm)", format="%d"),
                    "Average Track BPM": st.column_config.NumberColumn("Avg Music BPM", format="%d"),
                    "Songs Played": st.column_config.NumberColumn("Songs"),
                    "Elapsed Time (Mins)": st.column_config.NumberColumn("Duration (min)", format="%.1f")
                }
            )
            
            csv = df_combined.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Combined Data as CSV",
                data=csv,
                file_name='spotify_health_combined.csv',
                mime='text/csv',
            )
        else:
            st.warning("No overlapping data found between your Spotify and Apple Health exports.")
        
        st.divider()
        st.button("Start Over 🔄", on_click=reset_app)

# -----------------------------------------------------------------------------
# Main App Execution
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    init_session_state()
    apply_theme(st.session_state.step)
    
    if st.session_state.step == 1:
        home_page()
    elif st.session_state.step == 2:
        spotify_page()
    elif st.session_state.step == 3:
        apple_health_page()
    elif st.session_state.step == 4:
        combined_analysis_page()