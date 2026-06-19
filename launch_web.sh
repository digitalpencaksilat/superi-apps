#!/bin/bash
# Launch SUPER-I APP Web Dashboard
# Usage: ./launch_web.sh

cd "$(dirname "$0")"

echo "════════════════════════════════════════════"
echo "  SUPER-I APP Web Dashboard"
echo "════════════════════════════════════════════"

# Cek Flask
if ! python3 -c "import flask" 2>/dev/null; then
    echo "  Flask belum terinstall. Menginstall..."
    pip3 install flask --break-system-packages
fi

echo "  ✓ Menjalankan web app..."
echo "  ✓ Buka browser: http://localhost:8888"
echo "  (Tekan Ctrl+C untuk berhenti)"
echo "════════════════════════════════════════════"

# Auto-open browser (macOS)
sleep 2 && open http://localhost:8888 &

python3 superi_web.py
