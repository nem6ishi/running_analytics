import pytest
import io
import pandas as pd
from pathlib import Path
from src.coach import get_hr_zone, calculate_activity_insights
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


def test_calculate_activity_insights_dummy_df(tmp_path: Path):
    # ダミー CSV を経由して load_activities で読み込み
    csv_content = """アクティビティタイプ,日付,お気に入り,タイトル,距離,カロリー,タイム,平均心拍数,最大心拍数,平均ピッチ,最高ピッチ,平均ペース,最高ペース,総上昇量,総下降量,平均歩幅,Training Stress Score®,ステップ,減圧,ベストラップタイム,ラップ数,移動時間,経過時間,最低高度,最高高度,シューズ
ラン,2099-01-02 08:00:00,false,那覇市 ラン,10.0,600,00:52:00,160,178,176,184,5:12,4:30,20,20,1.02,0.0,5000,いいえ,00:00:00.0,10,00:52:00,00:52:00,0,20,Nike Pegasus
ラン,2099-01-01 18:00:00,false,那覇市 ラン,5.0,300,00:25:00,168,185,180,188,5:00,4:20,10,10,1.05,0.0,2500,いいえ,00:00:00.0,5,00:25:00,00:25:00,0,10,Nike Pegasus
"""
    csv_path = tmp_path / "Activities.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    df = load_activities(csv_path)

    insights = calculate_activity_insights(df, fit_dict=None, data_dir=tmp_path)
    assert len(insights) == 2
    for ins in insights:
        assert "evaluation" in ins
        assert "critical_bottlenecks" in ins["evaluation"]
        assert "strong_points" in ins["evaluation"]
        assert ins["evaluation"]["vdot"] is not None
        assert ins["evaluation"]["vdot"] > 0
        assert "analysis" in ins
        assert ins["analysis"]["workout_structure"]["type"] == "ランニング (AI未分析)"
        assert "recommendation" in ins
