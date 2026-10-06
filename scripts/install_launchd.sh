#!/usr/bin/env bash
set -euo pipefail

LABEL="com.nem6ishi.running-sync"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET_PLIST="${TARGET_DIR}/${LABEL}.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_PATH="${SCRIPT_DIR}/${LABEL}.plist.template"
LOGS_DIR="${PROJECT_DIR}/logs"

if [ "${1:-}" = "--uninstall" ]; then
    echo "🗑️  launchd ジョブ (${LABEL}) をアンインストール中..."
    launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
    if [ -f "${TARGET_PLIST}" ]; then
        rm -f "${TARGET_PLIST}"
        echo "✅ ${TARGET_PLIST} を削除しました。"
    else
        echo "ℹ️  ${TARGET_PLIST} は存在しません。"
    fi
    echo "🎉 アンインストールが完了しました。"
    exit 0
fi

UV_PATH="$(command -v uv || true)"
if [ -z "${UV_PATH}" ]; then
    echo "❌ エラー: 'uv' コマンドが見つかりません。PATH を確認してください。" >&2
    exit 1
fi
UV_BIN_DIR="$(dirname "${UV_PATH}")"

if [ ! -f "${TEMPLATE_PATH}" ]; then
    echo "❌ エラー: テンプレートファイルが見つかりません: ${TEMPLATE_PATH}" >&2
    exit 1
fi

mkdir -p "${LOGS_DIR}"
mkdir -p "${TARGET_DIR}"

echo "📝 launchd 設定ファイルを生成中..."
sed \
    -e "s|__UV__|${UV_PATH}|g" \
    -e "s|__UV_BIN_DIR__|${UV_BIN_DIR}|g" \
    -e "s|__PROJECT_DIR__|${PROJECT_DIR}|g" \
    "${TEMPLATE_PATH}" > "${TARGET_PLIST}"

echo "⚙️  既存の launchd ジョブがあれば停止中..."
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true

echo "🚀 新しい launchd ジョブを登録中..."
launchctl bootstrap "gui/$(id -u)" "${TARGET_PLIST}"

echo "✅ launchd の登録が正常に完了しました！"
echo "   設定ファイル: ${TARGET_PLIST}"
echo "   実行スケジュール: 毎日 21:00"
echo "   同期コマンド: ${UV_PATH} run python sync.py --push"
echo "   作業ディレクトリ: ${PROJECT_DIR}"
echo "   ログ出力先: ${LOGS_DIR}/sync.log"
