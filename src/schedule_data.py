from datetime import date, datetime
from typing import Dict, Any, List
import pandas as pd


# 42日間のマスタープラン定義 (2026-10-26 〜 2026-12-06)
RAW_SCHEDULE_PLAN = [
    # --- Week 1 (10/26〜11/01) ---
    {
        "date": "2026-10-26",
        "category": "point",
        "menu": "8km ビルドアップ走",
        "detail": "3kmアップ ➔ 4km加速 (5:32→4:58/km) ➔ 1kmダウン",
        "target_pace": "5:30 ➔ 4:58/km",
        "target_hr": "HR 160 ➔ 186 bpm",
        "purpose": "スピード刺激注入。Lap7でサブ50（5:00/km）を突破するキレを確認",
        "location": "那覇",
    },
    {
        "date": "2026-10-27",
        "category": "rest",
        "menu": "完全休養",
        "detail": "超回復・温冷交代浴・下肢ストレッチ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "ビルドアップ走の筋疲労抜き",
        "location": "那覇",
    },
    {
        "date": "2026-10-28",
        "category": "swim",
        "menu": "完全休養 / リカバリースイム",
        "detail": "ジムプール 1,150m (アップ150m ＋ クロール20往復1,000m)",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "着地衝撃ゼロで肩甲骨・体幹・股関節をほぐすアクティブリフレッシュ",
        "location": "那覇",
    },
    {
        "date": "2026-10-29",
        "category": "point",
        "menu": "8.32km LTテンポ巡航走 ＋ 流し2本",
        "detail": "3kmアップ ➔ 5km LT巡航 (5:37/km) ➔ ラスト流し100m×2本 (最速3:20/km)",
        "target_pace": "5:25〜5:35/km",
        "target_hr": "心拍上限 172 bpm キャップ",
        "purpose": "心拍キャップ制の遵守。乳酸クリアランス向上＆フォームのバネ改善",
        "location": "那覇",
    },
    {
        "date": "2026-10-30",
        "category": "kanto",
        "menu": "関東出社・移動（完全アクティブレスト）",
        "detail": "羽田オフィス出社・日常歩行のみ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "ラン完全オフ。移動と日常歩行で心筋・毛細血管のリモデリング",
        "location": "関東",
    },
    {
        "date": "2026-10-31",
        "category": "kanto",
        "menu": "関東滞在（完全アクティブレスト）",
        "detail": "ラン完全オフ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "積極的休養・リフレッシュ",
        "location": "関東",
    },
    {
        "date": "2026-11-01",
        "category": "kanto",
        "menu": "関東滞在（完全アクティブレスト）",
        "detail": "ラン完全オフ・入浴ストレッチ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "積極的休養・リフレッシュ",
        "location": "関東",
    },

    # --- Week 2 (11/02〜11/08) ---
    {
        "date": "2026-11-02",
        "category": "kanto",
        "menu": "関東滞在 ➔ 那覇帰着（完全アクティブレスト）",
        "detail": "フライト移動・完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "移動疲れを残さず、翌日からの那覇練習に備える",
        "location": "関東➔那覇",
    },
    {
        "date": "2026-11-03",
        "category": "point",
        "menu": "8.32km LTテンポ巡航走 ＋ 流し2本",
        "detail": "3kmアップ ➔ 5km LT巡航 (5:28/km) ➔ ラスト流し100m×2本 (最速3:32/km)",
        "target_pace": "5:25〜5:35/km",
        "target_hr": "心拍上限 172 bpm キャップ",
        "purpose": "4日休養明け。心拍171bpmでキロ9秒短縮し、ヨロンサブ2目標を完全手懐け",
        "location": "那覇",
    },
    {
        "date": "2026-11-04",
        "category": "rest",
        "menu": "完全休養 または リカバリースイム",
        "detail": "ジムプール 1,000m 前後（任意）",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "LT走の疲労抜き＆翌日の長距離LSDに向けた脚の温存",
        "location": "那覇",
    },
    {
        "date": "2026-11-05",
        "category": "long",
        "menu": "平日夕方 長距離LSD（15〜18km）",
        "detail": "18:00出走 ➔ 20:30帰宅即入浴 ➔ 20:30〜浴室乾燥機 (翌朝05:00完了・問題なし)",
        "target_pace": "7:30〜8:00/km",
        "target_hr": "心拍 135〜145 bpm (Zone 2)",
        "purpose": "低心拍の維持・毛細血管拡張。週末の関東休養に向けてしっかり踏み切る",
        "location": "那覇",
    },
    {
        "date": "2026-11-06",
        "category": "kanto",
        "menu": "羽田移動・出社（完全アクティブレスト）",
        "detail": "羽田オフィス出社・日常歩行のみ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "LSDの疲労を超回復へ導く完全オフ",
        "location": "関東",
    },
    {
        "date": "2026-11-07",
        "category": "kanto",
        "menu": "関東滞在（完全アクティブレスト）",
        "detail": "ちゃんぷる〜フェス＆同窓会参加（ラン完全オフ）",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "リフレッシュ・完全休養",
        "location": "関東",
    },
    {
        "date": "2026-11-08",
        "category": "kanto",
        "menu": "関東滞在 ➔ 那覇帰着（完全アクティブレスト）",
        "detail": "フライト移動・完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "翌週の最重要強化週に向けてエネルギーを完全充填",
        "location": "関東➔那覇",
    },

    # --- Week 3 (11/09〜11/15) 🔥 最重要強化週（関東宿泊なし） ---
    {
        "date": "2026-11-09",
        "category": "rest",
        "menu": "完全休養",
        "detail": "ストレッチ・睡眠",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "最重要週の立ち上げ準備",
        "location": "那覇",
    },
    {
        "date": "2026-11-10",
        "category": "point",
        "menu": "7km インターバル走 (1000m × 3本)",
        "detail": "3kmアップ ➔ 1000m×3本 (4:50/km・間疾走ジョグ400m) ➔ 1kmダウン",
        "target_pace": "4:45〜4:55/km",
        "target_hr": "Zone 5 (VO2max刺激)",
        "purpose": "心肺の天井を押し上げ、巡航時の余裕度（酸素摂取能力）を高める",
        "location": "那覇",
    },
    {
        "date": "2026-11-11",
        "category": "rest",
        "menu": "完全休養 または リカバリースイム",
        "detail": "プール 800〜1,000m（任意）",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "インターバルの強い筋疲労抜き",
        "location": "那覇",
    },
    {
        "date": "2026-11-12",
        "category": "easy",
        "menu": "有酸素イージージョグ 6〜8km ＋ 流し2本",
        "detail": "平日夕方18:00出走 ➔ 5:50〜6:10/km ➔ 流し100m×2本",
        "target_pace": "5:50〜6:10/km",
        "target_hr": "心拍 135〜145 bpm (Zone 2)",
        "purpose": "日曜の最長LSDに向けたフォーム・つなぎ調整",
        "location": "那覇",
    },
    {
        "date": "2026-11-13",
        "category": "kanto",
        "menu": "日帰り羽田出社（完全アクティブレスト）",
        "detail": "日帰り出社・新幹線/航空機移動",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "移動のみ。脚を使わず温存",
        "location": "関東日帰り",
    },
    {
        "date": "2026-11-14",
        "category": "rest",
        "menu": "完全休養",
        "detail": "炭水化物・水分補給、早め就寝",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "翌日の本番前最長走に向けたグリコーゲン満タン化",
        "location": "那覇",
    },
    {
        "date": "2026-11-15",
        "category": "long",
        "menu": "🔥【最重要ピーク】プログレッシブLSD 18〜20km",
        "detail": "3kmアップ ➔ 10〜12km Zone 2 ➔ 後半5km Mペース (6:05/km)",
        "target_pace": "前半 7:30〜8:00 ➔ 後半 6:05/km",
        "target_hr": "135〜145 ➔ 155 bpm",
        "purpose": "本番前最長走。NAHAフル後半（30km以降）のエネルギー枯渇耐性を完成させる",
        "location": "那覇",
    },

    # --- Week 4 (11/16〜11/22) テーパリング開始 ---
    {
        "date": "2026-11-16",
        "category": "rest",
        "menu": "完全休養",
        "detail": "超回復・テーパリング（疲労抜き期間）突入",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "20km LSDの筋損傷修復",
        "location": "那覇",
    },
    {
        "date": "2026-11-17",
        "category": "easy",
        "menu": "疲労抜きジョグ 5〜6km ＋ 流し1本",
        "detail": "平日夕方出走 ➔ 6:00/km 前後 ➔ 流し100m×1本",
        "target_pace": "6:00/km 前後",
        "target_hr": "心拍 130〜140 bpm",
        "purpose": "血流を促して疲労物質を除去",
        "location": "那覇",
    },
    {
        "date": "2026-11-18",
        "category": "rest",
        "menu": "完全休養 または リカバリースイム",
        "detail": "完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "超回復",
        "location": "那覇",
    },
    {
        "date": "2026-11-19",
        "category": "point",
        "menu": "10km ビルドアップ走",
        "detail": "3kmアップ ➔ 6km 段階加速 (5:30 ➔ 5:05/km) ➔ 1kmダウン",
        "target_pace": "5:30 ➔ 5:05/km",
        "target_hr": "165 ➔ 180 bpm",
        "purpose": "レース10日前のキレ研ぎ。サブ50ペースのスピード感を再確認",
        "location": "那覇",
    },
    {
        "date": "2026-11-20",
        "category": "kanto",
        "menu": "羽田移動・出社（完全アクティブレスト）",
        "detail": "羽田オフィス出社・日常歩行のみ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "完全休養",
        "location": "関東",
    },
    {
        "date": "2026-11-21",
        "category": "kanto",
        "menu": "関東滞在 ➔ 那覇帰着（完全アクティブレスト）",
        "detail": "フライト移動・完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "移動・休養",
        "location": "関東➔那覇",
    },
    {
        "date": "2026-11-22",
        "category": "easy",
        "menu": "8km 快調走（レース1週前）",
        "detail": "3kmアップ ➔ 5km 5:45/km巡航",
        "target_pace": "5:45/km 前後",
        "target_hr": "心拍 160〜165 bpm",
        "purpose": "ヨロンハーフ1週間前。巡航リズムと接地感覚を最終確認",
        "location": "那覇",
    },

    # --- Week 5 (11/23〜11/29) 🏁 ヨロンマラソン本番週 ---
    {
        "date": "2026-11-23",
        "category": "rest",
        "menu": "完全休養",
        "detail": "祝日・脚の温存",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "レース週入り。エネルギー充填",
        "location": "那覇",
    },
    {
        "date": "2026-11-24",
        "category": "easy",
        "menu": "5km 調整ジョグ ＋ 流し3本",
        "detail": "平日夕方 ➔ 6:00/km 前後 ➔ 流し100m×3本",
        "target_pace": "6:00/km",
        "target_hr": "Zone 1〜2",
        "purpose": "脱力と神経筋の最終活性化（バネの目覚まし）",
        "location": "那覇",
    },
    {
        "date": "2026-11-25",
        "category": "rest",
        "menu": "完全休養",
        "detail": "与論島遠征の荷造り・水分補給",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "水分・電解質補給",
        "location": "那覇",
    },
    {
        "date": "2026-11-26",
        "category": "easy",
        "menu": "4km 最終刺激確認",
        "detail": "3kmアップ ➔ 1km 5:30/km（本番ペース体感）",
        "target_pace": "5:30/km",
        "target_hr": "心拍 166〜170 bpm",
        "purpose": "本番ペースの感覚を体にインプットして終了",
        "location": "那覇",
    },
    {
        "date": "2026-11-27",
        "category": "race",
        "menu": "🚢 与論島へフェリー移動",
        "detail": "移動・完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "移動疲れ防止・リラックス",
        "location": "那覇➔与論島",
    },
    {
        "date": "2026-11-28",
        "category": "race",
        "menu": "与論島滞在（前日受付）",
        "detail": "コース下見・前日受付・カーボローディング・早め就寝",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "決戦準備完了",
        "location": "与論島",
    },
    {
        "date": "2026-11-29",
        "category": "race",
        "menu": "🏁【決戦】ヨロンマラソン ハーフ (21.0975km)",
        "detail": "目標：1:55:00〜1:59:59【サブ2達成！】(5:27〜5:38/km・HR 166〜170bpm)",
        "target_pace": "5:27〜5:38/km",
        "target_hr": "心拍 166〜170 bpm",
        "purpose": "LT走172bpmキャップの成果を爆発させ、イーブンペースでサブ2奪取！",
        "location": "与論島",
    },

    # --- Week 6 (11/30〜12/06) 👑 NAHAマラソン本番週 ---
    {
        "date": "2026-11-30",
        "category": "rest",
        "menu": "🚢 与論島 ➔ 那覇帰還",
        "detail": "アイシング・抗炎症ケア・完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "ハーフの筋肉ダメージ修復",
        "location": "与論島➔那覇",
    },
    {
        "date": "2026-12-01",
        "category": "rest",
        "menu": "完全休養",
        "detail": "睡眠・タンパク質補給",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "フル本番に向けた超回復",
        "location": "那覇",
    },
    {
        "date": "2026-12-02",
        "category": "easy",
        "menu": "3km 超スロージョグ",
        "detail": "6:30〜7:00/km（完全脱力）",
        "target_pace": "6:30〜7:00/km",
        "target_hr": "心拍 125〜135 bpm",
        "purpose": "ハーフの疲労抜け・脚の軽さ確認",
        "location": "那覇",
    },
    {
        "date": "2026-12-03",
        "category": "rest",
        "menu": "完全休養",
        "detail": "カーボローディング（高炭水化物食）開始",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "肝臓・筋肉のグリコーゲン蓄積",
        "location": "那覇",
    },
    {
        "date": "2026-12-04",
        "category": "easy",
        "menu": "2km 軽ジョグ ＋ 流し1本",
        "detail": "ジョグ ➔ 100m流し1本（脱力）",
        "target_pace": "イージー",
        "target_hr": "心拍軽く上昇",
        "purpose": "最終刺激。心拍を軽く一度上げて呼吸筋を活性化",
        "location": "那覇",
    },
    {
        "date": "2026-12-05",
        "category": "race",
        "menu": "完全休養・前日受付",
        "detail": "奥武山公園で受付・ゼッケン装着・睡眠最優先",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "フルマラソン決戦準備",
        "location": "那覇",
    },
    {
        "date": "2026-12-06",
        "category": "race",
        "menu": "👑【決戦】NAHAマラソン フル (42.195km)",
        "detail": "目標：4:15:00〜4:30:00【サブ4.5達成！】(6:00〜6:25/km・HR 150〜156bpm)",
        "target_pace": "6:00〜6:25/km",
        "target_hr": "心拍 150〜156 bpm",
        "purpose": "20km LSDとヨロンハーフで鍛え上げた有酸素エンジンで完走＆サブ4.5！",
        "location": "那覇",
    },
]


def prepare_full_schedule(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Activities.csv の実走ログと照合し、42日間の進捗と実績をマッピングした全スケジュールを返す"""
    # 日付ごとのアクティビティ集計
    act_map = {}
    if not df.empty:
        for _, row in df.iterrows():
            d_str = row["日付"][:10]
            # ランニングのサマリー
            act_map[d_str] = {
                "distance_km": row["距離"],
                "duration_str": row["タイム"],
                "pace_str": row["平均ペース"],
                "avg_hr": int(row["平均心拍数"]) if pd.notnull(row["平均心拍数"]) else None,
                "max_hr": int(row["最大心拍数"]) if pd.notnull(row["最大心拍数"]) else None,
                "shoe": row.get("シューズ") if pd.notnull(row.get("シューズ")) else "",
            }

    today_str = date.today().strftime("%Y-%m-%d")
    latest_run_str = df["日付"].max()[:10] if not df.empty else today_str
    # 基準日は本日または最新走日
    current_ref_str = max(today_str, latest_run_str)

    weekdays_jp = ["月", "火", "水", "木", "金", "土", "日"]

    schedule = []
    for item in RAW_SCHEDULE_PLAN:
        d_str = item["date"]
        d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
        w_jp = weekdays_jp[d_obj.weekday()]

        has_run = d_str in act_map
        actual = act_map.get(d_str)

        # ステータス判定
        if d_str == current_ref_str:
            status = "today"
            status_badge = "📍 本日"
            badge_color = "bg-indigo-500/20 text-indigo-300 border-indigo-500/40"
        elif d_str < current_ref_str:
            status = "done"
            status_badge = "✅ 完了"
            badge_color = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
        else:
            status = "upcoming"
            if item["category"] == "race":
                status_badge = "🏁 決戦"
                badge_color = "bg-rose-500/20 text-rose-300 border-rose-500/40"
            elif item["category"] == "kanto":
                status_badge = "✈️ 関東"
                badge_color = "bg-slate-800 text-slate-400 border-slate-700"
            elif item["category"] in ["point", "long"]:
                status_badge = "🔥 ポイント"
                badge_color = "bg-amber-500/20 text-amber-300 border-amber-500/30"
            elif item["category"] == "swim":
                status_badge = "🏊 スイム"
                badge_color = "bg-cyan-500/20 text-cyan-300 border-cyan-500/30"
            else:
                status_badge = "🌱 予定"
                badge_color = "bg-slate-800 text-slate-300 border-slate-700"

        # カテゴリ表示用
        cat_badge = {
            "point": ("🔥 ポイント走", "text-amber-400"),
            "long": ("🌟 ロングLSD", "text-emerald-400"),
            "easy": ("🌱 ジョグ・調整", "text-sky-400"),
            "rest": ("🛌 完全休養", "text-slate-400"),
            "swim": ("🏊 水泳・アクティブ", "text-cyan-400"),
            "kanto": ("✈️ 関東遠征", "text-purple-400"),
            "race": ("🏁 レース本番", "text-rose-400"),
        }.get(item["category"], ("その他", "text-slate-400"))

        entry = {
            "date": d_str,
            "date_display": f"{d_obj.month}/{d_obj.day} ({w_jp})",
            "weekday": w_jp,
            "is_weekend": w_jp in ["土", "日"],
            "status": status,
            "status_badge": status_badge,
            "badge_color": badge_color,
            "category": item["category"],
            "category_label": cat_badge[0],
            "category_color": cat_badge[1],
            "menu": item["menu"],
            "detail": item["detail"],
            "target_pace": item["target_pace"],
            "target_hr": item["target_hr"],
            "purpose": item["purpose"],
            "location": item["location"],
            "has_run": has_run,
            "actual": actual,
        }
        schedule.append(entry)

    return schedule
