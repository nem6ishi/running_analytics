import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from .parser import seconds_to_pace_str, seconds_to_time_str


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


def calculate_activity_insights(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """全アクティビティに対して詳細な分析・評価・提案（コーチング）データを生成"""
    insights_list = []
    total_runs = len(df)

    # 全体統計の事前計算（基準用）
    best_pace_sec = df["avg_pace_sec"].min()
    longest_dist = df["distance_km"].max()
    avg_dataset_cadence = df["avg_cadence"].mean()

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

        # 1. 心拍ゾーン判定
        hr_zone = get_hr_zone(avg_hr)

        # 2. 速度・有酸素効率 (AEI: Speed / HR * 100)
        speed_kmh = (3600.0 / pace_sec) if pace_sec > 0 else 0.0
        aei = (speed_kmh / avg_hr * 100.0) if avg_hr > 0 else 0.0

        # 3. 多角評価スコア (0-100)
        # スピードスコア: 4:30 (270s) を100点、6:30 (390s) を60点とするスケーリング
        speed_score = max(50.0, min(100.0, 100.0 - (pace_sec - 300) * 0.4))

        # 持久・ボリュームスコア: 10km以上を95-100点、5kmを75点、2.5kmを60点
        endurance_score = max(50.0, min(100.0, 50.0 + (dist * 4.8)))

        # フォームスコア: ピッチ174-178spmを100点、乖離に応じて減点
        cadence_diff = abs(cadence - 176)
        form_score = max(60.0, min(100.0, 100.0 - (cadence_diff * 4.0)))

        # 心肺効率スコア: aei = 6.8 を100点、5.5を70点
        aerobic_score = max(50.0, min(100.0, 50.0 + (aei - 5.0) * 28.0))

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

        # 4. バッジ付与
        badges = []
        if pace_sec <= best_pace_sec + 3:
            badges.append({"name": "最速ペース", "icon": "⚡", "type": "gold"})
        if dist >= longest_dist - 0.1:
            badges.append({"name": "最長10km走破", "icon": "🏃", "type": "indigo"})
        if cadence >= 175:
            badges.append({"name": "ハイケイデンス (175spm+)", "icon": "🎯", "type": "teal"})
        if avg_hr >= 174:
            badges.append({"name": "高負荷LTセッション", "icon": "🔥", "type": "orange"})
        if aei >= 6.4:
            badges.append({"name": "高い有酸素効率", "icon": "💎", "type": "cyan"})
        if stride >= 1.08:
            badges.append({"name": "ダイナミックストライド", "icon": "🚀", "type": "purple"})

        # 5. 前回ランとの比較
        prev_diff = None
        if i > 0:
            prev_row = df.iloc[i - 1]
            p_pace_diff = pace_sec - prev_row["avg_pace_sec"]  # 負なら速くなった
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

        # 6. コーチング分析・評価・提案コメント生成
        # 分析サマリー
        analysis_summary = (
            f"走行距離 **{dist:.2f} km** を平均ペース **{pace_str}/km** で完走。"
            f"平均心拍数は **{avg_hr} bpm**（最大 {max_hr} bpm）で、運動強度は【**{hr_zone['name']}（{hr_zone['intensity']}）**】に該当します。"
        )

        # 評価コメント (Good points & Notice points)
        good_points = []
        notice_points = []

        if cadence >= 172:
            good_points.append(
                f"平均ピッチ **{cadence} spm** とリズムが極めて良好です。着地衝撃を分散し、足腰への負担を軽減できています。"
            )
        else:
            notice_points.append(
                f"平均ピッチは **{cadence} spm** です。ストライドが伸びすぎないよう、骨盤の真下への接地を意識してピッチを172〜176前後に高めるとさらに省エネになります。"
            )

        if stride >= 1.05:
            good_points.append(
                f"平均歩幅 **{stride:.2f} m** と大きなストライドで力強い推進力が得られています。"
            )

        if avg_hr >= 173:
            good_points.append(
                "心肺機能・乳酸耐性を高める非常に刺激的な高強度トレーニングとなりました。"
            )
            notice_points.append(
                "心肺・筋肉への負荷が非常に高いセッションです。心拍が高止まりしているため、しっかりとした休息が必要です。"
            )
        elif avg_hr > 0 and avg_hr < 165:
            good_points.append(
                "心拍が安定しており、有酸素ベースの強化・毛細血管の発達に適した理想的なコントロールができています。"
            )

        if prev_diff and prev_diff["pace_improved"] and abs(prev_diff["pace_diff_sec"]) >= 5:
            good_points.append(
                f"前回（{prev_diff['date']}）よりペースが **{abs(int(prev_diff['pace_diff_sec']))}秒/km 短縮** され、着実なスピード強化が見られます！"
            )

        # 提案 (次回メニュー、フォーム意識、リカバリー)
        if avg_hr >= 172 or dist >= 10.0:
            next_menu_title = "アクティブリカバリー または 5km イージージョグ"
            next_menu_desc = (
                "今回は心肺・筋肉ともに高い負荷（Zone 4〜5）がかかりました。疲労を抜いて毛細血管の新生を促すため、"
                "次回は **心拍数 135〜145 bpm 前後** を意識した **ゆっくりとしたおしゃべりペース（6:15〜6:30/km、4〜5km）** を強く推奨します。"
            )
            recovery_hours = "36〜48時間"
            recovery_tips = "ふくらはぎと股関節の入念なストレッチ、十分な水分・たんぱく質の補給、質の高い睡眠を心がけましょう。"
        elif dist <= 5.0 and pace_sec > 330:
            next_menu_title = "ステップアップ走 (6〜7km) または ビルドアップ走"
            next_menu_desc = (
                "疲労の蓄積は穏やかです。次回は **走行距離を1〜2km伸ばす（6〜7km）** か、"
                "ラスト1kmだけ気持ちよくペースアップする **ビルドアップ走** に挑戦すると、持久力とスピード感覚が一段引き上がります。"
            )
            recovery_hours = "24〜36時間"
            recovery_tips = "足裏とアキレス腱周りを軽くほぐし、翌日または翌々日にはリフレッシュして走れる状態を整えましょう。"
        else:
            next_menu_title = "テンポ走 (6km) または 8〜10km ペース走"
            next_menu_desc = (
                "バランスの良いトレーニングができています。次回は **現在の安定したピッチ（174spm前後）を維持したまま、"
                "同じペースで少し距離を延ばすペース走** を行うと、マラソンに向けた確実な脚作りにつながります。"
            )
            recovery_hours = "24〜48時間"
            recovery_tips = "ランニング後のアイシングや股関節モビリティ運動を行い、疲労の持ち越しを防ぎましょう。"

        item = {
            "id": i,
            "date": date_str,
            "time_of_day": row["time_of_day"],
            "title": row["タイトル"],
            "distance_km": dist,
            "duration_str": row["duration_str"],
            "duration_sec": duration_sec,
            "pace_str": pace_str,
            "pace_sec": pace_sec,
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
            "total_score": total_score,
            "rank": rank,
            "rank_class": rank_class,
            "radar_scores": {
                "speed": round(speed_score),
                "endurance": round(endurance_score),
                "aerobic": round(aerobic_score),
                "form": round(form_score),
            },
            "badges": badges,
            "prev_diff": prev_diff,
            "analysis_summary": analysis_summary,
            "good_points": good_points,
            "notice_points": notice_points,
            "suggestion": {
                "menu_title": next_menu_title,
                "menu_desc": next_menu_desc,
                "recovery_hours": recovery_hours,
                "recovery_tips": recovery_tips,
            },
        }
        insights_list.append(item)

    return insights_list
