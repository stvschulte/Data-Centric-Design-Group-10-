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
        # Strava Theme (Deep Orange)
        bg1, bg2, bg3 = "#131313", "#2F2F2F", "#131313"
        accent_light, accent_dark = "#896A5E", "#FC4C02"
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

# Removed @st.cache_data so we can securely handle raw image bytes in memory
def process_strava_files(uploaded_files):
    """Parses Strava activities CSV and associated media files."""
    if not uploaded_files:
        return pd.DataFrame(), {}
        
    activities_files = [f for f in uploaded_files if f.name.lower().endswith('.csv') and 'media' not in f.name.lower()]
    media_files = [f for f in uploaded_files if f.name.lower().endswith('.csv') and 'media' in f.name.lower()]
    image_files = [f for f in uploaded_files if f.name.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    if not activities_files:
        activities_files = [f for f in uploaded_files if f.name.lower().endswith('.csv')]
        
    if not activities_files:
        st.error("The uploaded files must contain at least the 'activities.csv' file.")
        return pd.DataFrame(), {}
        
    df = pd.concat([pd.read_csv(f) for f in activities_files], ignore_index=True)

    if 'Activity Date' not in df.columns or 'Elapsed Time' not in df.columns:
        st.error("The uploaded CSV must contain at least 'Activity Date' and 'Elapsed Time' columns.")
        return pd.DataFrame(), {}

    df['Activity Date'] = pd.to_datetime(df['Activity Date'])
    if df['Activity Date'].dt.tz is not None:
        df['Activity Date'] = df['Activity Date'].dt.tz_localize(None)
    
    df['End Date'] = df['Activity Date'] + pd.to_timedelta(df['Elapsed Time'], unit='s')

    # Robust parsing to avoid chart filtering bugs, bringing in the exertion slider values
    df['Average Heart Rate'] = pd.to_numeric(df.get('Average Heart Rate', 0), errors='coerce').fillna(0)
    df['Perceived Exertion'] = pd.to_numeric(df.get('Perceived Exertion', 0), errors='coerce').fillna(0)
    df['Perceived Relative Effort'] = pd.to_numeric(df.get('Perceived Relative Effort', 0), errors='coerce').fillna(0)
    
    df['Activity Type'] = df.get('Activity Type', 'Workout')
    df['Activity Name'] = df.get('Activity Name', df['Activity Type'] + " Workout")

    activity_id_col = next((col for col in df.columns if col.lower() == 'activity id'), None)
    df['Activity ID'] = df[activity_id_col] if activity_id_col else df.index

    workout_images = {}
    if image_files:
        img_dict = {img.name: img for img in image_files}
        
        # 1. Probeer te koppelen via media.csv (indien aanwezig)
        if media_files:
            try:
                media_df = pd.read_csv(media_files[0])
                m_act_col = next((col for col in media_df.columns if 'activity' in col.lower()), None)
                m_file_col = next((col for col in media_df.columns if 'file' in col.lower() or 'path' in col.lower() or 'name' in col.lower()), None)
                
                if m_act_col and m_file_col:
                    for _, row in media_df.iterrows():
                        act_id, filepath = row[m_act_col], str(row[m_file_col])
                        filename = filepath.replace('\\', '/').split('/')[-1]
                        if filename in img_dict:
                            workout_images.setdefault(act_id, []).append(img_dict[filename].getvalue())
            except Exception as e:
                st.warning(f"Could not parse media files: {e}")
                
        # 2. Zoek rechtstreeks in activities.csv naar de afbeeldingsnaam (als de naam hier beschreven staat)
        for col in df.columns:
            if df[col].dtype == object:
                for _, row in df.iterrows():
                    val = str(row[col])
                    if val != 'nan' and val != 'None':
                        act_id = row['Activity ID']
                        for img_name, img_file in img_dict.items():
                            if img_name in val:
                                img_bytes = img_file.getvalue()
                                if act_id not in workout_images or img_bytes not in workout_images.get(act_id, []):
                                    workout_images.setdefault(act_id, []).append(img_bytes)

    cols_to_keep = ['Activity ID', 'Activity Name', 'Activity Type', 'Activity Date', 'End Date', 'Elapsed Time', 'Average Heart Rate', 'Perceived Exertion', 'Perceived Relative Effort']
    return df[cols_to_keep], workout_images

def get_mock_bpm(track_name: str) -> int:
    if not isinstance(track_name, str):
        return 120
    hash_val = int(hashlib.md5(track_name.encode('utf-8')).hexdigest(), 16)
    return (hash_val % 80) + 100

def get_mock_danceability(track_name: str) -> float:
    """Generates a mock danceability score between 0.0 and 1.0."""
    if not isinstance(track_name, str):
        return 0.5
    hash_val = int(hashlib.md5(track_name.encode('utf-8')).hexdigest(), 16)
    return ((hash_val % 100) / 100.0)

def get_mock_cover(track_name: str) -> str:
    """Generates a mock album cover URL based on the track name."""
    if not isinstance(track_name, str):
        return "https://picsum.photos/50/50"
    hash_val = hashlib.md5(track_name.encode('utf-8')).hexdigest()
    return f"https://picsum.photos/seed/{hash_val}/50/50"

def get_mock_genre(artist_name: str) -> str:
    """Generates a mock genre from a predefined list based on artist name."""
    if not isinstance(artist_name, str):
        return "Unknown"
    genres = ["Pop", "Rock", "Hip-Hop", "Electronic", "Indie", "Classical", "Jazz", "Metal"]
    hash_val = int(hashlib.md5(artist_name.encode('utf-8')).hexdigest(), 16)
    return genres[hash_val % len(genres)]

def analyze_image_fatigue(image_bytes: bytes) -> int:
    """
    Simuleert AI gezichtsherkenning en zweet-analyse voor vermoeidheid (0-100%).
    """
    if not image_bytes:
        return 0
        
    # We hashen de VOLLEDIGE afbeelding voor unieke variatie (i.p.v. alleen de metadata-header)
    full_hash = hashlib.md5(image_bytes).hexdigest()
    hash_int = int(full_hash, 16)
    
    # Simuleer "Gezichtsherkenning": is het gezicht duidelijk in beeld?
    face_present = (hash_int % 2 == 0)
    
    # Simuleer "Zweet/Roodheid": gebaseerd op complexiteit van de byte-data
    sweat_factor = len(image_bytes) % 40
    
    if face_present:
        # Gezicht gevonden: score valt hoger uit (tussen 30% en 100%)
        return min(100, (hash_int % 50) + 30 + sweat_factor)
    else:
        # Geen gezicht duidelijk in beeld (bijv. een foto van de omgeving): lagere score
        return min(100, (hash_int % 40) + 10 + (sweat_factor // 2))

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
        Have you ever wondered if the tempo of your music drives your pace, or if you naturally gravitate towards faster songs when your heart rate spikes? **Sync & Sweat** bridges the gap between your music library and your workout data.
        
        By merging your Spotify streaming history with your Strava workout logs, this tool provides deep, visual insights into your training habits and your ultimate workout soundtracks.
        
        **How it works:**
        1. **Spotify Data:** Upload your listening history to map out your musical journey.
        2. **Strava Data:** Upload your `activities.csv` to map out your physical performance.
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
            
            if 'Genre' not in df_spotify.columns:
                df_spotify['Genre'] = df_spotify['artistName'].apply(get_mock_genre)
            
            st.subheader("Top 5 Most Played Tracks")
            top_tracks = df_spotify.groupby(['trackName', 'artistName']).size().reset_index(name='play_count')
            top_tracks = top_tracks.sort_values(by='play_count', ascending=False).head(5)
            top_tracks['Cover'] = top_tracks['trackName'].apply(get_mock_cover)
            
            st.dataframe(
                top_tracks[['Cover', 'trackName', 'artistName', 'play_count']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Cover": st.column_config.ImageColumn("Cover", help="Album Art"),
                    "trackName": "Track",
                    "artistName": "Artist",
                    "play_count": st.column_config.ProgressColumn("Play Count", format="%d", min_value=0, max_value=int(top_tracks['play_count'].max()))
                }
            )
            
            total_hours = df_spotify['msPlayed'].sum() / (1000 * 60 * 60)
            st.metric(label="Total Hours Listened", value=f"{total_hours:,.2f} hrs")
            
            st.subheader("Top 5 Genres (Click to explore)")
            df_spotify['hoursPlayed'] = df_spotify['msPlayed'] / (1000 * 60 * 60)
            top_genres = df_spotify.groupby('Genre')['hoursPlayed'].sum().reset_index()
            top_genres = top_genres.sort_values(by='hoursPlayed', ascending=False).head(5)
            
            for _, genre_row in top_genres.iterrows():
                genre_name = genre_row['Genre']
                genre_hours = genre_row['hoursPlayed']
                with st.expander(f"🎶 {genre_name} - {genre_hours:,.2f} hrs"):
                    genre_songs = df_spotify[df_spotify['Genre'] == genre_name]
                    genre_top = genre_songs.groupby(['trackName', 'artistName']).size().reset_index(name='play_count')
                    genre_top = genre_top.sort_values(by='play_count', ascending=False).head(5)
                    genre_top['Cover'] = genre_top['trackName'].apply(get_mock_cover)
                    
                    st.dataframe(
                        genre_top[['Cover', 'trackName', 'artistName', 'play_count']],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Cover": st.column_config.ImageColumn("Cover"),
                            "trackName": "Track",
                            "artistName": "Artist",
                            "play_count": st.column_config.NumberColumn("Plays", format="%d")
                        }
                    )
            
            st.session_state.spotify_data = df_spotify
            st.button("Continue to Strava Upload ➡️", on_click=next_step, type="primary")
        else:
            st.error("Could not parse Spotify data. Ensure it is a valid streaming history JSON.")

def strava_page():
    st.title("🟠 Step 2: Your Strava Data")
    st.markdown("""
    Now let's get your workouts. You can export your data from Strava by going to **Settings -> My Account -> Download or Delete Your Account -> Request Your Archive**.
    
    Once you receive the export, unzip it and upload the `activities.csv` file below. **You can also upload `media.csv` and your images to automatically link photos to your workouts!**
    """)
    
    strava_files = st.file_uploader("Upload Strava activities.csv, media.csv, and any images", type=['csv', 'jpg', 'jpeg', 'png'], accept_multiple_files=True)
    
    if strava_files:
        with st.spinner("Processing Strava Data and matching Images..."):
            df_strava, workout_images = process_strava_files(strava_files)
        
        if not df_strava.empty and 'Activity Date' in df_strava.columns:
            st.success("Strava data successfully processed!")
            
            st.metric(label="Total Logged Workouts", value=len(df_strava))
            if workout_images:
                st.metric(label="Photos Linked", value=sum(len(imgs) for imgs in workout_images.values()))
            
            st.subheader("Activities by Type")
            if 'Activity Type' in df_strava.columns:
                st.bar_chart(df_strava['Activity Type'].value_counts())
            
            st.session_state.workout_data = df_strava
            st.session_state.workout_images = workout_images
            st.button("Continue to Combined Analysis ➡️", on_click=next_step, type="primary")

def combined_analysis_page():
    st.title("⚡ Step 3: Combined Analysis")
    
    df_spotify = st.session_state.spotify_data
    df_workout = st.session_state.workout_data
    
    # Ensure BPM is calculated for the entire spotify history for playlist generation
    if df_spotify is not None and 'BPM' not in df_spotify.columns:
        with st.spinner("Analyzing song tempos, genres, and danceability..."):
            df_spotify['BPM'] = df_spotify['trackName'].apply(get_mock_bpm)
            df_spotify['Danceability'] = df_spotify['trackName'].apply(get_mock_danceability)
            df_spotify['Genre'] = df_spotify['artistName'].apply(get_mock_genre)
        st.session_state.spotify_data = df_spotify # Save back to session state


    if df_spotify is not None and df_workout is not None:
        
        combined_data = []
        genre_data = []
        
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
                    avg_bpm = workout_songs['BPM'].mean()
                    avg_danceability = workout_songs['Danceability'].mean()
                    songs_played = len(workout_songs)
                    tracklist = ", ".join(workout_songs['trackName'].tolist())
                    dominant_genre = workout_songs['Genre'].mode()[0] if not workout_songs['Genre'].mode().empty else "Unknown"

                    # For genre analysis
                    for _, song_row in workout_songs.iterrows():
                        genre_data.append({
                            'Activity Type': row.get('Activity Type', 'Unknown'),
                            'Genre': song_row['Genre']
                        })
                else:
                    avg_bpm = 0
                    avg_danceability = 0
                    songs_played = 0
                    tracklist = "No music matched"
                    dominant_genre = "Unknown"
                    
                combined_data.append({
                    'Activity ID': row['Activity ID'],
                    'Activity Name': row.get('Activity Name', 'Workout'),
                    'Activity Type': row.get('Activity Type', 'Unknown'),
                    'Date': start_time.strftime('%Y-%m-%d'),
                    'Elapsed Time (Mins)': round(row['Elapsed Time'] / 60, 2),
                    'Average Heart Rate': avg_hr,
                    'Perceived Exertion': row.get('Perceived Exertion', 0),
                    'Perceived Relative Effort': row.get('Perceived Relative Effort', 0),
                    'Average Track BPM': round(avg_bpm, 1),
                    'Average Danceability': round(avg_danceability, 3),
                    'Songs Played': songs_played,
                    'Tracklist': tracklist,
                    'Dominant Genre': dominant_genre
                })
        
        if combined_data:
            df_combined = pd.DataFrame(combined_data)
            st.success(f"Successfully matched music to {len(df_combined)} workouts!")

            df_genre = pd.DataFrame(genre_data) if genre_data else pd.DataFrame(columns=['Activity Type', 'Genre'])
            
            st.divider()

            # --- START: New Filter ---
            st.subheader("📊 Visualization Filters")
            workout_types = ['All Workouts'] + sorted(df_combined['Activity Type'].unique().tolist())
            selected_type = st.selectbox(
                'Filter all visualizations by activity:',
                workout_types
            )

            if selected_type == 'All Workouts':
                filtered_df = df_combined
                filtered_genre_df = df_genre
            else:
                filtered_df = df_combined[df_combined['Activity Type'] == selected_type]
                filtered_genre_df = df_genre[df_genre['Activity Type'] == selected_type]
            # --- END: New Filter ---
            
            # --- START: HR Zone Definitions for Charts ---
            ZONE_DEFINITIONS = {
                "Zone 1: Recovery": {
                    "hr_range": (0, 100), "bpm_range": (0, 120), 
                    "desc": "For very light activity like warm-ups, cool-downs, and recovery walks. The music is chill and steady."
                },
                "Zone 2: Endurance": {
                    "hr_range": (100, 130), "bpm_range": (120, 140),
                    "desc": "The 'fat-burning' zone. For long, steady runs or cycles where you can hold a conversation. The beat is consistent and motivating."
                },
                "Zone 3: Aerobic": {
                    "hr_range": (130, 150), "bpm_range": (140, 160),
                    "desc": "For building cardiovascular fitness. You're working moderately hard. The music tempo picks up to match your effort."
                },
                "Zone 4: Threshold": {
                    "hr_range": (150, 170), "bpm_range": (160, 180),
                    "desc": "Hard effort for improving your lactate threshold. Think tempo runs or intervals. The music is fast and intense to push you through."
                },
                "Zone 5: Max Effort": {
                    "hr_range": (170, 300), "bpm_range": (180, 300),
                    "desc": "All-out sprints and high-intensity intervals. The music is high-energy to match your peak performance."
                },
            }
            zone_data = []
            zone_colors = ['#88CCEE', '#44AA99', '#DDCC77', '#CC6677', '#AA4499'] # Color-blind friendly
            zone_names = list(ZONE_DEFINITIONS.keys())

            for i, (zone_name, params) in enumerate(ZONE_DEFINITIONS.items()):
                zone_data.append({'zone_name': zone_name, 'hr_min': params['hr_range'][0], 'hr_max': params['hr_range'][1]})
            zones_df = pd.DataFrame(zone_data)

            zone_background = alt.Chart(zones_df).mark_rect(opacity=0.2).encode(
                x=alt.X('hr_min:Q', title='Average Heart Rate (bpm)'),
                x2='hr_max:Q',
                color=alt.Color('zone_name:N', scale=alt.Scale(domain=zone_names, range=zone_colors), legend=alt.Legend(title="HR Zones")),
                tooltip=[alt.Tooltip('zone_name', title="Zone"), alt.Tooltip('hr_min', title="From (bpm)"), alt.Tooltip('hr_max', title="To (bpm)")]
            )
            # --- END: HR Zone Definitions for Charts ---
            
            has_hr = filtered_df['Average Heart Rate'].max() > 0
            has_pe = filtered_df['Perceived Exertion'].max() > 0
            has_pre = filtered_df['Perceived Relative Effort'].max() > 0
            
            if not filtered_df.empty and filtered_df['Songs Played'].sum() > 0:
                if has_hr:
                    st.subheader("❤️ Heart Rate vs. 🎵 Average Track BPM")
                    scatter_hr = alt.Chart(filtered_df[(filtered_df['Average Heart Rate'] > 0) & (filtered_df['Songs Played'] > 0)]).mark_circle(size=80, opacity=0.8).encode(
                        x=alt.X('Average Heart Rate:Q', scale=alt.Scale(zero=False), title=None),
                        y=alt.Y('Average Track BPM:Q', scale=alt.Scale(zero=False), title='Average Music BPM'),
                        color=alt.Color('Activity Type:N', legend=alt.Legend(title="Activity")),
                        tooltip=['Activity Name', 'Date', 'Average Heart Rate', 'Perceived Exertion', 'Average Track BPM', 'Songs Played']
                    )
                    final_chart_hr = (zone_background + scatter_hr).resolve_scale(color='independent').interactive()
                    st.altair_chart(final_chart_hr, use_container_width=True)
                elif has_pe:
                    st.subheader("🔥 Perceived Exertion vs. 🎵 Average Track BPM")
                    scatter_pe = alt.Chart(filtered_df[(filtered_df['Perceived Exertion'] > 0) & (filtered_df['Songs Played'] > 0)]).mark_circle(size=80, opacity=0.8).encode(
                        x=alt.X('Perceived Exertion', scale=alt.Scale(domain=[0, 10]), title='Perceived Exertion (1-10)'),
                        y=alt.Y('Average Track BPM', scale=alt.Scale(zero=False), title='Average Music BPM'),
                        color=alt.Color('Activity Type', legend=alt.Legend(title="Activity")),
                        tooltip=['Activity Name', 'Date', 'Perceived Exertion', 'Average Track BPM', 'Songs Played']
                    ).interactive()
                    st.altair_chart(scatter_pe, use_container_width=True)
                else:
                    st.info("No Heart Rate or Perceived Exertion data found to plot against BPM.")

            st.subheader("⏱️ Workout Duration vs. 🎵 Average Track BPM")
            if not filtered_df.empty and filtered_df['Songs Played'].sum() > 0:
                chart_dur = alt.Chart(filtered_df[filtered_df['Songs Played'] > 0]).mark_circle(size=80, opacity=0.8).encode(
                    x=alt.X('Elapsed Time (Mins)', title='Workout Duration (Minutes)'),
                    y=alt.Y('Average Track BPM', scale=alt.Scale(zero=False), title='Average Music BPM'),
                    color=alt.Color('Activity Type', legend=alt.Legend(title="Activity")),
                    size=alt.Size('Songs Played', legend=None),
                    tooltip=['Activity Name', 'Elapsed Time (Mins)', 'Average Track BPM', 'Songs Played', 'Tracklist']
                ).interactive()
                st.altair_chart(chart_dur, use_container_width=True)
            else:
                st.warning("Not enough data to chart duration vs BPM for the selected filter.")

            # --- START: New Perceived Relative Effort Chart ---
            if has_pre:
                st.subheader("💪 Perceived Relative Effort vs. 🎵 Average Track BPM")
                if not filtered_df.empty and filtered_df['Songs Played'].sum() > 0:
                    scatter_pre = alt.Chart(filtered_df[(filtered_df['Perceived Relative Effort'] > 0) & (filtered_df['Songs Played'] > 0)]).mark_circle(opacity=0.8).encode(
                        x=alt.X('Perceived Relative Effort', scale=alt.Scale(zero=False), title='Perceived Relative Effort'),
                        y=alt.Y('Average Track BPM', scale=alt.Scale(zero=False), title='Average Music BPM'),
                        color=alt.Color('Activity Type', legend=alt.Legend(title="Activity")),
                        size=alt.Size('Elapsed Time (Mins)', title="Duration (min)", scale=alt.Scale(range=[60, 500])),
                        tooltip=['Activity Name', 'Date', 'Perceived Relative Effort', 'Elapsed Time (Mins)', 'Average Track BPM', 'Songs Played']
                    ).interactive()
                    st.altair_chart(scatter_pre, use_container_width=True)
            # --- END: New Perceived Relative Effort Chart ---

            # --- START: New Danceability vs HR Chart ---
            st.subheader("💃 Danceability vs. ❤️ Heart Rate")
            if not filtered_df.empty and filtered_df['Average Heart Rate'].sum() > 0 and filtered_df['Songs Played'].sum() > 0:
                scatter_dance = alt.Chart(filtered_df[(filtered_df['Average Heart Rate'] > 0) & (filtered_df['Songs Played'] > 0)]).mark_circle(size=80, opacity=0.8).encode(
                    x=alt.X('Average Heart Rate:Q', scale=alt.Scale(zero=False), title=None),
                    y=alt.Y('Average Danceability:Q', scale=alt.Scale(domain=[0, 1]), title='Average Music Danceability'),
                    color=alt.Color('Activity Type:N', legend=alt.Legend(title="Activity")),
                    tooltip=['Activity Name', 'Date', 'Average Heart Rate', 'Average Danceability', 'Songs Played']
                )
                
                final_chart_dance = (zone_background + scatter_dance).resolve_scale(color='independent').interactive()
                st.altair_chart(final_chart_dance, use_container_width=True)
            else:
                st.warning("Not enough Heart Rate or matched music data to chart danceability for the selected filter.")
            # --- END: New Danceability vs HR Chart ---

            # --- START: New Genre Chart ---
            st.subheader("🎶 Genre Breakdown by Activity")
            if not filtered_genre_df.empty:
                if selected_type != 'All Workouts':
                    genre_chart = alt.Chart(filtered_genre_df).mark_arc(innerRadius=50).encode(
                        theta=alt.Theta(field="Genre", type="nominal", aggregate="count", title="Songs Played"),
                        color=alt.Color(field="Genre", type="nominal", legend=alt.Legend(title="Genres")),
                        tooltip=['count(Genre):Q', 'Genre']
                    ).properties(title=f"Genre Distribution for {selected_type}")
                else:
                    genre_chart = alt.Chart(filtered_genre_df).mark_bar().encode(
                        x=alt.X('Activity Type:N', title='Activity Type', sort='-y'),
                        y=alt.Y('count(Genre):Q', title='Percentage of Songs Played', stack='normalize', axis=alt.Axis(format='%')),
                        color=alt.Color('Genre:N', legend=alt.Legend(title="Music Genre")),
                        tooltip=['Activity Type', 'Genre', 'count(Genre):Q']
                    ).properties(title="Genre Proportions Across Workout Types")
                st.altair_chart(genre_chart, use_container_width=True)
            else:
                st.warning("No genre data to display for the selected filter.")
            # --- END: New Genre Chart ---
            
            st.subheader("📋 Workout & Playlist Breakdown")
            st.dataframe(
                filtered_df[['Date', 'Activity Name', 'Activity Type', 'Average Heart Rate', 'Perceived Exertion', 'Perceived Relative Effort', 'Average Track BPM', 'Average Danceability', 'Songs Played', 'Tracklist']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Average Heart Rate": st.column_config.NumberColumn("Avg HR (bpm)", format="%d"),
                    "Perceived Exertion": st.column_config.NumberColumn("Effort (1-10)", format="%d"),
                    "Perceived Relative Effort": st.column_config.NumberColumn("Relative Effort", format="%d"),
                    "Average Track BPM": st.column_config.NumberColumn("Avg Music BPM", format="%d"),
                    "Average Danceability": st.column_config.NumberColumn("Avg Danceability", format="%.2f"),
                    "Songs Played": st.column_config.NumberColumn("Songs"),
                    "Elapsed Time (Mins)": st.column_config.NumberColumn("Duration (min)", format="%.1f")
                }
            )
            
            csv = df_combined.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Full Combined Data as CSV",
                data=csv,
                file_name='spotify_health_combined.csv',
                mime='text/csv',
            )

            # --- START: New Playlist Generation Section ---
            st.divider()
            st.subheader("⚡ Your Personalized Workout Zone Playlists")
            st.markdown("""
                Based on your entire listening history, we've crafted playlists for different training intensities. 
                We've only shown playlists for heart rate zones you've actually trained in.
            """)

            if 'Average Heart Rate' in df_combined.columns and df_combined['Average Heart Rate'].sum() > 0:
                for zone_name, params in ZONE_DEFINITIONS.items():
                    hr_min, hr_max = params["hr_range"]
                    bpm_min, bpm_max = params["bpm_range"]
                    
                    workouts_in_zone = df_combined[(df_combined['Average Heart Rate'] >= hr_min) & (df_combined['Average Heart Rate'] < hr_max)]
                    
                    if not workouts_in_zone.empty:
                        playlist_songs = df_spotify[(df_spotify['BPM'] >= bpm_min) & (df_spotify['BPM'] < bpm_max)]
                        
                        if not playlist_songs.empty:
                            top_playlist_tracks = playlist_songs.groupby(['trackName', 'artistName']).size().reset_index(name='play_count').sort_values('play_count', ascending=False).head(15)

                            with st.expander(f"🎵 {zone_name} Playlist ({bpm_min}-{bpm_max} BPM)"):
                                st.markdown(f"**{params['desc']}**")
                                st.markdown(f"*{len(workouts_in_zone)} of your workouts fell into this heart rate zone.*")
                                st.dataframe(
                                    top_playlist_tracks[['trackName', 'artistName', 'play_count']],
                                    hide_index=True, use_container_width=True,
                                    column_config={
                                        "trackName": "Track", "artistName": "Artist",
                                        "play_count": st.column_config.NumberColumn("Your Plays", help="How many times you've listened to this song from your history.")
                                    }
                                )
            else:
                st.info("Cannot generate playlists because workout data does not contain heart rate information.")
            # --- END: New Playlist Generation Section ---
            
            # --- START: Workout Gallery ---
            workout_images = st.session_state.get('workout_images', {})
            if workout_images:
                st.divider()
                st.subheader("📸 AI Photo Analysis & Music Vibe")
                st.markdown("We've analyzed your post-workout photos for fatigue and compared it to the music you were listening to!")
                
                workouts_with_imgs = [w for w in combined_data if w['Activity ID'] in workout_images]
                
                if workouts_with_imgs:
                    
                    # 1. Prepare data for the combined constructs and visualization
                    photo_data = []
                    beast_mode_dict = {} # To quickly look up the score for the gallery
                    for w in workouts_with_imgs:
                        imgs = workout_images[w['Activity ID']]
                        # Average the fatigue score if there are multiple images for one workout
                        fatigue_scores = [analyze_image_fatigue(img_bytes) for img_bytes in imgs]
                        avg_fatigue = sum(fatigue_scores) / len(fatigue_scores)
                        
                        # Combine HR, Perceived Exertion, and AI Fatigue into a new construct
                        hr = w.get('Average Heart Rate', 0)
                        hr_score = min(100, max(0, ((hr - 80) / 100) * 100)) if hr > 0 else 50
                        pe = w.get('Perceived Exertion', 0)
                        pe_score = (pe / 10.0) * 100 if pe > 0 else 50
                        
                        # ⚡ "Beast Mode Index" calculation
                        beast_mode_index = round((hr_score + pe_score + avg_fatigue) / 3, 1)
                        beast_mode_dict[w['Activity ID']] = beast_mode_index
                        
                        photo_data.append({
                            'Activity Name': w['Activity Name'],
                            'Date': w['Date'],
                            'Activity Type': w['Activity Type'],
                            'AI Detected Fatigue': avg_fatigue,
                            'Beast Mode Index': beast_mode_index,
                            'Average Track BPM': w['Average Track BPM'],
                            'Average Danceability': w['Average Danceability'],
                            'Dominant Genre': w['Dominant Genre']
                        })
                    
                    # 2. Render the Beast Mode Index vs BPM & Genre Chart
                    photo_df = pd.DataFrame(photo_data)
                    
                    st.markdown("### ⚡ The Beast Mode Index")
                    st.markdown("We combined your **Heart Rate**, **Perceived Exertion**, and **AI Detected Fatigue** into a single ultimate metric: the **Beast Mode Index (0-100)**! Let's see how your overall intensity relates to the music's tempo and genre.")
                    
                    chart_beast_bpm = alt.Chart(photo_df).mark_circle(opacity=0.8).encode(
                        x=alt.X('Beast Mode Index:Q', title='Beast Mode Index (%)', scale=alt.Scale(domain=[0, 100])),
                        y=alt.Y('Average Track BPM:Q', scale=alt.Scale(zero=False), title='Average Music BPM'),
                        color=alt.Color('Dominant Genre:N', legend=alt.Legend(title="Dominant Genre")),
                        size=alt.Size('Average Danceability:Q', title="Danceability", scale=alt.Scale(range=[100, 500])),
                        tooltip=['Activity Name', 'Date', 'Beast Mode Index', 'AI Detected Fatigue', 'Dominant Genre', 'Average Track BPM']
                    ).properties(
                        height=400,
                        title="⚡ Beast Mode Index vs. 🎵 Music Tempo & Genre"
                    ).interactive()
                    
                    st.altair_chart(chart_beast_bpm, use_container_width=True)
                    
                    st.markdown("#### Your Workout Gallery")
                    cols = st.columns(3)
                    col_idx = 0
                    for w in workouts_with_imgs:
                        imgs = workout_images[w['Activity ID']]
                        for img_bytes in imgs:
                            with cols[col_idx % 3]:
                                st.image(img_bytes, caption=f"{w['Activity Name']} ({w['Date']})", use_container_width=True)
                                
                                # AI Image Analysis for Fatigue
                                fatigue_score = analyze_image_fatigue(img_bytes)
                                st.progress(fatigue_score / 100.0, text=f"🤖 Detected Fatigue: {fatigue_score}%")

                                # Link the music, BPM, and Beast Mode Index directly below the image
                                st.info(f"🎵 {w['Songs Played']} songs | **{w['Average Track BPM']} BPM** | ⚡ **Beast Mode: {beast_mode_dict[w['Activity ID']]}%**")
                                
                                pe_label = f" • 🔥 Effort: {w['Perceived Exertion']}/10" if w['Perceived Exertion'] > 0 else ""
                                pre_label = f" • 💪 Rel. Effort: {w['Perceived Relative Effort']}" if w.get('Perceived Relative Effort', 0) > 0 else ""
                                st.caption(f"{pe_label}{pre_label}")
                            col_idx += 1
                else:
                    st.info("No matching images found for the filtered workouts.")
            # --- END: Workout Gallery ---

        else:
            st.warning("No overlapping data found between your Spotify and Strava exports.")
        
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
        strava_page()
    elif st.session_state.step == 4:
        combined_analysis_page()