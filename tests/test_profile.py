import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
import pandas as pd
from config import HR_MAX, HR_RESTING
from src.profile import load_profile, save_profile, get_hr_params
from src.coach import get_hr_zone
from sync import sync_resting_heart_rate


def test_load_save_profile(tmp_path: Path):
    data_dir = tmp_path / "data"

    # 1. 存在しない場合は空辞書
    assert load_profile(data_dir) == {}

    # 2. 保存と読み込み
    data = {"resting_heart_rate": 52, "updated_at": "2026-10-06"}
    save_profile(data_dir, data)
    loaded = load_profile(data_dir)
    assert loaded == data

    # 3. 破損したJSONの場合は空辞書
    profile_file = data_dir / "profile.json"
    profile_file.write_text("invalid json syntax", encoding="utf-8")
    assert load_profile(data_dir) == {}


def test_get_hr_params_defaults(tmp_path: Path):
    # profile.json も df もない場合
    params = get_hr_params(tmp_path)
    assert params["hr_max"] == HR_MAX
    assert params["hr_max_source"] == "既定値"
    assert params["hr_resting"] == HR_RESTING
    assert params["hr_resting_source"] == "既定値"
    assert "zone1" in params["zones"]
    assert "zone5" in params["zones"]
    assert params["zones"]["zone1"]["max_bpm"] == int(round(HR_MAX * 0.65))


def test_get_hr_params_with_profile(tmp_path: Path):
    # profile.json に安静時心拍がある場合
    data = {"resting_heart_rate": 48}
    save_profile(tmp_path, data)

    params = get_hr_params(tmp_path)
    assert params["hr_resting"] == 48
    assert params["hr_resting_source"] == "Garmin実測"
    assert params["hr_max"] == HR_MAX
    assert params["hr_max_source"] == "既定値"


def test_get_hr_params_with_df(tmp_path: Path):
    # df の最大心拍数が HR_MAX (195) を超える場合
    df_higher = pd.DataFrame([
        {"max_hr": 190},
        {"max_hr": 202},
        {"max_hr": 185},
    ])
    params = get_hr_params(tmp_path, df=df_higher)
    assert params["hr_max"] == 202
    assert params["hr_max_source"] == "アクティビティ実測最大"
    # ゾーン境界も 202 基準で計算されること
    assert params["zones"]["zone1"]["max_bpm"] == int(round(202 * 0.65))

    # df の最大心拍数が HR_MAX 以下の場合
    df_lower = pd.DataFrame([{"max_hr": 180}])
    params_lower = get_hr_params(tmp_path, df=df_lower)
    assert params_lower["hr_max"] == HR_MAX
    assert params_lower["hr_max_source"] == "既定値"


def test_get_hr_zone_dynamic_hr_max():
    # 1. デフォルト (hr_max=None) -> HR_MAX (195) 基準
    # 195 * 0.70 = 136.5 -> Zone 2 (65%〜76%)
    z_default = get_hr_zone(136)
    assert z_default["zone"] == "Zone 2"

    # 2. 動的 hr_max=220 基準
    # 136 / 220 = 61.8% -> Zone 1 (<65%)
    z_dynamic = get_hr_zone(136, hr_max=220)
    assert z_dynamic["zone"] == "Zone 1"

    # 3. 0以下の入力
    z_zero = get_hr_zone(0)
    assert z_zero["zone"] == "Zone 0"


def test_sync_resting_heart_rate(tmp_path: Path):
    client = MagicMock()
    # 1. get_user_summary から成功
    client.get_user_summary.return_value = {"restingHeartRate": 51}
    rhr = sync_resting_heart_rate(client, tmp_path)
    assert rhr == 51
    profile = load_profile(tmp_path)
    assert profile["resting_heart_rate"] == 51

    # 2. get_user_summary はエラーだが get_rhr_day から成功
    client.get_user_summary.side_effect = Exception("API error")
    client.get_rhr_day.return_value = {
        "allMetrics": {
            "metricsMap": {
                "WELLNESS_RESTING_HEART_RATE": [{"value": 49}]
            }
        }
    }
    rhr2 = sync_resting_heart_rate(client, tmp_path)
    assert rhr2 == 49
    profile2 = load_profile(tmp_path)
    assert profile2["resting_heart_rate"] == 49

    # 3. 両方エラーでも例外を出さず None を返す
    client.get_rhr_day.side_effect = Exception("API error 2")
    rhr3 = sync_resting_heart_rate(client, tmp_path)
    assert rhr3 is None
