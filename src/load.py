"""トレーニング負荷（CTL / ATL / TSB）および心拍強度配分（80/20ルール）分析モジュール

Banister TRIMP (Training Impulse) モデルに基づくフィットネス・疲労・コンディション推移の推計、
および有酸素運動の黄金比（低強度80% / 高強度20%）の分析を提供します。
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd


def calculate_trimp(
    duration_sec: float,
    avg_hr: float,
    hr_resting: float,
    hr_max: float,
) -> float:
    """Banister TRIMP (Training Impulse) を算出

    数式:
        TRIMP = Duration (分) * HRr * 0.64 * exp(1.92 * HRr)
        HRr (心拍予備率) = (avg_hr - hr_resting) / (hr_max - hr_resting)
    """
    if duration_sec <= 0 or hr_max <= hr_resting or avg_hr <= hr_resting:
        return 0.0

    hr_r = (avg_hr - hr_resting) / (hr_max - hr_resting)
    hr_r = max(0.0, min(1.0, hr_r))

    duration_min = duration_sec / 60.0
    trimp = duration_min * hr_r * 0.64 * math.exp(1.92 * hr_r)
    return round(trimp, 2)


def compute_training_load(
    df: pd.DataFrame,
    hr_params: Dict[str, Any],
) -> Dict[str, Any]:
    """最古のアクティビティ日から最新日までの日次 CTL / ATL / TSB トレーニング負荷を算出

    数式:
        CTL_t = CTL_{t-1} + (TRIMP_t - CTL_{t-1}) / 42  (Fitness, 42日)
        ATL_t = ATL_{t-1} + (TRIMP_t - ATL_{t-1}) / 7   (Fatigue, 7日)
        TSB_t = CTL_{t-1} - ATL_{t-1}                  (Form / コンディション)
    """
    if df.empty:
        return {
            "dates": [],
            "ctl": [],
            "atl": [],
            "tsb": [],
            "daily_trimp": [],
            "latest_ctl": 0.0,
            "latest_atl": 0.0,
            "latest_tsb": 0.0,
            "status_label": "データなし",
            "status_color": "text-slate-400",
            "status_badge": "bg-slate-800 text-slate-400 border-slate-700",
            "status_desc": "トレーニングログがありません。",
        }

    hr_resting = float(hr_params.get("hr_resting", 55))
    hr_max = float(hr_params.get("hr_max", 195))

    # 各アクティビティの TRIMP を計算
    df_load = df.copy()
    daily_trimp_map: Dict[str, float] = {}

    for _, row in df_load.iterrows():
        d_str = row["date_str"]
        dur = float(row["duration_sec"])
        hr = float(row["avg_hr"])
        t = calculate_trimp(dur, hr, hr_resting, hr_max)
        daily_trimp_map[d_str] = daily_trimp_map.get(d_str, 0.0) + t

    # 最古のアクティビティ日から最新日までの全日付カレンダーを作成
    start_dt = df_load["datetime"].min().date()
    end_dt = df_load["datetime"].max().date()

    dates: List[str] = []
    ctl_list: List[float] = []
    atl_list: List[float] = []
    tsb_list: List[float] = []
    trimp_list: List[float] = []

    curr = start_dt
    prev_ctl = 0.0
    prev_atl = 0.0
    is_first = True

    while curr <= end_dt:
        d_str = curr.strftime("%Y-%m-%d")
        t_val = daily_trimp_map.get(d_str, 0.0)

        if is_first:
            ctl = t_val / 42.0
            atl = t_val / 7.0
            tsb = 0.0
            is_first = False
        else:
            tsb = prev_ctl - prev_atl
            ctl = prev_ctl + (t_val - prev_ctl) / 42.0
            atl = prev_atl + (t_val - prev_atl) / 7.0

        dates.append(d_str)
        ctl_list.append(round(ctl, 1))
        atl_list.append(round(atl, 1))
        tsb_list.append(round(tsb, 1))
        trimp_list.append(round(t_val, 1))

        prev_ctl = ctl
        prev_atl = atl
        curr += timedelta(days=1)

    latest_ctl = ctl_list[-1] if ctl_list else 0.0
    latest_atl = atl_list[-1] if atl_list else 0.0
    # 最新ステータスとしてのForm（最新日のトレーニング反映後のコンディション値: CTL - ATL）
    latest_tsb = round(latest_ctl - latest_atl, 1)

    # コンディション評価
    if latest_tsb > 5.0:
        status_label = "フレッシュ / 絶好調"
        status_color = "text-emerald-400"
        status_badge = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
        status_desc = "疲労が抜け、レース本番やタイムアタックに最適なフレッシュなコンディションです。"
    elif -10.0 <= latest_tsb <= 5.0:
        status_label = "最適トレーニング領域 (Optimal)"
        status_color = "text-sky-400"
        status_badge = "bg-sky-500/20 text-sky-300 border-sky-500/40"
        status_desc = "適度な負荷と回復の好循環を維持できています。着実な走力向上が期待できる理想的なトレーニング状態です。"
    elif -30.0 <= latest_tsb < -10.0:
        status_label = "高負荷・疲労蓄積 (Overreaching)"
        status_color = "text-amber-400"
        status_badge = "bg-amber-500/20 text-amber-300 border-amber-500/40"
        status_desc = "負荷が高まっており疲労が蓄積しています。リカバリー走（Z1〜Z2）や休息日を挟んで超回復を促しましょう。"
    else:
        status_label = "オーバートレーニング注意 (Caution)"
        status_color = "text-rose-400"
        status_badge = "bg-rose-500/20 text-rose-300 border-rose-500/40"
        status_desc = "過剰な疲労が蓄積しており怪我・故障のリスクが高まっています。積極的な休養（レスト）を推奨します。"

    return {
        "dates": dates,
        "ctl": ctl_list,
        "atl": atl_list,
        "tsb": tsb_list,
        "daily_trimp": trimp_list,
        "latest_ctl": latest_ctl,
        "latest_atl": latest_atl,
        "latest_tsb": latest_tsb,
        "status_label": status_label,
        "status_color": status_color,
        "status_badge": status_badge,
        "status_desc": status_desc,
    }


def _get_hr_zone_key(hr: float, hr_max: float) -> str:
    """心拍数とHRmaxから心拍ゾーンキー (zone1〜zone5) を判定"""
    if hr <= 0 or hr_max <= 0:
        return "zone1"
    pct = (hr / hr_max) * 100.0
    if pct < 65.0:
        return "zone1"
    elif pct < 76.0:
        return "zone2"
    elif pct < 86.0:
        return "zone3"
    elif pct < 93.0:
        return "zone4"
    else:
        return "zone5"


def compute_zone_distribution(
    df: pd.DataFrame,
    fit_dict: Optional[Dict[str, Any]],
    hr_params: Dict[str, Any],
) -> Dict[str, Any]:
    """心拍ゾーン（Z1〜Z5）の滞在時間および80/20ルール（低強度80% / 高強度20%）強度配分を分析

    - FIT時系列がある場合はサンプル心拍から Z1〜Z5 の秒数を積算
    - FIT時系列がない場合は全走行時間を平均心拍ゾーンに割り当て
    - 全期間および直近4週間の滞在時間（秒数・割合%）を算出
    - 低強度（Z1+Z2）vs 中・高強度（Z3+Z4+Z5）の比率とアドバイスを提示
    """
    hr_max = float(hr_params.get("hr_max", 195))

    empty_result = {
        "all_time": {
            "total_sec": 0,
            "total_time_str": "0時間00分",
            "zones": {f"zone{i}": {"sec": 0, "pct": 0.0, "time_str": "0分"} for i in range(1, 6)},
            "low_intensity_pct": 0.0,
            "high_intensity_pct": 0.0,
            "is_80_20_achieved": False,
            "status_badge": "bg-slate-800 text-slate-400 border-slate-700",
            "status_label": "データなし",
            "advice": "走行データがありません。",
        },
        "recent_4w": {
            "total_sec": 0,
            "total_time_str": "0時間00分",
            "zones": {f"zone{i}": {"sec": 0, "pct": 0.0, "time_str": "0分"} for i in range(1, 6)},
            "low_intensity_pct": 0.0,
            "high_intensity_pct": 0.0,
            "is_80_20_achieved": False,
            "status_badge": "bg-slate-800 text-slate-400 border-slate-700",
            "status_label": "データなし",
            "advice": "直近4週間の走行データがありません。",
        },
        "weekly_zones": [],
    }

    if df.empty:
        return empty_result

    # 直近4週間の境界
    end_dt = df["datetime"].max()
    four_weeks_ago = end_dt - timedelta(days=28)

    all_zone_sec = {f"zone{i}": 0.0 for i in range(1, 6)}
    recent_zone_sec = {f"zone{i}": 0.0 for i in range(1, 6)}

    # 週別集計用
    df_temp = df.copy()
    df_temp["week_str"] = df_temp["datetime"].dt.to_period("W-MON").apply(
        lambda r: r.start_time.strftime("%m/%d週")
    )
    weekly_map: Dict[str, Dict[str, float]] = {}

    for _, row in df.iterrows():
        act_dt = row["datetime"]
        dur_sec = float(row["duration_sec"])
        if dur_sec <= 0:
            continue

        week_key = act_dt.to_period("W-MON").start_time.strftime("%m/%d週")
        if week_key not in weekly_map:
            weekly_map[week_key] = {f"zone{i}": 0.0 for i in range(1, 6)}

        is_recent = act_dt >= four_weeks_ago

        # FITファイルの照合
        date_key = row["datetime"].strftime("%Y-%m-%d %H:%M:%S")
        date_day = row["date_str"]
        fit_entry = None
        if fit_dict:
            fit_entry = fit_dict.get(date_key) or fit_dict.get(date_day)

        if fit_entry and fit_entry.get("heart_rates"):
            hr_list = fit_entry["heart_rates"]
            pts_count = len(hr_list)
            if pts_count > 0:
                sec_per_pt = dur_sec / pts_count
                for h in hr_list:
                    z = _get_hr_zone_key(float(h), hr_max)
                    all_zone_sec[z] += sec_per_pt
                    if is_recent:
                        recent_zone_sec[z] += sec_per_pt
                    weekly_map[week_key][z] += sec_per_pt
            else:
                # サンプルが空の場合のフォールバック
                z = _get_hr_zone_key(float(row["avg_hr"]), hr_max)
                all_zone_sec[z] += dur_sec
                if is_recent:
                    recent_zone_sec[z] += dur_sec
                weekly_map[week_key][z] += dur_sec
        else:
            # FIT時系列がない場合: 平均心拍ゾーンに全時間を割り当て
            z = _get_hr_zone_key(float(row["avg_hr"]), hr_max)
            all_zone_sec[z] += dur_sec
            if is_recent:
                recent_zone_sec[z] += dur_sec
            weekly_map[week_key][z] += dur_sec

    def _summarize_zones(zone_sec_dict: Dict[str, float]) -> Dict[str, Any]:
        total_sec = sum(zone_sec_dict.values())
        hours = int(total_sec // 3600)
        minutes = int((total_sec % 3600) // 60)
        total_time_str = f"{hours}時間{minutes:02d}分"

        zones_summary = {}
        for i in range(1, 6):
            zk = f"zone{i}"
            s = zone_sec_dict[zk]
            pct = round((s / total_sec * 100.0), 1) if total_sec > 0 else 0.0
            z_min = int(round(s / 60.0))
            zones_summary[zk] = {
                "sec": int(round(s)),
                "pct": pct,
                "time_str": f"{z_min}分",
            }

        low_pct = round(zones_summary["zone1"]["pct"] + zones_summary["zone2"]["pct"], 1)
        high_pct = round(100.0 - low_pct, 1)
        is_achieved = low_pct >= 80.0

        if low_pct >= 80.0:
            status_badge = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
            status_label = "80/20 ルール達成 (理想的配分)"
            advice = f"低強度（Z1+Z2）が {low_pct}% を占めており、怪我を防ぎながら有酸素基盤を最大化する理想的なポラライズド・トレーニングを実践できています。"
        elif low_pct >= 70.0:
            status_badge = "bg-amber-500/20 text-amber-300 border-amber-500/40"
            status_label = "中・高強度やや多め"
            advice = f"低強度の割合が {low_pct}% です。ジョグ（Eペース/Z2）をよりリラックスして走り、低強度比率80%以上を目指すと疲労の抜けが劇的に改善します。"
        else:
            status_badge = "bg-rose-500/20 text-rose-300 border-rose-500/40"
            status_label = "高強度過多 (疲労・怪我注意)"
            advice = f"中・高強度（Z3以上）が {high_pct}% を占めています。慢性疲労やランナー膝などの障害リスクが高まるため、ゆっくり走るイージージョグ（Z1〜Z2）の割合を増やしましょう。"

        return {
            "total_sec": int(round(total_sec)),
            "total_time_str": total_time_str,
            "zones": zones_summary,
            "low_intensity_pct": low_pct,
            "high_intensity_pct": high_pct,
            "is_80_20_achieved": is_achieved,
            "status_badge": status_badge,
            "status_label": status_label,
            "advice": advice,
        }

    all_time_summary = _summarize_zones(all_zone_sec)
    recent_4w_summary = _summarize_zones(recent_zone_sec)

    # 週別推移（直近8〜12週）
    weekly_zones_list = []
    # 週の時系列順
    sorted_weeks = sorted(weekly_map.keys())[-10:]
    for w in sorted_weeks:
        w_dict = weekly_map[w]
        w_total = sum(w_dict.values())
        z1_m = round(w_dict["zone1"] / 60.0, 1)
        z2_m = round(w_dict["zone2"] / 60.0, 1)
        z3_m = round(w_dict["zone3"] / 60.0, 1)
        z4_m = round(w_dict["zone4"] / 60.0, 1)
        z5_m = round(w_dict["zone5"] / 60.0, 1)
        low_p = round(((w_dict["zone1"] + w_dict["zone2"]) / w_total * 100.0), 1) if w_total > 0 else 0.0
        weekly_zones_list.append({
            "week": w,
            "zone1_min": z1_m,
            "zone2_min": z2_m,
            "zone3_min": z3_m,
            "zone4_min": z4_m,
            "zone5_min": z5_m,
            "total_min": round(w_total / 60.0, 1),
            "low_intensity_pct": low_p,
        })

    return {
        "all_time": all_time_summary,
        "recent_4w": recent_4w_summary,
        "weekly_zones": weekly_zones_list,
    }
