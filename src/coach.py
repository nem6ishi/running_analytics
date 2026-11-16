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
            "split_type": "-",
            "split_badge": "AI未分析",
            "split_desc": "AIコーチング分析待ち。",
            "phase_early": "-",
            "phase_mid": "-",
            "phase_late": "-",
            "drift_text": "AIコーチング分析待ち。",
            "decoupling_pct": 0.0,
            "decoupling_grade": "-",
            "decoupling_status": "AI未分析",
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

    # 有酸素デカップリング (Aerobic Decoupling: Pw:Hr / Pa:Hr)
    # EF (Efficiency Factor) = 速度(km/h) / 心拍数(bpm)
    ef_first = (first_half_speed / first_half_hr) if first_half_hr > 0 else 0.0
    ef_second = (second_half_speed / second_half_hr) if second_half_hr > 0 else 0.0

    if ef_first > 0:
        decoupling_pct = round(((ef_first - ef_second) / ef_first) * 100.0, 1)
    else:
        decoupling_pct = 0.0

    hr_diff = second_half_hr - first_half_hr

    return {
        "split_type": "-",
        "split_badge": "AI未分析",
        "split_desc": f"前半平均 {first_half_speed:.1f} km/h → 後半平均 {second_half_speed:.1f} km/h（差 {speed_diff_pct:+.1f}%）",
        "speed_diff_pct": round(speed_diff_pct, 1),
        "hr_diff": round(hr_diff, 1),
        "first_half_speed": round(first_half_speed, 1),
        "second_half_speed": round(second_half_speed, 1),
        "phase_early": "-",
        "phase_mid": "-",
        "phase_late": "-",
        "drift_text": f"前後半の心拍差: {hr_diff:+.1f} bpm（AIコーチング分析待ち）",
        "decoupling_pct": decoupling_pct,
        "decoupling_grade": "-",
        "decoupling_status": "AI未分析",
        "decoupling_badge": "bg-slate-800 text-slate-400 border-slate-700",
        "decoupling_desc": f"デカップリング率 {decoupling_pct:+.1f}%（AIコーチング分析待ち）",
        "running_cadence": running_cadence,
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

        # 4. 時系列グラフの分析（固定ルールによる種別自動判定は行わない）
        series_analysis = analyze_time_series(distance_series, dist)
        running_cadence = series_analysis.get("running_cadence") or cadence

        # 5. 【AIコーチング優先】ai_coaching.json に個別評価が存在する場合は最優先で適用
        note = ai_notes.get(dt_full) or ai_notes.get(date_str)
        if not note:
            for k in ai_notes:
                if k.startswith(date_str):
                    note = ai_notes[k]
                    break

        if note and "workout_structure" in note:
            workout_structure = dict(note["workout_structure"])
        else:
            workout_structure = {
                "type": "ランニング (AI未分析)",
                "badge": "🏃 ランニング (AI未分析)",
                "badge_color": "bg-slate-800 text-slate-300 border-slate-700",
                "summary_title": f"{dist:.2f}km ランニング ({pace_str}/km)",
                "summary_desc": f"走行距離 {dist:.2f}km、平均ペース {pace_str}/km、平均心拍 {avg_hr} bpm（AIコーチング分析待ち）。",
                "phases": [],
                "is_interval": False,
                "is_lsd": False,
            }

        is_lsd = workout_structure.get("is_lsd", False)

        # 6. VDOT スコアの算出 (ダニエルズ式: 意図的な低心拍LSDはタイムからの単純算出対象外とする)
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

        # ターゲット差分の算出
        gap_sec = pace_sec - TARGET_PACE_SEC

        # AIコーチング note から評価項目を直接取得
        if note and "evaluation" in note:
            ai_eval = note["evaluation"]
            overall_verdict = ai_eval.get("overall_verdict", f"走行距離 {dist:.2f}km を平均 {pace_str}/km で完走。")
            target_status = ai_eval.get("target_status", {
                "rank": "A",
                "label": f"有酸素巡航 ({pace_str}/km)",
                "badge_color": "bg-teal-500/20 text-teal-300 border-teal-500/40"
            })
            gap_pace_str = ai_eval.get("target_gap_str", f"{gap_sec:+.0f}秒/km" if pace_sec > 0 else "--")
            critical_bottlenecks = ai_eval.get("critical_bottlenecks", [])
            strong_points = ai_eval.get("strong_points", [])
            actionable_focus = ai_eval.get("actionable_focus", "コンディションに合わせて次回メニューを実施すること。")
            if "split_badge" in ai_eval:
                series_analysis["split_badge"] = ai_eval["split_badge"]
            if "decoupling_desc" in ai_eval:
                series_analysis["decoupling_desc"] = ai_eval["decoupling_desc"]
        else:
            # ai_coaching.json に未登録の場合は固定ルールによる評価を生成しない
            overall_verdict = f"走行距離 **{dist:.2f}km**（平均 **{pace_str}/km**・平均心拍 {avg_hr} bpm）の計測データ。AIコーチング分析待ちです。"
            target_status = {
                "rank": "-",
                "label": "AI未分析",
                "badge_color": "bg-slate-800 text-slate-300 border-slate-700"
            }
            gap_pace_str = f"{gap_sec:+.0f}秒/km" if pace_sec > 0 else "--"
            critical_bottlenecks = []
            strong_points = []
            actionable_focus = "AIコーチング分析待ち。"

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

        # 分析テキスト
        cadence_eval = (
            f"実走行時の平均ピッチは **{running_cadence} spm**（信号・ウォーク込み全体平均 {cadence} spm、最高 {row['max_cadence']} spm）。"
            if running_cadence != cadence and cadence < 160
            else f"平均ピッチは **{cadence} spm**（最高 {row['max_cadence']} spm）。"
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
        if note and "recommendation" in note:
            ai_rec = note["recommendation"]
            next_menu_title = ai_rec.get("menu_title", "コンディション確認ジョグ")
            next_menu_desc = ai_rec.get("menu_desc", "疲労を抜いて次のポイント練習に備えます。")
            form_advice = ai_rec.get("form_advice", "骨盤の真下に柔らかく着地するフォームを意識しましょう。")
            recovery_hours = ai_rec.get("recovery_hours", "24〜48時間")
            recovery_tips = ai_rec.get("recovery_tips", "入浴と十分な睡眠で身体を休めてください。")
        else:
            next_menu_title = "コンディション確認ジョグ"
            next_menu_desc = "疲労を抜いて次のポイント練習に備えます。"
            form_advice = "骨盤の真下に柔らかく着地するフォームを意識しましょう。"
            recovery_hours = "24〜48時間"
            recovery_tips = "入浴と十分な睡眠で身体を休めてください。"

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
