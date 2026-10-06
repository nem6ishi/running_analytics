import pytest
import io
import zipfile
from unittest.mock import MagicMock
from pathlib import Path
import pandas as pd
from sync import build_csv_row_from_activity, extract_shoe_name_from_gear, sync_activities


def test_extract_shoe_name_from_gear():
    # 辞書内に customMakeModel がある場合
    gear_dict = {"customMakeModel": "Nike Pegasus 40"}
    assert extract_shoe_name_from_gear(gear_dict) == "Nike Pegasus 40"

    # リスト形式で displayName がある場合
    gear_list = [{"displayName": "Asics Novablast 3", "modelName": "Novablast 3"}]
    assert extract_shoe_name_from_gear(gear_list) == "Asics Novablast 3"

    # modelName のみの場合
    gear_model_only = [{"modelName": "Novablast 3"}]
    assert extract_shoe_name_from_gear(gear_model_only) == "Novablast 3"

    # activityGear 形式
    nested = {"activityGear": [{"customMakeModel": "Hoka Clifton 9"}]}
    assert extract_shoe_name_from_gear(nested) == "Hoka Clifton 9"

    # 空データ
    assert extract_shoe_name_from_gear(None) == ""
    assert extract_shoe_name_from_gear([]) == ""


def test_build_csv_row_from_activity():
    act = {
        "activityId": 12345678,
        "activityName": "朝ラン",
        "startTimeLocal": "2026-10-06 07:00:00",
        "distance": 5000.0,
        "duration": 1500.0,
        "elapsedDuration": 1520.0,
        "movingDuration": 1495.0,
        "calories": 320.0,
        "averageHR": 155.0,
        "maxHR": 172.0,
        "averageRunningCadenceInStepsPerMinute": 178.0,
        "maxRunningCadenceInStepsPerMinute": 186.0,
        "elevationGain": 15.0,
        "elevationLoss": 15.0,
        "strideLength": 1.05,
        "favorite": False,
    }
    row = build_csv_row_from_activity(act, shoe_name="Nike Vaporfly")
    assert row["アクティビティタイプ"] == "ラン"
    assert row["日付"] == "2026-10-06 07:00:00"
    assert row["タイトル"] == "朝ラン"
    assert row["距離"] == "5.00"
    assert row["平均心拍数"] == "155"
    assert row["最大心拍数"] == "172"
    assert row["平均ピッチ"] == "178"
    assert row["シューズ"] == "Nike Vaporfly"


def test_sync_activities_skips_existing(tmp_path: Path):
    # 既存の CSV と FIT が存在する場合、新規取得対象からスキップされることを検証
    csv_file = tmp_path / "Activities.csv"
    df = pd.DataFrame([{
        "アクティビティタイプ": "ラン",
        "日付": "2026-10-05 18:00:00",
        "タイトル": "ラン",
        "距離": 5.0,
        "タイム": "00:25:00",
        "平均心拍数": 150,
        "シューズ": "Pegasus",
    }])
    df.to_csv(csv_file, index=False)

    # 既存の FIT ファイルを作成
    (tmp_path / "11111111_ACTIVITY.fit").touch()

    # ダミー zip（中に 22222222_ACTIVITY.fit を格納）
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("22222222_ACTIVITY.fit", b"DUMMY_FIT_DATA")
    valid_zip_bytes = zip_buf.getvalue()

    # モッククライアント
    client = MagicMock()
    # 1件目は既存、2件目は新規
    client.get_activities.return_value = [
        {
            "activityId": 11111111,
            "activityType": {"typeKey": "running"},
            "startTimeLocal": "2026-10-05 18:00:00",
            "distance": 5000.0,
        },
        {
            "activityId": 22222222,
            "activityType": {"typeKey": "running"},
            "startTimeLocal": "2026-10-06 07:00:00",
            "distance": 6000.0,
            "duration": 1800.0,
        },
    ]
    # FIT ダウンロードとギア取得のモック
    client.download_activity.return_value = valid_zip_bytes
    client.get_activity_gear.return_value = []

    count, rows = sync_activities(client, data_dir=tmp_path, limit=2)
    # 11111111 はスキップされ、22222222 のみダウンロードされる
    assert count == 1
    assert len(rows) == 1
    assert (tmp_path / "22222222_ACTIVITY.fit").exists()
