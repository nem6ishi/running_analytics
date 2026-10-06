import math
from datetime import datetime, timedelta
import pandas as pd
import pytest

from src.load import calculate_trimp, compute_training_load, compute_zone_distribution
from src.analytics import compute_sub50_forecast, compute_gear_stats


def test_calculate_trimp_zero_and_edge_cases():
    """TRIMP計算の境界値テスト"""
    # 走行時間0秒 -> 0.0
    assert calculate_trimp(0, 150, 50, 190) == 0.0
    # 心拍数が安静時心拍以下 -> 0.0
    assert calculate_trimp(3600, 50, 50, 190) == 0.0
    assert calculate_trimp(3600, 45, 50, 190) == 0.0
    # 最大心拍数が安静時以下（不正値） -> 0.0
    assert calculate_trimp(3600, 150, 60, 50) == 0.0


def test_calculate_trimp_normal_values():
    """TRIMP計算の通常値テスト"""
    # 60分 (3600s), avg_hr=150, rhr=50, max=200
    # HRr = (150-50)/(200-50) = 100/150 = 2/3 ≈ 0.666667
    # TRIMP = 60 * (2/3) * 0.64 * exp(1.92 * (2/3))
    hr_r = 100.0 / 150.0
    expected = 60.0 * hr_r * 0.64 * math.exp(1.92 * hr_r)
    val = calculate_trimp(3600, 150, 50, 200)
    assert abs(val - round(expected, 2)) < 0.05
    assert val > 90.0


def test_calculate_trimp_hr_clipping():
    """最大心拍数を超えた場合のクリッピングテスト"""
    val_at_max = calculate_trimp(1800, 200, 50, 200)
    val_over_max = calculate_trimp(1800, 210, 50, 200)
    # HRrが1.0にクリップされるため同じ値になる
    assert val_at_max == val_over_max
    assert val_over_max > 0.0


def test_compute_training_load_dummy_data():
    """ダミーデータを用いた CTL / ATL / TSB 計算テスト"""
    # 3日間の連続ラン
    dates = [
        datetime(2026, 1, 1, 10, 0),
        datetime(2026, 1, 2, 10, 0),
        datetime(2026, 1, 5, 10, 0),  # 2日間レストを挟む
    ]
    df = pd.DataFrame({
        "datetime": dates,
        "date_str": [d.strftime("%Y-%m-%d") for d in dates],
        "duration_sec": [3600, 1800, 3600],
        "avg_hr": [150, 140, 155],
    })
    hr_params = {"hr_resting": 50, "hr_max": 195}

    result = compute_training_load(df, hr_params)

    # 2026-01-01 から 2026-01-05 まで計5日間の時系列が生成されること
    assert len(result["dates"]) == 5
    assert result["dates"][0] == "2026-01-01"
    assert result["dates"][-1] == "2026-01-05"

    # レスト日 (1/3, 1/4) の TRIMP は 0.0
    assert result["daily_trimp"][2] == 0.0
    assert result["daily_trimp"][3] == 0.0

    # CTL, ATL, TSB が計算されていること
    assert len(result["ctl"]) == 5
    assert len(result["atl"]) == 5
    assert len(result["tsb"]) == 5
    assert "status_label" in result
    assert "latest_tsb" in result


def test_compute_zone_distribution():
    """80/20 ルールおよび心拍ゾーン配分計算テスト"""
    dates = [
        datetime(2026, 10, 1, 10, 0),
        datetime(2026, 10, 3, 10, 0),
    ]
    df = pd.DataFrame({
        "datetime": dates,
        "date_str": [d.strftime("%Y-%m-%d") for d in dates],
        "duration_sec": [3600, 3600],
        "avg_hr": [120, 175],  # 1本目: 低強度(Zone1/2), 2本目: 高強度(Zone4)
    })
    hr_params = {"hr_max": 200, "hr_resting": 50}

    # FITなしのケース
    result = compute_zone_distribution(df, fit_dict=None, hr_params=hr_params)

    assert "all_time" in result
    assert "recent_4w" in result
    assert "weekly_zones" in result

    all_time = result["all_time"]
    # ゾーン合計パーセントが100%前後であること
    total_pct = sum(all_time["zones"][f"zone{i}"]["pct"] for i in range(1, 6))
    assert abs(total_pct - 100.0) < 0.5
    assert "is_80_20_achieved" in all_time
    assert "advice" in all_time

    # FITありのケース（サンプル心拍あり）
    fit_dict = {
        "2026-10-01 10:00:00": {
            "heart_rates": [110, 115, 120, 125]  # 全てZone 1〜2
        }
    }
    result_with_fit = compute_zone_distribution(df, fit_dict=fit_dict, hr_params=hr_params)
    assert result_with_fit["all_time"]["total_sec"] == 7200


def test_compute_sub50_forecast():
    """サブ50 到達予測推計テスト"""
    # 1. 向上トレンドのデータ（回帰の傾き > 0）
    base = datetime(2026, 8, 1, 10, 0)
    # 日付が進むにつれて5kmタイムが速くなる（VDOT上昇）
    runs = []
    for i in range(6):
        dt = base + timedelta(days=i * 10)
        # タイムが速くなる (35分 -> 27分)
        t_sec = 2100 - i * 60
        runs.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "distance_km": 5.0,
            "duration_sec": t_sec,
        })
    df_improving = pd.DataFrame(runs)

    res = compute_sub50_forecast(df_improving, current_vdot=38.0, target_vdot=40.8)
    assert res["status"] in ["on_track", "achieved"]
    assert res["target_vdot"] == 40.8
    if res["status"] == "on_track":
        assert res["days_to_target"] is not None
        assert res["days_to_target"] > 0
        assert res["slope_per_day"] > 0

    # 2. 既に達成済み（current_vdot >= 40.8）
    res_achieved = compute_sub50_forecast(df_improving, current_vdot=41.5, target_vdot=40.8)
    assert res_achieved["status"] == "achieved"
    assert res_achieved["days_to_target"] == 0

    # 3. 停滞・減少トレンド（回帰の傾き <= 0）
    runs_declining = []
    for i in range(6):
        dt = base + timedelta(days=i * 10)
        t_sec = 1800 + i * 60  # 遅くなる
        runs_declining.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "distance_km": 5.0,
            "duration_sec": t_sec,
        })
    df_declining = pd.DataFrame(runs_declining)
    res_stagnant = compute_sub50_forecast(df_declining, current_vdot=35.0, target_vdot=40.8)
    assert res_stagnant["status"] == "stagnant"
    assert res_stagnant["days_to_target"] is None


def test_compute_gear_stats():
    """シューズ（ギア）別走行距離集計テスト"""
    # 1. シューズ列がある場合
    df = pd.DataFrame({
        "date_str": ["2026-09-01", "2026-09-10", "2026-09-15"],
        "distance_km": [10.0, 500.0, 150.0],
        "シューズ": ["Nike Pegasus 40", "Nike Pegasus 40", "Asics Novablast 4"],
    })
    stats = compute_gear_stats(df, lifespan_km=600.0)
    assert len(stats) == 2

    # Pegasus: 510km (needs_replacement=False, status='交換準備推奨')
    pegasus = next(s for s in stats if s["name"] == "Nike Pegasus 40")
    assert pegasus["total_distance_km"] == 510.0
    assert pegasus["runs"] == 2
    assert pegasus["lifespan_pct"] == round((510.0 / 600.0) * 100.0, 1)
    assert pegasus["remaining_km"] == 90.0
    assert pegasus["needs_replacement"] is False

    # 寿命超過テスト
    df_worn = pd.DataFrame({
        "date_str": ["2026-09-01"],
        "distance_km": [650.0],
        "シューズ": ["Old Shoes"],
    })
    worn_stats = compute_gear_stats(df_worn, lifespan_km=600.0)
    assert worn_stats[0]["needs_replacement"] is True
    assert worn_stats[0]["remaining_km"] == 0.0

    # 2. シューズ列がない場合 -> 空リスト
    df_no_gear = pd.DataFrame({
        "date_str": ["2026-09-01"],
        "distance_km": [10.0],
    })
    assert compute_gear_stats(df_no_gear) == []
