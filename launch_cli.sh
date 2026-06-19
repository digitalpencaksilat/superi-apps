#!/bin/bash
# Launch SUPER-I APP CLI Interactive
# Usage: ./launch_cli.sh

cd "$(dirname "$0")"
PYTHON=".venv/bin/python3"

# Cek venv ada
if [ ! -f "$PYTHON" ]; then
    echo "  ⚠ Virtual env belum ada. Setup dulu:"
    echo "    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

$PYTHON superi_app.py
