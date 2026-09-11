from typing import Dict, Any, List, Optional
import pandas as pd
from .parser import seconds_to_pace_str, seconds_to_time_str
from .coach import calculate_activity_insights


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


def compute_race_predictions(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """リーゲル公式（Riegel's Formula）に基づくレース予想タイム"""
    df_5k = df[(df["distance_km"] >= 4.5) & (df["distance_km"] <= 6.0)]
    if not df_5k.empty:
        base_row = df_5k.loc[df_5k["avg_pace_sec"].idxmin()]
        base_dist = 5.0
        base_time = base_row["avg_pace_sec"] * 5.0
    else:
        base_row = df.loc[df["avg_pace_sec"].idxmin()]
        base_dist = float(base_row["distance_km"])
        base_time = float(base_row["duration_sec"])

    targets = [
        ("5km", 5.0, "⚡"),
        ("10km", 10.0, "🏃"),
        ("ハーフマラソン", 21.0975, "🏅"),
        ("フルマラソン", 42.195, "👑"),
    ]

    predictions = []
    for name, d, icon in targets:
        pred_time_sec = base_time * ((d / base_dist) ** 1.06)
        pred_pace_sec = pred_time_sec / d
        predictions.append({
            "name": name,
            "icon": icon,
            "distance_km": d,
            "time_str": seconds_to_time_str(int(round(pred_time_sec))),
            "pace_str": seconds_to_pace_str(pred_pace_sec),
        })
    return predictions


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


def prepare_full_analytics(df: pd.DataFrame, fit_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """サイト描画に必要な全分析データをまとめる"""
    overview = compute_overview_stats(df)
    monthly = compute_monthly_stats(df)
    insights = calculate_activity_insights(df, fit_dict)
    personal_records = compute_personal_records(df)
    race_predictions = compute_race_predictions(df)
    weekly_workload = compute_weekly_workload(df)
    form_evolution = compute_form_evolution(df)

    # グラフ用データ系列の抽出
    chart_dates = [row["date_str"] for _, row in df.iterrows()]
    chart_distances = [round(float(row["distance_km"]), 2) for _, row in df.iterrows()]
    chart_paces = [round(float(row["avg_pace_sec"] / 60.0), 2) for _, row in df.iterrows()]  # 分単位
    chart_pace_labels = [row["pace_str"] for _, row in df.iterrows()]
    chart_hrs = [int(row["avg_hr"]) for _, row in df.iterrows()]
    chart_max_hrs = [int(row["max_hr"]) for _, row in df.iterrows()]
    chart_cadences = [int(row["avg_cadence"]) for _, row in df.iterrows()]
    chart_strides = [round(float(row["stride_length_m"]), 2) for _, row in df.iterrows()]

    # ペース vs 心拍数 散布図データ
    scatter_hr_pace = [
        {"x": round(float(row["avg_pace_sec"] / 60.0), 2), "y": int(row["avg_hr"]), "date": row["date_str"], "dist": float(row["distance_km"])}
        for _, row in df.iterrows()
    ]

    # 最新ラン（降順なので末尾）
    latest_insight = insights[-1] if insights else None

    # アクティビティ履歴は新しい順（降順）で表示
    reversed_insights = list(reversed(insights))

    return {
        "overview": overview,
        "monthly": monthly,
        "insights": insights,
        "reversed_insights": reversed_insights,
        "latest_insight": latest_insight,
        "personal_records": personal_records,
        "race_predictions": race_predictions,
        "weekly_workload": weekly_workload,
        "form_evolution": form_evolution,
        "chart_data": {
            "dates": chart_dates,
            "distances": chart_distances,
            "paces_min": chart_paces,
            "pace_labels": chart_pace_labels,
            "avg_hrs": chart_hrs,
            "max_hrs": chart_max_hrs,
            "cadences": chart_cadences,
            "strides": chart_strides,
            "scatter_hr_pace": scatter_hr_pace,
            "monthly_labels": [m["month"] for m in monthly],
            "monthly_distances": [m["distance_km"] for m in monthly],
            "monthly_runs": [m["runs"] for m in monthly],
        },
    }
