import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from .parser import seconds_to_pace_str, seconds_to_time_str
from .fit_parser import generate_estimated_series


HR_MAX = 195  # データセット全体および一般的なランナーの基準最大心拍数推定


def get_hr_zone(avg_hr: float) -> Dict[str, str]:
    """平均心拍数から心拍ゾーン・強度を判定"""
    if avg_hr <= 0:
        return {
            "zone": "Zone 0",
            "name": "計測なし",
            "intensity": "不明",
            "color": "gray",
            "bg_color": "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300",
            "desc": "心拍データがありません",
        }

    pct = (avg_hr / HR_MAX) * 100
    if pct < 65:
        return {
            "zone": "Zone 1",
            "name": "アクティブリカバリー",
            "intensity": "超低強度 (回復)",
            "color": "emerald",
            "bg_color": "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
            "desc": "疲労抜き・毛細血管の発達を促す回復ペース",
        }
    elif pct < 76:
        return {
            "zone": "Zone 2",
            "name": "基礎有酸素 (イージー)",
            "intensity": "低強度 (脂肪燃焼・持久力基礎)",
            "color": "blue",
            "bg_color": "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
            "desc": "スタミナの土台を築く最も重要なおしゃべりペース",
        }
    elif pct < 86:
        return {
            "zone": "Zone 3",
            "name": "テンポ走 (有酸素強化)",
            "intensity": "中強度 (持久力向上)",
            "color": "amber",
            "bg_color": "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
            "desc": "少し息が上がるが維持できるマラソンペース帯",
        }
    elif pct < 93:
        return {
            "zone": "Zone 4",
            "name": "乳酸閾値 (LT / しきい値)",
            "intensity": "高強度 (スピード持久力)",
            "color": "orange",
            "bg_color": "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
            "desc": "乳酸が溜まり始めるギリギリの粘り・勝負ペース",
        }
    else:
        return {
            "zone": "Zone 5",
            "name": "無酸素 / VO2max",
            "intensity": "最高強度 (最大酸素摂取量)",
            "color": "rose",
            "bg_color": "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
            "desc": "レース終盤やインターバル走のスプリント負荷",
        }


def analyze_time_series(series: Dict[str, Any], dist_km: float) -> Dict[str, Any]:
    """折れ線グラフの時系列データから前半・後半・スパートの特徴を抽出"""
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
        split_desc = f"前半平均 {first_half_speed:.1f} km/h に対し、後半平均 {second_half_speed:.1f} km/h と **+{speed_diff_pct:.1f}% ペースアップ** しています。理想的な余力配分とビルドアップができています。"
    elif speed_diff_pct < -2.5:
        split_type = "ポジティブスプリット"
        split_badge = "⚡ ポジティブスプリット (先行逃げ切り)"
        split_desc = f"前半平均 {first_half_speed:.1f} km/h から後半 {second_half_speed:.1f} km/h に推移。序盤から積極的に攻めたスピード練習となっています。"
    else:
        split_type = "イーブンペース"
        split_badge = "⚖️ イーブンペース (高精度巡航)"
        split_desc = f"前半（{first_half_speed:.1f} km/h）と後半（{second_half_speed:.1f} km/h）の差が極めて小さく、精密なペース配分ができています。"

    # 心拍ドリフト
    first_half_hr = float(np.mean(hrs[:half])) if hrs else 0
    second_half_hr = float(np.mean(hrs[half:])) if hrs else 0
    hr_diff = second_half_hr - first_half_hr

    if hr_diff >= 8:
        drift_text = f"後半に心拍数が約 **+{int(round(hr_diff))} bpm 上昇**（心拍ドリフト）。筋疲労や気温・脱水により心肺負荷が増加しています。水分補給とイージージョグでの回復が重要です。"
    elif hr_diff >= 3:
        drift_text = f"後半の心拍上昇は **+{int(round(hr_diff))} bpm** と適正範囲内です。持久力がしっかりと維持できています。"
    else:
        drift_text = "走行全般にわたって心拍数が極めて安定しており、高い有酸素エコノミーを発揮しています。"

    # 3フェーズ解説
    start_speed = speeds[0]
    early_hr = hrs[int(n * 0.2)] if hrs else 0
    max_s = max(speeds)
    max_h = max(hrs) if hrs else 0

    phase_early = f"**序盤 (0〜{dist_km * 0.25:.1f}km)**: ウォーミングアップから心拍数 {early_hr} bpm へスムーズに上昇し、安定したリズムを構築。"
    phase_mid = f"**中盤 ({dist_km * 0.25:.1f}〜{dist_km * 0.75:.1f}km)**: ピッチを安定させ、巡航速度をブレなくキープ。"
    phase_late = f"**終盤 ({dist_km * 0.75:.1f}〜{dist_km:.1f}km)**: ラストスパートで最高速度 **{max_s:.1f} km/h** に達し、最大心拍 **{max_h} bpm** でゴール。"

    return {
        "split_type": split_type,
        "split_badge": split_badge,
        "split_desc": split_desc,
        "phase_early": phase_early,
        "phase_mid": phase_mid,
        "phase_late": phase_late,
        "drift_text": drift_text,
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

    # 1. 疾走（fast）ラップの判定: 全体平均より12秒以上速く、かつ前後のラップより18秒以上速い
    lap_roles = []
    for i, l in enumerate(valid_laps):
        p = l["pace_sec"]
        prev_p = valid_laps[i - 1]["pace_sec"] if i > 0 else p
        next_p = valid_laps[i + 1]["pace_sec"] if i < len(valid_laps) - 1 else p

        is_fast = (p < overall_avg_pace - 12) and (prev_p - p >= 18 or next_p - p >= 18)
        lap_roles.append("fast" if is_fast else "base")

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


def calculate_activity_insights(df: pd.DataFrame, fit_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """全アクティビティに対して詳細な「評価」「分析」「次回おすすめとリカバリー提案」データを生成"""
    insights_list = []
    total_runs = len(df)
    if fit_dict is None:
        fit_dict = {}

    best_pace_sec = df["avg_pace_sec"].min()
    longest_dist = df["distance_km"].max()

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
        hr_zone = get_hr_zone(avg_hr)

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

        # 5. 分析結果を踏まえた多角評価スコア (0-100) & 判定
        # スピードスコア: 変化走の場合は疾走区間のペースを主軸に評価
        if workout_structure.get("is_interval") and workout_structure.get("best_fast_pace_sec"):
            eval_speed_pace = workout_structure["best_fast_pace_sec"]
            speed_score = max(60.0, min(100.0, 100.0 - (eval_speed_pace - 270) * 0.45))
        else:
            speed_score = max(50.0, min(100.0, 100.0 - (pace_sec - 300) * 0.4))

        endurance_score = max(50.0, min(100.0, 50.0 + (dist * 4.8)))
        cadence_diff = abs(cadence - 176)
        form_score = max(60.0, min(100.0, 100.0 - (cadence_diff * 4.0)))
        aerobic_score = max(50.0, min(100.0, 50.0 + (aei - 5.0) * 28.0))

        # 変化走でメリハリ（ペース差40秒以上）がついている場合、緩急コントロールの加点
        if workout_structure.get("is_interval") and workout_structure.get("pace_contrast_sec", 0) >= 40:
            form_score = min(100.0, form_score + 5.0)

        total_score = round(
            speed_score * 0.3 + endurance_score * 0.25 + aerobic_score * 0.25 + form_score * 0.2
        )
        total_score = max(55, min(99, total_score))

        if total_score >= 90:
            rank = "S"
            rank_class = "from-amber-400 to-yellow-500 text-slate-900"
        elif total_score >= 80:
            rank = "A"
            rank_class = "from-indigo-500 to-purple-600 text-white"
        elif total_score >= 70:
            rank = "B"
            rank_class = "from-teal-500 to-emerald-600 text-white"
        else:
            rank = "C"
            rank_class = "from-slate-500 to-gray-600 text-white"

        # バッジ付与
        badges = []
        if pace_sec <= best_pace_sec + 3 or (workout_structure.get("is_interval") and workout_structure.get("best_fast_pace_sec", 999) <= best_pace_sec):
            badges.append({"name": "最速ペース", "icon": "⚡", "type": "gold"})
        if dist >= longest_dist - 0.1:
            badges.append({"name": "最長走破", "icon": "🏃", "type": "indigo"})
        if cadence >= 175:
            badges.append({"name": "理想ピッチ (175spm+)", "icon": "🎯", "type": "teal"})
        if avg_hr >= 174 or max_hr >= 185:
            badges.append({"name": "高負荷LT・VO2max刺激", "icon": "🔥", "type": "orange"})
        if aei >= 6.4:
            badges.append({"name": "有酸素効率優秀", "icon": "💎", "type": "cyan"})
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

        # 分析結果を踏まえた「総合評価・達成度判定テキスト (conclusion)」
        if workout_structure.get("is_interval"):
            fast_c = workout_structure.get("fast_count", 2)
            best_f_str = seconds_to_pace_str(workout_structure.get("best_fast_pace_sec", pace_sec))
            contrast_sec = int(round(workout_structure.get("pace_contrast_sec", 60)))
            eval_conclusion = (
                f"分析結果の通り、入念なアップから **1km疾走×{fast_c}本（最速 {best_f_str}/km）** へのギアチェンジが極めて鮮やかでした。"
                f"疾走とつなぎの間で約 **{contrast_sec}秒/km** の明確な緩急差をコントロールできており、レース本番の揺さぶりやスパートに耐える心肺・脚力が高いレベルで発揮されています。"
            )
        elif workout_structure.get("type") == "ビルドアップ走":
            eval_conclusion = (
                "分析結果の通り、前半から後半にかけて段階的にペースを引き上げるビルドアップを完遂。"
                "余力を残しながら終盤に追い込む理想的なペース配分ができています。"
            )
        else:
            eval_conclusion = (
                f"分析結果の通り、全区間を通してペースのブレが小さく、一定のピッチ（{cadence}spm）と有酸素リズムを保って走り切った安定度の高い巡航走です。"
            )

        # 評価ポイントリスト
        eval_highlights = [
            f"総合判定 **{rank}ランク（{total_score}点）**。{eval_conclusion}",
            f"ピッチ **{cadence} spm** / 歩幅 **{stride:.2f} m** で、{('安定した効率的リズム' if cadence >= 172 else 'ストライド重視のダイナミックなフォーム')}を維持。",
        ]
        if prev_diff and prev_diff["pace_improved"]:
            eval_highlights.append(f"前回（{prev_diff['date']}）より全体平均ペースが **{abs(int(prev_diff['pace_diff_sec']))}秒/km 向上**。")

        # 分析テキスト
        analysis_body = {
            "summary": f"走行距離 **{dist:.2f} km** を平均ペース **{pace_str}/km** で完走。運動強度は【**{hr_zone['name']}（{hr_zone['intensity']}）**】に該当します。",
            "workout_structure": workout_structure,
            "phase_early": series_analysis["phase_early"],
            "phase_mid": series_analysis["phase_mid"],
            "phase_late": series_analysis["phase_late"],
            "drift_text": series_analysis["drift_text"],
            "cadence_eval": f"平均ピッチは **{cadence} spm**（最高 {row['max_cadence']} spm）。接地時間が短く、着地衝撃を分散できています。" if cadence >= 172 else f"平均ピッチ **{cadence} spm**。骨盤の真下に着地する意識でピッチを172〜176前後に高めるとさらに省エネになります。",
        }

        # 次回おすすめメニュー & リカバリー提案
        if workout_structure.get("is_interval"):
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
            # ② 評価 (Evaluation: 分析結果に基づく総合判定)
            "evaluation": {
                "total_score": total_score,
                "rank": rank,
                "rank_class": rank_class,
                "conclusion": eval_conclusion,
                "radar_scores": {
                    "speed": round(speed_score),
                    "endurance": round(endurance_score),
                    "aerobic": round(aerobic_score),
                    "form": round(form_score),
                },
                "badges": badges,
                "prev_diff": prev_diff,
                "highlights": eval_highlights,
                "split_badge": series_analysis["split_badge"],
            },
            # ② 分析 (Analysis)
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
