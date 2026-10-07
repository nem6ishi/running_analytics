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
        }

    n = len(speeds)
    half = n // 2

    # 前半・後半の速度
    first_half_speed = float(np.mean(speeds[:half]))
    second_half_speed = float(np.mean(speeds[half:]))
    speed_diff_pct = ((second_half_speed - first_half_speed) / first_half_speed) * 100 if first_half_speed > 0 else 0

    if speed_diff_pct > 2.5:
        split_type = "ネガティブスプリット"
        split_badge = "🔥 ネガティブスプリット (後半加速)"
        split_desc = f"前半平均 {first_half_speed:.1f} km/h に対し、後半平均 {second_half_speed:.1f} km/h と **+{speed_diff_pct:.1f}% ペースアップ**。理想的な余力配分とビルドアップができています。"
    elif speed_diff_pct < -2.5:
        split_type = "ポジティブスプリット"
        split_badge = "⚠️ ポジティブスプリット (後半失速)"
        split_desc = f"前半平均 {first_half_speed:.1f} km/h に対し、後半平均 {second_half_speed:.1f} km/h と **{speed_diff_pct:.1f}% の失速**。序盤の突っ込みすぎ、または後半を押し切る脚筋力・乳酸耐性の不足が顕著に出ています。"
    else:
        split_type = "イーブンペース"
        split_badge = "⚖️ イーブンペース (高精度巡航)"
        split_desc = f"前半（{first_half_speed:.1f} km/h）と後半（{second_half_speed:.1f} km/h）の差が極めて小さく、精密なペース配分ができています。"

    # 心拍ドリフト
    first_half_hr = float(np.mean(hrs[:half])) if hrs else 0
    second_half_hr = float(np.mean(hrs[half:])) if hrs else 0
    hr_diff = second_half_hr - first_half_hr

    if hr_diff >= 10:
        drift_text = f"後半に心拍数が **+{int(round(hr_diff))} bpm 急上昇**（著しい心拍ドリフト）。同じ出力を保てず心肺が悲鳴を上げており、有酸素の器（毛細血管網・心拍出量）が不足している明確な証拠です。"
    elif hr_diff >= 4:
        drift_text = f"後半に心拍数が約 **+{int(round(hr_diff))} bpm 上昇**（心拍ドリフト）。筋疲労や気温・脱水により心肺負荷が増加しています。水分補給とイージージョグでの回復が重要です。"
    else:
        drift_text = "走行全般にわたって心拍数が極めて安定しており、高い有酸素エコノミーを発揮しています。"

    # 有酸素デカップリング (Aerobic Decoupling: Pw:Hr / Pa:Hr)
    # EF (Efficiency Factor) = 速度(km/h) / 心拍数(bpm)
    ef_first = (first_half_speed / first_half_hr) if first_half_hr > 0 else 0
    ef_second = (second_half_speed / second_half_hr) if second_half_hr > 0 else 0

    if ef_first > 0:
        # デカップリング率 (%): 前半の効率から後半の効率が何%低下したか
        decoupling_pct = round(((ef_first - ef_second) / ef_first) * 100.0, 1)
    else:
        decoupling_pct = 0.0

    if decoupling_pct <= 3.0:
        decoupling_grade = "S"
        decoupling_status = "極めて安定 (スタミナ十分)"
        decoupling_badge = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
        decoupling_desc = f"デカップリング率 {decoupling_pct:+.1f}%。前半と後半で有酸素エコノミーが衰えず、目標ペースを押し切る十分なスタミナベースがあります。"
    elif decoupling_pct <= 5.0:
        decoupling_grade = "A"
        decoupling_status = "適正範囲 (有酸素ベース合格)"
        decoupling_badge = "bg-teal-500/20 text-teal-300 border-teal-500/30"
        decoupling_desc = f"デカップリング率 {decoupling_pct:+.1f}%。運動生理学上の合格ライン（5%以内）を維持。筋疲労を抑えて粘り強く走れています。"
    elif decoupling_pct <= 8.0:
        decoupling_grade = "B"
        decoupling_status = "軽度デカップリング (スタミナ低下)"
        decoupling_badge = "bg-amber-500/20 text-amber-300 border-amber-500/30"
        decoupling_desc = f"デカップリング率 {decoupling_pct:+.1f}%。後半に同じ出力を維持できず心肺負担が増加（または速度が低下）。毛細血管網の基礎持久力不足が伺えます。"
    else:
        decoupling_grade = "C"
        decoupling_status = "重度デカップリング (有酸素枯渇)"
        decoupling_badge = "bg-rose-500/20 text-rose-300 border-rose-500/30"
        decoupling_desc = f"デカップリング率 {decoupling_pct:+.1f}%。後半に著しい失速または心拍急上昇が発生。設定ペースに対し心肺・脚持久力がオーバーキャパシティです。"

    # 3フェーズ解説
    start_speed = speeds[0]
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
    }


def detect_workout_structure(
    laps: List[Dict[str, Any]], dist_km: float, avg_pace_sec: float, avg_hr: int
) -> Dict[str, Any]:
    """ラップデータや時系列からトレーニングの構造（アップ、疾走、つなぎ、ダウン等）を自動判定"""
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
            "summary_desc": f"全行程を通して一定のペースで走行しました。",
            "phases": [],
            "is_interval": False,
        }

    paces = [l["pace_sec"] for l in valid_laps]
    overall_avg_pace = sum(paces) / len(paces)

    # 0. LSD (Long Slow Distance) 判定
    # 長時間（75分以上または12km以上）かつ低強度（avg_hr <= 148、各ラップ心拍 <= 155）
    total_time_estimate = sum(l.get("time_sec", 0) for l in valid_laps)
    if total_time_estimate <= 0:
        total_time_estimate = dist_km * avg_pace_sec
    max_lap_hr = max((l.get("avg_hr", 0) for l in valid_laps), default=0)

    if (dist_km >= 12.0 or total_time_estimate >= 4500) and (0 < avg_hr <= 148) and (max_lap_hr <= 155):
        for l in valid_laps:
            l["role_tag"] = "低心拍巡航"
            l["role_badge"] = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"

        return {
            "type": "LSD (Long Slow Distance)",
            "badge": "🌱 LSD (有酸素ベース構築)",
            "badge_color": "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
            "summary_title": f"【LSD】{dist_km:.1f}km 有酸素ベース構築走（低心拍キープ）",
            "summary_desc": (
                f"走行距離 **{dist_km:.2f}km** を平均心拍 **{avg_hr} bpm** の低強度有酸素ゾーン（Z1〜Z2）を保ち続けて走破した理想的なLSDです。"
                "地形の起伏に合わせてペースを自然にコントロールし、心拍の跳ね上がりを抑制。"
                "末梢の毛細血管網の新生、遅筋線維のミトコンドリア活性化、および脂質代謝効率を高める最高の有酸素土台作りができています。"
            ),
            "phases": [],
            "is_interval": False,
            "is_lsd": True,
        }

    # 1. 疾走（fast）ラップの判定: 全体平均より12秒以上速く、かつ前後のラップより18秒以上速い
    lap_roles = []
    for i, l in enumerate(valid_laps):
        p = l["pace_sec"]
        prev_p = valid_laps[i - 1]["pace_sec"] if i > 0 else p
        next_p = valid_laps[i + 1]["pace_sec"] if i < len(valid_laps) - 1 else p

        is_fast = (p < overall_avg_pace - 12) and (prev_p - p >= 18 or next_p - p >= 18)
        lap_roles.append("fast" if is_fast else "base")

    # 低強度ジョグ（avg_hr <= 145 かつ max_lap_hr <= 150）で起伏等によりラップペースがばらついただけの場合はファルトレクとみなさない
    if 0 < avg_hr <= 145 and max_lap_hr <= 150:
        fast_count = 0
    else:
        fast_count = lap_roles.count("fast")

    # A. 変化走 / ファルトレク / インターバル判定 (急加速と緩走が交互に存在)
    if fast_count >= 1 and "base" in lap_roles:
        first_fast_idx = lap_roles.index("fast")
        last_fast_idx = len(lap_roles) - 1 - list(reversed(lap_roles)).index("fast")

        phases = []
        # ① ウォーミングアップ
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
                "desc": f"最初の **{wu_dist:.0f}km** は無理をせず平均 **{seconds_to_pace_str(wu_avg_pace)}/km**（心拍 {int(round(wu_avg_hr))} bpm）でゆっくり走行。徐々に心拍を上げて筋肉を温める理想的なアップです。",
            })

        # ② 疾走 & つなぎ
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
                    "desc": f"一気にギアを上げ **{l['pace_str']}/km** まで急加速（平均心拍 **{l['avg_hr']} bpm**）。乳酸閾値（LT）を超える強い刺激を注入。",
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
                    "desc": f"**{l['pace_str']}/km** まで意図的にペースを落とし、呼吸と筋疲労を整えながら次の疾走に備えるつなぎジョグ。",
                })

        # ③ クールダウン
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
            f"最初の{first_fast_idx}kmをウォーミングアップとしてゆっくり走った後、"
            f"**「1km早めに走る ＋ 1kmゆっくり走る」緩急走を{fast_count}セット** 行った高強度トレーニングです。"
            f"単調なジョグにとどまらず、心肺と速筋に強烈な刺激を入れてレース本番のペース切り替え力・粘りを養う非常に実戦的な構成となっています。"
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

    # B. ビルドアップ走判定
    half = len(valid_laps) // 2
    first_half_avg = sum(paces[:half]) / half
    second_half_avg = sum(paces[half:]) / (len(valid_laps) - half)
    if first_half_avg - second_half_avg > 18:
        for i, l in enumerate(valid_laps):
            if i < half:
                l["role_tag"] = "前半巡航"
                l["role_badge"] = "bg-slate-800 text-slate-300 border-slate-700"
            else:
                l["role_tag"] = "後半加速"
                l["role_badge"] = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"

        return {
            "type": "ビルドアップ走",
            "badge": "📈 ビルドアップ走",
            "badge_color": "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
            "summary_title": f"【ビルドアップ走】前半 {seconds_to_pace_str(first_half_avg)} → 後半 {seconds_to_pace_str(second_half_avg)}/km",
            "summary_desc": f"前半（{seconds_to_pace_str(first_half_avg)}/km）から後半（{seconds_to_pace_str(second_half_avg)}/km）にかけて段階的にペースを引き上げるビルドアップ走です。余力を残しながら終盤に追い込む理想的なペース配分ができています。",
            "phases": [],
            "is_interval": False,
        }

    # C. イーブンペース持続走
    for l in valid_laps:
        l["role_tag"] = "巡航"
        l["role_badge"] = "bg-slate-800 text-slate-400 border-slate-700"

    return {
        "type": "持続走 (ペース走)",
        "badge": "⚖️ イーブンペース走",
        "badge_color": "bg-slate-800 text-slate-300 border-slate-700",
        "summary_title": f"【ペース走】平均 {seconds_to_pace_str(overall_avg_pace)}/km 安定巡航",
        "summary_desc": f"全行程を通してペースのばらつきが小さく、一定のピッチと有酸素リズムを保って走り切った安定したトレーニングです。",
        "phases": [],
        "is_interval": False,
    }


def calculate_activity_insights(
    df: pd.DataFrame,
    fit_dict: Optional[Dict[str, Any]] = None,
    hr_params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """全アクティビティに対して詳細な「評価」「分析」「次回おすすめとリカバリー提案」データを生成"""
    insights_list = []
    total_runs = len(df)
    if fit_dict is None:
        fit_dict = {}

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

        # 5. VDOT スコアの算出 (ダニエルズ式)
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

        # 6. 分析結果を踏まえた多角評価（忖度なしの厳格アスリートコーチング）
        # 目標: 10km 50分 (TARGET_PACE_SEC)
        gap_sec = pace_sec - TARGET_PACE_SEC
        gap_pace_str = f"{gap_sec:+.0f}秒/km" if pace_sec > 0 else "--"

        # サブ50目標ランク判定
        if pace_sec <= 0:
            target_status = {"rank": "-", "label": "計測なし", "badge_color": "bg-slate-800 text-slate-400 border-slate-700"}
        elif pace_sec <= TARGET_PACE_SEC:
            target_status = {"rank": "S", "label": "50分ペース達成 (5:00/km以内)", "badge_color": "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"}
        elif pace_sec <= TARGET_PACE_SEC + 15.0:
            target_status = {"rank": "A", "label": f"サブ50射程圏内 (+{int(round(gap_sec))}秒/km遅れ)", "badge_color": "bg-teal-500/20 text-teal-300 border-teal-500/40"}
        elif pace_sec <= TARGET_PACE_SEC + 35.0:
            target_status = {"rank": "B", "label": f"ペース改善途上 (+{int(round(gap_sec))}秒/km遅れ)", "badge_color": "bg-amber-500/20 text-amber-300 border-amber-500/40"}
        elif pace_sec <= TARGET_PACE_SEC + 60.0:
            target_status = {"rank": "C", "label": f"基礎スタミナ不足 (+{int(round(gap_sec))}秒/km遅れ)", "badge_color": "bg-orange-500/20 text-orange-300 border-orange-500/40"}
        else:
            target_status = {"rank": "D", "label": f"有酸素土台作り段階 (+{int(round(gap_sec))}秒超/km遅れ)", "badge_color": "bg-rose-500/20 text-rose-300 border-rose-500/40"}

        # バッジ付与
        badges = []
        if pace_sec <= best_pace_sec + 3 or (workout_structure.get("is_interval") and workout_structure.get("best_fast_pace_sec", 999) <= best_pace_sec):
            badges.append({"name": "最速ペース更新", "icon": "⚡", "type": "gold"})
        if dist >= longest_dist - 0.1:
            badges.append({"name": "最長走破", "icon": "🏃", "type": "indigo"})
        if act_vdot >= 42.0:
            badges.append({"name": f"高VDOT ({act_vdot:.1f})", "icon": "🎖️", "type": "emerald"})
        if cadence >= 174:
            badges.append({"name": f"理想ピッチ ({cadence}spm)", "icon": "🎯", "type": "teal"})
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

        # --- ▲ 容赦ない反省点・ボトルネック (Critical Bottlenecks) の厳格抽出 ---
        critical_bottlenecks = []
        is_decay = series_analysis.get("split_type") == "ポジティブスプリット"
        hr_drift_val = series_analysis.get("hr_diff", 0.0)
        decoupling_pct = series_analysis.get("decoupling_pct", 0.0)

        # 1. 失速・タレ
        if is_decay:
            speed_drop = abs(series_analysis.get("speed_diff_pct", 0.0))
            critical_bottlenecks.append(
                f"**後半のタレ・失速（{speed_drop:.1f}% 減速）**: 前半平均 {series_analysis.get('first_half_speed')} km/h から後半 {series_analysis.get('second_half_speed')} km/h へ失速。"
                "序盤の突っ込みすぎ、または後半を押し切る脚筋力・乳酸耐性がまだ不足しています。"
            )

        # 2. 有酸素デカップリング（スタミナ枯渇）
        if decoupling_pct > 8.0:
            critical_bottlenecks.append(
                f"**重度の有酸素デカップリング（後半 {decoupling_pct:+.1f}% 効率低下）**: 後半にかけて心肺とペースのバランスが崩壊。"
                "前半の巡航速度に対して有酸素スタミナが持たず、心肺負担がオーバーフローした証拠です（基準値5%以内）。"
            )
        elif decoupling_pct > 5.0 and dist >= 4.0:
            critical_bottlenecks.append(
                f"**有酸素デカップリング発生（後半 {decoupling_pct:+.1f}% 効率低下）**: 許容範囲（5%以内）を超えて後半に心拍が上昇。"
                "同じペースを維持するために心拍数を余計に消費しており、Zone 2 での有酸素土台の走り込みが不可欠です。"
            )
        elif hr_drift_val >= 8:
            critical_bottlenecks.append(
                f"**顕著な心拍ドリフト（後半 +{int(round(hr_drift_val))} bpm 急上昇）**: 後半にかけて心肺負荷が跳ね上がっています。"
                "同じ出力を保てず心肺が悲鳴を上げており、有酸素の器（毛細血管網・心拍出量）が不足している証拠です。"
            )

        # 3. 低ピッチ・腰落ち
        if cadence < 168 and cadence > 0:
            critical_bottlenecks.append(
                f"**低ピッチ・オーバーストライド ({cadence} spm)**: 平均ピッチが170未満と回転数が少なすぎます。"
                "足先で突っ張るブレーキ着地になり、膝や腰への負担を増やしています。174〜180 spm を目指してください。"
            )

        # 4. 変化走でのスピード不足
        if workout_structure.get("is_interval"):
            best_fast = workout_structure.get("best_fast_pace_sec", 999)
            if best_fast > TARGET_PACE_SEC:
                best_f_pace = seconds_to_pace_str(best_fast)
                critical_bottlenecks.append(
                    f"**疾走スピードの不足（最速 {best_f_pace}/km）**: 変化走の疾走ラップを行ったものの、目標の10km本番ペース（5:00/km）に届いていません。"
                    "短い距離でもキロ5分を切る絶対スピードの引き上げが急務です。"
                )

        # 5. 巡航ペースの大幅遅れ (LSD走以外)
        if not workout_structure.get("is_interval") and not is_lsd and gap_sec > 30 and dist >= 5.0:
            critical_bottlenecks.append(
                f"**目標ペース（5:00/km）から大幅乖離（+{int(round(gap_sec))}秒/km）**: 巡航スピードが50分目標から大きく離れています。"
                "5:15〜5:25/km でのLTテンポ走（4〜6km）を取り入れ、目標速度に対する耐性を養う必要があります。"
            )

        # 6. ジョグなのに心拍高すぎ
        if pace_sec >= 360 and avg_hr >= 162:
            critical_bottlenecks.append(
                f"**高心拍による疲労残り（平均 {avg_hr} bpm）**: 6分超のゆっくりペースに対して心拍数が高止まりしています。"
                "Zone 2（135〜148 bpm）でリラックスして走れておらず、無駄な疲労を蓄積させています。"
            )

        # 7. 歩幅不足
        if stride < 0.95 and stride > 0 and pace_sec > 340 and not is_lsd:
            critical_bottlenecks.append(
                f"**歩幅不足（平均 {stride:.2f} m）**: 地面を真後ろに押せておらず、ピッチだけで刻むちょこちょこ走りになっています。"
                "体幹の前傾を使って骨盤から脚を振り出す意識が必要です。"
            )

        if not critical_bottlenecks:
            if is_lsd:
                critical_bottlenecks.append(
                    "**長時間の脚筋疲労に留意**: ペース・心拍コントロールは完璧ですが、2時間におよぶ着地衝撃により関節や腱に深部疲労が蓄積しています。無理な連日走を避け、十分な休息を確保してください。"
                )
            else:
                critical_bottlenecks.append(
                    "**現状維持の打破**: ペースと心拍のバランスは良好ですが、目標（5:00/km）に向けてさらに距離を伸ばすか、設定ペースを5秒引き上げる挑戦が必要です。"
                )

        # --- ◎ 客観的な収穫・強み (Strong Points) の抽出 ---
        strong_points = []
        if is_lsd:
            strong_points.append(
                f"**低心拍ゾーンの徹底維持（平均 {avg_hr} bpm）**: 長時間走の中で心拍をZone 1〜Zone 2に完璧にコントロールし、毛細血管網の新生と脂質代謝効率を飛躍的に強化。"
            )
            strong_points.append(
                f"**{dist:.1f}km・2時間の接地耐久性**: 2時間以上の長時間接地衝撃に耐え、後半も大崩れせずに完走した高い脚筋スタミナを発揮。"
            )
        elif workout_structure.get("is_interval") and workout_structure.get("best_fast_pace_sec", 999) < TARGET_PACE_SEC:
            best_f_pace = seconds_to_pace_str(workout_structure.get("best_fast_pace_sec"))
            strong_points.append(
                f"**キロ5分を切るスピード出力（最速 {best_f_pace}/km）**: 疾走ラップで目標を上回るトップスピードを叩き出し、50分切りに必要なスピード自体のポテンシャルを実証。"
            )
        elif not workout_structure.get("is_interval") and pace_sec <= TARGET_PACE_SEC:
            strong_points.append(
                f"**目標ペース（5:00/km以内）での巡航完遂**: 平均ペース **{pace_str}/km** で走り切り、10km 50分切りに向けた実戦力を発揮。"
            )

        if sub50_sustained_km >= 3.0:
            strong_points.append(
                f"**サブ50ペース連続維持（{sub50_sustained_km:.1f}km）**: キロ5:00以内を連続 **{sub50_sustained_km:.1f}km** キープし、50分切りに必要な持続力を前進。"
            )

        if decoupling_pct <= 3.0 and dist >= 4.5:
            strong_points.append(
                f"**優れた有酸素エコノミー（デカップリング率 {decoupling_pct:+.1f}%）**: 後半も心拍と速度の比率が崩れず、目標ペースを押し切る十分なスタミナベースを発揮。"
            )

        if act_vdot >= 41.0:
            strong_points.append(
                f"**高水準の走力指数（VDOT {act_vdot:.1f}）**: ダニエルズ式走力指数でサブ50射程圏の有酸素エンジンを確認。"
            )

        if cadence >= 174:
            strong_points.append(
                f"**理想的なハイピッチ維持 ({cadence} spm)**: 安定した足回転をキープし、上下動を抑えた着地コントロールが定着。"
            )

        if series_analysis.get("split_type") == "ネガティブスプリット":
            strong_points.append(
                f"**後半のビルドアップ（+{series_analysis.get('speed_diff_pct')}%）**: 終盤までフォームを崩さず、力強くペースアップしてフィニッシュ。"
            )

        if dist >= 9.5:
            strong_points.append(
                f"**10km距離走破の筋持久力**: **{dist:.2f} km** を歩かずに完走し、レース本番に必要な脚筋力と腱の衝撃耐性を強化。"
            )

        if hr_drift_val < 5.0 and dist >= 5.0 and not any("有酸素" in s for s in strong_points):
            strong_points.append(
                "**心肺リズムの安定**: 後半の心拍ドリフトを抑え、一定の有酸素出力を維持。"
            )

        if not strong_points:
            strong_points.append(
                f"**トレーニングの確実な消化**: {dist:.1f}km を走り切り、日々の有酸素刺激を途切れさせずに継続。"
            )

        # --- 【総括 (Overall Verdict)】忖度なしの現在地診断 ---
        if is_lsd:
            overall_verdict = (
                f"**【理想的な有酸素ベース構築】走行距離 {dist:.1f}km を平均心拍 {avg_hr} bpm で完走。** "
                f"起伏のあるタフなコースでも心拍急上昇をコントロールし、約2時間の長時間接地を達成。"
                "フルマラソンやサブ50の後半を粘り抜くための『有酸素の器（毛細血管網・脂質代謝）』を確実に広げる完璧なLSDセッションです。"
            )
        elif workout_structure.get("is_interval"):
            fast_c = workout_structure.get("fast_count", 2)
            best_f_str = seconds_to_pace_str(workout_structure.get("best_fast_pace_sec", pace_sec))
            best_fast_val = workout_structure.get("best_fast_pace_sec", 999)
            if best_fast_val < TARGET_PACE_SEC:
                overall_verdict = (
                    f"**【スピード出力は合格、課題は持続力】** 1km疾走で **{best_f_str}/km** を叩き出し、"
                    "キロ5分を切る脚力があることを実証。ただし最大心拍 **{max_hr} bpm** まで追い込まれており、"
                    "これを10km押し切るには乳酸閾値（LT）の底上げと有酸素ベースの強化が絶対条件です。"
                )
            else:
                overall_verdict = (
                    f"**【スピード不足】疾走区間でキロ5分切れず。** 緩急をつけた構成ですが、疾走の最速が **{best_f_str}/km** にとどまり、"
                    "10km 50分目標（5:00/km）に対するスピード余力を生み出せていません。まずは単発で4分台を刻む絶対スピードの強化が必要です。"
                )
        elif workout_structure.get("type") == "ビルドアップ走":
            if is_decay:
                overall_verdict = (
                    f"**【ビルドアップ失敗・後半失速】** 後半加速を狙ったものの、終盤に脚が止まり減速（平均 {pace_str}/km）。"
                    f"目標（5:00/km）から **{int(round(gap_sec))}秒/km** 遅れており、余力配分と筋持久力の見直しが急務です。"
                )
            else:
                overall_verdict = (
                    f"**【余力管理は良好、巡航スピードの底上げが急務】** 後半にかけてビルドアップ（後半加速）を達成。"
                    f"ただし全体の平均ペースは **{pace_str}/km**（目標まであと -{int(round(gap_sec))}秒/km）。"
                    "ペース配分の技術は身についているため、巡航全体のギアを一段引き上げる練習が必要です。"
                )
        elif dist >= 8.0:
            if hr_drift_val >= 8 or is_decay or decoupling_pct > 6.0:
                overall_verdict = (
                    f"**【スタミナ不足露呈】10km走破も後半に心拍急上昇・失速。** 距離は走破したものの、"
                    f"デカップリング率 **{decoupling_pct:+.1f}%**、後半心拍が **+{int(round(hr_drift_val))} bpm** ドリフト。"
                    "50分切り（5:00/km）で10kmを押し切るための有酸素の器（毛細血管網）が明らかに不足しています。"
                )
            else:
                overall_verdict = (
                    f"**【安定巡航もスピード不足】** ペースと心拍の乱れは小さくまとまりましたが、平均 **{pace_str}/km** は"
                    f"目標（5:00/km）から **{int(round(gap_sec))}秒/km 遅れ**。このペースで満足せず、5:15〜5:25/km でのLT走に挑む段階です。"
                )
        else:
            overall_verdict = (
                f"**【短距離セッション】走行距離 {dist:.1f}km、平均 {pace_str}/km。** "
                f"目標（5:00/km）に対し {gap_pace_str}。疲労抜きのジョグか、スピード練習か、トレーニングの目的意識をより明確にして臨む必要があります。"
            )

        # --- 【🔥 次回への是正アクション (Actionable Focus)】 ---
        if is_lsd:
            actionable_focus = "次回は【48時間の休養または軽めの疲労抜きウォーク/超スロージョグ】で脚筋の超回復を最優先。脚の張りが抜けたらLT走へステップアップすること。"
        elif decoupling_pct > 8.0 or hr_drift_val >= 8 or (pace_sec >= 360 and avg_hr >= 162):
            actionable_focus = "次回は【有酸素土台の再構築：心拍上限 145 bpm を死守】。ペースを 6:20〜6:50/km に落としてでも毛細血管を育てる超スロージョグに徹すること。"
        elif workout_structure.get("is_interval") and workout_structure.get("best_fast_pace_sec", 999) > TARGET_PACE_SEC:
            actionable_focus = "次回は【4:45〜4:55/km の1km疾走×3本】に挑戦し、5:00/km を楽に感じるスピード余裕度を身体に叩き込むこと。"
        elif is_decay:
            actionable_focus = "次回は【最初の2kmを設定より15秒遅く入る】。オーバーペースを抑え、ラスト2kmで必ず最速ラップを刻むネガティブスプリットを完遂すること。"
        elif cadence < 168 and cadence > 0:
            actionable_focus = "次回は【ピッチ 176 spm を維持】。骨盤の真下に着地し、上下動を抑えた軽快な足回転を徹底すること。"
        else:
            actionable_focus = "次回は【5:10〜5:20/km のLTテンポ走 (5km)】に挑戦し、10km 50分（5:00/km）への巡航耐性を直接引き上げること。"

        # 分析テキスト
        analysis_body = {
            "summary": f"走行距離 **{dist:.2f} km** を平均ペース **{pace_str}/km** で完走。運動強度は【**{hr_zone['name']}（{hr_zone['intensity']}）**】に該当します。",
            "workout_structure": workout_structure,
            "phase_early": series_analysis["phase_early"],
            "phase_mid": series_analysis["phase_mid"],
            "phase_late": series_analysis["phase_late"],
            "drift_text": series_analysis["drift_text"],
            "decoupling_desc": series_analysis["decoupling_desc"],
            "cadence_eval": f"平均ピッチは **{cadence} spm**（最高 {row['max_cadence']} spm）。接地時間が短く、着地衝撃を分散できています。" if cadence >= 172 else f"平均ピッチ **{cadence} spm**。骨盤の真下に着地する意識でピッチを172〜176前後に高めるとさらに省エネになります。",
        }

        # 次回おすすめメニュー & リカバリー提案
        if is_lsd:
            next_menu_title = "完全休養 または 30分 疲労抜きアクティブリカバリー（散歩・ストレッチ）"
            next_menu_desc = (
                f"今回は **{dist:.1f}km・約2時間のLSD** を低心拍で完璧に完遂しました。"
                "心肺への負担は穏やかですが、2時間におよぶ接地衝撃により脚の深部筋肉や関節・腱には強い疲労が蓄積しています。"
                "次回は **完全休養** または **軽い散歩・フォームローラーでの筋膜リリース** に留め、48時間しっかりと筋線維を超回復させましょう。"
            )
            form_advice = "スピードは完全に意識せず、脱力して手足をリラックスさせ、血流を促すことだけに集中してください。"
            recovery_hours = "48時間"
            recovery_tips = "ふくらはぎ・ハムストリングスのフォームローラーほぐし、温冷交代浴、クエン酸とたんぱく質の積極的摂取を推奨します。"
        elif workout_structure.get("is_interval"):
            fast_c = workout_structure.get("fast_count", 2)
            next_menu_title = "完全休養 または 4km 超スロージョグ (アクティブリカバリー)"
            next_menu_desc = (
                f"今回は **1km疾走×{fast_c}本のファルトレク（変化走）** で最大心拍 **{max_hr} bpm** まで追い込んだ高強度トレーニングでした。"
                "速筋線維の微細損傷や乳酸疲労を抜くため、次回は **心拍数 130〜140 bpm を超えない極めてゆっくりとしたリカバリージョグ**、"
                "または完全休養とし、超回復（筋力・心肺機能の向上）を促進させましょう。"
            )
            form_advice = "スピードは完全に意識せず、脱力して手足をリラックスさせ、血流を促すことだけに集中してください。"
            recovery_hours = "48時間"
            recovery_tips = "ふくらはぎ・ハムストリングスのフォームローラーほぐし、温冷交代浴、クエン酸とたんぱく質の積極的摂取を推奨します。"
        elif avg_hr >= 172 or dist >= 10.0:
            next_menu_title = "アクティブリカバリー または 5km イージージョグ"
            next_menu_desc = (
                "今回は心拍数170bpm超の高強度LT走でした。筋肉・心肺の疲労を抜いて毛細血管の新生を促すため、"
                "次回は **心拍数 135〜145 bpm 前後** を上限とした **ゆっくりとしたイージージョグ（6:15〜6:30/km、4〜5km）** を強く推奨します。"
            )
            form_advice = "無理にスピードを出さず、脱力して腕を自然に振り、足裏全体で柔らかく着地する感覚を意識してください。"
            recovery_hours = "36〜48時間"
            recovery_tips = "ふくらはぎと股関節の入念なストレッチ、温冷交代浴、水分・たんぱく質の補給を重視してください。"
        elif dist <= 5.0 and pace_sec > 330:
            next_menu_title = "ステップアップ走 (6〜7km) または ビルドアップ走"
            next_menu_desc = (
                "疲労度は比較的穏やかです。次回は **距離を1〜2km伸ばす（6〜7km）** か、"
                "ラスト1kmだけ気持ちよくペースアップする **ビルドアップ走** に挑戦すると、持久力とスピード感覚が一段引き上がります。"
            )
            form_advice = "現在の安定したピッチ（174spm前後）を崩さずに、体幹の前傾を使って自然に推進力を得るフォームを意識しましょう。"
            recovery_hours = "24〜36時間"
            recovery_tips = "足裏とアキレス腱周りを軽くほぐし、翌日または翌々日にはリフレッシュして走れる状態を整えましょう。"
        else:
            next_menu_title = "テンポ走 (6km) または 8〜10km ペース走"
            next_menu_desc = (
                "バランスの良いトレーニングができています。次回は **現在の安定したピッチを維持したまま、"
                "同じペースで少し距離を延ばすペース走** を行うと、フルマラソン・ハーフマラソンに向けた確実な脚作りにつながります。"
            )
            form_advice = "後半に疲れが出てきたときほど、背筋を伸ばして目線を遠くに置き、骨盤から脚を運ぶ意識を持ちましょう。"
            recovery_hours = "24〜48時間"
            recovery_tips = "入浴後の股関節・ハムストリングスのモビリティストレッチを行い、翌日への疲労持ち越しを防ぎましょう。"

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
            "max_cadence": row["max_cadence"],
            "stride": stride,
            "calories": row["calories"],
            "elevation_gain": elevation,
            "aei": round(aei, 2),
            "speed_kmh": round(speed_kmh, 1),
            "distance_series": distance_series,
            # ② 評価 (Evaluation: 忖度なしの厳格アスリート判定)
            "evaluation": {
                "overall_verdict": overall_verdict,
                "overall_summary": overall_verdict,  # 互換性維持
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
            },
            # ① 分析 (Analysis)
            "analysis": analysis_body,
            # ③ 次回おすすめとリカバリー提案 (Recommendation)
            "recommendation": {
                "menu_title": next_menu_title,
                "menu_desc": next_menu_desc,
                "form_advice": form_advice,
                "recovery_hours": recovery_hours,
                "recovery_tips": recovery_tips,
            },
        }
        insights_list.append(item)

    return insights_list
