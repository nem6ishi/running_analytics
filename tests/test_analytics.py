import pytest
import pandas as pd
from pathlib import Path
from src.parser import load_activities
from src.analytics import compute_vdot_analytics, compute_sub50_progress, compute_calendar_heatmap, compute_rolling_volume
from src.coach import analyze_time_series


def test_analyze_time_series_decoupling():
    # 前半と後半で速度同じ、心拍同じ -> デカップリング 0%
    series_even = {
        "distances": [1, 2, 3, 4],
        "speeds_kmh": [10.0, 10.0, 10.0, 10.0],
        "heart_rates": [150, 150, 150, 150],
        "cadences": [175, 175, 175, 175],
    }
    res = analyze_time_series(series_even, 4.0)
    assert res["decoupling_pct"] == 0.0
    assert res["decoupling_grade"] == "S"

    # 後半に心拍が急上昇した場合 -> デカップリング正値 (心肺効率低下)
    series_drift = {
        "distances": [1, 2, 3, 4],
        "speeds_kmh": [10.0, 10.0, 10.0, 10.0],
        "heart_rates": [140, 140, 160, 160],
        "cadences": [175, 175, 175, 175],
    }
    res_drift = analyze_time_series(series_drift, 4.0)
    assert res_drift["decoupling_pct"] > 5.0
    assert res_drift["decoupling_grade"] in ["B", "C"]


def test_analytics_with_real_csv():
    csv_path = Path("data/Activities.csv")
    if not csv_path.exists():
        pytest.skip("Activities.csv not found")

    df = load_activities(csv_path)
    assert len(df) > 0

    vdot_res = compute_vdot_analytics(df)
    assert vdot_res["current_vdot"] > 0
    assert vdot_res["peak_vdot"] >= vdot_res["current_vdot"]

    heatmap = compute_calendar_heatmap(df)
    assert len(heatmap) >= 100
    # 7の倍数（完全な週で構成されていること）
    assert len(heatmap) % 7 == 0
    # 最初の要素は月曜日、最後の要素は日曜日
    assert heatmap[0]["weekday"] == 0
    assert heatmap[0]["weekday_jp"] == "月"
    assert heatmap[-1]["weekday"] == 6
    assert heatmap[-1]["weekday_jp"] == "日"
    # 必須キーの存在チェック
    sample = heatmap[0]
    for key in ["date", "date_jp", "year", "month", "day", "weekday", "weekday_jp", "distance_km", "is_future", "is_first_day"]:
        assert key in sample

    rolling = compute_rolling_volume(df, window_days=30)
    assert len(rolling["dates"]) >= 100
    assert len(rolling["volumes"]) == len(rolling["dates"])
    assert len(rolling["runs"]) == len(rolling["dates"])
    assert rolling["current_volume"] > 0
    assert rolling["peak_volume"] >= rolling["current_volume"]
    assert rolling["window_days"] == 30


def test_prepare_full_analytics():
    from src.analytics import prepare_full_analytics
    csv_path = Path("data/Activities.csv")
    if not csv_path.exists():
        pytest.skip("Activities.csv not found")

    df = load_activities(csv_path)
    res = prepare_full_analytics(df, data_dir=Path("data"))
    assert "hr_params" in res
    assert res["hr_params"]["hr_max"] >= 195
    assert "hr_max_source" in res["hr_params"]
    assert "hr_resting" in res["hr_params"]
    assert "hr_resting_source" in res["hr_params"]
    assert "zones" in res["hr_params"]
    assert len(res["insights"]) == len(df)
