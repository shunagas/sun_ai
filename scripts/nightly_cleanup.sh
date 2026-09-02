#!/bin/bash
# 毎日22時（cron）に実行：作業中の一時ファイル（スクリーンショット等）を削除し、
# 残っている変更があればコミット・pushしてgit statusをきれいな状態に保つ。
set -uo pipefail
cd "$(dirname "$0")/.."

LOG="$HOME/.sun_ai_nightly_cleanup.log"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') ====="

  git clean -fdX
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
