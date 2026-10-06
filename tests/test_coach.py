import pytest
import io
import pandas as pd
from pathlib import Path
from src.coach import get_hr_zone, detect_workout_structure, calculate_activity_insights
from src.parser import load_activities


def test_get_hr_zone_boundaries():
    # 既定 HR_MAX=195 の場合
    # Zone 1: 0 - 65% (<= 126.75)
    # Zone 2: 65 - 76% (126.75 - 148.2)
    # Zone 3: 76 - 86% (148.2 - 167.7)
    # Zone 4: 86 - 93% (167.7 - 181.35)
    # Zone 5: 93 - 100% (181.35 - 195)
    
    z1 = get_hr_zone(120, hr_max=195)
    assert z1["zone"] == "Zone 1"

    z2 = get_hr_zone(140, hr_max=195)
    assert z2["zone"] == "Zone 2"

    z3 = get_hr_zone(155, hr_max=195)
    assert z3["zone"] == "Zone 3"

    z4 = get_hr_zone(175, hr_max=195)
    assert z4["zone"] == "Zone 4"

    z5 = get_hr_zone(190, hr_max=195)
    assert z5["zone"] == "Zone 5"

    # 極端な値のテスト
    z_zero = get_hr_zone(0, hr_max=195)
    assert z_zero["zone"] == "Zone 0"

    z_over = get_hr_zone(210, hr_max=195)
    assert z_over["zone"] == "Zone 5"


def test_detect_workout_structure_pace_run():
    # ラップ数が少ない、または均一ペースの場合は「持続走 (ペース走)」
    laps_few = [
        {"lap_index": 1, "distance_km": 1.0, "pace_sec": 330.0, "pace_str": "5:30", "avg_hr": 150},
        {"lap_index": 2, "distance_km": 1.0, "pace_sec": 332.0, "pace_str": "5:32", "avg_hr": 152},
    ]
    res_few = detect_workout_structure(laps_few, 2.0, 331.0, 151)
    assert not res_few["is_interval"]
    assert "持続走" in res_few["type"]

    # 5ラップでペース均一
    laps_steady = [
        {"lap_index": 1, "distance_km": 1.0, "pace_sec": 300.0, "pace_str": "5:00", "avg_hr": 150},
        {"lap_index": 2, "distance_km": 1.0, "pace_sec": 302.0, "pace_str": "5:02", "avg_hr": 152},
        {"lap_index": 3, "distance_km": 1.0, "pace_sec": 298.0, "pace_str": "4:58", "avg_hr": 153},
        {"lap_index": 4, "distance_km": 1.0, "pace_sec": 301.0, "pace_str": "5:01", "avg_hr": 154},
        {"lap_index": 5, "distance_km": 1.0, "pace_sec": 300.0, "pace_str": "5:00", "avg_hr": 155},
    ]
    res_steady = detect_workout_structure(laps_steady, 5.0, 300.0, 153)
    assert not res_steady["is_interval"]


def test_detect_workout_structure_interval():
    # インターバル走（疾走ラップとつなぎラップが存在）
    laps_interval = [
        {"lap_index": 1, "distance_km": 1.0, "pace_sec": 360.0, "pace_str": "6:00", "avg_hr": 140},
        {"lap_index": 2, "distance_km": 1.0, "pace_sec": 270.0, "pace_str": "4:30", "avg_hr": 175},
        {"lap_index": 3, "distance_km": 1.0, "pace_sec": 350.0, "pace_str": "5:50", "avg_hr": 150},
        {"lap_index": 4, "distance_km": 1.0, "pace_sec": 268.0, "pace_str": "4:28", "avg_hr": 177},
        {"lap_index": 5, "distance_km": 1.0, "pace_sec": 360.0, "pace_str": "6:00", "avg_hr": 148},
    ]
    res = detect_workout_structure(laps_interval, 5.0, 321.0, 158)
    assert res["is_interval"] or "疾走" in str(res["phases"])


def test_calculate_activity_insights_dummy_df(tmp_path: Path):
    # ダミー CSV を経由して load_activities で読み込み
    csv_content = """アクティビティタイプ,日付,お気に入り,タイトル,距離,カロリー,タイム,平均心拍数,最大心拍数,平均ピッチ,最高ピッチ,平均ペース,最高ペース,総上昇量,総下降量,平均歩幅,Training Stress Score®,ステップ,減圧,ベストラップタイム,ラップ数,移動時間,経過時間,最低高度,最高高度,シューズ
ラン,2026-10-06 08:00:00,false,那覇市 ラン,10.0,600,00:52:00,160,178,176,184,5:12,4:30,20,20,1.02,0.0,5000,いいえ,00:00:00.0,10,00:52:00,00:52:00,0,20,Nike Pegasus
ラン,2026-10-05 18:00:00,false,那覇市 ラン,5.0,300,00:25:00,168,185,180,188,5:00,4:20,10,10,1.05,0.0,2500,いいえ,00:00:00.0,5,00:25:00,00:25:00,0,10,Nike Pegasus
"""
    csv_path = tmp_path / "Activities.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    df = load_activities(csv_path)

    insights = calculate_activity_insights(df, fit_dict=None)
    assert len(insights) == 2
    for ins in insights:
        assert "evaluation" in ins
        assert "critical_bottlenecks" in ins["evaluation"]
        assert "strong_points" in ins["evaluation"]
        assert ins["evaluation"]["vdot"] is not None
        assert ins["evaluation"]["vdot"] > 0
        assert "analysis" in ins
        assert "recommendation" in ins
