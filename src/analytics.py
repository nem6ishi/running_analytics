from typing import Dict, Any, List, Optional
import math
from datetime import datetime, timedelta, date
from pathlib import Path
import pandas as pd
from config import (
    TARGET_DISTANCE_KM,
    TARGET_TIME_SEC,
    TARGET_PACE_SEC,
    TARGET_LABEL,
    HALF_RACE_NAME,
    HALF_RACE_DATE,
    HALF_DISTANCE_KM,
    HALF_TARGET_TIME_SEC,
    HALF_TARGET_PACE_SEC,
    HALF_TARGET_LABEL,
    FULL_RACE_NAME,
    FULL_RACE_DATE,
    FULL_DISTANCE_KM,
    FULL_TARGET_TIME_SEC,
    FULL_TARGET_PACE_SEC,
    FULL_TARGET_LABEL,
    WARMUP_DISTANCE_KM,
)
from .parser import seconds_to_pace_str, seconds_to_time_str
from .coach import calculate_activity_insights
from .vdot import calculate_vdot, get_training_paces, predict_race_times_vdot
from .profile import get_hr_params
from .load import compute_training_load, compute_zone_distribution


def compute_overview_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """全体の累積・平均KPIを計算"""
    total_dist = df["distance_km"].sum()
    total_runs = len(df)
    total_sec = df["duration_sec"].sum()
    total_cal = df["calories"].sum()

    avg_pace_sec = df["avg_pace_sec"].mean()
    avg_hr = df["avg_hr"].mean()
    avg_cadence = df["avg_cadence"].mean()
    avg_stride = df["stride_length_m"].mean()

    best_pace_sec = df["avg_pace_sec"].min()
    max_dist = df["distance_km"].max()

    # 総時間を "○○時間○○分" 形式に
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    total_time_str = f"{hours}時間{minutes}分"

    # 有酸素効率 (速度 / 心拍数 * 100)
    speed_kmh = 3600.0 / df["avg_pace_sec"]
    aei_series = (speed_kmh / df["avg_hr"]) * 100.0
    avg_aei = aei_series.mean()

    # 期間 (YYYY.MM - YYYY.MM)
    start_date = df["datetime"].min().strftime("%Y.%m")
    end_date = df["datetime"].max().strftime("%Y.%m")
    date_range = f"{start_date} - {end_date}"

    return {
        "total_distance_km": round(total_dist, 1),
        "total_runs": total_runs,
        "total_time_str": total_time_str,
        "total_calories": f"{total_cal:,}",
        "avg_pace_str": seconds_to_pace_str(avg_pace_sec),
        "avg_pace_sec": round(avg_pace_sec, 1),
        "avg_pace_min": round(avg_pace_sec / 60.0, 2),
        "avg_hr": round(avg_hr),
        "avg_cadence": round(avg_cadence),
        "avg_stride_m": round(avg_stride, 2),
        "avg_aei": round(avg_aei, 2),
        "best_pace_str": seconds_to_pace_str(best_pace_sec),
        "max_dist_km": round(max_dist, 2),
        "date_range": date_range,
    }


def compute_monthly_stats(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """月別の走行実績を集計"""
    monthly = (
        df.groupby("year_month")
        .agg(
            distance_km=("distance_km", "sum"),
            runs=("distance_km", "count"),
            avg_pace_sec=("avg_pace_sec", "mean"),
            avg_hr=("avg_hr", "mean"),
            calories=("calories", "sum"),
            duration_sec=("duration_sec", "sum"),
        )
        .reset_index()
    )

    monthly_list = []
    for _, row in monthly.iterrows():
        monthly_list.append(
            {
                "month": row["year_month"],
                "distance_km": round(row["distance_km"], 1),
                "runs": int(row["runs"]),
                "avg_pace_str": seconds_to_pace_str(row["avg_pace_sec"]),
                "avg_pace_sec": round(row["avg_pace_sec"], 1),
                "avg_hr": round(row["avg_hr"]),
                "calories": int(row["calories"]),
                "time_str": seconds_to_time_str(int(row["duration_sec"])),
            }
        )
    return monthly_list


def compute_personal_records(df: pd.DataFrame) -> Dict[str, Any]:
    """自己ベスト（PR）記録を抽出"""
    # 1. 最長距離
    max_dist_row = df.loc[df["distance_km"].idxmax()]
    # 2. 最速平均ペース
    best_pace_row = df.loc[df["avg_pace_sec"].idxmin()]
    # 3. 5kmベスト（4.5km〜6.0kmのアクティビティで最速ペース）
    df_5k = df[(df["distance_km"] >= 4.5) & (df["distance_km"] <= 6.0)]
    if not df_5k.empty:
        best_5k_row = df_5k.loc[df_5k["avg_pace_sec"].idxmin()]
        best_5k_time = seconds_to_time_str(int(round(best_5k_row["avg_pace_sec"] * 5.0)))
        best_5k_date = best_5k_row["date_str"]
        best_5k_pace = best_5k_row["pace_str"]
    else:
        best_5k_time = seconds_to_time_str(int(round(best_pace_row["avg_pace_sec"] * 5.0)))
        best_5k_date = best_pace_row["date_str"]
        best_5k_pace = best_pace_row["pace_str"]

    # 4. 最高有酸素効率 (AEI)
    speed_kmh = 3600.0 / df["avg_pace_sec"]
    aei_series = (speed_kmh / df["avg_hr"]) * 100.0
    best_aei_idx = aei_series.idxmax()
    best_aei_row = df.loc[best_aei_idx]
    best_aei_val = round(float(aei_series.loc[best_aei_idx]), 2)

    # 5. 月間最多走行距離
    monthly = df.groupby("year_month")["distance_km"].sum()
    max_month = monthly.idxmax()
    max_month_dist = round(float(monthly.max()), 1)

    return {
        "longest_dist": {
            "val": f"{round(float(max_dist_row['distance_km']), 2)} km",
            "date": max_dist_row["date_str"],
            "pace": max_dist_row["pace_str"],
            "time": max_dist_row["duration_str"],
        },
        "best_pace": {
            "val": f"{best_pace_row['pace_str']} /km",
            "date": best_pace_row["date_str"],
            "dist": f"{round(float(best_pace_row['distance_km']), 2)} km",
            "hr": f"{int(best_pace_row['avg_hr'])} bpm",
        },
        "best_5k": {
            "val": best_5k_time,
            "date": best_5k_date,
            "pace": f"{best_5k_pace} /km",
        },
        "best_aei": {
            "val": best_aei_val,
            "date": best_aei_row["date_str"],
            "pace": best_aei_row["pace_str"],
            "hr": f"{int(best_aei_row['avg_hr'])} bpm",
        },
        "best_month": {
            "val": f"{max_month_dist} km",
            "date": max_month,
        },
    }


def compute_race_predictions(df: pd.DataFrame, current_vdot: float = 40.0) -> List[Dict[str, Any]]:
    """VDOTに基づく科学的レース予想タイム"""
    vdot_preds = predict_race_times_vdot(current_vdot)
    results = []
    targets = [
        ("5km", 5.0, "⚡"),
        ("10km", 10.0, "🏃"),
        ("ハーフマラソン", 21.0975, "🏅"),
        ("フルマラソン", 42.195, "👑"),
    ]
    for name, d, icon in targets:
        if name in vdot_preds:
            p = vdot_preds[name]
            results.append({
                "name": name,
                "icon": icon,
                "distance_km": d,
                "time_str": p["time_str"],
                "pace_str": p["pace_str"],
            })
    return results


def _filter_vdot_eligible_runs(df: pd.DataFrame) -> pd.DataFrame:
    """VDOT算出に適した中〜高強度ランを抽出（意図的な低心拍LSDやウォーク混じりスロージョグを除外）"""
    valid_runs = df[df["distance_km"] >= 3.0].copy()
    if valid_runs.empty:
        valid_runs = df[df["distance_km"] >= 1.0].copy()
    if valid_runs.empty:
        return valid_runs

    # 意図的な低心拍LSD（平均心拍150以下 または 平均ペース6:40/kmより遅い有酸素ベース走）は
    # タイムのみから算出するダニエルズ式VDOTを不当に引き下げるため除外する
    if "avg_hr" in valid_runs.columns and "avg_pace_sec" in valid_runs.columns:
        quality_runs = valid_runs[
            ~((valid_runs["avg_hr"] > 0) & (valid_runs["avg_hr"] <= 150))
            & (valid_runs["avg_pace_sec"] <= 400.0)
        ].copy()
        if not quality_runs.empty:
            return quality_runs

    return valid_runs


def compute_vdot_analytics(df: pd.DataFrame) -> Dict[str, Any]:
    """全走行データから VDOT スコアと 5大トレーニングペース（E / M / T / I / R）を算出"""
    valid_runs = _filter_vdot_eligible_runs(df)
    
    if valid_runs.empty:
        default_paces = get_training_paces(40.0)
        return {
            "current_vdot": 40.0,
            "peak_vdot": 40.0,
            "paces": default_paces,
            "race_predictions": predict_race_times_vdot(40.0)
        }

    # 各アクティビティの VDOT 計算
    vdots = []
    for _, row in valid_runs.iterrows():
        d_m = row["distance_km"] * 1000.0
        t_s = row["duration_sec"]
        v = calculate_vdot(d_m, t_s)
        if v > 0:
            vdots.append((row["datetime"], v))

    if not vdots:
        return {"current_vdot": 40.0, "peak_vdot": 40.0, "paces": get_training_paces(40.0), "race_predictions": predict_race_times_vdot(40.0)}

    peak_vdot = max(v for _, v in vdots)

    # 直近走力 (直近5走の加重平均)
    recent_vdots = [v for _, v in vdots[-5:]]
    weights = list(range(1, len(recent_vdots) + 1))
    current_vdot = sum(v * w for v, w in zip(recent_vdots, weights)) / sum(weights)
    current_vdot = round(current_vdot, 1)

    paces = get_training_paces(current_vdot)
    race_preds = predict_race_times_vdot(current_vdot)

    return {
        "current_vdot": current_vdot,
        "peak_vdot": round(peak_vdot, 1),
        "paces": paces,
        "race_predictions": race_preds,
    }


def compute_sub50_progress(df: pd.DataFrame, insights: List[Dict[str, Any]], current_vdot: float) -> Dict[str, Any]:
    """10km 50分（サブ50）達成プログレストラッカー"""
    # 1. サブ50 (5:00/km以内) を連続維持できた過去最長距離
    max_sustained_km = 0.0
    latest_sustained_km = 0.0
    for act in insights:
        ev = act.get("evaluation", {})
        s = ev.get("sub50_sustained_km", 0.0)
        if s > max_sustained_km:
            max_sustained_km = s

    if insights:
        latest_sustained_km = insights[-1].get("evaluation", {}).get("sub50_sustained_km", 0.0)

    # 2. 現在の推定 10km タイム (VDOTベース)
    vdot_preds = predict_race_times_vdot(current_vdot)
    ten_k_info = vdot_preds.get("10km", {})
    est_10k_sec = ten_k_info.get("time_sec", 3120.0)
    est_10k_time_str = ten_k_info.get("time_str", "52:00")
    est_10k_pace_str = ten_k_info.get("pace_str", "5:12")

    # 3. 目標 (3000秒 = 50:00) とのギャップ
    gap_time_sec = est_10k_sec - TARGET_TIME_SEC
    gap_pace_sec = (est_10k_sec / TARGET_DISTANCE_KM) - TARGET_PACE_SEC

    if gap_time_sec <= 0:
        gap_status = "目標ペース圏内 (50分切り可能)"
        gap_color = "text-emerald-400"
        gap_badge = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
        gap_time_str = f"-{abs(int(round(gap_time_sec)))}秒 (クリア)"
        gap_pace_str = f"-{abs(int(round(gap_pace_sec)))}秒/km"
    else:
        gap_status = f"あと {int(round(gap_time_sec // 60))}分{int(round(gap_time_sec % 60)):02d}秒 短縮が必要"
        gap_color = "text-amber-400"
        gap_badge = "bg-amber-500/20 text-amber-300 border-amber-500/40"
        gap_time_str = f"+{int(round(gap_time_sec // 60))}分{int(round(gap_time_sec % 60)):02d}秒"
        gap_pace_str = f"+{int(round(gap_pace_sec))}秒/km"

    # 進捗率 (60分=0%, 50分=100%)
    progress_pct = max(10.0, min(100.0, round(((3600.0 - est_10k_sec) / 600.0) * 100.0, 1)))

    return {
        "target_label": TARGET_LABEL,
        "target_time_str": "50:00",
        "target_pace_str": "5:00 /km",
        "est_10k_time_str": est_10k_time_str,
        "est_10k_pace_str": est_10k_pace_str,
        "gap_time_str": gap_time_str,
        "gap_pace_str": gap_pace_str,
        "gap_status": gap_status,
        "gap_color": gap_color,
        "gap_badge": gap_badge,
        "progress_pct": progress_pct,
        "max_sustained_km": round(max_sustained_km, 1),
        "latest_sustained_km": round(latest_sustained_km, 1),
    }


def compute_sub50_forecast(
    df: pd.DataFrame,
    current_vdot: float,
    target_vdot: float = 40.8,
    window_days: int = 90,
) -> Dict[str, Any]:
    """10km 50分（VDOT 40.8）到達予測推計

    直近のアクティビティ（直近90日、不足時は直近全データ）のVDOT推移から線形回帰を行い、
    1日あたりの成長率（傾き）から目標到達見込み日数・日付を算出します。
    """
    if df.empty or current_vdot <= 0:
        return {
            "target_vdot": target_vdot,
            "current_vdot": current_vdot,
            "slope_per_day": 0.0,
            "monthly_growth": 0.0,
            "days_to_target": None,
            "predicted_date_str": "--",
            "status": "insufficient_data",
            "status_label": "データ不足",
            "status_badge": "bg-slate-800 text-slate-400 border-slate-700",
            "desc": "予測推計に必要な走行データが不足しています。",
            "sample_runs": 0,
        }

    # 3.0km 以上の有効ラン（意図的な低心拍LSDは除外）
    valid_runs = _filter_vdot_eligible_runs(df)

    if valid_runs.empty:
        return {
            "target_vdot": target_vdot,
            "current_vdot": current_vdot,
            "slope_per_day": 0.0,
            "monthly_growth": 0.0,
            "days_to_target": None,
            "predicted_date_str": "--",
            "status": "insufficient_data",
            "status_label": "データ不足",
            "status_badge": "bg-slate-800 text-slate-400 border-slate-700",
            "desc": "距離3km以上の有効な走行データが不足しています。",
            "sample_runs": 0,
        }

    latest_dt = valid_runs["datetime"].max()
    latest_date = latest_dt.date()
    start_dt = latest_dt - timedelta(days=window_days)

    recent_runs = valid_runs[valid_runs["datetime"] >= start_dt].copy()
    # 直近90日のデータが5件未満なら直近180日または全有効データを使用
    if len(recent_runs) < 5:
        wider_start = latest_dt - timedelta(days=180)
        recent_runs = valid_runs[valid_runs["datetime"] >= wider_start].copy()
        if len(recent_runs) < 5:
            recent_runs = valid_runs.tail(15).copy()

    points = []
    base_dt = recent_runs["datetime"].min()
    for _, row in recent_runs.iterrows():
        d_m = float(row["distance_km"]) * 1000.0
        t_s = float(row["duration_sec"])
        v = calculate_vdot(d_m, t_s)
        if v > 0:
            days = (row["datetime"] - base_dt).total_seconds() / 86400.0
            points.append((days, v))

    if len(points) < 2:
        return {
            "target_vdot": target_vdot,
            "current_vdot": current_vdot,
            "slope_per_day": 0.0,
            "monthly_growth": 0.0,
            "days_to_target": None,
            "predicted_date_str": "--",
            "status": "insufficient_data",
            "status_label": "データ不足",
            "status_badge": "bg-slate-800 text-slate-400 border-slate-700",
            "desc": "回帰分析に必要なデータポイントが不足しています。",
            "sample_runs": len(points),
        }

    # 最小二乗法
    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    mean_x = sum_x / n
    mean_y = sum_y / n
    denom = sum((p[0] - mean_x) ** 2 for p in points)

    slope = (sum((p[0] - mean_x) * (p[1] - mean_y) for p in points) / denom) if denom > 1e-9 else 0.0
    monthly_growth = round(slope * 30.0, 2)

    # 既に目標到達済みか？
    if current_vdot >= target_vdot:
        return {
            "target_vdot": target_vdot,
            "current_vdot": current_vdot,
            "slope_per_day": round(slope, 4),
            "monthly_growth": monthly_growth,
            "days_to_target": 0,
            "predicted_date_str": "達成済み",
            "status": "achieved",
            "status_label": "目標走力 到達済み",
            "status_badge": "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
            "desc": f"現在の走力 (VDOT {current_vdot}) は既にサブ50基準 (VDOT {target_vdot}) をクリアしています！",
            "sample_runs": n,
        }

    # 傾き判定
    if slope > 0.0001:
        rem_vdot = target_vdot - current_vdot
        days_to_target = max(1, int(math.ceil(rem_vdot / slope)))
        predicted_date = latest_date + timedelta(days=days_to_target)
        pred_str = predicted_date.strftime("%Y年%m月%d日")
        growth_sign = f"+{monthly_growth}" if monthly_growth > 0 else f"{monthly_growth}"

        return {
            "target_vdot": target_vdot,
            "current_vdot": current_vdot,
            "slope_per_day": round(slope, 4),
            "monthly_growth": monthly_growth,
            "days_to_target": days_to_target,
            "predicted_date_str": pred_str,
            "status": "on_track",
            "status_label": f"約 {days_to_target} 日後 ({pred_str}頃) 到達予測",
            "status_badge": "bg-sky-500/20 text-sky-300 border-sky-500/40",
            "desc": f"直近の成長傾向（月間 {growth_sign} VDOT）を維持した場合、約 {days_to_target} 日後（{pred_str}頃）にサブ50相当走力（VDOT {target_vdot}）へ到達する見込みです。",
            "sample_runs": n,
        }
    else:
        return {
            "target_vdot": target_vdot,
            "current_vdot": current_vdot,
            "slope_per_day": round(slope, 4),
            "monthly_growth": monthly_growth,
            "days_to_target": None,
            "predicted_date_str": "--",
            "status": "stagnant",
            "status_label": "現状維持・停滞トレンド",
            "status_badge": "bg-amber-500/20 text-amber-300 border-amber-500/40",
            "desc": "直近のVDOTトレンドは横ばい〜微減傾向です。現状ペースの維持では到達予測の算出が難しいため、Tペース（閾値走）などのポイント練習で刺激を入れましょう。",
            "sample_runs": n,
        }


def compute_gear_stats(df: pd.DataFrame, lifespan_km: float = 600.0) -> List[Dict[str, Any]]:
    """シューズ（ギア）別の累計走行距離、寿命進捗率、交換推奨ステータスを集計"""
    if df.empty:
        return []

    # 「シューズ」または「gear_name」列をチェック
    shoe_col = None
    if "シューズ" in df.columns:
        shoe_col = "シューズ"
    elif "gear_name" in df.columns:
        shoe_col = "gear_name"

    if not shoe_col:
        return []

    # シューズ名ごとにグルーピング
    gear_groups: Dict[str, List[Any]] = {}
    for _, row in df.iterrows():
        raw_name = str(row.get(shoe_col, "")).strip()
        if not raw_name or raw_name.lower() in ["nan", "none", ""]:
            continue

        if raw_name not in gear_groups:
            gear_groups[raw_name] = []
        gear_groups[raw_name].append(row)

    if not gear_groups:
        return []

    results = []
    for shoe_name, rows in gear_groups.items():
        sub_df = pd.DataFrame(rows)
        total_dist = round(float(sub_df["distance_km"].sum()), 1)
        runs_count = len(sub_df)
        last_used = str(sub_df["date_str"].max())

        lifespan_pct = min(100.0, round((total_dist / lifespan_km) * 100.0, 1))
        remaining_km = max(0.0, round(lifespan_km - total_dist, 1))
        needs_replacement = total_dist >= lifespan_km

        if needs_replacement:
            status_label = "交換推奨 (寿命到達)"
            status_color = "text-rose-400"
            status_badge = "bg-rose-500/20 text-rose-300 border-rose-500/40"
        elif total_dist >= lifespan_km * 0.8:
            status_label = "交換準備推奨"
            status_color = "text-amber-400"
            status_badge = "bg-amber-500/20 text-amber-300 border-amber-500/40"
        else:
            status_label = "良好"
            status_color = "text-emerald-400"
            status_badge = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"

        results.append({
            "name": shoe_name,
            "total_distance_km": total_dist,
            "runs": runs_count,
            "last_used": last_used,
            "lifespan_km": lifespan_km,
            "lifespan_pct": lifespan_pct,
            "remaining_km": remaining_km,
            "needs_replacement": needs_replacement,
            "status_label": status_label,
            "status_color": status_color,
            "status_badge": status_badge,
        })

    # 累計距離降順でソート
    results.sort(key=lambda x: x["total_distance_km"], reverse=True)
    return results


def compute_calendar_heatmap(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """カレンダーヒートマップ用デイリー集計データ (直近1年間・週境界アライン)"""
    if df.empty:
        return []

    # 日付ごとの集計
    daily = (
        df.groupby("date_str")
        .agg(
            distance_km=("distance_km", "sum"),
            runs=("distance_km", "count"),
            avg_pace_sec=("avg_pace_sec", "mean"),
            avg_hr=("avg_hr", "mean"),
        )
        .reset_index()
    )

    daily_map = {
        row["date_str"]: {
            "distance_km": round(float(row["distance_km"]), 2),
            "runs": int(row["runs"]),
            "pace_str": seconds_to_pace_str(row["avg_pace_sec"]),
            "avg_hr": int(row["avg_hr"]),
        }
        for _, row in daily.iterrows()
    }

    start_dt = df["datetime"].min().date()
    end_dt = df["datetime"].max().date()

    # 直近約1年 (370日) を上限とする
    max_history_days = 370
    earliest_allowed = end_dt - timedelta(days=max_history_days)
    if start_dt < earliest_allowed:
        start_dt = earliest_allowed

    min_start = end_dt - timedelta(days=150)
    if start_dt > min_start:
        start_dt = min_start

    # 週の開始曜日（月曜日: weekday=0）にアライン
    aligned_start = start_dt - timedelta(days=start_dt.weekday())
    # 週の終了曜日（日曜日: weekday=6）にアライン
    aligned_end = end_dt + timedelta(days=(6 - end_dt.weekday()))

    weekday_jp_map = ["月", "火", "水", "木", "金", "土", "日"]

    heatmap_list = []
    curr = aligned_start
    while curr <= aligned_end:
        date_str = curr.strftime("%Y-%m-%d")
        is_future = curr > end_dt
        weekday_idx = curr.weekday()
        weekday_jp = weekday_jp_map[weekday_idx]
        date_jp = f"{curr.year}年{curr.month}月{curr.day}日 ({weekday_jp})"

        if date_str in daily_map and not is_future:
            info = daily_map[date_str]
            heatmap_list.append({
                "date": date_str,
                "date_jp": date_jp,
                "year": curr.year,
                "month": curr.month,
                "day": curr.day,
                "weekday": weekday_idx,
                "weekday_jp": weekday_jp,
                "is_future": False,
                "is_first_day": curr.day == 1,
                "distance_km": info["distance_km"],
                "runs": info["runs"],
                "pace_str": info["pace_str"],
                "avg_hr": info["avg_hr"],
            })
        else:
            heatmap_list.append({
                "date": date_str,
                "date_jp": date_jp,
                "year": curr.year,
                "month": curr.month,
                "day": curr.day,
                "weekday": weekday_idx,
                "weekday_jp": weekday_jp,
                "is_future": is_future,
                "is_first_day": curr.day == 1,
                "distance_km": 0.0,
                "runs": 0,
                "pace_str": "--:--",
                "avg_hr": 0,
            })
        curr += timedelta(days=1)

    return heatmap_list


def compute_weekly_workload(df: pd.DataFrame) -> Dict[str, Any]:
    """週間走行負荷と怪我予防（前週比+10%ルール）を計算"""
    df_temp = df.copy()
    df_temp["week_str"] = df_temp["datetime"].dt.to_period("W-MON").apply(lambda r: r.start_time.strftime("%m/%d週"))
    
    weekly = (
        df_temp.groupby("week_str", sort=False)
        .agg(
            distance_km=("distance_km", "sum"),
            runs=("distance_km", "count"),
            avg_hr=("avg_hr", "mean"),
        )
        .reset_index()
    )

    recent_8 = weekly.tail(8)
    labels = recent_8["week_str"].tolist()
    distances = [round(float(d), 1) for d in recent_8["distance_km"]]
    runs = [int(r) for r in recent_8["runs"]]

    current_week_dist = distances[-1] if distances else 0.0
    prev_week_dist = distances[-2] if len(distances) >= 2 else current_week_dist

    if prev_week_dist > 0:
        ratio_pct = round((current_week_dist / prev_week_dist) * 100)
    else:
        ratio_pct = 100

    if ratio_pct <= 75:
        status = "リカバリー・減量週"
        status_color = "text-sky-400"
        status_badge = "bg-sky-500/10 text-sky-300 border-sky-500/20"
        desc = f"前週比 {ratio_pct}%。疲労を抜き、関節・筋肉の超回復を促すリカバリー週です。"
    elif 76 <= ratio_pct <= 112:
        status = "適正トレーニング負荷 (Optimal)"
        status_color = "text-emerald-400"
        status_badge = "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
        desc = f"前週比 {ratio_pct}%。走力向上と怪我予防の黄金比（前週比±10%以内）を維持できています。"
    elif 113 <= ratio_pct <= 130:
        status = "増量・強化週 (Challenging)"
        status_color = "text-amber-400"
        status_badge = "bg-amber-500/10 text-amber-300 border-amber-500/20"
        desc = f"前週比 {ratio_pct}%。走行量を意図的に引き上げています。入念なストレッチと睡眠を確保してください。"
    else:
        status = "急激な走行量増加注意 (Caution)"
        status_color = "text-rose-400"
        status_badge = "bg-rose-500/10 text-rose-300 border-rose-500/20"
        desc = f"前週比 {ratio_pct}%。急激な距離増（130%超）はランナー膝等の障害リスクを高めます。無理せず休息日を挟みましょう。"

    return {
        "labels": labels,
        "distances": distances,
        "runs": runs,
        "current_week_dist": current_week_dist,
        "prev_week_dist": prev_week_dist,
        "ratio_pct": ratio_pct,
        "status": status,
        "status_color": status_color,
        "status_badge": status_badge,
        "desc": desc,
    }


def compute_form_evolution(df: pd.DataFrame) -> Dict[str, Any]:
    """月別の平均ピッチ（spm）と平均歩幅（m）の推移"""
    monthly_form = (
        df.groupby("year_month")
        .agg(
            cadence=("avg_cadence", "mean"),
            stride=("stride_length_m", "mean"),
            speed=("avg_pace_sec", lambda s: (3600.0 / s).mean()),
        )
        .reset_index()
    )
    return {
        "months": monthly_form["year_month"].tolist(),
        "cadences": [round(float(c), 1) for c in monthly_form["cadence"]],
        "strides": [round(float(s), 2) for s in monthly_form["stride"]],
        "speeds_kmh": [round(float(sp), 2) for sp in monthly_form["speed"]],
    }


def compute_rolling_volume(df: pd.DataFrame, window_days: int = 30) -> Dict[str, Any]:
    """各日における過去N日間（デフォルト30日間＝過去1ヶ月）のスライディングウィンドウ合計走行距離と回数を集計"""
    if df.empty:
        return {
            "dates": [],
            "volumes": [],
            "runs": [],
            "daily_distances": [],
            "current_volume": 0.0,
            "peak_volume": 0.0,
            "mean_volume": 0.0,
            "window_days": window_days,
        }

    daily = (
        df.groupby("date_str")
        .agg(
            distance_km=("distance_km", "sum"),
            runs=("distance_km", "count")
        )
    )

    min_date = df["datetime"].min().date()
    max_date = df["datetime"].max().date()

    all_dates = pd.date_range(min_date, max_date, freq="D")
    df_daily = pd.DataFrame(index=all_dates)
    df_daily["distance_km"] = 0.0
    df_daily["runs"] = 0

    for d_str, row in daily.iterrows():
        dt = pd.to_datetime(d_str)
        if dt in df_daily.index:
            df_daily.loc[dt, "distance_km"] = float(row["distance_km"])
            df_daily.loc[dt, "runs"] = int(row["runs"])

    # ローリング集計 (window=window_days, min_periods=1)
    df_daily["rolling_dist"] = df_daily["distance_km"].rolling(window=window_days, min_periods=1).sum()
    df_daily["rolling_runs"] = df_daily["runs"].rolling(window=window_days, min_periods=1).sum()

    dates = [d.strftime("%Y-%m-%d") for d in df_daily.index]
    volumes = [round(float(v), 2) for v in df_daily["rolling_dist"]]
    rolling_runs = [int(r) for r in df_daily["rolling_runs"]]
    daily_distances = [round(float(d), 2) for d in df_daily["distance_km"]]

    current_volume = volumes[-1] if volumes else 0.0
    peak_volume = round(float(df_daily["rolling_dist"].max()), 2) if not df_daily.empty else 0.0
    mean_volume = round(float(df_daily["rolling_dist"].mean()), 2) if not df_daily.empty else 0.0

    return {
        "dates": dates,
        "volumes": volumes,
        "runs": rolling_runs,
        "daily_distances": daily_distances,
        "current_volume": current_volume,
        "peak_volume": peak_volume,
        "mean_volume": mean_volume,
        "window_days": window_days,
    }


def _extract_post_warmup_summary(act: Optional[Dict[str, Any]], warmup_km: float = WARMUP_DISTANCE_KM) -> Dict[str, Any]:
    """アクティビティの1〜3kmウォームアップ区間と3km以降の本練習区間（Quality Zone）を分離集計"""
    if not act:
        return {
            "has_split": False,
            "warmup_km": 0.0,
            "warmup_pace_str": "--:--",
            "warmup_hr": 0,
            "main_km": 0.0,
            "main_pace_str": "--:--",
            "main_pace_sec": 0.0,
            "main_hr": 0,
            "fastest_lap_str": "--:--",
            "fastest_lap_idx": 0,
            "cooldown_km": 0.0,
            "cooldown_pace_str": "--:--",
            "laps_summary": [],
        }

    laps = (act.get("distance_series") or {}).get("laps") or []
    valid_laps = [l for l in laps if l.get("distance_km", 0) >= 0.3]

    if not valid_laps or act.get("distance_km", 0) <= warmup_km + 0.5:
        return {
            "has_split": False,
            "warmup_km": round(float(act.get("distance_km", 0)), 2),
            "warmup_pace_str": act.get("pace_str", "--:--"),
            "warmup_hr": int(act.get("avg_hr", 0)),
            "main_km": round(float(act.get("distance_km", 0)), 2),
            "main_pace_str": act.get("pace_str", "--:--"),
            "main_pace_sec": float(act.get("pace_sec", 0.0)),
            "main_hr": int(act.get("avg_hr", 0)),
            "fastest_lap_str": act.get("max_pace_str", "--:--"),
            "fastest_lap_idx": 1,
            "cooldown_km": 0.0,
            "cooldown_pace_str": "--:--",
            "laps_summary": valid_laps,
        }

    wu_laps = []
    post_laps = []
    acc_km = 0.0
    for l in valid_laps:
        if acc_km < warmup_km - 0.15:
            wu_laps.append(l)
            acc_km += float(l.get("distance_km", 0))
        else:
            post_laps.append(l)

    if not post_laps:
        post_laps = valid_laps[-1:]
        wu_laps = valid_laps[:-1]

    # 最終ラップが明確なクールダウン（直前より25秒以上遅い、またはrole_tagにクールダウンを含む）の場合は本練習集計から分離可能にする
    cooldown_laps = []
    main_laps = list(post_laps)
    if len(post_laps) >= 2:
        last_l = post_laps[-1]
        prev_l = post_laps[-2]
        role_tag = str(last_l.get("role_tag", ""))
        if "クールダウン" in role_tag or (last_l.get("pace_sec", 0) - prev_l.get("pace_sec", 0) >= 25):
            cooldown_laps = [last_l]
            main_laps = post_laps[:-1]

    def _agg_laps(lap_list: List[Dict[str, Any]]):
        if not lap_list:
            return 0.0, 0.0, "--:--", 0
        tot_d = sum(float(x.get("distance_km", 0)) for x in lap_list)
        if tot_d <= 0:
            return 0.0, 0.0, "--:--", 0
        # 距離加重平均ペース
        tot_sec = sum(float(x.get("pace_sec", 0)) * float(x.get("distance_km", 0)) for x in lap_list)
        avg_p = tot_sec / tot_d
        hrs = [float(x.get("avg_hr", 0)) for x in lap_list if x.get("avg_hr", 0) > 0]
        avg_h = int(round(sum(hrs) / len(hrs))) if hrs else 0
        return round(tot_d, 2), round(avg_p, 1), seconds_to_pace_str(avg_p), avg_h

    wu_km, _, wu_pace_str, wu_hr = _agg_laps(wu_laps)
    main_km, main_pace_sec, main_pace_str, main_hr = _agg_laps(main_laps)
    cd_km, _, cd_pace_str, _ = _agg_laps(cooldown_laps)

    fastest_lap = min(valid_laps, key=lambda x: x.get("pace_sec", 9999))

    return {
        "has_split": True,
        "warmup_km": wu_km,
        "warmup_pace_str": wu_pace_str,
        "warmup_hr": wu_hr,
        "main_km": main_km,
        "main_pace_str": main_pace_str,
        "main_pace_sec": main_pace_sec,
        "main_hr": main_hr,
        "fastest_lap_str": fastest_lap.get("pace_str", "--:--"),
        "fastest_lap_idx": fastest_lap.get("lap_index", 1),
        "cooldown_km": cd_km,
        "cooldown_pace_str": cd_pace_str,
        "laps_summary": valid_laps,
    }


def compute_three_pillars(
    df: pd.DataFrame,
    insights: List[Dict[str, Any]],
    current_vdot: float,
    sub50_progress: Dict[str, Any],
) -> Dict[str, Any]:
    """トップページの核となる「3大種目目標（11/29ヨロンハーフ・12/6 NAHAフル・10kmサブ50）」の進捗・実戦KPIを算出"""
    today = date.today()
    latest_act_date = df["datetime"].max().date() if not df.empty else today
    ref_date = max(today, latest_act_date)

    half_dt = datetime.strptime(HALF_RACE_DATE, "%Y-%m-%d").date()
    full_dt = datetime.strptime(FULL_RACE_DATE, "%Y-%m-%d").date()

    days_to_half = max(0, (half_dt - ref_date).days)
    days_to_full = max(0, (full_dt - ref_date).days)

    # 関東遠征オフ日 (2026年10月〜11月)
    kanto_off_dates = {
        "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02",
        "2026-11-06", "2026-11-07", "2026-11-08",
        "2026-11-13",
        "2026-11-20", "2026-11-21",
    }

    # ヨロンハーフまでに那覇で走れる実質日数と想定ポイント練習回数
    available_days_to_half = 0
    curr_d = ref_date + timedelta(days=1)
    while curr_d < half_dt:
        if curr_d.strftime("%Y-%m-%d") not in kanto_off_dates:
            available_days_to_half += 1
        curr_d += timedelta(days=1)
    est_sessions_to_half = max(1, round(available_days_to_half * 0.42))  # 週3回ペース換算

    vdot_preds = predict_race_times_vdot(current_vdot)
    half_pred = vdot_preds.get("ハーフマラソン", {"time_sec": 6900, "time_str": "1:55:00", "pace_str": "5:27"})
    full_pred = vdot_preds.get("フルマラソン", {"time_sec": 14400, "time_str": "4:00:00", "pace_str": "5:41"})

    # 3km以降（または全体）での「ハーフ目標ペース (5:38/km = 338秒以内)」連続維持最長距離 ＆ ベスト本練習
    max_half_pace_km = 0.0
    best_half_session_str = "--"
    for act in insights:
        laps = (act.get("distance_series") or {}).get("laps") or []
        cur_km = 0.0
        for l in laps:
            if l.get("pace_sec", 999) <= 340.0:  # 5:40/km 以内
                cur_km += float(l.get("distance_km", 0))
                if cur_km > max_half_pace_km:
                    max_half_pace_km = round(cur_km, 1)
                    best_half_session_str = f"{act['date']} ({l['pace_str']}/km)"
            else:
                cur_km = 0.0

    # フルマラソン向け指標: 最長走破距離 ＆ 12km以上のロング走における有酸素安定度
    max_dist_km = round(float(df["distance_km"].max()), 2) if not df.empty else 0.0
    long_runs = [a for a in insights if a.get("distance_km", 0) >= 12.0]
    if long_runs:
        best_long = max(long_runs, key=lambda x: x.get("distance_km", 0))
        long_run_summary = f"{best_long['distance_km']}km ({best_long['duration_str']} / 平均HR {best_long['avg_hr']}bpm)"
    else:
        long_run_summary = f"最長 {max_dist_km}km"

    # ハーフ進捗率 (2時間20分=8400秒を0%、1時間58分=7080秒を100%としてスケーリング)
    est_half_sec = float(half_pred.get("time_sec", 7000))
    half_gap_sec = est_half_sec - HALF_TARGET_TIME_SEC
    if half_gap_sec <= 0:
        half_status = f"サブ2圏内 ({seconds_to_time_str(abs(int(half_gap_sec)))} 余裕)"
        half_badge = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
    else:
        half_status = f"サブ2まであと {seconds_to_time_str(int(half_gap_sec))}"
        half_badge = "bg-amber-500/20 text-amber-300 border-amber-500/40"
    half_reach_pct = min(100.0, max(15.0, round((max_dist_km / HALF_DISTANCE_KM) * 100.0, 1)))

    # フル進捗率 (距離到達率 + VDOT持久力)
    est_full_sec = float(full_pred.get("time_sec", 15000))
    full_gap_sec = est_full_sec - FULL_TARGET_TIME_SEC
    if full_gap_sec <= 0:
        full_status = f"VDOT理論値クリア (脚作り {round((max_dist_km / 30.0) * 100)}%)"
        full_badge = "bg-sky-500/20 text-sky-300 border-sky-500/40"
    else:
        full_status = f"あと {seconds_to_time_str(int(full_gap_sec))} 短縮"
        full_badge = "bg-amber-500/20 text-amber-300 border-amber-500/40"
    full_dist_pct = min(100.0, round((max_dist_km / FULL_DISTANCE_KM) * 100.0, 1))

    return {
        "ref_date": ref_date.strftime("%Y-%m-%d"),
        "half_marathon": {
            "race_name": HALF_RACE_NAME,
            "race_date": "2026.11.29 (日)",
            "days_left": days_to_half,
            "available_days": available_days_to_half,
            "est_sessions_left": est_sessions_to_half,
            "target_label": HALF_TARGET_LABEL,
            "target_time_str": "1:55:00〜1:59:59",
            "target_pace_str": "5:27〜5:38 /km",
            "est_time_str": half_pred.get("time_str", "--"),
            "est_pace_str": half_pred.get("pace_str", "--"),
            "sustained_pace_km": max_half_pace_km,
            "longest_dist_km": max_dist_km,
            "dist_reach_pct": half_reach_pct,
            "status_label": half_status,
            "status_badge": half_badge,
            "strategy_note": "0-3km アップ(5:50) → 4-18km 巡航(5:30) → 19-21km スパート(5:15)",
        },
        "full_marathon": {
            "race_name": FULL_RACE_NAME,
            "race_date": "2026.12.06 (日)",
            "days_left": days_to_full,
            "target_label": FULL_TARGET_LABEL,
            "target_time_str": "4:15:00〜4:29:59",
            "target_pace_str": "6:00〜6:25 /km",
            "est_time_str": full_pred.get("time_str", "--"),
            "est_pace_str": full_pred.get("pace_str", "--"),
            "longest_dist_km": max_dist_km,
            "long_run_summary": long_run_summary,
            "dist_reach_pct": full_dist_pct,
            "status_label": full_status,
            "status_badge": full_badge,
            "strategy_note": "0-3km 省エネ(7:30) → 4-35km イーブン(6:05-6:20/HR155未満) → 終盤粘り",
        },
        "ten_k": {
            "race_name": "10km スピードコア (Sub-50)",
            "target_label": TARGET_LABEL,
            "target_time_str": "50:00",
            "target_pace_str": "5:00 /km",
            "est_time_str": sub50_progress["est_10k_time_str"],
            "est_pace_str": sub50_progress["est_10k_pace_str"],
            "gap_time_str": sub50_progress["gap_time_str"],
            "gap_pace_str": sub50_progress["gap_pace_str"],
            "gap_status": sub50_progress["gap_status"],
            "progress_pct": sub50_progress["progress_pct"],
            "max_sustained_km": sub50_progress["max_sustained_km"],
            "latest_sustained_km": sub50_progress["latest_sustained_km"],
            "current_vdot": current_vdot,
        },
    }


def compute_training_roadmap(df: pd.DataFrame) -> Dict[str, Any]:
    """docs/TRAINING_PLAN_2026.md の6週間計画と実際の走行ログを照合し、現在週のアクションと全体進捗を返す"""
    run_dates = set(df["date_str"].unique()) if not df.empty else set()
    run_dist_map = df.groupby("date_str")["distance_km"].sum().to_dict() if not df.empty else {}

    today = date.today()
    latest_act_date = df["datetime"].max().date() if not df.empty else today
    ref_date = max(today, latest_act_date)

    weeks_plan = [
        {
            "week_num": 1,
            "title": "Week 1: スピード刺激注入 ＆ 関東遠征①",
            "period": "10/26 (月) 〜 11/01 (日)",
            "start": "2026-10-26",
            "end": "2026-11-01",
            "theme": "8kmビルドアップ完遂 ＋ 遠征前ジョグ ＋ 週末関東アクティブレスト",
            "days": [
                {"date": "2026-10-26", "label": "10/26(月)", "type": "point", "menu": "🔥 8km ビルドアップ走 (3kmアップ+4km加速+1kmダウン)", "target": "Lap7 4:58/km達成"},
                {"date": "2026-10-27", "label": "10/27(火)", "type": "rest", "menu": "完全休養（超回復・温冷ケア）", "target": "疲労抜き"},
                {"date": "2026-10-28", "label": "10/28(水)", "type": "rest", "menu": "完全休養（那覇雨予報60%・与論フェリー手配）", "target": "休養"},
                {"date": "2026-10-29", "label": "10/29(木)", "type": "easy", "menu": "🌱 6〜7km 有酸素イージージョグ (3kmアップ+Zone 2)", "target": "130〜145 bpm"},
                {"date": "2026-10-30", "label": "10/30(金)〜11/01(日)", "type": "kanto", "menu": "✈️ 関東滞在（ラン完全オフ・積極的休養）", "target": "リフレッシュ"},
            ],
        },
        {
            "week_num": 2,
            "title": "Week 2: LT閾値強化 ＆ 関東遠征②",
            "period": "11/02 (月) 〜 11/08 (日)",
            "start": "2026-11-02",
            "end": "2026-11-08",
            "theme": "帰沖リカバリー ＋ 木曜 5km LT走(5:20/km)でハーフ巡航エンジン構築",
            "days": [
                {"date": "2026-11-03", "label": "11/03(火・祝)", "type": "easy", "menu": "🌱 5〜6km 帰沖リカバリージョグ", "target": "Zone 2 ゆるジョグ"},
                {"date": "2026-11-05", "label": "11/05(木)", "type": "point", "menu": "🔥 9km LT閾値走 (3kmアップ + 5km 5:15〜5:25/km + 1kmダウン)", "target": "LT巡航維持"},
                {"date": "2026-11-06", "label": "11/06(金)〜11/08(日)", "type": "kanto", "menu": "✈️ 関東滞在（ラン完全オフ・ちゃんぷる〜フェス＆同窓会）", "target": "完全オフ"},
            ],
        },
        {
            "week_num": 3,
            "title": "Week 3: 🔥 最重要強化週（心肺上限突破 ＆ 18kmプログレッシブ走）",
            "period": "11/09 (月) 〜 11/15 (日)",
            "start": "2026-11-09",
            "end": "2026-11-15",
            "theme": "関東遠征なしの勝負週！インターバルと16〜18km段階加速ロング走",
            "days": [
                {"date": "2026-11-10", "label": "11/10(火)", "type": "point", "menu": "⚡ 7km インターバル (3kmアップ + 1000m×3本 4:50/km + 1kmダウン)", "target": "VO2max刺激"},
                {"date": "2026-11-12", "label": "11/12(木)", "type": "easy", "menu": "🌱 6km 有酸素イージージョグ (Zone 2)", "target": "つなぎ回復"},
                {"date": "2026-11-15", "label": "11/15(日)", "type": "long", "menu": "🌟 16〜18km プログレッシブ走 (3kmアップ+8km Z2+後半5km 6:05/km)", "target": "Mペース耐性"},
            ],
        },
        {
            "week_num": 4,
            "title": "Week 4: テーパリング開始 ＆ スピードキレ研ぎ",
            "period": "11/16 (月) 〜 11/22 (日)",
            "start": "2026-11-16",
            "end": "2026-11-22",
            "theme": "疲労を抜きながら木曜6kmビルドアップと日曜8km快調走で調子を上げる",
            "days": [
                {"date": "2026-11-17", "label": "11/17(火)", "type": "easy", "menu": "🌱 5〜6km 疲労抜きリカバリージョグ", "target": "超回復"},
                {"date": "2026-11-19", "label": "11/19(木)", "type": "point", "menu": "🔥 10km ビルドアップ (3kmアップ + 6km 5:30→5:05/km + 1kmダウン)", "target": "レースキレ注入"},
                {"date": "2026-11-22", "label": "11/22(日)", "type": "easy", "menu": "🏃 8km 快調走 (3kmアップ + 5km 5:45/km)", "target": "ハーフ1週前確認"},
            ],
        },
        {
            "week_num": 5,
            "title": "Week 5: 🏁 ヨロンマラソン（ハーフ本番・サブ2奪取！）",
            "period": "11/23 (月) 〜 11/29 (日)",
            "start": "2026-11-23",
            "end": "2026-11-29",
            "theme": "完全ピーキング（TSB +5〜+15）で与論島へ！1時間55分〜59分でサブ2達成",
            "days": [
                {"date": "2026-11-24", "label": "11/24(火)", "type": "easy", "menu": "🌱 5km 調整ジョグ ＋ 流し3本", "target": "神経系刺激"},
                {"date": "2026-11-26", "label": "11/26(木)", "type": "easy", "menu": "✨ 4km 最終確認 (3kmアップ + 1km 5:30/km)", "target": "本番リズム"},
                {"date": "2026-11-29", "label": "11/29(日)", "type": "race", "menu": "🏁 【決戦】ヨロンマラソン ハーフ (21.0975km)", "target": "1:55:00〜1:59:59"},
            ],
        },
        {
            "week_num": 6,
            "title": "Week 6: 👑 超回復 ＆ NAHAマラソン（フル本番・サブ4.5！）",
            "period": "11/30 (月) 〜 12/06 (日)",
            "start": "2026-11-30",
            "end": "2026-12-06",
            "theme": "ヨロン後の徹底アイシング・栄養補給で超回復し、奥武山公園へサブ4.5ゴール",
            "days": [
                {"date": "2026-12-02", "label": "12/02(水)", "type": "easy", "menu": "🌱 3km 超スロージョグ（脚の軽さ確認）", "target": "完全脱力"},
                {"date": "2026-12-04", "label": "12/04(金)", "type": "easy", "menu": "✨ 2km ジョグ ＋ 100m流し1本", "target": "最終調整"},
                {"date": "2026-12-06", "label": "12/06(日)", "type": "race", "menu": "👑 【決戦】NAHAマラソン フル (42.195km)", "target": "4:15:00〜4:30:00"},
            ],
        },
    ]

    current_week_idx = 0
    for idx, w in enumerate(weeks_plan):
        s_dt = datetime.strptime(w["start"], "%Y-%m-%d").date()
        e_dt = datetime.strptime(w["end"], "%Y-%m-%d").date()
        if s_dt <= ref_date <= e_dt:
            current_week_idx = idx
            break
        elif ref_date > e_dt:
            current_week_idx = idx

    for idx, w in enumerate(weeks_plan):
        w["is_current"] = (idx == current_week_idx)
        w["is_past"] = (idx < current_week_idx)
        for d in w["days"]:
            d_str = d["date"]
            d_dt = datetime.strptime(d_str, "%Y-%m-%d").date()
            if d_str in run_dates:
                d["status"] = "done"
                d["actual_km"] = round(float(run_dist_map[d_str]), 2)
            elif d_dt == ref_date:
                d["status"] = "today"
                d["actual_km"] = 0.0
            elif d_dt < ref_date:
                d["status"] = "past"
                d["actual_km"] = 0.0
            else:
                d["status"] = "upcoming"
                d["actual_km"] = 0.0

    return {
        "current_week": weeks_plan[current_week_idx],
        "all_weeks": weeks_plan,
    }


def prepare_full_analytics(
    df: pd.DataFrame,
    fit_dict: Optional[Dict[str, Any]] = None,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """サイト描画に必要な全分析データをまとめる"""
    hr_params = get_hr_params(data_dir=data_dir, df=df)
    overview = compute_overview_stats(df)
    monthly = compute_monthly_stats(df)
    insights = calculate_activity_insights(df, fit_dict, hr_params=hr_params, data_dir=data_dir)
    personal_records = compute_personal_records(df)

    # VDOT & トレーニングゾーン分析
    vdot_data = compute_vdot_analytics(df)
    race_predictions = compute_race_predictions(df, vdot_data["current_vdot"])
    sub50_progress = compute_sub50_progress(df, insights, vdot_data["current_vdot"])
    sub50_forecast = compute_sub50_forecast(df, vdot_data["current_vdot"])
    sub50_progress["forecast"] = sub50_forecast

    # トレーニング負荷 (CTL / ATL / TSB) ＆ 80/20 心拍強度配分
    training_load = compute_training_load(df, hr_params=hr_params)
    zone_distribution = compute_zone_distribution(df, fit_dict=fit_dict, hr_params=hr_params)

    # ギア（シューズ）走行距離
    gear_stats = compute_gear_stats(df)

    weekly_workload = compute_weekly_workload(df)
    form_evolution = compute_form_evolution(df)
    calendar_heatmap = compute_calendar_heatmap(df)
    rolling_volume = compute_rolling_volume(df, window_days=30)

    # グラフ用データ系列の抽出
    chart_dates = [row["date_str"] for _, row in df.iterrows()]
    chart_distances = [round(float(row["distance_km"]), 2) for _, row in df.iterrows()]
    chart_paces = [round(float(row["avg_pace_sec"] / 60.0), 2) for _, row in df.iterrows()]  # 分単位
    chart_pace_labels = [row["pace_str"] for _, row in df.iterrows()]
    chart_hrs = [int(row["avg_hr"]) for _, row in df.iterrows()]
    chart_max_hrs = [int(row["max_hr"]) for _, row in df.iterrows()]
    chart_cadences = [int(row["avg_cadence"]) for _, row in df.iterrows()]
    chart_strides = [round(float(row["stride_length_m"]), 2) for _, row in df.iterrows()]

    # 有酸素効率 (AEI: スピード対心肺機能スコア = 速度km/h / 心拍数 * 100)
    chart_aeis = []
    for _, row in df.iterrows():
        p_sec = row["avg_pace_sec"]
        hr = row["avg_hr"]
        if p_sec > 0 and hr > 0:
            sp = 3600.0 / p_sec
            val = round(float((sp / hr) * 100.0), 2)
        else:
            val = 0.0
        chart_aeis.append(val)

    # 5走ローリング移動平均
    aei_series = pd.Series(chart_aeis)
    aei_rolling = [round(float(v), 2) for v in aei_series.rolling(window=5, min_periods=1).mean().tolist()]

    # AEI サマリー統計
    valid_aeis = [v for v in chart_aeis if v > 0]
    initial_5_avg = round(float(pd.Series(valid_aeis[:5]).mean()), 2) if len(valid_aeis) >= 5 else (valid_aeis[0] if valid_aeis else 0.0)
    recent_5_avg = round(float(pd.Series(valid_aeis[-5:]).mean()), 2) if len(valid_aeis) >= 5 else (valid_aeis[-1] if valid_aeis else 0.0)
    growth_pct = round(((recent_5_avg - initial_5_avg) / initial_5_avg) * 100.0, 1) if initial_5_avg > 0 else 0.0
    latest_aei = valid_aeis[-1] if valid_aeis else 0.0
    max_aei = max(valid_aeis) if valid_aeis else 0.0

    aei_stats = {
        "latest": latest_aei,
        "max": max_aei,
        "initial_5_avg": initial_5_avg,
        "recent_5_avg": recent_5_avg,
        "growth_pct": growth_pct,
    }

    # ペース vs 心拍数 散布図データ
    scatter_hr_pace = [
        {"x": round(float(row["avg_pace_sec"] / 60.0), 2), "y": int(row["avg_hr"]), "date": row["date_str"], "dist": float(row["distance_km"])}
        for _, row in df.iterrows()
    ]

    # 最新ラン（降順なので末尾）および「3kmアップ vs 3km以降本練習」サマリー
    latest_insight = insights[-1] if insights else None
    latest_quality_split = _extract_post_warmup_summary(latest_insight)
    three_pillars = compute_three_pillars(df, insights, vdot_data["current_vdot"], sub50_progress)
    training_roadmap = compute_training_roadmap(df)

    # アクティビティ履歴は新しい順（降順）で表示
    reversed_insights = list(reversed(insights))

    return {
        "overview": overview,
        "monthly": monthly,
        "insights": insights,
        "reversed_insights": reversed_insights,
        "latest_insight": latest_insight,
        "latest_quality_split": latest_quality_split,
        "three_pillars": three_pillars,
        "training_roadmap": training_roadmap,
        "personal_records": personal_records,
        "vdot_data": vdot_data,
        "race_predictions": race_predictions,
        "sub50_progress": sub50_progress,
        "sub50_forecast": sub50_forecast,
        "training_load": training_load,
        "zone_distribution": zone_distribution,
        "gear_stats": gear_stats,
        "weekly_workload": weekly_workload,
        "form_evolution": form_evolution,
        "calendar_heatmap": calendar_heatmap,
        "rolling_volume": rolling_volume,
        "hr_params": hr_params,
        "aei_stats": aei_stats,
        "chart_data": {
            "dates": chart_dates,
            "distances": chart_distances,
            "paces_min": chart_paces,
            "pace_labels": chart_pace_labels,
            "avg_hrs": chart_hrs,
            "max_hrs": chart_max_hrs,
            "cadences": chart_cadences,
            "strides": chart_strides,
            "aeis": chart_aeis,
            "aei_rolling": aei_rolling,
            "aei_stats": aei_stats,
            "scatter_hr_pace": scatter_hr_pace,
            "monthly_labels": [m["month"] for m in monthly],
            "monthly_distances": [m["distance_km"] for m in monthly],
            "monthly_runs": [m["runs"] for m in monthly],
        },
    }

