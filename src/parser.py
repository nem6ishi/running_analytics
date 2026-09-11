import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd


def parse_time_to_seconds(val: str) -> int:
    """HH:MM:SS または MM:SS を総秒数に変換"""
    if pd.isna(val) or not val:
        return 0
    val_str = str(val).strip()
    parts = val_str.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(float(parts[1]))
        return int(float(val_str))
    except (ValueError, TypeError):
        return 0


def seconds_to_time_str(seconds: int) -> str:
    """総秒数を HH:MM:SS または MM:SS 文字列に変換"""
    if seconds < 0:
        return "--:--"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_pace_to_seconds(val: str) -> float:
    """M:SS 形式のペース（分/km）を秒/kmに変換"""
    if pd.isna(val) or not val:
        return 0.0
    val_str = str(val).strip()
    parts = val_str.split(":")
    try:
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(val_str)
    except (ValueError, TypeError):
        return 0.0


def seconds_to_pace_str(seconds_per_km: float) -> str:
    """秒/km を M:SS 形式のペース文字列に変換"""
    if seconds_per_km <= 0 or pd.isna(seconds_per_km):
        return "--:--"
    minutes = int(seconds_per_km // 60)
    secs = int(round(seconds_per_km % 60))
    if secs == 60:
        minutes += 1
        secs = 0
    return f"{minutes}:{secs:02d}"


def clean_numeric(val: Any, default: float = 0.0) -> float:
    """カンマや余分なクォート（'-1など）を除去して数値に変換"""
    if pd.isna(val):
        return default
    val_str = str(val).strip()
    cleaned = re.sub(r"[^\d.-]", "", val_str)
    try:
        return float(cleaned) if cleaned else default
    except ValueError:
        return default


def load_activities(csv_path: Path) -> pd.DataFrame:
    """Garmin CSVを読み込み、正規化したDataFrameを返す"""
    df = pd.read_csv(csv_path)

    # 日時パース
    df["datetime"] = pd.to_datetime(df["日付"])
    df["date_str"] = df["datetime"].dt.strftime("%Y-%m-%d")
    df["year_month"] = df["datetime"].dt.strftime("%Y-%m")
    df["time_of_day"] = df["datetime"].dt.strftime("%H:%M")

    # 数値化
    df["distance_km"] = df["距離"].apply(lambda x: clean_numeric(x, 0.0))
    df["calories"] = df["カロリー"].apply(lambda x: int(clean_numeric(x, 0)))
    df["duration_sec"] = df["タイム"].apply(parse_time_to_seconds)
    df["avg_hr"] = df["平均心拍数"].apply(lambda x: int(clean_numeric(x, 0)))
    df["max_hr"] = df["最大心拍数"].apply(lambda x: int(clean_numeric(x, 0)))
    df["avg_cadence"] = df["平均ピッチ"].apply(lambda x: int(clean_numeric(x, 0)))
    df["max_cadence"] = df["最高ピッチ"].apply(lambda x: int(clean_numeric(x, 0)))
    df["avg_pace_sec"] = df["平均ペース"].apply(parse_pace_to_seconds)
    df["max_pace_sec"] = df["最高ペース"].apply(parse_pace_to_seconds)
    df["elevation_gain"] = df["総上昇量"].apply(lambda x: int(clean_numeric(x, 0)))
    df["elevation_loss"] = df["総下降量"].apply(lambda x: int(clean_numeric(x, 0)))
    df["stride_length_m"] = df["平均歩幅"].apply(lambda x: clean_numeric(x, 0.0))
    df["steps"] = df["ステップ"].apply(lambda x: int(clean_numeric(x, 0)))
    df["laps"] = df["ラップ数"].apply(lambda x: int(clean_numeric(x, 0)))

    # 表示用文字列カラム
    df["pace_str"] = df["avg_pace_sec"].apply(seconds_to_pace_str)
    df["duration_str"] = df["duration_sec"].apply(seconds_to_time_str)

    # 時系列（古い順）にソートしてインデックスを振り直す
    df = df.sort_values("datetime").reset_index(drop=True)

    return df
