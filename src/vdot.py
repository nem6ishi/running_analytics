"""ジャック・ダニエルズ式 VDOT（Daniels' Running Formula）計算モジュール

走力（VDOTスコア）の算出および、科学的根拠に基づく5大トレーニングペース（E / M / T / I / R）を提供します。
"""

import math
from typing import Dict, Any, Tuple, Optional
from .parser import seconds_to_pace_str, seconds_to_time_str


def calculate_vo2(velocity_m_per_min: float) -> float:
    """分速 (m/min) から酸素消費量 VO2 (ml/kg/min) を計算"""
    v = velocity_m_per_min
    return -4.60 + 0.182258 * v + 0.000104 * (v ** 2)


def calculate_percent_vo2max(time_minutes: float) -> float:
    """走行時間 (分) から %VO2max（最大酸素摂取量の稼働比率）を計算"""
    t = time_minutes
    if t <= 0:
        return 1.0
    return 0.8 + 0.1894393 * math.exp(-0.012778 * t) + 0.2989558 * math.exp(-0.1932605 * t)


def calculate_vdot(distance_m: float, time_seconds: float) -> float:
    """距離 (m) と所要時間 (秒) から VDOT スコアを算出"""
    if distance_m <= 0 or time_seconds <= 0:
        return 0.0
    t_min = time_seconds / 60.0
    v = distance_m / t_min  # m/min
    vo2 = calculate_vo2(v)
    pct = calculate_percent_vo2max(t_min)
    if pct <= 0:
        return 0.0
    return round(vo2 / pct, 2)


def velocity_from_vo2(target_vo2: float) -> float:
    """目標 VO2 から必要分速 (m/min) を逆算 (二次方程式の解)"""
    a = 0.000104
    b = 0.182258
    c = -(4.60 + target_vo2)
    discriminant = b ** 2 - 4 * a * c
    if discriminant < 0:
        return 0.0
    return (-b + math.sqrt(discriminant)) / (2 * a)


def pace_from_intensity(vdot: float, intensity_pct: float) -> float:
    """VDOT と目標強度比率 (%VO2max) からペース (秒/km) を算出"""
    if vdot <= 0:
        return 0.0
    target_vo2 = vdot * intensity_pct
    v_m_per_min = velocity_from_vo2(target_vo2)
    if v_m_per_min <= 0:
        return 0.0
    # 60,000 / 分速 = 秒/km
    return 60000.0 / v_m_per_min


def get_training_paces(vdot: float) -> Dict[str, Any]:
    """VDOT スコアから5大トレーニングゾーン（E / M / T / I / R）の適正ペースを算出"""
    if vdot <= 0:
        return {}

    # 強度基準 (Daniels' Running Formula 準拠)
    # Eペース (Easy): 65% 〜 78% VO2max (回復〜有酸素基礎)
    e_slow_sec = pace_from_intensity(vdot, 0.65)
    e_fast_sec = pace_from_intensity(vdot, 0.78)

    # Mペース (Marathon): 84% VO2max (マラソン巡航)
    m_sec = pace_from_intensity(vdot, 0.84)

    # Tペース (Threshold / LT): 88% VO2max (乳酸閾値向上・20〜30分持続ペース)
    t_sec = pace_from_intensity(vdot, 0.88)

    # Iペース (Interval): 97% VO2max (VO2max向上・3〜5分疾走)
    i_sec = pace_from_intensity(vdot, 0.97)

    # Rペース (Repetition): 105% VO2max (ランニングエコノミー・無酸素スピード)
    r_sec = pace_from_intensity(vdot, 1.05)

    return {
        "vdot": round(vdot, 1),
        "e_pace": {
            "name": "Eペース (Easy / イージー)",
            "short": "E",
            "range_str": f"{seconds_to_pace_str(e_fast_sec)} 〜 {seconds_to_pace_str(e_slow_sec)}",
            "fast_sec": round(e_fast_sec, 1),
            "slow_sec": round(e_slow_sec, 1),
            "intensity": "65〜78% VO2max",
            "purpose": "毛細血管網の発達・基礎持久力養成・翌日への超回復",
            "badge_color": "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
        },
        "m_pace": {
            "name": "Mペース (Marathon / マラソン)",
            "short": "M",
            "pace_str": f"{seconds_to_pace_str(m_sec)} /km",
            "pace_sec": round(m_sec, 1),
            "intensity": "84% VO2max",
            "purpose": "フルマラソン巡航ペースの身体的定着・糖質節約型代謝",
            "badge_color": "bg-blue-500/20 text-blue-300 border-blue-500/30",
        },
        "t_pace": {
            "name": "Tペース (Threshold / 乳酸閾値)",
            "short": "T",
            "pace_str": f"{seconds_to_pace_str(t_sec)} /km",
            "pace_sec": round(t_sec, 1),
            "intensity": "88% VO2max",
            "purpose": "乳酸蓄積を防ぎ、快適なスピード持久力を引き上げる【10km 50分攻略の要】",
            "badge_color": "bg-amber-500/20 text-amber-300 border-amber-500/30",
        },
        "i_pace": {
            "name": "Iペース (Interval / インターバル)",
            "short": "I",
            "pace_str": f"{seconds_to_pace_str(i_sec)} /km",
            "pace_sec": round(i_sec, 1),
            "intensity": "97% VO2max",
            "purpose": "最大酸素摂取量 (VO2max) を極限まで引き上げるスピード練習 (1km×3〜5本)",
            "badge_color": "bg-rose-500/20 text-rose-300 border-rose-500/30",
        },
        "r_pace": {
            "name": "Rペース (Repetition / レペティション)",
            "short": "R",
            "pace_str": f"{seconds_to_pace_str(r_sec)} /km",
            "pace_sec": round(r_sec, 1),
            "intensity": "105% VO2max",
            "purpose": "ランニングフォームの改善・足の回転効率・無酸素パワー向上 (200〜400m)",
            "badge_color": "bg-purple-500/20 text-purple-300 border-purple-500/30",
        },
    }


def predict_race_times_vdot(vdot: float) -> Dict[str, Dict[str, Any]]:
    """VDOT に基づく各主要レース距離（5k, 10k, ハーフ, フル）の予想タイム"""
    if vdot <= 0:
        return {}

    distances = [
        ("5km", 5000.0, "⚡"),
        ("10km", 10000.0, "🏃"),
        ("ハーフマラソン", 21097.5, "🏅"),
        ("フルマラソン", 42195.0, "👑"),
    ]

    predictions = {}
    for name, d_m, icon in distances:
        # 二分探索で該当距離を走れるタイム (t_sec) を探索
        low_t = (d_m / 1000.0) * 120.0  # 2:00/km
        high_t = (d_m / 1000.0) * 600.0 # 10:00/km

        best_t = low_t
        for _ in range(40):
            mid_t = (low_t + high_t) / 2.0
            cur_vdot = calculate_vdot(d_m, mid_t)
            if cur_vdot > vdot:
                low_t = mid_t
            else:
                high_t = mid_t
            best_t = mid_t

        pace_sec = best_t / (d_m / 1000.0)
        predictions[name] = {
            "name": name,
            "icon": icon,
            "distance_km": round(d_m / 1000.0, 2),
            "time_str": seconds_to_time_str(int(round(best_t))),
            "pace_str": seconds_to_pace_str(pace_sec),
            "time_sec": round(best_t, 1),
            "pace_sec": round(pace_sec, 1),
        }

    return predictions
