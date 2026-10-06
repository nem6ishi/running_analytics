"""ユーザープロファイルおよび生理パラメータ管理モジュール

安静時心拍数（Garmin Connect 同期）や実測最大心拍数（アクティビティ履歴から抽出）を
管理し、心拍ゾーンの動的境界計算を提供します。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
from config import HR_MAX, HR_RESTING, HR_ZONES
from .parser import clean_numeric


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
