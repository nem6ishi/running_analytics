import json
from pathlib import Path
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from config import HR_MAX, HR_ZONES, TARGET_PACE_SEC, TARGET_DISTANCE_KM, TARGET_TIME_SEC
from .parser import seconds_to_pace_str, seconds_to_time_str
from .fit_parser import generate_estimated_series
from .vdot import calculate_vdot, get_training_paces


def get_hr_zone(avg_hr: float, hr_max: Optional[int] = None) -> Dict[str, str]:
    """平均心拍数から心拍ゾーン・強度を判定 (config.HR_ZONES 準拠)"""
    if avg_hr <= 0:
        return {
            "zone": "Zone 0",
            "name": "計測なし",
            "intensity": "不明",
            "color": "gray",
            "bg_color": "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300",
            "desc": "心拍データがありません",
        }

    effective_hr_max = hr_max if hr_max and hr_max > 0 else HR_MAX
    pct = (avg_hr / effective_hr_max) * 100
    if pct < 65:
        z = HR_ZONES["zone1"]
        return {"zone": "Zone 1", "name": z["label"], "intensity": z["intensity"], "color": z["color"], "bg_color": z["bg_color"], "desc": z["desc"]}
    elif pct < 76:
        z = HR_ZONES["zone2"]
        return {"zone": "Zone 2", "name": z["label"], "intensity": z["intensity"], "color": z["color"], "bg_color": z["bg_color"], "desc": z["desc"]}
    elif pct < 86:
        z = HR_ZONES["zone3"]
        return {"zone": "Zone 3", "name": z["label"], "intensity": z["intensity"], "color": z["color"], "bg_color": z["bg_color"], "desc": z["desc"]}
    elif pct < 93:
        z = HR_ZONES["zone4"]
        return {"zone": "Zone 4", "name": z["label"], "intensity": z["intensity"], "color": z["color"], "bg_color": z["bg_color"], "desc": z["desc"]}
    else:
        z = HR_ZONES["zone5"]
        return {"zone": "Zone 5", "name": z["label"], "intensity": z["intensity"], "color": z["color"], "bg_color": z["bg_color"], "desc": z["desc"]}


def analyze_time_series(series: Dict[str, Any], dist_km: float) -> Dict[str, Any]:
    """折れ線グラフの時系列データから前半・後半・有酸素デカップリング（Pw:Hr）の特徴を抽出"""
    speeds = series.get("speeds_kmh", [])
    hrs = series.get("heart_rates", [])
    cadences = series.get("cadences", [])
    distances = series.get("distances", [])

    if not speeds or len(speeds) < 4:
        return {
            "split_type": "イーブンペース",
            "split_badge": "⚖️ イーブンペース",
            "split_desc": "全行程を通して一定の安定したペースで走行しました。",
            "phase_early": "スタート直後からスムーズにペースに入りました。",
            "phase_mid": "中盤も安定した巡航ペースを維持しました。",
            "phase_late": "終盤まで粘り強く走り切りました。",
            "drift_text": "心拍推移は適正にコントロールされています。",
            "decoupling_pct": 0.0,
            "decoupling_grade": "-",
            "decoupling_status": "データ不足",
            "decoupling_badge": "bg-slate-800 text-slate-400 border-slate-700",
            "decoupling_desc": "時系列データが少ないためデカップリング率は算出対象外です。",
            "running_cadence": None,
        }

    # 実走行時（信号待ちやウォーク区間を除外）のケイデンス・速度・心拍を抽出
    running_cads = [c for c in cadences if c >= 145] if cadences else []
    running_cadence = int(round(float(np.mean(running_cads)))) if len(running_cads) >= 4 else None

    # 信号停止や給水ウォーク (speed < 4.8 km/h) が混じる場合、実走行ポイントで前後半を比較
    if hrs and len(hrs) == len(speeds):
        moving_pairs = [
            (s, h)
            for idx, (s, h) in enumerate(zip(speeds, hrs))
            if s >= 4.8 and h > 0 and (not cadences or idx >= len(cadences) or cadences[idx] >= 135)
        ]
    else:
        moving_pairs = []

    if len(moving_pairs) >= 6:
        m_speeds = [p[0] for p in moving_pairs]
        m_hrs = [p[1] for p in moving_pairs]
        half_m = len(m_speeds) // 2
        first_half_speed = float(np.mean(m_speeds[:half_m]))
        second_half_speed = float(np.mean(m_speeds[half_m:]))
        first_half_hr = float(np.mean(m_hrs[:half_m]))
        second_half_hr = float(np.mean(m_hrs[half_m:]))
    else:
        n = len(speeds)
        half = n // 2
        first_half_speed = float(np.mean(speeds[:half]))
        second_half_speed = float(np.mean(speeds[half:]))
        first_half_hr = float(np.mean(hrs[:half])) if hrs else 0.0
        second_half_hr = float(np.mean(hrs[half:])) if hrs else 0.0

    speed_diff_pct = ((second_half_speed - first_half_speed) / first_half_speed) * 100 if first_half_speed > 0 else 0.0

    if speed_diff_pct > 2.5:
        split_type = "ネガティブスプリット"
        split_badge = "🔥 ネガティブスプリット (後半加速)"
        split_desc = f"前半平均 {first_half_speed:.1f} km/h に対し、後半平均 {second_half_speed:.1f} km/h と **+{speed_diff_pct:.1f}% ペースアップ**。理想的な余力配分とビルドアップができています。"
    elif speed_diff_pct < -2.5:
        split_type = "ポジティブスプリット"
        split_badge = "⚠️ ポジティブスプリット (後半失速)"
        split_desc = f"前半平均 {first_half_speed:.1f} km/h に対し、後半平均 {second_half_speed:.1f} km/h と **{speed_diff_pct:.1f}% の減速**。"
    else:
        split_type = "イーブンペース"
        split_badge = "⚖️ イーブンペース (高精度巡航)"
        split_desc = f"前半（{first_half_speed:.1f} km/h）と後半（{second_half_speed:.1f} km/h）の差が極めて小さく、精密なペース配分ができています。"

    # 有酸素デカップリング (Aerobic Decoupling: Pw:Hr / Pa:Hr)
    # EF (Efficiency Factor) = 速度(km/h) / 心拍数(bpm)
    ef_first = (first_half_speed / first_half_hr) if first_half_hr > 0 else 0.0
    ef_second = (second_half_speed / second_half_hr) if second_half_hr > 0 else 0.0

    if ef_first > 0:
        decoupling_pct = round(((ef_first - ef_second) / ef_first) * 100.0, 1)
    else:
        decoupling_pct = 0.0

    # 心拍ドリフト評価（後半ビルドアップ時の自然な心拍上昇と、失速・同ペースでの心拍ドリフトを明確に区別）
    hr_diff = second_half_hr - first_half_hr
    if speed_diff_pct > 2.5 and decoupling_pct <= 5.0:
        drift_text = (
            f"後半のペースアップ（+{speed_diff_pct:.1f}%）に伴い心拍数が **+{int(round(hr_diff))} bpm** 推移。"
            f"速度対心拍の有酸素効率は維持されており（Pw:Hr {decoupling_pct:+.1f}%）、ビルドアップに対する正常な生理的応答です。"
        )
    elif hr_diff >= 10 and decoupling_pct > 5.0:
        drift_text = f"後半に心拍数が **+{int(round(hr_diff))} bpm 上昇**（心拍ドリフト）。後半にかけて同じ速度を維持するための心肺コストが増加しています。"
    elif hr_diff >= 5:
        drift_text = f"後半に心拍数が約 **+{int(round(hr_diff))} bpm 上昇**。気温・発汗や筋疲労に伴う緩やかな心拍ドリフトが見られます。"
    else:
        drift_text = f"前後半の心拍差は **{hr_diff:+.1f} bpm** と極めて安定しており、高い有酸素エコノミーを発揮しています。"

    if decoupling_pct <= 3.0:
        decoupling_grade = "S"
        decoupling_status = "極めて安定 (スタミナ十分)"
        decoupling_badge = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
        decoupling_desc = f"デカップリング率 {decoupling_pct:+.1f}%。前半と後半で有酸素エコノミー（速度÷心拍）が衰えず、高い持久力を発揮しています。"
    elif decoupling_pct <= 5.0:
        decoupling_grade = "A"
        decoupling_status = "適正範囲 (有酸素ベース合格)"
        decoupling_badge = "bg-teal-500/20 text-teal-300 border-teal-500/30"
        decoupling_desc = f"デカップリング率 {decoupling_pct:+.1f}%。運動生理学上の合格ライン（5%以内）を維持し、安定した有酸素巡航ができています。"
    elif decoupling_pct <= 8.0:
        decoupling_grade = "B"
        decoupling_status = "軽度デカップリング (後半負荷増)"
        decoupling_badge = "bg-amber-500/20 text-amber-300 border-amber-500/30"
        decoupling_desc = f"デカップリング率 {decoupling_pct:+.1f}%。後半の上り勾配や筋疲労により、前半に比べて速度あたりの心拍コストがやや増加しています。"
    else:
        decoupling_grade = "C"
        decoupling_status = "デカップリング大 (後半失速・疲労)"
        decoupling_badge = "bg-rose-500/20 text-rose-300 border-rose-500/30"
        decoupling_desc = f"デカップリング率 {decoupling_pct:+.1f}%。後半にかけて減速または心拍上昇が見られ、コース起伏や暑熱・スタミナ消耗の影響が出ています。"

    n = len(speeds)
    early_hr = hrs[int(n * 0.2)] if hrs else 0
    max_s = max(speeds)
    max_h = max(hrs) if hrs else 0

    phase_early = f"**序盤 (0〜{dist_km * 0.25:.1f}km)**: ウォーミングアップから心拍数 {early_hr} bpm へ推移し、ペースを形成。"
    phase_mid = f"**中盤 ({dist_km * 0.25:.1f}〜{dist_km * 0.75:.1f}km)**: 巡航速度を維持し、フォームとピッチをコントロール。"
    phase_late = f"**終盤 ({dist_km * 0.75:.1f}〜{dist_km:.1f}km)**: 最高速度 **{max_s:.1f} km/h**、最大心拍 **{max_h} bpm** でフィニッシュ。"

    return {
        "split_type": split_type,
        "split_badge": split_badge,
        "split_desc": split_desc,
        "speed_diff_pct": round(speed_diff_pct, 1),
        "hr_diff": round(hr_diff, 1),
        "first_half_speed": round(first_half_speed, 1),
        "second_half_speed": round(second_half_speed, 1),
        "phase_early": phase_early,
        "phase_mid": phase_mid,
        "phase_late": phase_late,
        "drift_text": drift_text,
        "decoupling_pct": decoupling_pct,
        "decoupling_grade": decoupling_grade,
        "decoupling_status": decoupling_status,
        "decoupling_badge": decoupling_badge,
        "decoupling_desc": decoupling_desc,
        "running_cadence": running_cadence,
    }


def detect_workout_structure(
    laps: List[Dict[str, Any]], dist_km: float, avg_pace_sec: float, avg_hr: int
) -> Dict[str, Any]:
    """ラップデータや時系列からトレーニングの構造（LSD、ビルドアップ、インターバル、ペース走等）を自動判定"""
    if not laps or len(laps) < 3:
        return {
            "type": "持続走 (ペース走)",
            "badge": "🏃 ペース走",
            "badge_color": "bg-slate-800 text-slate-300 border-slate-700",
            "summary_title": f"{dist_km:.1f}km 持続走 (イーブンペース)",
            "summary_desc": f"全行程（{dist_km:.2f}km）を平均ペース **{seconds_to_pace_str(avg_pace_sec)}/km**、平均心拍 **{avg_hr} bpm** で巡航しました。安定した有酸素ペースを刻むトレーニングです。",
            "phases": [],
            "is_interval": False,
        }

    valid_laps = [l for l in laps if l.get("distance_km", 0) >= 0.4]
    if len(valid_laps) < 3:
        return {
            "type": "持続走 (ペース走)",
            "badge": "🏃 ペース走",
            "badge_color": "bg-slate-800 text-slate-300 border-slate-700",
            "summary_title": f"{dist_km:.1f}km ペース走",
            "summary_desc": "全行程を通して一定のペースで走行しました。",
            "phases": [],
            "is_interval": False,
        }

    paces = [l["pace_sec"] for l in valid_laps]
    overall_avg_pace = sum(paces) / len(paces)

    # 0. LSD (Long Slow Distance) 判定
    # 長時間（75分以上または12km以上）かつ低強度（avg_hr <= 148、メイン区間の心拍が低強度）
    total_time_estimate = sum(l.get("time_sec", 0) for l in valid_laps)
    if total_time_estimate <= 0:
        total_time_estimate = dist_km * avg_pace_sec
    core_laps = valid_laps[:-1] if len(valid_laps) > 4 else valid_laps
    max_core_lap_hr = max((l.get("avg_hr", 0) for l in core_laps), default=0)

    if (dist_km >= 12.0 or total_time_estimate >= 4500) and (0 < avg_hr <= 148) and (max_core_lap_hr <= 155):
        for idx, l in enumerate(valid_laps):
            if idx == len(valid_laps) - 1 and l["pace_sec"] < overall_avg_pace - 40:
                l["role_tag"] = "⚡ ラスト流し"
                l["role_badge"] = "bg-amber-500/20 text-amber-300 border-amber-500/30"
            elif l.get("ascent", 0) >= 45 and l["pace_sec"] > overall_avg_pace + 15:
                l["role_tag"] = "⛰️ 登坂コントロール"
                l["role_badge"] = "bg-teal-500/20 text-teal-300 border-teal-500/30"
            else:
                l["role_tag"] = "🌱 低心拍巡航"
                l["role_badge"] = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"

        # LSD を序盤・中盤・終盤の3フェーズに要約表示
        n_l = len(valid_laps)
        p1_end = max(1, n_l // 3)
        p2_end = max(p1_end + 1, (n_l * 2) // 3)
        chunks = [
            ("序盤ベース導入", "🌱 序盤巡航", "bg-emerald-500/20 text-emerald-300 border-emerald-500/30", valid_laps[:p1_end], "無理なく有酸素ゾーン（Zone 2）へ入り、長丁場に向けたリズムと呼吸を安定化。"),
            ("中盤イーブン巡航", "🌱 中盤巡航", "bg-teal-500/20 text-teal-300 border-teal-500/30", valid_laps[p1_end:p2_end], "コース起伏に合わせて出力を一定に保ち、心拍の跳ね上がりを抑えて脂質代謝を活性化。"),
            ("終盤持久・フィニッシュ", "🏁 終盤粘り", "bg-sky-500/20 text-sky-300 border-sky-500/30", valid_laps[p2_end:], "長時間接地による脚疲労の中でも心拍ドリフトを最小限に抑え、余力を残して完走。"),
        ]
        lsd_phases = []
        for title_p, tag_p, badge_p, c_laps, desc_p in chunks:
            if not c_laps:
                continue
            c_dist = round(sum(x["distance_km"] for x in c_laps), 1)
            c_pace = sum(x["pace_sec"] for x in c_laps) / len(c_laps)
            c_hr = int(round(sum(x["avg_hr"] for x in c_laps) / len(c_laps)))
            lsd_phases.append({
                "name": f"{title_p} ({c_laps[0]['lap_index']}〜{c_laps[-1]['lap_index']}km)",
                "tag": tag_p,
                "badge_color": badge_p,
                "distance_km": c_dist,
                "pace_str": seconds_to_pace_str(c_pace),
                "avg_hr": c_hr,
                "desc": desc_p,
            })

        return {
            "type": "LSD (Long Slow Distance)",
            "badge": "🌱 LSD (有酸素ベース構築)",
            "badge_color": "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
            "summary_title": f"【LSD】{dist_km:.1f}km 有酸素ベース構築走（平均 {avg_hr} bpm・低心拍キープ）",
            "summary_desc": (
                f"走行距離 **{dist_km:.2f}km（{seconds_to_time_str(int(total_time_estimate))}）** を平均心拍 **{avg_hr} bpm** の有酸素ベースゾーン（Zone 2）で徹底コントロールした理想的なロングスローディスタンス（LSD）です。"
                "上り坂や信号ストップを挟みながらも心拍の跳ね上がりを完璧に抑え込み、毛細血管網の新生・ミトコンドリア増殖・脚筋の長時間耐性を引き上げています。"
            ),
            "phases": lsd_phases,
            "is_interval": False,
            "is_lsd": True,
        }

    # 1. 疾走（fast）ラップの判定:
    # 本物のインターバル・ファルトレクは「疾走ラップが5:35/km (335秒) 以内」かつ「全体平均より15秒以上速い」かつ「前後より20秒以上速い」
    lap_roles = []
    for i, l in enumerate(valid_laps):
        p = l["pace_sec"]
        prev_p = valid_laps[i - 1]["pace_sec"] if i > 0 else p
        next_p = valid_laps[i + 1]["pace_sec"] if i < len(valid_laps) - 1 else p

        is_fast = (p <= 335.0) and (p < overall_avg_pace - 15) and (prev_p - p >= 20 or next_p - p >= 20)
        lap_roles.append("fast" if is_fast else "base")

    if 0 < avg_hr <= 148:
        fast_count = 0
    else:
        fast_count = lap_roles.count("fast")

    # 2. ビルドアップ走（後半加速 ＋ ラスト1〜2kmスパート ＋ 任意で最終1kmクールダウン）の優先判定
    # 最終ラップがクールダウン（直前ラップより25秒以上遅い）かどうかをチェック
    has_cooldown = (
        len(valid_laps) >= 5
        and valid_laps[-1]["pace_sec"] - valid_laps[-2]["pace_sec"] >= 25
        and valid_laps[-2]["pace_sec"] < overall_avg_pace - 10
    )
    active_laps = valid_laps[:-1] if has_cooldown else valid_laps
    active_paces = [l["pace_sec"] for l in active_laps]
    half_act = len(active_laps) // 2
    first_half_avg = sum(active_paces[:half_act]) / half_act
    second_half_avg = sum(active_paces[half_act:]) / (len(active_laps) - half_act)

    # 疾走が「アクティブ区間の最後1〜2ラップのみ」で前半→後半が加速している場合はファルトレクではなくビルドアップ走！
    fast_indices = [idx for idx, r in enumerate(lap_roles) if r == "fast"]
    is_end_spurt_only = (
        len(fast_indices) == 1 and fast_indices[0] >= len(active_laps) - 1
    )

    # A. 変化走 / ファルトレク / インターバル判定 (複数本の疾走と緩走が交互に存在する場合)
    if fast_count >= 2 and not is_end_spurt_only and "base" in lap_roles:
        first_fast_idx = lap_roles.index("fast")
        last_fast_idx = len(lap_roles) - 1 - list(reversed(lap_roles)).index("fast")

        phases = []
        if first_fast_idx > 0:
            wu_laps = valid_laps[:first_fast_idx]
            wu_dist = sum(l["distance_km"] for l in wu_laps)
            wu_avg_pace = sum(l["pace_sec"] for l in wu_laps) / len(wu_laps)
            wu_avg_hr = sum(l["avg_hr"] for l in wu_laps) / len(wu_laps)
            for l in wu_laps:
                l["role_tag"] = "アップ"
                l["role_badge"] = "bg-slate-800 text-slate-300 border-slate-700"

            phases.append({
                "name": f"ウォーミングアップ (1〜{first_fast_idx}km)",
                "tag": "ウォーミングアップ",
                "badge_color": "bg-slate-800 text-slate-300 border-slate-700",
                "distance_km": round(wu_dist, 1),
                "pace_str": seconds_to_pace_str(wu_avg_pace),
                "avg_hr": int(round(wu_avg_hr)),
                "desc": f"最初の **{wu_dist:.0f}km** は無理をせず平均 **{seconds_to_pace_str(wu_avg_pace)}/km**（心拍 {int(round(wu_avg_hr))} bpm）で走行。徐々に心拍を上げて筋肉を温めるアップ区間です。",
            })

        fast_seq = 1
        for i in range(first_fast_idx, last_fast_idx + 1):
            l = valid_laps[i]
            role = lap_roles[i]
            if role == "fast":
                l["role_tag"] = f"🔥 疾走 {fast_seq}本目"
                l["role_badge"] = "bg-rose-500/20 text-rose-300 border-rose-500/30"
                phases.append({
                    "name": f"疾走 {fast_seq}本目 ({l['lap_index']}km目)",
                    "tag": f"🔥 疾走 {fast_seq}本目",
                    "badge_color": "bg-rose-500/20 text-rose-300 border-rose-500/30",
                    "distance_km": l["distance_km"],
                    "pace_str": l["pace_str"],
                    "avg_hr": l["avg_hr"],
                    "desc": f"ギアを上げ **{l['pace_str']}/km** へ加速（平均心拍 **{l['avg_hr']} bpm**）。スピード持久力と心肺に強い刺激を注入。",
                })
                fast_seq += 1
            else:
                l["role_tag"] = "🧊 つなぎ・リカバリー"
                l["role_badge"] = "bg-sky-500/20 text-sky-300 border-sky-500/30"
                phases.append({
                    "name": f"つなぎ・リカバリー ({l['lap_index']}km目)",
                    "tag": "🧊 つなぎ",
                    "badge_color": "bg-sky-500/20 text-sky-300 border-sky-500/30",
                    "distance_km": l["distance_km"],
                    "pace_str": l["pace_str"],
                    "avg_hr": l["avg_hr"],
                    "desc": f"**{l['pace_str']}/km** で呼吸と筋疲労を整えながら次の疾走に備えるつなぎ区間。",
                })

        if last_fast_idx < len(valid_laps) - 1:
            cd_laps = valid_laps[last_fast_idx + 1:]
            cd_dist = sum(l["distance_km"] for l in cd_laps)
            cd_avg_pace = sum(l["pace_sec"] for l in cd_laps) / len(cd_laps)
            cd_avg_hr = sum(l["avg_hr"] for l in cd_laps) / len(cd_laps)
            for l in cd_laps:
                l["role_tag"] = "クールダウン"
                l["role_badge"] = "bg-slate-800 text-slate-400 border-slate-700"

            phases.append({
                "name": f"クールダウン ({last_fast_idx + 2}〜{len(valid_laps)}km)",
                "tag": "クールダウン",
                "badge_color": "bg-slate-800 text-slate-400 border-slate-700",
                "distance_km": round(cd_dist, 1),
                "pace_str": seconds_to_pace_str(cd_avg_pace),
                "avg_hr": int(round(cd_avg_hr)),
                "desc": f"疾走終了後の息を整えながら **{seconds_to_pace_str(cd_avg_pace)}/km** でリラックスしてフィニッシュ。",
            })

        wu_title = f"{first_fast_idx}kmアップ ＋ " if first_fast_idx > 0 else ""
        summary_title = f"【変化走 / ファルトレク】{wu_title}1km疾走 × {fast_count}本（つなぎジョグ挟み）"
        summary_desc = (
            f"最初の{first_fast_idx}kmをウォーミングアップとして走った後、"
            f"**「1km疾走 ＋ つなぎジョグ」の緩急走を{fast_count}セット** 行ったポイント練習です。"
            f"単調なジョグにとどまらず、心肺と速筋に刺激を入れてレース本番のペース切り替え力を養う実戦的な構成です。"
        )

        fast_laps = [l for l in valid_laps if "疾走" in l.get("role_tag", "")]
        base_laps = [l for l in valid_laps if "疾走" not in l.get("role_tag", "")]
        fast_paces = [l["pace_sec"] for l in fast_laps]
        base_paces = [l["pace_sec"] for l in base_laps]
        fast_avg_pace = sum(fast_paces) / len(fast_paces) if fast_paces else overall_avg_pace
        base_avg_pace = sum(base_paces) / len(base_paces) if base_paces else overall_avg_pace
        best_fast_pace = min(fast_paces) if fast_paces else overall_avg_pace
        pace_contrast = base_avg_pace - fast_avg_pace

        return {
            "type": "変化走 / ファルトレク",
            "badge": "⚡ 変化走 / ファルトレク",
            "badge_color": "bg-amber-500/20 text-amber-300 border-amber-500/30",
            "summary_title": summary_title,
            "summary_desc": summary_desc,
            "phases": phases,
            "is_interval": True,
            "fast_count": fast_count,
            "fast_avg_pace_sec": fast_avg_pace,
            "best_fast_pace_sec": best_fast_pace,
            "base_avg_pace_sec": base_avg_pace,
            "pace_contrast_sec": pace_contrast,
        }

    # B. ビルドアップ走判定 (前半→後半で12秒以上加速、またはラストスパート注入)
    if first_half_avg - second_half_avg > 12 or is_end_spurt_only:
        peak_lap = min(active_laps, key=lambda x: x["pace_sec"])
        for i, l in enumerate(valid_laps):
            if has_cooldown and i == len(valid_laps) - 1:
                l["role_tag"] = "🧊 クールダウン"
                l["role_badge"] = "bg-sky-500/20 text-sky-300 border-sky-500/30"
            elif l["lap_index"] == peak_lap["lap_index"] and l["pace_sec"] <= 315:
                l["role_tag"] = "🔥 最終スパート"
                l["role_badge"] = "bg-rose-500/20 text-rose-300 border-rose-500/30"
            elif i < half_act:
                l["role_tag"] = "前半イージー導入"
                l["role_badge"] = "bg-slate-800 text-slate-300 border-slate-700"
            else:
                l["role_tag"] = "📈 後半ビルドアップ"
                l["role_badge"] = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"

        bu_phases = []
        early_laps = active_laps[:half_act]
        late_laps = active_laps[half_act:]
        if early_laps:
            e_dist = round(sum(x["distance_km"] for x in early_laps), 1)
            e_pace = sum(x["pace_sec"] for x in early_laps) / len(early_laps)
            e_hr = int(round(sum(x["avg_hr"] for x in early_laps) / len(early_laps)))
            bu_phases.append({
                "name": f"前半：導入巡航 (1〜{early_laps[-1]['lap_index']}km)",
                "tag": "導入巡航",
                "badge_color": "bg-slate-800 text-slate-300 border-slate-700",
                "distance_km": e_dist,
                "pace_str": seconds_to_pace_str(e_pace),
                "avg_hr": e_hr,
                "desc": f"平均 **{seconds_to_pace_str(e_pace)}/km**（心拍 {e_hr} bpm）で余裕を持って入り、後半の加速に向けて脚と心肺を温める導入フェーズ。",
            })
        if late_laps:
            l_dist = round(sum(x["distance_km"] for x in late_laps), 1)
            l_pace = sum(x["pace_sec"] for x in late_laps) / len(late_laps)
            l_hr = int(round(sum(x["avg_hr"] for x in late_laps) / len(late_laps)))
            bu_phases.append({
                "name": f"後半：ビルドアップ加速 ({late_laps[0]['lap_index']}〜{late_laps[-1]['lap_index']}km)",
                "tag": "📈 後半加速",
                "badge_color": "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
                "distance_km": l_dist,
                "pace_str": seconds_to_pace_str(l_pace),
                "avg_hr": l_hr,
                "desc": f"平均 **{seconds_to_pace_str(l_pace)}/km**（最速 **{peak_lap['pace_str']}/km**）まで段階的にギアを引き上げ、乳酸閾値（LT）〜サブ50ペースの刺激を注入。",
            })
        if has_cooldown:
            cd_l = valid_laps[-1]
            bu_phases.append({
                "name": f"クールダウン ({cd_l['lap_index']}km目)",
                "tag": "🧊 クールダウン",
                "badge_color": "bg-sky-500/20 text-sky-300 border-sky-500/30",
                "distance_km": cd_l["distance_km"],
                "pace_str": cd_l["pace_str"],
                "avg_hr": cd_l["avg_hr"],
                "desc": f"ピークラップ（{peak_lap['pace_str']}/km）到達後、**{cd_l['pace_str']}/km** へ落として呼吸と心拍を整える理想的なクールダウン。",
            })

        return {
            "type": "ビルドアップ走",
            "badge": "📈 ビルドアップ走",
            "badge_color": "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
            "summary_title": f"【ビルドアップ走】前半 {seconds_to_pace_str(first_half_avg)} → 後半 {seconds_to_pace_str(second_half_avg)}/km（最速 {peak_lap['pace_str']}/km）",
            "summary_desc": (
                f"前半（平均 **{seconds_to_pace_str(first_half_avg)}/km**）でリズムを作った後、後半（平均 **{seconds_to_pace_str(second_half_avg)}/km**、最速 **{peak_lap['pace_str']}/km**）にかけて段階的にペースを引き上げたビルドアップ走です。"
                "余力を残して終盤にサブ50〜LT域のスピード刺激を入れる、実戦的かつ質の高い内容です。"
            ),
            "phases": bu_phases,
            "is_interval": False,
            "best_fast_pace_sec": peak_lap["pace_sec"],
        }

    # C. イーブンペース持続走 / テンポ走
    for l in valid_laps:
        l["role_tag"] = "巡航"
        l["role_badge"] = "bg-slate-800 text-slate-400 border-slate-700"

    is_tempo = overall_avg_pace <= 350 and avg_hr >= 162
    return {
        "type": "LTテンポ走 / ペース走" if is_tempo else "持続走 (ペース走)",
        "badge": "🔥 ペース走 (テンポ)" if is_tempo else "⚖️ イーブンペース走",
        "badge_color": "bg-amber-500/20 text-amber-300 border-amber-500/30" if is_tempo else "bg-slate-800 text-slate-300 border-slate-700",
        "summary_title": f"【{'テンポペース走' if is_tempo else 'ペース走'}】平均 {seconds_to_pace_str(overall_avg_pace)}/km 安定巡航",
        "summary_desc": "全行程を通して一定のピッチと有酸素リズムを保ち、安定した巡航ペースで走り切ったトレーニングです。",
        "phases": [],
        "is_interval": False,
        "best_fast_pace_sec": min(paces) if paces else overall_avg_pace,
    }


def _load_ai_coaching_notes(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """data/ai_coaching.json からAIによる柔軟な個別コーチング評価データを読み込む"""
    candidates = []
    if data_dir:
        candidates.append(Path(data_dir) / "ai_coaching.json")
    candidates.append(Path(__file__).resolve().parent.parent / "data" / "ai_coaching.json")

    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


def calculate_activity_insights(
    df: pd.DataFrame,
    fit_dict: Optional[Dict[str, Any]] = None,
    hr_params: Optional[Dict[str, Any]] = None,
    data_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """全アクティビティに対して詳細な「評価」「分析」「次回おすすめとリカバリー提案」データを生成"""
    insights_list = []
    if fit_dict is None:
        fit_dict = {}

    ai_notes = _load_ai_coaching_notes(data_dir=data_dir)

    best_pace_sec = df["avg_pace_sec"].min()
    longest_dist = df["distance_km"].max()
    effective_hr_max = hr_params.get("hr_max") if hr_params else None

    for i, row in df.iterrows():
        dist = row["distance_km"]
        pace_sec = row["avg_pace_sec"]
        pace_str = row["pace_str"]
        avg_hr = row["avg_hr"]
        max_hr = row["max_hr"]
        cadence = row["avg_cadence"]
        stride = row["stride_length_m"]
        duration_sec = row["duration_sec"]
        elevation = row["elevation_gain"]
        date_str = row["date_str"]
        time_of_day = row["time_of_day"]

        # 1. 心拍ゾーン判定
        hr_zone = get_hr_zone(avg_hr, hr_max=effective_hr_max)

        # 2. 速度・有酸素効率
        speed_kmh = (3600.0 / pace_sec) if pace_sec > 0 else 0.0
        aei = (speed_kmh / avg_hr * 100.0) if avg_hr > 0 else 0.0

        # 3. FIT時系列または推定プロファイルの取得
        dt_full = f"{date_str} {time_of_day}"
        fit_data = None
        for k in fit_dict:
            if k.startswith(dt_full) or k == date_str:
                fit_data = fit_dict[k]
                break

        if fit_data:
            distance_series = {
                "has_fit": True,
                "distances": fit_data["distances"],
                "speeds_kmh": fit_data["speeds_kmh"],
                "paces_str": fit_data["paces_str"],
                "heart_rates": fit_data["heart_rates"],
                "cadences": fit_data["cadences"],
                "altitudes": fit_data.get("altitudes", []),
                "coordinates": fit_data.get("coordinates", []),
                "laps": fit_data.get("laps", []),
            }
        else:
            distance_series = generate_estimated_series(
                dist, pace_sec, avg_hr, max_hr, cadence, row["max_cadence"], elevation
            )

        # 4. 時系列グラフの分析 & ワークアウト構造の自動検出
        series_analysis = analyze_time_series(distance_series, dist)
        workout_structure = detect_workout_structure(distance_series.get("laps", []), dist, pace_sec, avg_hr)
        is_lsd = workout_structure.get("is_lsd", False)
        is_buildup = workout_structure.get("type") == "ビルドアップ走"
        running_cadence = series_analysis.get("running_cadence") or cadence

        # 5. VDOT スコアの算出 (ダニエルズ式: 意図的な低心拍LSDはタイムからの単純算出対象外とする)
        if is_lsd or (0 < avg_hr <= 148 and pace_sec >= 420):
            act_vdot = 0.0
        else:
            act_vdot = calculate_vdot(dist * 1000.0, duration_sec) if dist >= 1.0 and duration_sec > 0 else 0.0

        # サブ50 (5:00/km以内) 連続維持距離の算出
        laps = distance_series.get("laps", [])
        sub50_sustained_km = 0.0
        current_sustained = 0.0
        for l in laps:
            if l.get("pace_sec", 999) <= TARGET_PACE_SEC:
                current_sustained += l.get("distance_km", 0.0)
                if current_sustained > sub50_sustained_km:
                    sub50_sustained_km = round(current_sustained, 2)
            else:
                current_sustained = 0.0

        # 6. 目的に応じたターゲットステータス判定
        gap_sec = pace_sec - TARGET_PACE_SEC
        if is_lsd:
            gap_pace_str = "Zone 2 有酸素走"
            target_status = {
                "rank": "LSD",
                "label": f"有酸素ベース構築 (平均 {avg_hr} bpm)",
                "badge_color": "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
            }
            if elevation >= 80 and abs(series_analysis.get("hr_diff", 0.0)) <= 6.0:
                series_analysis["split_badge"] = "🌱 低心拍イーブン出力 (起伏適応)"
                series_analysis["decoupling_desc"] = (
                    f"前半平均心拍と後半平均心拍の差はわずか {series_analysis.get('hr_diff', 0.0):+.1f} bpm。"
                    f"獲得標高 {elevation}m の起伏に対して後半ペースを調整し、心拍をZone 2内に完璧に収めた高度なペースマネジメントです。"
                )
        else:
            gap_pace_str = f"{gap_sec:+.0f}秒/km" if pace_sec > 0 else "--"
            if pace_sec <= 0:
                target_status = {"rank": "-", "label": "計測なし", "badge_color": "bg-slate-800 text-slate-400 border-slate-700"}
            elif pace_sec <= TARGET_PACE_SEC:
                target_status = {"rank": "S", "label": "50分ペース達成 (5:00/km以内)", "badge_color": "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"}
            elif pace_sec <= TARGET_PACE_SEC + 15.0:
                target_status = {"rank": "A", "label": f"サブ50射程圏内 (+{int(round(gap_sec))}秒/km)", "badge_color": "bg-teal-500/20 text-teal-300 border-teal-500/40"}
            elif pace_sec <= TARGET_PACE_SEC + 35.0:
                target_status = {"rank": "B", "label": f"テンポ巡航 (+{int(round(gap_sec))}秒/km)", "badge_color": "bg-amber-500/20 text-amber-300 border-amber-500/40"}
            elif pace_sec <= TARGET_PACE_SEC + 60.0:
                target_status = {"rank": "C", "label": f"有酸素持久走 (+{int(round(gap_sec))}秒/km)", "badge_color": "bg-sky-500/20 text-sky-300 border-sky-500/40"}
            else:
                target_status = {"rank": "E", "label": f"イージー / 基礎構築 (+{int(round(gap_sec))}秒/km)", "badge_color": "bg-slate-800 text-slate-300 border-slate-700"}

        # バッジ付与
        badges = []
        best_lap_pace = workout_structure.get("best_fast_pace_sec", 999)
        if pace_sec <= best_pace_sec + 3 or best_lap_pace <= TARGET_PACE_SEC:
            badges.append({"name": "サブ50ペース到達", "icon": "⚡", "type": "gold"})
        if dist >= longest_dist - 0.1:
            badges.append({"name": "最長走破記録", "icon": "🏃", "type": "indigo"})
        elif dist >= 15.0:
            badges.append({"name": f"ロング走 ({dist:.1f}km)", "icon": "🏅", "type": "indigo"})
        if act_vdot >= 42.0:
            badges.append({"name": f"高VDOT ({act_vdot:.1f})", "icon": "🎖️", "type": "emerald"})
        if running_cadence >= 174:
            badges.append({"name": f"理想ピッチ ({running_cadence}spm)", "icon": "🎯", "type": "teal"})
        if avg_hr >= 174 or max_hr >= 185:
            badges.append({"name": "高負荷LT・VO2max刺激", "icon": "🔥", "type": "orange"})
        if aei >= 6.4:
            badges.append({"name": "有酸素効率優秀", "icon": "💎", "type": "cyan"})
        if series_analysis.get("decoupling_pct", 99) <= 3.0 and dist >= 5.0:
            badges.append({"name": "スタミナ維持(Pw:Hr S)", "icon": "🛡️", "type": "sky"})
        badges.append({"name": workout_structure["badge"], "icon": "📊", "type": "amber" if workout_structure.get("is_interval") else "slate"})

        # 前回比較
        prev_diff = None
        if i > 0:
            prev_row = df.iloc[i - 1]
            p_pace_diff = pace_sec - prev_row["avg_pace_sec"]
            p_hr_diff = avg_hr - prev_row["avg_hr"]
            p_dist_diff = dist - prev_row["distance_km"]
            prev_diff = {
                "date": prev_row["date_str"],
                "pace_diff_sec": float(round(p_pace_diff, 1)),
                "pace_diff_str": f"{'-' if p_pace_diff < 0 else '+'}{abs(int(round(p_pace_diff)))}秒/km",
                "pace_improved": bool(p_pace_diff <= 0),
                "hr_diff": int(p_hr_diff),
                "hr_diff_str": f"{'+' if p_hr_diff > 0 else ''}{int(p_hr_diff)} bpm",
                "dist_diff": float(round(p_dist_diff, 2)),
            }

        # --- ▲ 反省点・課題・留意点 (Critical Bottlenecks) の文脈適応抽出 ---
        critical_bottlenecks = []
        is_decay = series_analysis.get("split_type") == "ポジティブスプリット"
        is_negative_split = series_analysis.get("split_type") == "ネガティブスプリット"
        hr_drift_val = series_analysis.get("hr_diff", 0.0)
        decoupling_pct = series_analysis.get("decoupling_pct", 0.0)

        if is_lsd:
            # LSDではスピードの遅さや登坂でのペース低下を責めず、長時間接地のケアと補給・フォーム維持に焦点を当てる
            critical_bottlenecks.append(
                f"**長時間接地（{row['duration_str']}）による深部筋・腱への機械的負荷**: 心肺負荷はZone 2（平均 {avg_hr} bpm）で穏やかですが、"
                f"**{dist:.1f}km（獲得標高 {elevation}m）** の着地衝撃によりふくらはぎ・大腿四頭筋・膝周りには大きな疲労が蓄積しています。48時間は強いポイント練習を避けて超回復を優先してください。"
            )
            if running_cadence != cadence and cadence < 160:
                critical_bottlenecks.append(
                    f"**信号待ち・給水ウォーク後の再加速リズム**: 停止・ウォーク区間を含むため全体平均ピッチは {cadence} spm ですが、**実走行時は平均 {running_cadence} spm** で巡航できています。"
                    "終盤の疲労時や上り坂からの切り替えでも、ストライドを広げず小刻みなリズム（170 spm前後）を意識するとさらに脚を残せます。"
                )
        else:
            # 1. 失速・タレ
            if is_decay:
                speed_drop = abs(series_analysis.get("speed_diff_pct", 0.0))
                critical_bottlenecks.append(
                    f"**後半のペース低下（-{speed_drop:.1f}%）**: 前半平均 {series_analysis.get('first_half_speed')} km/h から後半 {series_analysis.get('second_half_speed')} km/h へ減速。"
                    "序盤の入りをキロ5〜10秒抑え、後半に余力を残すイーブン〜ネガティブスプリットを意識しましょう。"
                )

            # 2. 有酸素デカップリング / 心拍ドリフト（ビルドアップ時の正常な心拍上昇は除外）
            if decoupling_pct > 8.0:
                critical_bottlenecks.append(
                    f"**後半の有酸素デカップリング（{decoupling_pct:+.1f}% 効率低下）**: 後半にかけて速度あたりの心拍負荷が上昇。"
                    "暑熱・脱水または前半のオーバーペースにより後半のランニングエコノミーが低下しています。"
                )
            elif decoupling_pct > 5.0 and dist >= 4.0:
                critical_bottlenecks.append(
                    f"**軽度の有酸素デカップリング（後半 {decoupling_pct:+.1f}%）**: 基準値（5%以内）をわずかに超過。"
                    "Zone 2でのロング走とLT巡航走を組み合わせることで、後半まで心拍を抑えて押し切る持久力がさらに安定します。"
                )
            elif hr_drift_val >= 10 and not is_negative_split and not is_buildup:
                critical_bottlenecks.append(
                    f"**後半の心拍上昇（+{int(round(hr_drift_val))} bpm）**: ペース維持に対して後半の心肺コストが高まっています。"
                    "力みを抜いた腕振りと呼吸リズムの安定を意識しましょう。"
                )

            # 3. 低ピッチ（実走行ピッチで判定）
            if running_cadence < 168 and running_cadence > 0:
                critical_bottlenecks.append(
                    f"**ピッチの改善余地（実走行平均 {running_cadence} spm）**: 回転数が170未満になると接地時間が長くなり、ブレーキ着地になりやすくなります。骨盤の真下へ素早く足を置く 172〜176 spm を目指しましょう。"
                )

            # 4. サブ50目標ペースとの距離感
            if best_lap_pace <= TARGET_PACE_SEC and pace_sec > TARGET_PACE_SEC + 20:
                critical_bottlenecks.append(
                    f"**サブ50ペース維持距離の拡張（現在最速ラップ {seconds_to_pace_str(best_lap_pace)}/km）**: 単発ラップでキロ5分切りを達成できています。"
                    "次のステップとして、5:15〜5:25/km のLTテンポ巡航を4〜6km連続で維持する持久力を養いましょう。"
                )
            elif gap_sec > 35 and dist >= 5.0 and avg_hr >= 165:
                critical_bottlenecks.append(
                    f"**高心拍域での巡航エコノミー改善（平均 {pace_str}/km・{avg_hr} bpm）**: 心拍がZone 3〜4に入りながらペースが5分台後半にとどまっています。"
                    "低心拍LSDで有酸素の器を広げつつ、短い距離での5:15〜5:25/km テンポ走で動きの効率を高めましょう。"
                )

        if not critical_bottlenecks:
            critical_bottlenecks.append(
                "**次なるステップへの負荷設定**: ペース配分・心拍コントロール・ピッチともに非常に高い完成度です。疲労を溜めない範囲で、LT巡航区間の距離をあと1km伸ばす挑戦が有効です。"
            )

        # --- ◎ 客観的な収穫・強み (Strong Points) の抽出 ---
        strong_points = []
        if is_lsd:
            strong_points.append(
                f"**Zone 2 低心拍の徹底維持（平均 {avg_hr} bpm / 最大 {max_hr} bpm）**: **{row['duration_str']}** の長丁場を通して心拍の暴走を完全に抑え込み、毛細血管網の新生と脂質代謝能力を最大限に引き出す理想的なLSDを完遂。"
            )
            strong_points.append(
                f"**{dist:.2f}km 走破の脚作り（ハーフ・フル対策）**: 獲得標高 **{elevation}m** のタフなコースを最後まで走り切り、11月ハーフ・12月フルマラソン完走に直結する着地耐性と時間耐久力を実証。"
            )
            if abs(hr_drift_val) <= 5.0:
                strong_points.append(
                    f"**驚異の心拍安定性（前後半差 {hr_drift_val:+.1f} bpm）**: 2時間超の走行でも心血管ドリフトを5bpm以内に抑え、上り坂で無理をしない賢明なペースコントロールを発揮。"
                )
        else:
            if best_lap_pace <= TARGET_PACE_SEC:
                strong_points.append(
                    f"**キロ5分を切るスピード出力（最速ラップ {seconds_to_pace_str(best_lap_pace)}/km）**: 目標である10km 50分ペース（5:00/km）を上回るスピードを実戦で刻み、十分な速筋出力とフォームの伸びを実証。"
                )
            if sub50_sustained_km >= 2.0:
                strong_points.append(
                    f"**サブ50ペース連続維持（{sub50_sustained_km:.1f}km）**: キロ5:00以内を連続 **{sub50_sustained_km:.1f}km** キープし、スピード持続力を着実に強化。"
                )
            if decoupling_pct <= 3.5 and dist >= 4.5:
                strong_points.append(
                    f"**極めて優秀な有酸素エコノミー（Pw:Hr {decoupling_pct:+.1f}% / Grade {series_analysis.get('decoupling_grade')}）**: 後半にかけてペースを上げても速度対心拍の効率が一切落ちず、高いスタミナベースを発揮。"
                )
            if running_cadence >= 173:
                strong_points.append(
                    f"**理想的なハイピッチ巡航（{running_cadence} spm）**: 175 spm 前後の軽快なリズムが完全に定着し、着地衝撃を逃がす効率的なフォームで走行。"
                )
            if is_negative_split or is_buildup:
                strong_points.append(
                    f"**理想的なビルドアップ配分（後半 +{abs(series_analysis.get('speed_diff_pct', 0.0)):.1f}% 加速）**: 序盤に余力を蓄え、終盤に向けて段階的にギアを上げるレースさながらのペースマネジメントを達成。"
                )
            if dist >= 9.5:
                strong_points.append(
                    f"**10km距離走破の持久力**: **{dist:.2f} km** を安定したリズムで完走し、10km〜ハーフに向けた有酸素持久力を強化。"
                )

        if not strong_points:
            strong_points.append(
                f"**着実な有酸素刺激の継続**: **{dist:.2f}km（{pace_str}/km）** を走り切り、走力向上の土台となる継続性を維持。"
            )

        # --- 【総括 (Overall Verdict)】 ---
        if is_lsd:
            overall_verdict = (
                f"**【特A評価：完璧な有酸素ベース＆時間耐久LSD】走行距離 {dist:.2f}km（{row['duration_str']}）を平均心拍 {avg_hr} bpm で完走。** "
                f"獲得標高 {elevation}m の起伏に合わせ、上りで心拍を跳ね上げず前後半の心拍ドリフトを **{hr_drift_val:+.1f} bpm** に抑え込んだ模範的なロング走です。"
                "11月末のハーフ・12月初旬のフルマラソン完走に向けた『2時間超を動き続ける脚と脂質代謝エンジン』が確実に仕上がっています。"
            )
        elif is_buildup:
            best_f_str = seconds_to_pace_str(best_lap_pace)
            if best_lap_pace <= TARGET_PACE_SEC:
                overall_verdict = (
                    f"**【理想的なビルドアップ＆サブ50刺激注入】平均 {pace_str}/km（最速ラップ {best_f_str}/km）で {dist:.2f}km を完走。** "
                    f"序盤のイージー導入から段階的にペースを引き上げ、終盤にキロ5分を切る **{best_f_str}/km** のスピード刺激を見事に注入できています。"
                    f"有酸素デカップリングも **{decoupling_pct:+.1f}%** と極めて優秀で、スピード余裕度とペース配分技術の両面で大きな収穫となるポイント練習です。"
                )
            else:
                overall_verdict = (
                    f"**【質の高いビルドアップ走】前半から後半にかけて段階的に加速し、平均 {pace_str}/km（最速 {best_f_str}/km）で {dist:.2f}km を走破。** "
                    "後半に向けて出力を高める理想的なネガティブスプリットを実践できています。このリズムをベースに、終盤ラップを5:10〜5:00/kmへ少しずつ近づけていきましょう。"
                )
        elif workout_structure.get("is_interval"):
            best_f_str = seconds_to_pace_str(best_lap_pace)
            overall_verdict = (
                f"**【緩急を活かした変化走】最速ラップ {best_f_str}/km を含む {dist:.2f}km セッション（平均 {pace_str}/km・心拍 {avg_hr} bpm）。** "
                f"ペースの切り替えによって心肺と速筋線維に刺激を入れています。最大心拍 **{max_hr} bpm** までの負荷を消化した後は、しっかりリカバリーを取って超回復につなげましょう。"
            )
        elif dist >= 8.0:
            overall_verdict = (
                f"**【安定した有酸素ペース走】走行距離 {dist:.2f}km を平均 {pace_str}/km（平均心拍 {avg_hr} bpm・ピッチ {running_cadence} spm）で完走。** "
                "大崩れすることなく一定のリズムで距離を踏み切っており、10km〜ハーフマラソンに向けた確かな巡航スタミナが養われています。"
            )
        else:
            overall_verdict = (
                f"**【テンポ・スピード維持セッション】走行距離 {dist:.2f}km を平均 {pace_str}/km（平均心拍 {avg_hr} bpm）で走破。** "
                f"ピッチ **{running_cadence} spm** の軽快な接地リズムを確認できた実りあるランです。ロング走と組み合わせることで走力が一段引き上がります。"
            )

        # --- 【🔥 次回への是正アクション (Actionable Focus)】 ---
        if is_lsd:
            actionable_focus = (
                "次回は【48〜72時間の積極的休養後、5〜6kmの疲労抜きイージージョグ（6:30〜7:00/km）】を実施し、"
                "脚の張りが完全に抜けてから【5:25〜5:35/km のビルドアップまたはテンポ走】へつなげること。"
            )
        elif is_buildup and best_lap_pace <= TARGET_PACE_SEC:
            actionable_focus = (
                "次回は【Zone 2 低心拍ジョグまたはLSD（心拍 135〜145 bpm）】で高強度刺激からの超回復を促し、"
                "次回のポイント練習では【5:15〜5:25/km 巡航区間を3〜4km連続維持】に挑戦すること。"
            )
        elif decoupling_pct > 8.0:
            actionable_focus = "次回は【前半3kmを控えめに入り、心拍 145〜155 bpm で余裕を残す配分】を徹底し、後半の失速を防ぐこと。"
        else:
            actionable_focus = "次回は【ピッチ 175 spm のリズムを維持したまま、中盤〜終盤の3kmを 5:20〜5:30/km で巡航するテンポ走】に取り組むこと。"

        # 分析テキスト
        cadence_eval = (
            f"実走行時の平均ピッチは **{running_cadence} spm**（信号・ウォーク込み全体平均 {cadence} spm、最高 {row['max_cadence']} spm）。リズム良く接地衝撃を分散できています。"
            if running_cadence != cadence and cadence < 160
            else (
                f"平均ピッチは **{cadence} spm**（最高 {row['max_cadence']} spm）。接地時間が短く、着地衝撃を効率よく推進力に変えられています。"
                if cadence >= 172
                else f"平均ピッチ **{cadence} spm**。骨盤の真下に着地する意識で172〜176 spm前後に保つとさらに省エネになります。"
            )
        )

        analysis_body = {
            "summary": f"走行距離 **{dist:.2f} km** を平均ペース **{pace_str}/km** で完走。運動強度は【**{hr_zone['name']}（{hr_zone['intensity']}）**】に該当します。",
            "workout_structure": workout_structure,
            "phase_early": series_analysis["phase_early"],
            "phase_mid": series_analysis["phase_mid"],
            "phase_late": series_analysis["phase_late"],
            "drift_text": series_analysis["drift_text"],
            "decoupling_desc": series_analysis["decoupling_desc"],
            "cadence_eval": cadence_eval,
        }

        # 次回おすすめメニュー & リカバリー提案
        if is_lsd:
            next_menu_title = "48〜72時間の休養 → 5〜6km 疲労抜きイージージョグ（6:30〜7:00/km）"
            next_menu_desc = (
                f"今回は **{dist:.2f}km・{row['duration_str']}のロングLSD** を平均心拍 **{avg_hr} bpm** で完璧に完遂しました。"
                "心肺の疲労は穏やかですが、2時間超・2万歩以上の連続着地により筋線維や腱には大きな機械的負荷がかかっています。"
                "まずは2日間しっかり休養・栄養補給して超回復させ、次回は脚の状態を確かめるイージージョグから再開しましょう。"
            )
            form_advice = "再開ジョグではスピードを追わず、クッション性の高いシューズで脱力して股関節から脚を運ぶ感覚を大切にしてください。"
            recovery_hours = "48〜72時間"
            recovery_tips = "炭水化物（グリコーゲン補充）＋たんぱく質（筋修復）を多めに摂取し、ふくらはぎ・大腿四頭筋・臀部のフォームローラーケアを推奨します。"
        elif is_buildup or workout_structure.get("is_interval") or max_hr >= 182:
            next_menu_title = "Zone 2 リカバリージョグ（5〜6km / 心拍140bpm前後）または 90分 LSD"
            next_menu_desc = (
                f"今回は最速 **{seconds_to_pace_str(best_lap_pace)}/km**（最大心拍 **{max_hr} bpm**）までしっかり刺激を入れた質の高いポイント練習でした。"
                "次回はあえてスピードを出さず、**心拍数 135〜145 bpm のZone 2 ジョグまたはLSD** を組み合わせることで、ポラライズド（二極化）効果により有酸素ベースとスピード持久力が同時に伸びていきます。"
            )
            form_advice = "ポイント練習の翌走は腕振りと肩の力を抜き、接地音を静かに保つリラックスフォームを意識しましょう。"
            recovery_hours = "36〜48時間"
            recovery_tips = "ハムストリングス・ふくらはぎのストレッチと温冷交代浴、クエン酸・アミノ酸の補給で速筋線維の回復を促しましょう。"
        elif avg_hr >= 170 or dist >= 10.0:
            next_menu_title = "5〜6km イージージョグ（心拍 140〜148 bpm）"
            next_menu_desc = (
                "しっかりとした距離・心拍負荷を消化できています。疲労を翌週へ持ち越さないよう、"
                "次回は **心拍数 145 bpm 以下** を目安に、呼吸が弾まないイージージョグで毛細血管の血流を促進させましょう。"
            )
            form_advice = "無理にストライドを広げず、足裏全体で柔らかく着地する感覚を意識してください。"
            recovery_hours = "36〜48時間"
            recovery_tips = "股関節周りとふくらはぎの入念なストレッチ、十分な睡眠と水分・たんぱく質の補給を重視してください。"
        else:
            next_menu_title = "7〜8km ビルドアップ走（6:00 → 5:20/km）"
            next_menu_desc = (
                "安定したピッチで走れています。次回は **前半3〜4kmを 6:00/km 前後で入り、後半にかけて 5:30〜5:15/km へ段階的に引き上げるビルドアップ走** を行うと、サブ50に向けた巡航余裕度が大きく向上します。"
            )
            form_advice = "ペースを上げる際も力まず、175 spm 前後のピッチを保ちながら骨盤の前傾で自然に歩幅を伸ばしましょう。"
            recovery_hours = "24〜36時間"
            recovery_tips = "入浴後の股関節・ハムストリングスのモビリティストレッチを行い、フレッシュな状態で次走に臨みましょう。"

        evaluation_dict = {
            "overall_verdict": overall_verdict,
            "overall_summary": overall_verdict,
            "target_status": target_status,
            "target_gap_sec": round(gap_sec, 1),
            "target_gap_str": gap_pace_str,
            "vdot": round(act_vdot, 1) if act_vdot > 0 else None,
            "sub50_sustained_km": sub50_sustained_km,
            "decoupling_pct": series_analysis.get("decoupling_pct", 0.0),
            "decoupling_grade": series_analysis.get("decoupling_grade", "-"),
            "decoupling_status": series_analysis.get("decoupling_status", ""),
            "decoupling_badge": series_analysis.get("decoupling_badge", ""),
            "decoupling_desc": series_analysis.get("decoupling_desc", ""),
            "critical_bottlenecks": critical_bottlenecks,
            "strong_points": strong_points,
            "actionable_focus": actionable_focus,
            "badges": badges,
            "prev_diff": prev_diff,
            "split_badge": series_analysis["split_badge"],
        }

        recommendation_dict = {
            "menu_title": next_menu_title,
            "menu_desc": next_menu_desc,
            "form_advice": form_advice,
            "recovery_hours": recovery_hours,
            "recovery_tips": recovery_tips,
        }

        # --- 🤖 AI コーチング個別オーバーライド (data/ai_coaching.json) の適用 ---
        ai_override = ai_notes.get(dt_full) or ai_notes.get(date_str)
        if ai_override:
            if "workout_structure" in ai_override:
                workout_structure.update(ai_override["workout_structure"])
                analysis_body["workout_structure"] = workout_structure
            if "lap_roles" in ai_override and laps:
                role_map = {int(k): v for k, v in ai_override["lap_roles"].items()}
                for l in laps:
                    idx_l = l.get("lap_index")
                    if idx_l in role_map:
                        l["role_tag"] = role_map[idx_l].get("role_tag", l.get("role_tag"))
                        l["role_badge"] = role_map[idx_l].get("role_badge", l.get("role_badge"))
            if "evaluation" in ai_override:
                evaluation_dict.update(ai_override["evaluation"])
                if "overall_verdict" in ai_override["evaluation"]:
                    evaluation_dict["overall_summary"] = ai_override["evaluation"]["overall_verdict"]
            if "analysis" in ai_override:
                for k_an, v_an in ai_override["analysis"].items():
                    if k_an != "workout_structure":
                        analysis_body[k_an] = v_an
            if "recommendation" in ai_override:
                recommendation_dict.update(ai_override["recommendation"])

        item = {
            "id": i,
            "date": date_str,
            "time_of_day": time_of_day,
            "title": row["タイトル"],
            "distance_km": dist,
            "duration_str": row["duration_str"],
            "duration_sec": duration_sec,
            "pace_str": pace_str,
            "pace_sec": pace_sec,
            "max_pace_str": seconds_to_pace_str(row["max_pace_sec"]),
            "max_pace_sec": row["max_pace_sec"],
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "hr_zone": hr_zone,
            "cadence": cadence,
            "running_cadence": running_cadence,
            "max_cadence": row["max_cadence"],
            "stride": stride,
            "calories": row["calories"],
            "elevation_gain": elevation,
            "aei": round(aei, 2),
            "speed_kmh": round(speed_kmh, 1),
            "distance_series": distance_series,
            "evaluation": evaluation_dict,
            "analysis": analysis_body,
            "recommendation": recommendation_dict,
        }
        insights_list.append(item)

    return insights_list
