from datetime import timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from fitparse import FitFile
from .parser import seconds_to_pace_str


def parse_fit_file(fit_path: Path) -> Optional[Dict[str, Any]]:
    """1つのFITファイルをパースして、距離軸の時系列データを返す"""
    try:
        fitfile = FitFile(str(fit_path))
    except Exception as e:
        print(f"Error reading {fit_path}: {e}")
        return None

    records = []
    start_time_jst = None

    for record in fitfile.get_messages("record"):
        values = record.get_values()
        timestamp = values.get("timestamp")
        distance = values.get("distance")  # メートル

        if timestamp is None or distance is None:
            continue

        # UTC -> JST (+9時間)
        jst_time = timestamp + timedelta(hours=9)
        if start_time_jst is None:
            start_time_jst = jst_time

        # 速度 (m/s -> km/h, pace)
        speed_ms = values.get("enhanced_speed") or values.get("speed") or 0.0
        speed_kmh = round(speed_ms * 3.6, 2)
        pace_sec = (1000.0 / speed_ms) if speed_ms > 0.5 else 0.0
        pace_str = seconds_to_pace_str(pace_sec) if pace_sec > 0 else "--:--"

        # 心拍数
        hr = values.get("heart_rate")

        # ケイデンス (spm: GarminランニングのFITは片足rpmで記録されることが多い)
        raw_cadence = values.get("cadence") or 0
        cadence_spm = (raw_cadence * 2) if 40 <= raw_cadence <= 110 else raw_cadence

        # 標高
        altitude = values.get("enhanced_altitude") or values.get("altitude") or 0.0

        records.append({
            "distance_km": round(distance / 1000.0, 2),
            "speed_kmh": speed_kmh,
            "pace_sec": round(pace_sec, 1),
            "pace_str": pace_str,
            "heart_rate": hr,
            "cadence": cadence_spm,
            "altitude": round(altitude, 1),
        })

    if not records or start_time_jst is None:
        return None

    # DataFrame化して間引き (最大180ポイント前後にサンプリング)
    df_rec = pd.DataFrame(records)
    # 欠損補完
    df_rec["heart_rate"] = df_rec["heart_rate"].ffill().bfill().fillna(0).astype(int)
    df_rec["cadence"] = df_rec["cadence"].ffill().bfill().fillna(0).astype(int)

    total_pts = len(df_rec)
    if total_pts > 180:
        step = max(1, total_pts // 180)
        df_sampled = df_rec.iloc[::step].copy()
        # 最後の点も必ず含める
        if df_sampled.index[-1] != df_rec.index[-1]:
            df_sampled = pd.concat([df_sampled, df_rec.iloc[[-1]]])
    else:
        df_sampled = df_rec

    date_key = start_time_jst.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "date_key": date_key,
        "date_day": start_time_jst.strftime("%Y-%m-%d"),
        "distances": df_sampled["distance_km"].tolist(),
        "speeds_kmh": df_sampled["speed_kmh"].tolist(),
        "paces_str": df_sampled["pace_str"].tolist(),
        "heart_rates": df_sampled["heart_rate"].tolist(),
        "cadences": df_sampled["cadence"].tolist(),
        "altitudes": df_sampled["altitude"].tolist(),
        "total_points": len(df_sampled),
    }


def generate_estimated_series(dist_km: float, pace_sec: float, avg_hr: int, max_hr: int, cadence: int, max_cadence: int) -> Dict[str, Any]:
    """FITファイルがない場合に、平均・最高値からリアルな距離別推移を推定生成"""
    import numpy as np
    
    if dist_km <= 0:
        return {"has_fit": False, "distances": [], "speeds_kmh": [], "paces_str": [], "heart_rates": [], "cadences": []}

    # 0kmからdist_kmまで、おおよそ0.2km〜0.5km刻み（20〜30ポイント）
    num_pts = max(15, min(40, int(dist_km * 4)))
    distances = np.linspace(0.0, dist_km, num_pts)

    avg_speed = (3600.0 / pace_sec) if pace_sec > 0 else 10.0
    # スピード推移: 序盤90%、中盤100%、終盤105%
    speed_curve = np.ones(num_pts) * avg_speed
    speed_curve[:int(num_pts * 0.15)] *= 0.93  # ウォーミングアップ
    speed_curve[-int(num_pts * 0.15):] *= 1.05 # スパート

    # 心拍推移: 序盤低めから立ち上がり、中盤維持、終盤上昇
    start_hr = max(110, avg_hr - 25)
    hr_curve = []
    for d in distances:
        progress = d / dist_km if dist_km > 0 else 0
        if progress < 0.2:
            h = start_hr + (avg_hr - start_hr) * (progress / 0.2)
        else:
            h = avg_hr + (max_hr - avg_hr) * 0.5 * ((progress - 0.2) / 0.8)
        hr_curve.append(int(round(h)))

    # ケイデンス推移: 序盤やや低め、終盤ピッチアップ
    cadence_curve = [int(round(cadence - 2 + 4 * (d / dist_km))) for d in distances]

    speeds_kmh = [round(float(s), 2) for s in speed_curve]
    paces_str = [seconds_to_pace_str(3600.0 / s) if s > 0 else "--:--" for s in speeds_kmh]

    return {
        "has_fit": False,
        "distances": [round(float(d), 2) for d in distances],
        "speeds_kmh": speeds_kmh,
        "paces_str": paces_str,
        "heart_rates": hr_curve,
        "cadences": cadence_curve,
    }


def load_all_fit_series(data_dir: Path) -> Dict[str, Dict[str, Any]]:
    """dataディレクトリ内の全FITファイルを読み込み、date_keyをキーにした辞書で返す"""
    fit_dict = {}
    for fit_file in data_dir.glob("*.fit"):
        print(f"Parsing FIT file: {fit_file.name}...")
        parsed = parse_fit_file(fit_file)
        if parsed:
            parsed["has_fit"] = True
            fit_dict[parsed["date_key"]] = parsed
            fit_dict[parsed["date_day"]] = parsed
            print(f"  -> Successfully loaded {parsed['total_points']} points for {parsed['date_key']}")
    return fit_dict
