from typing import Dict, Any, List
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

    return {
        "total_distance_km": round(total_dist, 1),
        "total_runs": total_runs,
        "total_time_str": total_time_str,
        "total_calories": f"{total_cal:,}",
        "avg_pace_str": seconds_to_pace_str(avg_pace_sec),
        "avg_pace_sec": round(avg_pace_sec, 1),
        "avg_hr": round(avg_hr),
        "avg_cadence": round(avg_cadence),
        "avg_stride_m": round(avg_stride, 2),
        "best_pace_str": seconds_to_pace_str(best_pace_sec),
        "max_dist_km": round(max_dist, 2),
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


def prepare_full_analytics(df: pd.DataFrame) -> Dict[str, Any]:
    """サイト描画に必要な全分析データをまとめる"""
    overview = compute_overview_stats(df)
    monthly = compute_monthly_stats(df)
    insights = calculate_activity_insights(df)

    # グラフ用データ系列の抽出
    chart_dates = [row["date_str"] for _, row in df.iterrows()]
    chart_distances = [round(row["distance_km"], 2) for _, row in df.iterrows()]
    chart_paces = [round(row["avg_pace_sec"] / 60.0, 2) for _, row in df.iterrows()]  # 分単位
    chart_pace_labels = [row["pace_str"] for _, row in df.iterrows()]
    chart_hrs = [int(row["avg_hr"]) for _, row in df.iterrows()]
    chart_max_hrs = [int(row["max_hr"]) for _, row in df.iterrows()]
    chart_cadences = [int(row["avg_cadence"]) for _, row in df.iterrows()]
    chart_strides = [round(row["stride_length_m"], 2) for _, row in df.iterrows()]

    # ペース vs 心拍数 散布図データ
    scatter_hr_pace = [
        {"x": round(row["avg_pace_sec"] / 60.0, 2), "y": int(row["avg_hr"]), "date": row["date_str"], "dist": row["distance_km"]}
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
