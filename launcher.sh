#!/bin/bash
# SUPER-I APP Quick Launcher
# Symlink ke /usr/local/bin/superi agar bisa dipanggil dari mana saja:
#   sudo ln -sf "$(pwd)/launcher.sh" /usr/local/bin/superi

# Resolve symlink agar SUPERI_DIR menunjuk ke lokasi project asli, bukan symlink
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
SUPERI_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
PYTHON="$SUPERI_DIR/.venv/bin/python3"

if [ ! -f "$PYTHON" ]; then
    echo "  ⚠ Virtual env belum ada. Setup dulu:"
    echo "    cd $SUPERI_DIR"
    echo "    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [ "$1" == "web" ] || [ "$1" == "w" ]; then
    cd "$SUPERI_DIR"
    echo "🌐 Menjalankan SUPER-I APP Web Dashboard..."
    echo "   Akses: http://localhost:8888"
    $PYTHON superi_web.py

elif [ "$1" == "cli" ] || [ "$1" == "c" ]; then
    cd "$SUPERI_DIR"
    echo "💻 Menjalankan SUPER-I APP CLI Interactive..."
    $PYTHON superi_app.py

elif [ "$1" == "input" ] || [ "$1" == "i" ]; then
    cd "$SUPERI_DIR"
    shift
    echo "📊 SUPER-I APP CLI Input (scripting mode)"
    $PYTHON superi_input.py "$@"

elif [ "$1" == "sync" ] || [ "$1" == "s" ]; then
    cd "$SUPERI_DIR"
    shift
    if [ $# -eq 0 ]; then
        echo "🔄 Sync ke Portal APD sekarang ada di CLI → menu [P]"
        $PYTHON superi_app.py          # menu sync sekarang di cli ([P])
    else
        echo "🔄 SUPER-I → Portal APD Sync (non-interactive)"
        $PYTHON superi_sync.py "$@"   # --type/--jam/--dry-run untuk script/cron
    fi

elif [ "$1" == "auto" ] || [ "$1" == "a" ]; then
    cd "$SUPERI_DIR"
    shift
    $PYTHON superi_auto.py "$@"

else
    echo "SUPER-I APP Launcher"
    echo "===================="
    echo ""
    echo "Usage: superi [command] [options]"
    echo ""
    echo "Commands:"
    echo "  web, w           Jalankan web dashboard (http://localhost:8888)"
    echo "  cli, c           Jalankan CLI interaktif"
    echo "  input, i [opts]  Jalankan CLI scripting (input ke SUPER-I)"
    echo "  sync, s [opts]   Sync ke Portal APD (no-args = buka CLI; --type/--jam = non-interactive)"
    echo ""
    echo "Examples:"
    echo "  superi web"
    echo "  superi cli"
    echo "  superi sync                          # buka CLI (menu [P] Sync)"
    echo "  superi sync --type all --jam 09      # sync semua tipe jam 09"
    echo "  superi sync --type penyulang --jam 08-10 --dry-run"
    echo "  superi input --help"
    echo ""
    echo "Project Location: $SUPERI_DIR"
fi
