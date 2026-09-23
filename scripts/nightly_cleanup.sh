#!/bin/bash
# 毎日22時（cron）に実行：作業中の一時ファイル（スクリーンショット等）を
# 削除はせず「.trash/」フォルダへ退避し、残っている変更があればコミット・pushして
# git statusをきれいな状態に保つ。実際の削除は行わない（本人が.trash/を確認の上、手動で削除する）。
#
# 2026-09-23: git clean -fdX が.gitignore対象の.secrets/（API認証情報）まで
# 削除してしまう事故が発生したため、削除ではなく退避方式に変更し、
# .secrets/・経理帳簿は退避対象からも明示的に除外するようにした。
set -uo pipefail
cd "$(dirname "$0")/.."

LOG="$HOME/.sun_ai_nightly_cleanup.log"
TRASH_DIR=".trash/$(date '+%Y-%m-%d_%H%M%S')"

{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') ====="

  # .gitignore対象の未追跡ファイル・ディレクトリの一覧を取得（この時点では削除しない）
  mapfile -t CANDIDATES < <(git clean -ndX | sed -E 's/^Would remove //')

  MOVED=0
  for f in "${CANDIDATES[@]}"; do
    # 認証情報・経理帳簿・.trash自体は絶対に退避対象にしない（安全のための明示的な除外）
    case "$f" in
      *".secrets"*|*"経理帳簿.xlsx"|.trash/*|.trash)
        echo "skip (protected): $f"
        continue
        ;;
    esac

    dest="$TRASH_DIR/$f"
    mkdir -p "$TRASH_DIR/$(dirname "$f")"
    if mv "$f" "$dest" 2>>"$LOG"; then
      echo "moved: $f -> $dest"
      MOVED=$((MOVED + 1))
    else
      echo "[warn] failed to move: $f"
    fi
  done
  echo "moved ${MOVED} item(s) to ${TRASH_DIR}"

  git add -A

  if ! git diff --cached --quiet; then
    git commit -m "chore: 夜間クリーンアップ $(date '+%Y-%m-%d')"
    if git push origin main; then
      echo "push ok"
    else
      echo "[warn] push failed（SSHエージェントにcronからアクセスできない可能性）"
    fi
  else
    echo "変更なし"
  fi

  echo "done"
} >> "$LOG" 2>&1
