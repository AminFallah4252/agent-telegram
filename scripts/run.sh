#!/usr/bin/env bash
# ==============================================================================
# Telegram Bot Manager CLI Wrapper (Linux / macOS)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_PATH="${SCRIPT_DIR}/telegram_cli.py"

# Find python interpreter
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Error: Python 3 is required. Please install python3." >&2
    exit 1
fi

exec "$PYTHON_BIN" "$CLI_PATH" "$@"
