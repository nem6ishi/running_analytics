import io
import os
import sys
import zipfile
import argparse
import subprocess
import getpass
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# 秒数から "HH:MM:SS" または "MM:SS" を生成
def format_seconds_to_time(seconds: float) -> str:
    total_sec = int(round(seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# 秒/km から "M:SS" ペース文字列を生成
def format_seconds_to_pace(seconds_per_km: float) -> str:
    if seconds_per_km <= 0 or seconds_per_km > 3600:
        return "--:--"
    minutes = int(seconds_per_km // 60)
    secs = int(round(seconds_per_km % 60))
    if secs == 60:
        minutes += 1
        secs = 0
    return f"{minutes}:{secs:02d}"


# m/s から "M:SS" ペース文字列を生成
def speed_to_pace_str(speed_ms: Optional[float]) -> str:
    if not speed_ms or speed_ms <= 0.1:
        return "--:--"
    sec_per_km = 1000.0 / speed_ms
    return format_seconds_to_pace(sec_per_km)


def get_garmin_client(token_dir: Path, relogin: bool = False) -> Garmin:
    """Garmin Connect クライアントを初期化（トークンキャッシュ優先）"""
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path_str = str(token_dir.resolve())

    # CI環境などで環境変数 GARMIN_TOKENS_BASE64 が設定されている場合、自動展開
    tokens_base64 = os.environ.get("GARMIN_TOKENS_BASE64")
    if tokens_base64 and not list(token_dir.glob("*")):
        import base64
        import json
        try:
            print("📦 環境変数 GARMIN_TOKENS_BASE64 からトークンを復元中...")
            raw_bytes = base64.b64decode(tokens_base64.encode("utf-8"))
            # 1. tar.gz 形式の展開を試行
            try:
                import io
                import tarfile
                with tarfile.open(fileobj=io.BytesIO(raw_bytes), mode="r:*") as tar:
                    tar.extractall(path=token_dir.parent)
                    print("✅ トークン (tarアーカイブ) の復元に成功しました。")
            except Exception:
                # 2. JSON 形式の展開を試行
                decoded = raw_bytes.decode("utf-8")
                token_data = json.loads(decoded)
                if isinstance(token_data, dict):
                    if any(k.endswith(".json") for k in token_data.keys()):
                        for fname, val in token_data.items():
                            (token_dir / fname).write_text(json.dumps(val) if isinstance(val, (dict, list)) else str(val), encoding="utf-8")
                    else:
                        (token_dir / "garmin_tokens.json").write_text(json.dumps(token_data), encoding="utf-8")
                print("✅ トークン (JSON) の復元に成功しました。")
        except Exception as e:
            print(f"⚠️ トークンの復元に失敗しました: {e}")

    # トークンが存在し、再ログイン要求がなければトークンでログイン
    if not relogin and list(token_dir.glob("*")):
        try:
            print("🔑 キャッシュされたトークンで Garmin Connect に接続中...")
            client = Garmin()
            client.login(tokenstore=token_path_str)
            print("✅ トークン認証に成功しました！")
            return client
        except Exception as e:
            print(f"⚠️ トークンでの認証に失敗しました ({e})。再ログインを試みます。")

    # トークンがないか無効な場合、認証情報を取得
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")

    # 非対話環境（CIなど）で認証情報がない場合
    if not sys.stdin.isatty() and (not email or not password):
        print("❌ エラー: 非対話環境で Garmin 認証情報（またはキャッシュトークン）が見つかりません。")
        print("GitHub Secrets に GARMIN_TOKENS_BASE64 または GARMIN_EMAIL / GARMIN_PASSWORD を設定してください。")
        sys.exit(1)

    if not email:
        email = input("Garmin Connect メールアドレス: ").strip()
    if not password:
        password = getpass.getpass("Garmin Connect パスワード: ").strip()

    def mfa_callback():
        if not sys.stdin.isatty():
            raise RuntimeError("2段階認証コードの入力が必要ですが、非対話環境のため入力できません。")
        return input("📱 2段階認証 (MFA) コードを入力してください: ").strip()

    print("🔐 Garmin Connect にログイン中...")
    client = Garmin(
        email=email,
        password=password,
        prompt_mfa=mfa_callback,
    )
    try:
        client.login(tokenstore=token_path_str)
        print("✅ ログインに成功し、認証トークンを安全に保存しました！")
        return client
    except GarminConnectAuthenticationError as e:
        print(f"❌ 認証エラー: メールアドレスまたはパスワードが正しくありません。\n{e}")
        sys.exit(1)
    except GarminConnectTooManyRequestsError:
        print("❌ ログイン試行回数が多すぎます。数分待ってから再試行してください。")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ログインに失敗しました: {e}")
        sys.exit(1)


def build_csv_row_from_activity(act: Dict[str, Any]) -> Dict[str, str]:
    """Garmin APIのアクティビティ辞書から Activities.csv の1行を作成"""
    start_time = act.get("startTimeLocal", "")
    title = act.get("activityName", "那覇市 ラン")
    dist_m = act.get("distance", 0.0)
    dist_km = round(dist_m / 1000.0, 2)
    duration_sec = act.get("duration", 0.0)
    elapsed_sec = act.get("elapsedDuration", duration_sec)
    moving_sec = act.get("movingDuration", duration_sec)
    calories = int(round(act.get("calories", 0.0)))

    avg_hr = int(round(act.get("averageHR", 0.0))) if act.get("averageHR") else 0
    max_hr = int(round(act.get("maxHR", 0.0))) if act.get("maxHR") else 0

    # ケイデンス (Garmin API では片足rpmで返る場合があるため120未満なら2倍)
    avg_cad = act.get("averageRunningCadenceInStepsPerMinute", 0.0)
    max_cad = act.get("maxRunningCadenceInStepsPerMinute", 0.0)
    if avg_cad and avg_cad < 120:
        avg_cad *= 2
    if max_cad and max_cad < 120:
        max_cad *= 2

    # ペース
    avg_speed = act.get("averageSpeed", 0.0)
    max_speed = act.get("maxSpeed", 0.0)
    avg_pace_str = speed_to_pace_str(avg_speed)
    max_pace_str = speed_to_pace_str(max_speed)

    # 標高
    elev_gain = int(round(act.get("elevationGain", 0.0)))
    elev_loss = int(round(act.get("elevationLoss", 0.0)))
    min_elev = int(round(act.get("minElevation", 0.0)))
    max_elev = int(round(act.get("maxElevation", 0.0)))

    # 歩幅 (cm または m)
    stride_val = act.get("avgStrideLength") or act.get("strideLength", 0.0)
    stride_m = (stride_val / 100.0) if stride_val > 10 else stride_val

    steps = int(round(act.get("steps", 0.0)))
    lap_count = act.get("lapCount", 1)

    return {
        "アクティビティタイプ": "ラン",
        "日付": start_time,
        "お気に入り": "false",
        "タイトル": title,
        "距離": f"{dist_km:.2f}",
        "カロリー": str(calories),
        "タイム": format_seconds_to_time(duration_sec),
        "平均心拍数": str(avg_hr) if avg_hr > 0 else "",
        "最大心拍数": str(max_hr) if max_hr > 0 else "",
        "平均ピッチ": str(int(round(avg_cad))) if avg_cad > 0 else "",
        "最高ピッチ": str(int(round(max_cad))) if max_cad > 0 else "",
        "平均ペース": avg_pace_str,
        "最高ペース": max_pace_str,
        "総上昇量": str(elev_gain),
        "総下降量": str(elev_loss),
        "平均歩幅": f"{stride_m:.2f}",
        "Training Stress Score®": "0.0",
        "ステップ": f"{steps:,}",
        "減圧": "いいえ",
        "ベストラップタイム": "00:00:00.0",
        "ラップ数": str(lap_count),
        "移動時間": format_seconds_to_time(moving_sec),
        "経過時間": format_seconds_to_time(elapsed_sec),
        "最低高度": str(min_elev),
        "最高高度": str(max_elev),
    }


def sync_activities(
    client: Garmin,
    data_dir: Path,
    limit: Optional[int] = None,
    fetch_all: bool = False,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Garmin Connect から過去・最新のランニングアクティビティとFITファイルを自動同期"""
    import time
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "Activities.csv"

    # 1. 既存の Activities.csv から取得済みの日時を収集
    existing_dates = set()
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            if "日付" in df.columns:
                existing_dates = set(df["日付"].astype(str).str.strip())
        except Exception as e:
            print(f"⚠️ 既存の Activities.csv 読み込みエラー ({e})。新規作成・追記します。")

    # 2. 既存の FIT ファイルから ID を収集
    existing_fit_ids = set()
    for fit_path in data_dir.glob("*.fit"):
        fit_id = fit_path.name.split("_")[0].split(".")[0]
        if fit_id.isdigit():
            existing_fit_ids.add(int(fit_id))

    # 3. アクティビティをページネーションで取得
    target_count_str = "全件" if fetch_all else f"最大 {limit} 件"
    print(f"📡 Garmin Connect からアクティビティ一覧を取得中 ({target_count_str})...")

    activities = []
    start = 0
    batch_size = 50

    while True:
        try:
            req_limit = batch_size
            if not fetch_all and limit is not None:
                remaining = limit - len(activities)
                if remaining <= 0:
                    break
                req_limit = min(batch_size, remaining)

            batch = client.get_activities(start, req_limit)
            if not batch:
                break
            activities.extend(batch)
            start += len(batch)
            print(f"  ... {len(activities)} 件取得済み (開始位置: {start})")

            # 取得件数がバッチサイズ未満ならこれ以上データなし
            if len(batch) < req_limit:
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"⚠️ アクティビティ一覧の取得中断 ({e})。取得済み {len(activities)} 件で処理を継続します。")
            break

    # ランニングのアクティビティのみ抽出
    running_activities = []
    for act in activities:
        act_type = act.get("activityType", {}).get("typeKey", "").lower()
        if any(k in act_type for k in ["running", "treadmill", "trail"]):
            running_activities.append(act)

    print(f"🏃 ランニングアクティビティ: 全 {len(running_activities)} 件検出 (既存FITファイル保有: {len(existing_fit_ids)} 件)")

    # 未取得のアクティビティ（CSV未登録、またはFIT未ダウンロード）を特定
    new_activities = []
    for act in running_activities:
        act_id = act.get("activityId")
        start_time = str(act.get("startTimeLocal", "")).strip()

        # CSVにない、または FIT がないものを対象とする
        is_in_csv = start_time in existing_dates
        has_fit = act_id in existing_fit_ids

        if not is_in_csv or not has_fit:
            new_activities.append(act)

    if not new_activities:
        print("🎉 すべてのランニングデータ（FITファイル＆サマリー）は最新・完全同期済みです！")
        return 0, []

    print(f"📥 {len(new_activities)} 件のアクティビティについて、FITファイルまたはCSVサマリーを取得します...")
    downloaded_count = 0
    new_csv_rows = []

    for idx, act in enumerate(new_activities, 1):
        act_id = act["activityId"]
        name = act.get("activityName", "ラン")
        date_str = act.get("startTimeLocal", "")
        dist_km = round(act.get("distance", 0.0) / 1000.0, 2)
        print(f"\n📦 [{idx}/{len(new_activities)}] [{date_str}] {name} ({dist_km} km / ID: {act_id})")

        # FIT ファイルダウンロード
        fit_dest = data_dir / f"{act_id}_ACTIVITY.fit"
        if not fit_dest.exists():
            print(f"  ⬇️ オリジナルFITファイルをダウンロード中...")
            try:
                zip_data = client.download_activity(act_id, dl_fmt=client.ActivityDownloadFormat.ORIGINAL)
                with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                    fit_found = False
                    for zip_info in z.infolist():
                        if zip_info.filename.endswith(".fit"):
                            with z.open(zip_info) as zf, open(fit_dest, "wb") as of:
                                of.write(zf.read())
                            print(f"  💾 保存完了: {fit_dest.name} ({fit_dest.stat().st_size:,} bytes)")
                            fit_found = True
                            time.sleep(0.5)
                            break
                        elif zip_info.filename.endswith(".fit.gz"):
                            import gzip
                            with z.open(zip_info) as zf:
                                uncompressed = gzip.decompress(zf.read())
                                with open(fit_dest, "wb") as of:
                                    of.write(uncompressed)
                            print(f"  💾 保存完了: {fit_dest.name} ({fit_dest.stat().st_size:,} bytes)")
                            fit_found = True
                            time.sleep(0.5)
                            break
                    if not fit_found:
                        print(f"  ⚠️ ZIP内に .fit ファイルが見つかりませんでした。")
            except Exception as e:
                print(f"  ⚠️ FITファイルのダウンロード失敗: {e}")
        else:
            print(f"  ⏩ FITファイルはすでに存在します: {fit_dest.name}")

        # CSV 行構築
        if date_str not in existing_dates:
            row_dict = build_csv_row_from_activity(act)
            new_csv_rows.append(row_dict)
            existing_dates.add(date_str)

        downloaded_count += 1

    # Activities.csv の更新
    if new_csv_rows:
        print(f"\n📝 Activities.csv に {len(new_csv_rows)} 件の新規データを追記中...")
        new_df = pd.DataFrame(new_csv_rows)
        if csv_path.exists():
            try:
                old_df = pd.read_csv(csv_path)
                combined_df = pd.concat([new_df, old_df], ignore_index=True)
                combined_df["_dt_temp"] = pd.to_datetime(combined_df["日付"], errors="coerce")
                combined_df = combined_df.sort_values("_dt_temp", ascending=False).drop(columns=["_dt_temp"])
                combined_df.to_csv(csv_path, index=False, encoding="utf-8")
                print(f"✅ Activities.csv を正常に更新しました (合計 {len(combined_df)} 件)。")
            except Exception as e:
                print(f"⚠️ CSVの更新に失敗したため新規行のみ保存します: {e}")
                new_df.to_csv(csv_path, index=False, encoding="utf-8")
        else:
            new_df.to_csv(csv_path, index=False, encoding="utf-8")
            print(f"✅ Activities.csv を新規作成しました。")

    return downloaded_count, new_csv_rows


def main():
    parser = argparse.ArgumentParser(description="Garmin Connect からランニングデータを自動同期")
    parser.add_argument("--all", action="store_true", help="過去の全アクティビティを対象に同期する")
    parser.add_argument("--limit", type=int, default=15, help="チェックする最新アクティビティ件数 (デフォルト: 15)")
    parser.add_argument("--relogin", action="store_true", help="トークンを破棄して再ログインする")
    parser.add_argument("--no-build", action="store_true", help="データ同期後に build.py を実行しない")
    parser.add_argument("--push", action="store_true", help="同期＆ビルド後に GitHub に自動 push する")
    parser.add_argument("--open", action="store_true", help="ビルド後にブラウザでダッシュボードを開く")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent
    data_dir = root_dir / "data"
    token_dir = root_dir / ".garmin_tokens"

    print("=" * 60)
    print("🏃 Garmin Connect ランニングデータ自動同期ツール")
    print("=" * 60)

    # 1. ログイン
    client = get_garmin_client(token_dir, relogin=args.relogin)

    # 2. 同期実行
    try:
        synced_count, new_rows = sync_activities(client, data_dir, limit=args.limit, fetch_all=args.all)
    except Exception as e:
        print(f"❌ 同期エラー: {e}")
        sys.exit(1)

    # 新規データのサマリー表示
    if new_rows:
        print("\n" + "=" * 60)
        print(f"📊 新規取得アクティビティ速報 ({len(new_rows)} 件):")
        print("=" * 60)
        for r in new_rows:
            dist_km = r.get("距離", "0")
            pace = r.get("平均ペース", "--:--")
            hr = r.get("平均心拍数", "--")
            t = r.get("タイム", "--")
            print(f"  🏃 {r.get('日付')} : {dist_km} km ({t}) | ペース {pace}/km | 平均心拍 {hr} bpm")
        print("=" * 60)

    # 3. ビルド実行
    if not args.no_build:
        if synced_count > 0 or not (root_dir / "docs" / "index.html").exists():
            print("\n" + "=" * 60)
            print("🚀 新規データが検出されたため、ダッシュボードを自動ビルドします...")
            print("=" * 60)
            try:
                from build import build
                build()
                print("\n✨ ダッシュボード (docs/index.html) の更新が完了しました！")
            except Exception as e:
                print(f"❌ ビルドエラー: {e}")
                sys.exit(1)
        else:
            print("\n💡 新規データはなかったため、ビルドはスキップしました。")

    # 4. ブラウザで開く
    if args.open:
        html_path = (root_dir / "docs" / "index.html").resolve()
        if html_path.exists():
            import webbrowser
            webbrowser.open(html_path.as_uri())
            print(f"🌐 ブラウザでダッシュボードを開きました: {html_path.as_uri()}")
        else:
            print("⚠️ docs/index.html が見つからないため、ブラウザを開けませんでした。")

    # 5. GitHub Push
    if args.push:
        print("\n" + "=" * 60)
        print("📤 GitHub へ変更を push します...")
        print("=" * 60)
        try:
            # push 前にリモートの最新状態を取り込む
            subprocess.run(
                ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                cwd=root_dir,
                check=True,
            )
            subprocess.run(["git", "add", "docs/"], cwd=root_dir, check=True)
            status_res = subprocess.run(
                ["git", "status", "--porcelain", "docs/"],
                cwd=root_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            if not status_res.stdout.strip():
                print("コミットする変更（docs/）はありませんでした。")
            else:
                subprocess.run(
                    ["git", "commit", "-m", f"Sync Garmin activities & update dashboard ({synced_count} new)"],
                    cwd=root_dir,
                    check=True,
                )
                subprocess.run(["git", "push", "origin", "main"], cwd=root_dir, check=True)
                print("🚀 GitHub への push が完了しました！GitHub Pages が自動更新されます。")
        except subprocess.CalledProcessError as e:
            print(f"❌ Git 操作エラー: {e}")
            sys.exit(1)


    print("\n" + "=" * 60)
    print("🏁 全ての処理が完了しました！お疲れ様でした。")
    print("=" * 60)


if __name__ == "__main__":
    main()
