# Running Analytics (Garmin Data Analytics & Coaching)

Garmin Connect の走行データ（CSV & FITファイル）を解析し、科学的トレーニング指標・レース予想・個別ランの詳細分析＆コーチングを提供するパーソナルダッシュボードです。

---

## 🏃 自動データ同期の使い方

Garmin Connect から未取得のランニングデータ（FITファイル＆アクティビティ概要）を自動ダウンロードし、ダッシュボードの更新まで一気通貫で行えます。

### 1. 同期コマンドを実行
```bash
uv run python sync.py
```
- **初回実行時**:
  Garmin Connect のメールアドレス・パスワード（および2段階認証コード）の入力を求められます。
  認証に成功すると、ローカル（`.garmin_tokens/`）に安全な認証トークンが保存されます。
- **2回目以降**:
  保存されたトークンで自動ログインするため、パスワード入力不要で一瞬で同期が完了します。

### 2. 同期と同時に GitHub Pages に push する場合
```bash
uv run python sync.py --push
```
新規データを取得後、自動で `build.py`（HTML生成）を実行し、そのまま `git push` まで全自動で行います。

### 主なオプション
- `--limit <件数>`: チェックする直近アクティビティの件数（デフォルト: 15）
- `--relogin`: キャッシュされたトークンを破棄して再ログイン
- `--no-build`: データのダウンロードのみ行い、ビルドをスキップ
- `--push`: 同期＆ビルド完了後に GitHub へ自動 push

---

## 🛠️ 手動ビルド（ローカル確認）

```bash
uv run python build.py
```
`docs/index.html` が生成されます。ブラウザで開いて確認できます。
