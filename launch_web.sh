#!/bin/bash
# Launch SUPER-I APP Web Dashboard
# Usage: ./launch_web.sh

cd "$(dirname "$0")"
PYTHON=".venv/bin/python3"

echo "════════════════════════════════════════════"
echo "  SUPER-I APP Web Dashboard"
echo "════════════════════════════════════════════"

# Cek venv ada
if [ ! -f "$PYTHON" ]; then
    echo "  ⚠ Virtual env belum ada. Setup dulu:"
    echo "    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

echo "  ✓ Menjalankan web app..."
echo "  ✓ Buka browser: http://localhost:8888"
echo "  (Tekan Ctrl+C untuk berhenti)"
echo "════════════════════════════════════════════"

# Auto-open browser (macOS)
sleep 2 && open http://localhost:8888 &

$PYTHON superi_web.py
