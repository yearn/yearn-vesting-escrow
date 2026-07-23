#!/usr/bin/env bash
set -euo pipefail

contract_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to regenerate requirements.txt." >&2
  exit 1
fi

uv pip compile \
  "$contract_dir/requirements.in" \
  --universal \
  --python-version 3.11 \
  --custom-compile-command './update-lock.sh' \
  --output-file "$contract_dir/requirements.txt"
