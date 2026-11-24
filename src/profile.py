"""ユーザープロファイルおよび生理パラメータ管理モジュール

安静時心拍数（Garmin Connect 同期）や実測最大心拍数（アクティビティ履歴から抽出）を
管理し、心拍ゾーンの動的境界計算を提供します。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd
from config import HR_MAX, HR_RESTING, HR_ZONES
from .parser import clean_numeric

VO2MAX_HISTORY_FILENAME = "vo2max_history.json"


def load_profile(data_dir: Path) -> Dict[str, Any]:
    """data_dir / "profile.json" を読み込む。存在しない場合や破損時は空辞書を返す。"""
    profile_file = data_dir / "profile.json"
    if not profile_file.exists():
        return {}
    try:
        with open(profile_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_profile(data_dir: Path, data: Dict[str, Any]) -> None:
    """data_dir / "profile.json" に保存する。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    profile_file = data_dir / "profile.json"
    with open(profile_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_hr_params(
    data_dir: Optional[Path] = None,
    df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """生理パラメータ（安静時心拍、最大心拍、心拍ゾーン）を動的に決定して返す。

    Args:
        data_dir: profile.json が保存されているディレクトリ（通常は data/）
        df: アクティビティの DataFrame（最大心拍数の抽出に使用）

    Returns:
        hr_max: 最大心拍数 (bpm)
        hr_max_source: 出どころ ("アクティビティ実測最大" または "既定値")
        hr_resting: 安静時心拍数 (bpm)
        hr_resting_source: 出どころ ("Garmin実測" または "既定値")
        zones: 動的計算された各心拍ゾーンの辞書
    """
    # 1. 安静時心拍 (hr_resting)
    profile = load_profile(data_dir) if data_dir else {}
    rhr_val = profile.get("resting_heart_rate")
    if rhr_val is not None:
        try:
            rhr_int = int(round(float(rhr_val)))
            if rhr_int > 0:
                hr_resting = rhr_int
                hr_resting_source = "Garmin実測"
            else:
                hr_resting = HR_RESTING
                hr_resting_source = "既定値"
        except (ValueError, TypeError):
            hr_resting = HR_RESTING
            hr_resting_source = "既定値"
    else:
        hr_resting = HR_RESTING
        hr_resting_source = "既定値"

    # 2. 最大心拍数 (hr_max)
    observed_max_hr = 0
    if df is not None and not df.empty:
        if "max_hr" in df.columns:
            series = pd.to_numeric(df["max_hr"], errors="coerce").dropna()
            if not series.empty:
                observed_max_hr = int(round(series.max()))
        elif "最大心拍数" in df.columns:
            series = df["最大心拍数"].apply(lambda x: clean_numeric(x, 0.0))
            if not series.empty:
                observed_max_hr = int(round(series.max()))

    if observed_max_hr > HR_MAX:
        hr_max = observed_max_hr
        hr_max_source = "アクティビティ実測最大"
    else:
        hr_max = HR_MAX
        hr_max_source = "既定値"

    # 3. ゾーン境界 (bpm) の計算
    zones = {}
    for zone_key, zone_def in HR_ZONES.items():
        min_pct = zone_def.get("min_pct", 0)
        max_pct = zone_def.get("max_pct", 100)
        min_bpm = int(round(hr_max * (min_pct / 100.0)))
        max_bpm = int(round(hr_max * (max_pct / 100.0)))

        z_info = dict(zone_def)
        z_info["min_bpm"] = min_bpm
        z_info["max_bpm"] = max_bpm
        if max_pct >= 100:
            z_info["bpm_label"] = f"{min_bpm} bpm+"
        elif min_pct <= 0:
            z_info["bpm_label"] = f"<{max_bpm} bpm"
        else:
            z_info["bpm_label"] = f"{min_bpm}-{max_bpm} bpm"
        zones[zone_key] = z_info

    return {
        "hr_max": hr_max,
        "hr_max_source": hr_max_source,
        "hr_resting": hr_resting,
        "hr_resting_source": hr_resting_source,
        "zones": zones,
    }


def load_vo2max_history(data_dir: Optional[Path]) -> List[Dict[str, Any]]:
    """data_dir / "vo2max_history.json" を読み込む。存在しない場合や破損時は空リストを返す。"""
    if not data_dir:
        return []
    history_file = data_dir / VO2MAX_HISTORY_FILENAME
    if not history_file.exists():
        return []
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_vo2max_history(data_dir: Path, records: List[Dict[str, Any]]) -> None:
    """VO2max 履歴を日付昇順で data_dir / "vo2max_history.json" に保存する。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    sorted_records = sorted(
        [r for r in records if isinstance(r, dict) and r.get("date")],
        key=lambda r: r["date"],
    )
    history_file = data_dir / VO2MAX_HISTORY_FILENAME
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(sorted_records, f, ensure_ascii=False, indent=2)


def merge_vo2max_records(
    existing: List[Dict[str, Any]],
    new_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """既存履歴と新規取得レコードを date キーでマージし、日付昇順で返す。"""
    merged: Dict[str, Dict[str, Any]] = {}
    for rec in existing:
        if isinstance(rec, dict) and rec.get("date"):
            merged[rec["date"]] = rec
    for rec in new_records:
        if isinstance(rec, dict) and rec.get("date"):
            merged[rec["date"]] = rec
    return [merged[d] for d in sorted(merged.keys())]


def get_vo2max_summary(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """保存済みの Garmin VO2max 履歴からサマリー統計を生成する。"""
    history = load_vo2max_history(data_dir)
    valid = [
        r for r in history
        if r.get("vo2max_precise") is not None or r.get("vo2max") is not None
    ]
    if not valid:
        return {
            "has_data": False,
            "latest": None,
            "latest_date": None,
            "peak": None,
            "peak_date": None,
            "initial": None,
            "diff": 0.0,
            "fitness_age": None,
            "count": 0,
            "history": [],
        }

    def _val(r: Dict[str, Any]) -> float:
        v = r.get("vo2max_precise")
        if v is None:
            v = r.get("vo2max")
        return float(v)

    latest_rec = valid[-1]
    initial_rec = valid[0]
    peak_rec = max(valid, key=_val)

    latest_val = round(_val(latest_rec), 1)
    initial_val = round(_val(initial_rec), 1)
    peak_val = round(_val(peak_rec), 1)

    return {
        "has_data": True,
        "latest": latest_val,
        "latest_date": latest_rec["date"],
        "peak": peak_val,
        "peak_date": peak_rec["date"],
        "initial": initial_val,
        "diff": round(latest_val - initial_val, 1),
        "fitness_age": latest_rec.get("fitness_age"),
        "count": len(valid),
        "history": [
            {
                "date": r["date"],
                "vo2max": round(_val(r), 1),
                "vo2max_display": r.get("vo2max"),
                "fitness_age": r.get("fitness_age"),
            }
            for r in valid
        ],
    }
