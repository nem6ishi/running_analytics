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
        "menu": "遠征・移動（完全アクティブレスト）",
        "detail": "ラン完全オフ・日常歩行のみ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "ラン完全オフ。移動と日常歩行で心筋・毛細血管のリモデリング",
        "location": "遠征先",
    },
    {
        "date": "2026-10-31",
        "category": "kanto",
        "menu": "遠征滞在（完全アクティブレスト）",
        "detail": "ラン完全オフ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "積極的休養・リフレッシュ",
        "location": "遠征先",
    },
    {
        "date": "2026-11-01",
        "category": "kanto",
        "menu": "遠征滞在（完全アクティブレスト）",
        "detail": "ラン完全オフ・入浴ストレッチ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "積極的休養・リフレッシュ",
        "location": "遠征先",
    },

    # --- Week 2 (11/02〜11/08) ---
    {
        "date": "2026-11-02",
        "category": "kanto",
        "menu": "移動日（完全アクティブレスト）",
        "detail": "移動・完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "移動疲れを残さず、翌日からの練習に備える",
        "location": "移動日",
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
        "detail": "プール 1,000m 前後（任意）",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "LT走の疲労抜き＆翌日の長距離LSDに向けた脚の温存",
        "location": "那覇",
    },
    {
        "date": "2026-11-05",
        "category": "long",
        "menu": "【完了】21.22km 本格LSD（平均心拍145bpm Zone2死守＆ラスト3:55/km 👑）",
        "detail": "2時間41分走破 ➔ 雨上がりの公園周回で終始Zone 2徹底制御 ➔ ラスト220mスプリント3:55/km",
        "target_pace": "7:36/km",
        "target_hr": "平均 145 bpm (最大 180 bpm)",
        "purpose": "ハーフ完走距離を達成。有酸素エンジン・毛細血管拡張と時間耐久を完全クリア",
        "location": "那覇",
    },
    {
        "date": "2026-11-06",
        "category": "kanto",
        "menu": "遠征・移動（完全アクティブレスト）",
        "detail": "ラン完全オフ・日常歩行のみ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "LSDの疲労を超回復へ導く完全オフ",
        "location": "遠征先",
    },
    {
        "date": "2026-11-07",
        "category": "kanto",
        "menu": "遠征滞在（完全アクティブレスト）",
        "detail": "ラン完全オフ・休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "リフレッシュ・完全休養",
        "location": "遠征先",
    },
    {
        "date": "2026-11-08",
        "category": "kanto",
        "menu": "移動日（完全アクティブレスト）",
        "detail": "移動・完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "翌週の最重要強化週に向けてエネルギーを完全充填",
        "location": "移動日",
    },

    # --- Week 3 (11/09〜11/15) 🔥 最重要強化週（移動宿泊なし） ---
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
        "menu": "【完了】🔥 1km交代走×3本（疾走 4:38 ➔ 4:29 ➔ 4:20/km 圧倒的爆発力！👑）",
        "detail": "3kmアップ (6:00➔5:40➔5:35) ➔ 1km疾走(4:38/4:29/4:20) ⇄ つなぎ(5:48/5:50/5:39) ➔ 10km全体53:25 (5:20/km) HR167",
        "target_pace": "疾走 4:38➔4:29➔4:20/km / つなぎ 5:48➔5:50➔5:39/km",
        "target_hr": "平均 167 bpm (最大 187 bpm)",
        "purpose": "想定4:55を大幅粉砕し最速4:20/km！動的目標【レベルA：絶好調】を達成し、ヨロンサブ1:55＆10km48〜49分台が完全視野へ！",
        "location": "那覇",
    },
    {
        "date": "2026-11-11",
        "category": "rest",
        "menu": "完全休養 または リカバリースイム",
        "detail": "プール 800〜1,000m（任意）",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "流しで使った神経系と筋肉のリフレッシュ",
        "location": "那覇",
    },
    {
        "date": "2026-11-12",
        "category": "easy",
        "menu": "有酸素イージージョグ 6〜8km ＋ 流し2本",
        "detail": "夕方出走 ➔ 5:50〜6:10/km ➔ 流し100m×2本",
        "target_pace": "5:50〜6:10/km",
        "target_hr": "心拍 135〜145 bpm (Zone 2)",
        "purpose": "日曜の実戦Mペース走に向けたフォーム・つなぎ調整",
        "location": "那覇",
    },
    {
        "date": "2026-11-13",
        "category": "kanto",
        "menu": "移動日（完全アクティブレスト）",
        "detail": "移動日・ラン完全オフ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "移動のみ。脚を使わず温存",
        "location": "移動日",
    },
    {
        "date": "2026-11-14",
        "category": "rest",
        "menu": "完全休養",
        "detail": "炭水化物・水分補給、早め就寝",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "翌日の実戦Mペース走に向けたグリコーゲン満タン化",
        "location": "那覇",
    },
    {
        "date": "2026-11-15",
        "category": "long",
        "menu": "🌟【最重要実戦走】16〜18km Mペース持続走（フル本番シミュレーション）",
        "detail": "3kmアップ（6:45〜7:00/km） ➔ 11〜13km Mペース巡航（6:00〜6:15/km・心拍150〜155bpm） ➔ ラスト2kmフリー（5:50〜6:00/km）",
        "target_pace": "6:00〜6:15/km (Mペース巡航)",
        "target_hr": "150〜155 bpm (Zone 3)",
        "purpose": "NAHAフル本番巡航ペース（6:05/km）を完全インストール。5km電解質給水＆10kmジェル補給で心拍ドリフト防止を実戦検証！",
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
        "detail": "夕方出走 ➔ 6:00/km 前後 ➔ 流し100m×1本",
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
        "menu": "遠征・移動（完全アクティブレスト）",
        "detail": "ラン完全オフ・日常歩行のみ",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "完全休養",
        "location": "遠征先",
    },
    {
        "date": "2026-11-21",
        "category": "kanto",
        "menu": "移動日（完全アクティブレスト）",
        "detail": "移動・完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "移動・休養",
        "location": "移動日",
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
        "menu": "4km 最終刺激入れ ＋ 流し2本",
        "detail": "平日夕方 ➔ 3kmアップ ➔ 1km 5:30/km（本番ペース確認） ➔ 流し100m×2本",
        "target_pace": "5:30/km",
        "target_hr": "心拍 160〜168 bpm",
        "purpose": "本番ペース感覚と神経筋のバネを刺激。前倒しでレース前刺激を完了させる",
        "location": "那覇",
    },
    {
        "date": "2026-11-27",
        "category": "rest",
        "menu": "完全休養（走る場合は早朝2〜3km軽ジョグ・任意）",
        "detail": "走るなら朝サクッと散歩ジョグ（省略可） ➔ 翌朝フェリーに向けた荷造り・水分・糖質補給",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "エネルギー蓄積・翌朝07:00発フェリーに向けた前々日完全超回復",
        "location": "那覇",
    },
    {
        "date": "2026-11-28",
        "category": "race",
        "menu": "🚢 那覇 ➔ 与論島フェリー移動（07:00発 ➔ 11:50着）",
        "detail": "マリックスライン乗船 ➔ 与論島到着・前日受付・コース下見・早め就寝",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "決戦前日の体調・メンタル調整完了",
        "location": "那覇➔与論島",
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
        "menu": "🚢 与論島 ➔ 那覇フェリー帰還（14:10発 ➔ 19:00着）",
        "detail": "マルエーフェリー乗船 ➔ 那覇帰着・アイシング・抗炎症ケア・完全休養",
        "target_pace": "-",
        "target_hr": "-",
        "purpose": "ハーフの筋肉ダメージ修復・リカバリー",
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
                status_badge = "✈️ 遠征"
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
            "kanto": ("✈️ 遠征・移動", "text-purple-400"),
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
