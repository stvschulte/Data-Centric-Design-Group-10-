"""
features/researcher/data_loader.py
===================================
负责从参与者上传的数据中聚合，供 researcher 分析使用。

数据流：
  Spotify uploads (JSON) + Strava uploads (CSV)
  → 时间戳对齐 → 每行 = 一次运动 + 运动期间的音乐特征聚合
  → 提供给 researcher dashboard

实际项目中应该从你们的 /data 文件夹 + 数据库读取。
这里提供 sample data 用于演示。
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path


@st.cache_data(show_spinner=False)
def load_aggregated_data() -> pd.DataFrame:
    """
    加载聚合后的研究数据。

    返回的 DataFrame 应包含：
      - participant_id
      - date
      - activity_type            (running, cycling, strength, yoga, HIIT, ...)
      - duration_min
      - avg_heart_rate
      - max_heart_rate
      - hr_zone                  (1-5, derived from %max HR)
      - perceived_intensity      (1-5, self-reported)
      - music_energy             (0-1, Spotify)
      - music_tempo              (BPM, Spotify)
      - music_valence            (0-1, Spotify)
      - music_danceability       (0-1, Spotify)
      - music_loudness           (dB, Spotify)
      - notes                    (text from participant)
      - fer_fatigue_score        (0-10, from FER if photo uploaded)
    """
    # 实际项目: 从 /data/aggregated/ 读取每个参与者的 CSV
    data_path = Path("data/aggregated")

    if not data_path.exists():
        return None

    files = list(data_path.glob("*.csv"))
    if len(files) == 0:
        return None

    all_data = []
    for csv_file in files:
        try:
            df = pd.read_csv(csv_file)
            if "participant_id" not in df.columns:
                df["participant_id"] = csv_file.stem
            all_data.append(df)
        except Exception as e:
            st.warning(f"Could not load {csv_file.name}: {e}")

    if len(all_data) == 0:
        return None

    return pd.concat(all_data, ignore_index=True)


def generate_sample_data() -> pd.DataFrame:
    """
    生成演示数据。
    用于在没有真实参与者上传时演示 dashboard 功能。
    """
    np.random.seed(42)

    participants = ["P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08"]
    activities = ["running", "cycling", "strength", "yoga", "HIIT", "walking"]

    # 不同活动类型有典型的强度模式
    activity_profiles = {
        "running": {"intensity": [3, 4, 5], "p": [0.2, 0.4, 0.4], "max_hr": 175},
        "cycling": {"intensity": [2, 3, 4], "p": [0.3, 0.4, 0.3], "max_hr": 160},
        "strength": {"intensity": [3, 4, 5], "p": [0.25, 0.5, 0.25], "max_hr": 150},
        "yoga": {"intensity": [1, 1, 2], "p": [0.5, 0.3, 0.2], "max_hr": 130},
        "HIIT": {"intensity": [4, 5], "p": [0.3, 0.7], "max_hr": 180},
        "walking": {"intensity": [1, 1, 2], "p": [0.6, 0.3, 0.1], "max_hr": 130},
    }

    notes_pool = {
        "high": [
            "Crushed it! Music kept me locked in.",
            "Tough session but the beat pushed me through.",
            "Best workout this week, music was on fire.",
            "Aggressive hip-hop made me push harder.",
            "Pushed my limits. The drops timed perfectly.",
        ],
        "mid": [
            "Solid steady-state session.",
            "Music matched my pace well today.",
            "Comfortable run, kept tempo with the beat.",
            "Felt good, controlled effort throughout.",
        ],
        "low": [
            "Recovery day, needed calm tracks.",
            "Slow flow, ambient vibes were perfect.",
            "Easy session. Music was relaxing.",
            "Active recovery with chill playlist.",
            "Stretching and breathing. Calm music helped.",
        ],
    }

    rows = []
    base_date = pd.Timestamp("2026-05-01")

    for p_idx, p in enumerate(participants):
        n_sessions = np.random.randint(12, 25)
        for i in range(n_sessions):
            activity = np.random.choice(activities)
            profile = activity_profiles[activity]
            intensity = np.random.choice(profile["intensity"], p=profile["p"])

            # 心率：与强度强相关 + 个体差异
            base_hr = 60 + intensity * 22
            avg_hr = base_hr + np.random.randint(-8, 8) + (p_idx * 1.5)
            avg_hr = max(50, min(190, avg_hr))
            max_hr_estimate = profile["max_hr"] + np.random.randint(-10, 10)

            # HR Zone（基于实际心率与该活动最大心率的百分比）
            hr_pct = avg_hr / max_hr_estimate
            if hr_pct < 0.6:
                hr_zone = 1
            elif hr_pct < 0.7:
                hr_zone = 2
            elif hr_pct < 0.8:
                hr_zone = 3
            elif hr_pct < 0.9:
                hr_zone = 4
            else:
                hr_zone = 5

            # 音乐特征：与强度相关
            music_energy = min(
                0.95, max(0.1, intensity * 0.18 + np.random.uniform(-0.08, 0.08))
            )
            music_tempo = 80 + intensity * 20 + np.random.randint(-12, 12)
            music_valence = round(
                min(0.95, max(0.15, 0.4 + intensity * 0.08 + np.random.uniform(-0.1, 0.1))),
                2,
            )
            music_danceability = round(
                min(0.95, max(0.2, 0.5 + intensity * 0.05 + np.random.uniform(-0.1, 0.1))),
                2,
            )
            music_loudness = round(-20 + intensity * 3 + np.random.uniform(-2, 2), 1)

            # FER fatigue score
            fer_fatigue = round(
                min(10, max(0, intensity * 1.5 + np.random.uniform(-1.5, 1.5))), 1
            )

            # 备注：根据强度选不同情感
            if intensity >= 4:
                note = np.random.choice(notes_pool["high"])
            elif intensity == 3:
                note = np.random.choice(notes_pool["mid"])
            else:
                note = np.random.choice(notes_pool["low"])

            rows.append(
                {
                    "participant_id": p,
                    "date": base_date + pd.Timedelta(days=i + p_idx * 2),
                    "activity_type": activity,
                    "duration_min": np.random.randint(15, 95),
                    "avg_heart_rate": int(avg_hr),
                    "max_heart_rate": int(max_hr_estimate),
                    "hr_zone": hr_zone,
                    "perceived_intensity": intensity,
                    "music_energy": round(music_energy, 2),
                    "music_tempo": int(music_tempo),
                    "music_valence": music_valence,
                    "music_danceability": music_danceability,
                    "music_loudness": music_loudness,
                    "fer_fatigue_score": fer_fatigue,
                    "notes": note,
                }
            )

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# Heart rate zone 元数据，供其他模块使用
HR_ZONE_INFO = {
    1: {"name": "Z1 Recovery", "range": "<60%", "color": "#4DA8DA"},
    2: {"name": "Z2 Endurance", "range": "60-70%", "color": "#4DDA8B"},
    3: {"name": "Z3 Tempo", "range": "70-80%", "color": "#F5C661"},
    4: {"name": "Z4 Threshold", "range": "80-90%", "color": "#F58A4A"},
    5: {"name": "Z5 VO2 Max", "range": ">90%", "color": "#E84C3D"},
}
