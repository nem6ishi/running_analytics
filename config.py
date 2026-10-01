"""設定ファイル (Running Analytics Configuration)

目標値や生理学的パラメータ、表示設定をここで一括管理します。
将来「10km 45分切り」や「フルマラソン目標」に移行する際も、ここを変更するだけでシステム全体に反映されます。
"""

from typing import Dict, Any

# ==========================================
# 🎯 メインターゲット目標設定 (Primary Goal)
# ==========================================
# 現在の目標: 10km 50分切り (サブ50)
TARGET_DISTANCE_KM: float = 10.0
TARGET_TIME_SEC: int = 3000          # 50分00秒 = 3000秒
TARGET_PACE_SEC: float = 300.0       # 5:00/km = 300.0秒/km
TARGET_LABEL: str = "10km 50分切り (サブ50)"

# ==========================================
# 🫀 生理学的パラメータ (Physiological Parameters)
# ==========================================
HR_MAX: int = 195                    # 最大心拍数 (bpm)
HR_RESTING: int = 55                 # 安静時心拍数 (bpm)

# 心拍ゾーン定義 (% of HR_MAX)
HR_ZONES: Dict[str, Dict[str, Any]] = {
    "zone1": {
        "name": "Zone 1 (回復)",
        "label": "アクティブリカバリー",
        "min_pct": 0,
        "max_pct": 65,
        "intensity": "超低強度 (回復・疲労抜き)",
        "desc": "疲労抜き・毛細血管の発達を促す回復ペース",
        "color": "emerald",
        "bg_color": "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
    },
    "zone2": {
        "name": "Zone 2 (基礎有酸素)",
        "label": "基礎有酸素 (イージー)",
        "min_pct": 65,
        "max_pct": 76,
        "intensity": "低強度 (脂肪燃焼・持久力基礎)",
        "desc": "スタミナの土台を築く最も重要なおしゃべりペース",
        "color": "blue",
        "bg_color": "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
    },
    "zone3": {
        "name": "Zone 3 (テンポ)",
        "label": "テンポ走 (有酸素強化)",
        "min_pct": 76,
        "max_pct": 86,
        "intensity": "中強度 (持久力向上)",
        "desc": "少し息が上がるが維持できるマラソンペース帯",
        "color": "amber",
        "bg_color": "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
    },
    "zone4": {
        "name": "Zone 4 (乳酸閾値/LT)",
        "label": "乳酸閾値 (LT / しきい値)",
        "min_pct": 86,
        "max_pct": 93,
        "intensity": "高強度 (スピード持久力)",
        "desc": "乳酸が溜まり始めるギリギリの粘り・勝負ペース（サブ50攻略の要）",
        "color": "orange",
        "bg_color": "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
    },
    "zone5": {
        "name": "Zone 5 (VO2max/無酸素)",
        "label": "無酸素 / VO2max",
        "min_pct": 93,
        "max_pct": 100,
        "intensity": "最高強度 (最大酸素摂取量)",
        "desc": "レース終盤やインターバル走のスプリント負荷",
        "color": "rose",
        "bg_color": "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
    },
}

# ==========================================
# 📊 UI・分析表示設定 (Display & Analytics)
# ==========================================
MAX_FIT_SAMPLE_POINTS: int = 180     # 時系列グラフの間引き最大ポイント数
WEEKLY_WORKLOAD_WEEKS: int = 8       # 週間負荷グラフの表示週数
ENABLE_ELEVATION_OVERLAY: bool = True # グラフ背景への標高オーバーレイ表示
