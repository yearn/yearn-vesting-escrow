#!/usr/bin/env bash
set -euo pipefail

contract_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PYTHON_BIN:-python3.11}"
venv_dir="$contract_dir/.venv"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "Python 3.11 is required. Set PYTHON_BIN to a Python 3.11 executable." >&2
  exit 1
fi

# Rebuild instead of layering dependencies over an older Ape environment. Ape
# and Titanoboa both register pytest isolation hooks and cannot safely coexist.
"$python_bin" -m venv --clear "$venv_dir"
"$venv_dir/bin/python" -m pip install --upgrade pip
"$venv_dir/bin/python" -m pip install -r "$contract_dir/requirements.txt"

echo "Contract environment ready at $venv_dir"
