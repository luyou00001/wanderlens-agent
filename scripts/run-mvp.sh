#!/usr/bin/env bash
# 清點、描述、產生草稿並匯出到本機。不會登入或上傳。
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -x .venv/bin/wanderlens ]]; then
  cmd=(.venv/bin/wanderlens)
else
  cmd=(python3 -m wanderlens)
fi
input="${1:-assets_vault/inbox}"
"${cmd[@]}" ingest --input "$input"
"${cmd[@]}" describe
"${cmd[@]}" draft
"${cmd[@]}" export-posts
"${cmd[@]}" bundle
