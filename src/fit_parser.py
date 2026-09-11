from datetime import timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from fitparse import FitFile
from .parser import seconds_to_pace_str, seconds_to_time_str


def parse_fit_file(fit_path: Path) -> Optional[Dict[str, Any]]:
    """1つのFITファイルをパースして、距離軸の時系列データ、ラップ、GPS座標を返す"""
    try:
        fitfile = FitFile(str(fit_path))
    except Exception as e:
        print(f"Error reading {fit_path}: {e}")
        return None

    records = []
    start_time_jst = None
    coords_raw = []

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

        # GPS座標 (semicircles -> degrees)
        lat = values.get("position_lat")
        lon = values.get("position_long")
        if lat is not None and lon is not None:
            deg_lat = lat * (180.0 / (2**31))
            deg_lon = lon * (180.0 / (2**31))
            coords_raw.append([round(deg_lat, 6), round(deg_lon, 6)])

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

    # Lap情報の抽出
    laps = []
    lap_idx = 1
    for lap_msg in fitfile.get_messages("lap"):
        dist_m = lap_msg.get_value("total_distance") or 0
        time_s = lap_msg.get_value("total_timer_time") or 0
        if dist_m < 50 and laps:
            continue
        lap_dist_km = round(dist_m / 1000.0, 2)
        lap_speed_ms = lap_msg.get_value("avg_speed") or (dist_m / time_s if time_s > 0 else 0)
        lap_pace_sec = (1000.0 / lap_speed_ms) if lap_speed_ms > 0 else 0
        lap_hr = lap_msg.get_value("avg_heart_rate") or 0
        ascent = lap_msg.get_value("total_ascent") or 0
        descent = lap_msg.get_value("total_descent") or 0

        laps.append({
            "lap_index": lap_idx,
            "distance_km": lap_dist_km,
            "time_str": seconds_to_time_str(int(time_s)),
            "time_sec": round(time_s, 1),
            "pace_str": seconds_to_pace_str(lap_pace_sec),
            "pace_sec": round(lap_pace_sec, 1),
            "avg_hr": int(lap_hr),
            "ascent": int(ascent),
            "descent": int(descent),
        })
        lap_idx += 1

    # DataFrame化して間引き (最大180ポイント前後にサンプリング)
    df_rec = pd.DataFrame(records)
    # 欠損補完
    df_rec["heart_rate"] = df_rec["heart_rate"].ffill().bfill().fillna(0).astype(int)
    df_rec["cadence"] = df_rec["cadence"].ffill().bfill().fillna(0).astype(int)

    total_pts = len(df_rec)
    if total_pts > 180:
        step = max(1, total_pts // 180)
        df_sampled = df_rec.iloc[::step].copy()
        if df_sampled.index[-1] != df_rec.index[-1]:
            df_sampled = pd.concat([df_sampled, df_rec.iloc[[-1]]])
    else:
        df_sampled = df_rec

    # GPS座標の間引き (最大80点程度)
    coords_sampled = []
    if coords_raw:
        c_step = max(1, len(coords_raw) // 80)
        coords_sampled = coords_raw[::c_step]
        if coords_raw[-1] != coords_sampled[-1]:
            coords_sampled.append(coords_raw[-1])

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
        "coordinates": coords_sampled,
        "laps": laps,
    }


def generate_estimated_series(dist_km: float, pace_sec: float, avg_hr: int, max_hr: int, cadence: int, max_cadence: int, elevation_gain: float = 0.0) -> Dict[str, Any]:
    """FITファイルがない場合に、平均・最高値からリアルな距離別推移・ラップ・標高を推定生成"""
    import numpy as np
    
    if dist_km <= 0:
        return {"has_fit": False, "distances": [], "speeds_kmh": [], "paces_str": [], "heart_rates": [], "cadences": [], "altitudes": [], "coordinates": [], "laps": []}

    # 0kmからdist_kmまで、おおよそ0.2km〜0.5km刻み（20〜30ポイント）
    num_pts = max(15, min(40, int(dist_km * 4)))
    distances = np.linspace(0.0, dist_km, num_pts)

    avg_speed = (3600.0 / pace_sec) if pace_sec > 0 else 10.0
    speed_curve = np.ones(num_pts) * avg_speed
    speed_curve[:int(num_pts * 0.15)] *= 0.93  # ウォーミングアップ
    speed_curve[-int(num_pts * 0.15):] *= 1.05 # スパート

    # 心拍推移
    start_hr = max(110, avg_hr - 25)
    hr_curve = []
    for d in distances:
        progress = d / dist_km if dist_km > 0 else 0
        if progress < 0.2:
            h = start_hr + (avg_hr - start_hr) * (progress / 0.2)
        else:
            h = avg_hr + (max_hr - avg_hr) * 0.5 * ((progress - 0.2) / 0.8)
        hr_curve.append(int(round(h)))

    # ケイデンス推移
    cadence_curve = [int(round(cadence - 2 + 4 * (d / dist_km))) for d in distances]

    # 標高カーブ（総上昇量から滑らかな起伏を生成）
    alt_base = 15.0
    alt_gain = max(5.0, float(elevation_gain) if elevation_gain else 10.0)
    alt_curve = [round(alt_base + (alt_gain * 0.4 * np.sin(i * 0.8)), 1) for i in range(num_pts)]

    speeds_kmh = [round(float(s), 2) for s in speed_curve]
    paces_str = [seconds_to_pace_str(3600.0 / s) if s > 0 else "--:--" for s in speeds_kmh]

    # 推定ラップ生成 (1kmごと)
    laps = []
    full_km = int(dist_km)
    rem_km = round(dist_km - full_km, 2)
    lap_count = full_km + (1 if rem_km > 0.05 else 0)

    for i in range(1, lap_count + 1):
        is_last = (i == lap_count and rem_km > 0.05)
        lap_dist = rem_km if is_last else 1.0
        lap_prog = i / max(1, lap_count)
        factor = 1.04 if i == 1 else (0.97 if i == lap_count else 1.0)
        l_pace_sec = pace_sec * factor
        l_time_sec = l_pace_sec * lap_dist
        l_hr = int(round(start_hr + (avg_hr - start_hr) * 0.6 + (max_hr - avg_hr) * 0.4 * lap_prog))

        laps.append({
            "lap_index": i,
            "distance_km": round(lap_dist, 2),
            "time_str": seconds_to_time_str(int(l_time_sec)),
            "time_sec": round(l_time_sec, 1),
            "pace_str": seconds_to_pace_str(l_pace_sec),
            "pace_sec": round(l_pace_sec, 1),
            "avg_hr": l_hr,
            "ascent": int(round(alt_gain / max(1, lap_count))),
            "descent": int(round(alt_gain / max(1, lap_count))),
        })

    return {
        "has_fit": False,
        "distances": [round(float(d), 2) for d in distances],
        "speeds_kmh": speeds_kmh,
        "paces_str": paces_str,
        "heart_rates": hr_curve,
        "cadences": cadence_curve,
        "altitudes": alt_curve,
        "coordinates": [],
        "laps": laps,
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
