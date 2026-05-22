# Sync & Sweat — Spotify x Strava Analyzer

**Data-Centric Design for Connected Products | Group 10 | TU Delft Q4 2026**

An interactive web app that merges your Spotify streaming history with your Strava workout logs to reveal the relationship between your music and your physical performance.

## Features

- Upload your **Spotify** listening history (JSON) to visualize your top tracks, artists, and genres
- Upload your **Strava** activities (CSV) to map out your workout history
- **Sync** the two datasets by timestamp to see exactly what you were listening to during each workout
- Visualize correlations between **Heart Rate**, **Perceived Exertion**, and **Music BPM / Danceability**
- Generate **personalized playlists** based on your training heart rate zones
- **Photo gallery** with AI fatigue detection and a Beast Mode Index (if you upload workout photos)

## Data Privacy

All processing happens locally in your browser session. No personal data is stored or uploaded to any server. The `.gitignore` is configured to prevent accidentally committing Spotify/Strava data files.

## Installation

```bash
pip install -r requirements.txt
```

Optional facial-expression analysis for workout photos needs a much larger ML
stack. Install it locally only when you need that feature:

```bash
pip install -r requirements-ml.txt
```

## Running the App

```bash
streamlit run app.py
```

## Streamlit Community Cloud

The deployed requirements are kept compatible with Streamlit Community Cloud's
current Python runtime. Community Cloud does not use `runtime.txt` for Python
version selection.

The optional `requirements-ml.txt` file is intended for local installs only and
may require an older Python version because TensorFlow/FER support lags behind
new Python releases.

Or use the provided script (Linux/macOS):

```bash
chmod +x run.sh
./run.sh
```

The app supports uploading files up to **2 GB** (configured via `.streamlit/config.toml`).

## How to Export Your Data

### Spotify
1. Go to [spotify.com/account/privacy](https://www.spotify.com/account/privacy/)
2. Request your data under **"Download your data"**
3. Upload the `StreamingHistory_music_0.json` (and any numbered variants) to the app

### Strava
1. Go to **Settings → My Account → Download or Delete Your Account → Request Your Archive**
2. Unzip the export and upload `activities.csv`
3. Optionally upload `media.csv` and workout photos (`.jpg`, `.png`) to enable the photo gallery

## Tech Stack

- [Streamlit](https://streamlit.io/) — UI framework
- [Pandas](https://pandas.pydata.org/) — data processing
- [Altair](https://altair-viz.github.io/) — interactive charts
