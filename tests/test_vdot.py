import pytest
from src.vdot import calculate_vo2, calculate_percent_vo2max, calculate_vdot, get_training_paces, predict_race_times_vdot


def test_calculate_vdot():
    # 5000m を 24分00秒 (1440秒 = 4:48/km) で走った場合、VDOT は約 40.2
    vdot = calculate_vdot(5000.0, 1440.0)
    assert 39.5 <= vdot <= 41.0

    # 10000m を 50分00秒 (3000秒 = 5:00/km) で走った場合、VDOT は約 40.0
    vdot_10k = calculate_vdot(10000.0, 3000.0)
    assert 39.0 <= vdot_10k <= 41.0


def test_get_training_paces():
    paces = get_training_paces(40.2)
    assert "e_pace" in paces
    assert "t_pace" in paces
    assert "i_pace" in paces
    assert "r_pace" in paces

    # Tペースは概ね 5:00〜5:10/km の範囲
    assert 295.0 <= paces["t_pace"]["pace_sec"] <= 315.0

    # Eペースは Tペースより遅い (秒数が大きい)
    assert paces["e_pace"]["slow_sec"] > paces["t_pace"]["pace_sec"]

    # Iペースは Tペースより速い (秒数が小さい)
    assert paces["i_pace"]["pace_sec"] < paces["t_pace"]["pace_sec"]


def test_predict_race_times_vdot():
    preds = predict_race_times_vdot(40.2)
    assert "5km" in preds
    assert "10km" in preds
    assert "ハーフマラソン" in preds
    assert "フルマラソン" in preds

    # 10km予想タイムは 49分〜51分の間
    assert 2900 <= preds["10km"]["time_sec"] <= 3100
