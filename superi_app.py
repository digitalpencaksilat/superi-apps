#!/usr/bin/env python3
"""
SUPER-I APP - Interactive Data Input
=====================================
Interface interaktif untuk input data SUPER-I APP.
Tinggal pilih menu, script akan memandu langkah demi langkah.

Konfigurasi disimpan di ~/.superi_config.json
"""

import urllib.request
import urllib.error
import json
import os
import sys
import base64
import subprocess
import platform
import random
import time
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
BASE_URL = "https://super-i-app.plnes.co.id"
API_BASE = f"{BASE_URL}/api"
AUTH_URL = f"{API_BASE}/auth/login-mobile"
BOUNDARY = "----FormBoundary7MA4YWxkTrZu0gW"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".superi_config.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import cli_render as ui
except Exception:
    ui = None

try:
    import superi_humanizer as hu
except Exception:
    hu = None


def _human_foto_date(date_str, periode, durasi_min=None, data_type="beban-penyulang"):
    if hu:
        return hu.rand_foto_datetime(date_str, periode, durasi_min)
    return f"{date_str}T{periode:02d}:00:00.000Z"


def _human_foto_pair(date_str, periode, durasi_min=None):
    if hu:
        return hu.rand_foto_pair(date_str, periode, durasi_min)
    ts = f"{date_str}T{periode:02d}:00:00.000Z"
    return ts, ts


def _human_durasi(data_type="beban-penyulang"):
    if hu:
        return hu.rand_durasi_for_type(data_type)
    import random
    # fallback: 2-7 detik -> menit
    if "tegangan" in data_type:
        return round(random.uniform(8.0, 35.0) / 60.0, 8)
    return round(random.uniform(2.0, 7.0) / 60.0, 8)


def _human_foto_dict(date_str, periode, durasi_min=None, data_type="beban-penyulang"):
    if hu:
        return hu.rand_foto_dict(data_type=data_type, date_str=date_str, periode=periode, durasi_min=durasi_min)
    return {"date": _human_foto_date(date_str, periode, durasi_min), "address": "Jl. Swadaya 1 No.36, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", "latitude": -6.213095, "longitude": 106.846073}


def _human_foto_pair_dicts(date_str, periode, durasi_min=None):
    if hu:
        return hu.rand_foto_pair_dicts(date_str, periode, durasi_min)
    ts1, ts2 = _human_foto_pair(date_str, periode, durasi_min)
    base_addr = "Jl. Swadaya 1 No.36, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia"
    return (
        {"date": ts1, "address": base_addr, "latitude": -6.213095, "longitude": 106.846073},
        {"date": ts2, "address": base_addr, "latitude": -6.213095, "longitude": 106.846073},
    )


def _human_sleep(a=0.6, b=2.2):
    if hu:
        hu.human_sleep(a, b)
    else:
        import time
        time.sleep(0.35)


def _human_shuffled(seq):
    if hu:
        return hu.shuffled(seq)
    return list(seq)


def _get_jpeg_bytes(single=True, item_name=None, data_type=None, subtype=None):
    """Return JPEG bytes humanized: random size 30-150KB, hash berbeda tiap call.
    single=True -> 1 foto, single=False -> (jpeg1, jpeg2) untuk tegangan.

    - Jika photo_source=manual + item_name -> per-item sesuai input (random dari folder item + hv/mv terpisah)
    - Jika photo_source=pool -> 1 foto untuk semua (generic)
    - Filename upload tetap humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg (bukan basename manual)
    """
    source = get_photo_source()
    if hu:
        if single:
            # STRICT 720x720 untuk semua tipe
            return hu.rand_jpeg_bytes(target_w=720, target_h=720, item_name=item_name, data_type=data_type, subtype=subtype, photo_source=source)
        else:
            return hu.rand_jpeg_pair(target_w=720, target_h=720, item_name=item_name, data_type=data_type, photo_source=source)
    return DUMMY_JPEG, DUMMY_JPEG


def _enable_win_vt100():
    """Enable VT100 escape processing on Windows 10+ so \\r + ANSI colors work."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass  # older Windows — \r still works, ANSI colors may degrade

# Fallback: kalau di project folder tidak ada, cek home (~/.superi_config.json)
_HOME_CONFIG = os.path.expanduser("~/.superi_config.json")

DUMMY_JPEG = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
    0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
    0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
    0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
    0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
    0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
    0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
    0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
    0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A,
    0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03, 0x03, 0x02,
    0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D, 0x01, 0x02,
    0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13, 0x51,
    0x61, 0x61, 0xFF, 0xD9
])

ENDPOINTS = {
    "beban-penyulang": {
        "input": "/gama/opgi-20kv/operator-gi/beban-penyulang/input",
        "list": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "delete": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "id_field": "penyulangId", "value_field": "beban",
        "label": "Beban Penyulang", "unit": "Ampere",
        "file_field": "file", "num_photos": 1,
    },
    "beban-trafo": {
        "input": "/gama/opgi-20kv/operator-gi/beban-trafo/input",
        "list": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "delete": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "id_field": "trafoId", "value_field": "beban",
        "label": "Beban Trafo", "unit": "Ampere",
        "file_field": "file", "num_photos": 1,
    },
    "tegangan-trafo": {
        "input": "/gama/opgi-20kv/operator-gi/tegangan-trafo/input",
        "list": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
        "delete": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
        "id_field": "trafoId", "value_field": "mv",
        "label": "Tegangan Trafo", "unit": "kV",
        "file_field": "files", "num_photos": 2,
        "extra_fields": ["hv"],
    },
}

# ============================================================
# HELPERS
# ============================================================

def load_config():
    # Prioritas: project folder .superi_config.json
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    # Fallback: home ~/.superi_config.json (config lama, sebelum pindah ke project)
    if os.path.exists(_HOME_CONFIG):
        with open(_HOME_CONFIG) as f:
            return json.load(f)
    return {}

def save_config(cfg):
    # Selalu simpan ke project folder (dipakai bersama superi_sync.py)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


# ============================================================
# LOGOUT - Credential wipe + Auto disable + Scheduler cleanup
# ============================================================

def backup_config():
    """Backup config file sebelum wipe, untuk safety re-login."""
    try:
        if os.path.exists(CONFIG_FILE):
            import shutil
            bak = CONFIG_FILE + ".bak"
            shutil.copy2(CONFIG_FILE, bak)
            try:
                os.chmod(bak, 0o600)
            except Exception:
                pass
            return bak
    except Exception:
        pass
    return None


def clear_history_cache():
    """Clear fetch_history_bulk in-memory cache."""
    try:
        # _cache adalah mutable default arg di fetch_history_bulk
        # akses via __defaults__
        cache_obj = fetch_history_bulk.__defaults__[0] if fetch_history_bulk.__defaults__ else None
        if isinstance(cache_obj, dict):
            cache_obj.clear()
    except Exception:
        pass


def disable_auto_and_scheduler(keep_scheduler=False):
    """Lapis 1 + 3: matikan auto flag + (opsional) uninstall scheduler.
    Return dict status.
    """
    cfg = load_config()
    was_enabled = cfg.get("auto_enabled", False)
    cfg["auto_enabled"] = False
    save_config(cfg)

    sched_removed = False
    sched_error = None
    if not keep_scheduler:
        try:
            if scheduler_is_installed():
                if platform.system() == "Windows":
                    ok, msg = win_task_uninstall()
                else:
                    ok, msg = cron_uninstall()
                sched_removed = ok
                if not ok:
                    sched_error = msg
            else:
                sched_removed = True  # already not installed = success
        except Exception as e:
            sched_error = str(e)

    return {
        "auto_was_enabled": was_enabled,
        "auto_disabled": True,
        "scheduler_removed": sched_removed,
        "scheduler_error": sched_error,
    }


def clear_credentials(purge_all=False, keep_portal=False, keep_scheduler=False, keep_non_creds=True):
    """Wipe kredensial dari .superi_config.json (dan fallback ~/.superi_config.json).

    Args:
        purge_all: kalau True, hapus file config total (project + home).
        keep_portal: kalau True, jangan hapus portal_user/password.
        keep_scheduler: kalau True, jangan uninstall cron/task.
        keep_non_creds: kalau True, pertahankan gi_id, portal_url, history_days, etc.

    Return status dict.
    """
    backup_config()

    result = {
        "project_cleared": False,
        "home_cleared": False,
        "auto_status": None,
        "purged": purge_all,
    }

    if purge_all:
        # Hapus total file config
        for p in [CONFIG_FILE, _HOME_CONFIG]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        # Scheduler
        if not keep_scheduler:
            try:
                if scheduler_is_installed():
                    if platform.system() == "Windows":
                        win_task_uninstall()
                    else:
                        cron_uninstall()
            except Exception:
                pass
        clear_history_cache()
        result["project_cleared"] = True
        result["home_cleared"] = True
        return result

    # Soft wipe: hapus nip/password (+ optional portal) tapi keep setting lain
    cfg = load_config()
    had_nip = bool(cfg.get("nip"))

    # Keys kredensial yang dihapus
    cred_keys = ["nip", "password"]
    if not keep_portal:
        cred_keys += ["portal_user", "portal_password"]

    for k in cred_keys:
        cfg.pop(k, None)

    # Auto disable (lapis 1)
    cfg["auto_enabled"] = False
    # keep_non_creds = True -> biarkan gi_id, portal_url, portal_gi_id, history_days, auto_* lain tetap
    # jika False, reset juga tapi tetap simpan file kosong
    save_config(cfg)

    # Bersihkan juga file home legacy jika ada
    if os.path.exists(_HOME_CONFIG):
        try:
            with open(_HOME_CONFIG) as f:
                hc = json.load(f)
            changed = False
            for k in cred_keys:
                if k in hc:
                    hc.pop(k)
                    changed = True
            if "auto_enabled" in hc:
                hc["auto_enabled"] = False
                changed = True
            if changed:
                if not hc.get("nip") and not hc:  # kosong total -> hapus
                    os.remove(_HOME_CONFIG)
                else:
                    with open(_HOME_CONFIG, "w") as f:
                        json.dump(hc, f, indent=2)
            result["home_cleared"] = True
        except Exception:
            pass

    # Lapis 3: scheduler uninstall (best-effort)
    if not keep_scheduler:
        try:
            if scheduler_is_installed():
                if platform.system() == "Windows":
                    win_task_uninstall()
                else:
                    cron_uninstall()
        except Exception:
            pass

    clear_history_cache()

    result["project_cleared"] = had_nip
    result["had_nip"] = had_nip
    result["kept_portal"] = keep_portal
    result["kept_scheduler"] = keep_scheduler
    return result


def do_logout_interactive(current_user=None):
    """Menu logout interaktif: konfirmasi, wipe, auto-disable, scheduler cleanup.

    Akan dipanggil dari main() menu [O].
    Return (should_exit_to_setup: bool, new_config: dict)
    """
    clear()
    header("🚪 LOGOUT AKUN")
    print()
    cfg = load_config()

    nip = cfg.get("nip", "")
    has_portal = bool(cfg.get("portal_user") and cfg.get("portal_password"))
    auto_on = cfg.get("auto_enabled", False)
    sched_on = scheduler_is_installed()
    os_name = "Task Scheduler" if platform.system() == "Windows" else "cron"

    # Info akun aktif
    if current_user and isinstance(current_user, dict):
        nama = current_user.get("namaLengkap", "?")
        print(f"  {C['B']}Akun aktif:{C['R']} {nama} {C['D']}({nip}){C['R']}")
    elif nip:
        print(f"  {C['B']}Akun aktif:{C['R']} {nip}")
    else:
        print(f"  {C['Y']}⚠ Tidak ada akun tersimpan di config{C['R']}")
        print(f"  {C['D']}Token di RAM akan dibuang, tapi tidak ada kredensial file yang dihapus.{C['R']}")
        print()
        input(f"  {C['D']}[Enter]{C['R']}")
        return False, cfg

    print()
    print(f"  {C['Y']}{C['B']}Yang akan terjadi saat logout:{C['R']}")
    print(f"  {C['D']}  {'─'*44}{C['R']}")
    print(f"  {C['RE']}  ✗ Hapus:{C['R']} NIP + Password SUPER-I")
    if has_portal:
        print(f"  {C['RE']}  ✗ Hapus:{C['R']} Portal APD (user + password)")
    else:
        print(f"  {C['D']}  · Portal APD belum diset{C['R']}")
    print(f"  {C['G']}  ✓ Keep:{C['R']} GI ID, Portal URL, history_days (setting non-kredensial)")
    print(f"  {C['RE']}  ✗ Auto Mode:{C['R']} {'AKTIF -> akan OTOMATIS NONAKTIF' if auto_on else 'sudah nonaktif'}")
    sched_msg = 'TERPASANG -> akan OTOMATIS DIHAPUS' if sched_on else 'belum terpasang'
    print(f"  {C['RE']}  ✗ Scheduler {os_name}:{C['R']} {sched_msg}")
    print(f"  {C['D']}  · Token RAM: dibuang (perlu Login Ulang / Setup){C['R']}")
    print(f"  {C['D']}  · Backup: .superi_config.json.bak akan dibuat{C['R']}")
    print()

    # Opsi
    keep_portal = False
    keep_sched = False

    if has_portal:
        ans = input(f"  {C['B']}Tetap simpan kredensial Portal APD?{C['R']} {C['D']}(y/N){C['R']}: ").strip().lower()
        keep_portal = (ans == 'y')

    if sched_on:
        ans2 = input(f"  {C['B']}Hapus jadwal {os_name}?{C['R']} {C['D']}(Y/n){C['R']}: ").strip().lower()
        # default Y (hapus), n = keep
        keep_sched = (ans2 == 'n')

    print()
    final = input(f"  {C['RE']}{C['B']}Yakin logout & hapus kredensial?{C['R']} {C['D']}(y/N){C['R']}: ").strip().lower()
    if final != 'y':
        print(f"\n  {C['Y']}⊘ Logout dibatalkan.{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return False, cfg

    # Eksekusi
    print()
    print(f"  {C['Y']}Melakukan logout...{C['R']}")

    bak_path = backup_config()
    if bak_path:
        print(f"  {C['D']}  · Backup dibuat: {os.path.basename(bak_path)}{C['R']}")

    # Wipe
    status = clear_credentials(
        purge_all=False,
        keep_portal=keep_portal,
        keep_scheduler=keep_sched,
    )

    # Verifikasi
    new_cfg = load_config()
    print(f"  {C['G']}  ✓ Kredensial SUPER-I dihapus{C['R']}")
    if not keep_portal and has_portal:
        print(f"  {C['G']}  ✓ Kredensial Portal APD dihapus{C['R']}")
    elif keep_portal:
        print(f"  {C['D']}  · Kredensial Portal APD dipertahankan{C['R']}")

    if status.get("auto_status") is None:
        # kita sudah set auto_enabled=False di clear_credentials
        print(f"  {C['G']}  ✓ Auto Mode OTOMATIS NONAKTIF{C['R']}")
    if sched_on and not keep_sched:
        if not scheduler_is_installed():
            print(f"  {C['G']}  ✓ Scheduler {os_name} OTOMATIS DIHAPUS{C['R']}")
        else:
            print(f"  {C['Y']}  ⚠ Gagal hapus {os_name}, silakan hapus manual{C['R']}")

    print()
    print(f"  {C['G']}✓ Logout berhasil!{C['R']}")
    print(f"  {C['D']}  Token di RAM sudah dibuang.{C['R']}")
    print(f"  {C['D']}  Gunakan [S] Setup untuk login akun baru, atau{C['R']}")
    print(f"  {C['D']}  tutup dan buka CLI lagi -> otomatis minta setup.{C['R']}")
    print()
    print(f"  {C['D']}  Untuk login ulang: NIP + password baru akan diminta saat{C['R']}")
    print(f"  {C['D']}  kamu pilih [S] Setup atau next start.{C['R']}")
    print()
    input(f"  {C['D']}[Enter untuk kembali ke menu...]{C['R']}")

    return True, new_cfg


def cmd_logout_cli(argv):
    """Non-interactive CLI: superi_app.py --logout [options]
    Options:
      --yes              skip konfirmasi
      --purge-all        hapus file config total
      --keep-portal      jangan hapus portal creds
      --keep-scheduler   jangan uninstall cron/task
    """
    purge_all = "--purge-all" in argv
    keep_portal = "--keep-portal" in argv
    keep_sched = "--keep-scheduler" in argv
    force_yes = "--yes" in argv or "-y" in argv

    cfg = load_config()
    nip = cfg.get("nip", "")
    has_portal = bool(cfg.get("portal_user"))
    auto_on = cfg.get("auto_enabled", False)
    sched_on = scheduler_is_installed()

    if not nip and not os.path.exists(CONFIG_FILE):
        print(f"  {C['Y']}⚠ Tidak ada config ditemukan, tidak ada yang perlu di-logout{C['R']}")
        return True

    if not force_yes:
        print()
        print(f"  {C['Y']}{C['B']}LOGOUT{C['R']}")
        if nip:
            print(f"  Akun: {nip}")
        if auto_on:
            print(f"  Auto: AKTIF → akan NONAKTIF otomatis")
        if sched_on:
            print(f"  Scheduler: TERPASANG → akan DIHAPUS otomatis" + (" (skip karena --keep-scheduler)" if keep_sched else ""))
        print(f"  Wipe : {'FULL PURGE (hapus file total)' if purge_all else 'nip/password' + ('' if not has_portal or keep_portal else ' + portal')}")
        print()
        ans = input(f"  Yakin logout? (y/N): ").strip().lower()
        if ans != 'y':
            print(f"  {C['Y']}⊘ Dibatalkan{C['R']}")
            return False

    bak = backup_config()
    if bak:
        print(f"  Backup: {bak}")

    status = clear_credentials(
        purge_all=purge_all,
        keep_portal=keep_portal,
        keep_scheduler=keep_sched,
    )

    if purge_all:
        print(f"  {C['G']}✓ Config file dihapus total (purge){C['R']}")
    else:
        print(f"  {C['G']}✓ Kredensial SUPER-I dihapus, auto_enabled=False{C['R']}")
        if not keep_portal and has_portal:
            print(f"  {C['G']}✓ Portal kredensial dihapus{C['R']}")
        if sched_on and not keep_sched:
            if not scheduler_is_installed():
                print(f"  {C['G']}✓ Scheduler dihapus{C['R']}")
            else:
                print(f"  {C['Y']}⚠ Scheduler gagal dihapus (cek permission){C['R']}")

    print()
    print(f"  {C['G']}✓ Logout berhasil. Login ulang: jalankan superi cli → [S] Setup{C['R']}")
    return True

_VALID_HISTORY_DAYS = {3, 7, 14}

def get_history_days():
    """Baca history_days dari config, validasi (3/7/14), fallback 7."""
    cfg = load_config()
    val = cfg.get("history_days", 7)
    try:
        val = int(val)
    except (TypeError, ValueError):
        return 7
    return val if val in _VALID_HISTORY_DAYS else 7


# === FOTO SOURCE: manual (per-item sesuai) vs pool (1 foto untuk semua) ===
_VALID_PHOTO_SOURCES = {"pool", "manual"}
_DEFAULT_PHOTO_SOURCE = "pool"


def get_photo_source():
    """Baca photo_source dari config, validasi pool/manual, fallback pool."""
    cfg = load_config()
    # env override untuk testing
    env_val = os.environ.get("SUPERI_PHOTO_SOURCE", "").strip().lower()
    if env_val in _VALID_PHOTO_SOURCES:
        return env_val
    v = cfg.get("photo_source", _DEFAULT_PHOTO_SOURCE)
    if not v:
        return _DEFAULT_PHOTO_SOURCE
    v = str(v).lower().strip()
    return v if v in _VALID_PHOTO_SOURCES else _DEFAULT_PHOTO_SOURCE


def set_photo_source(source: str):
    """Set photo_source ke config, return True jika sukses."""
    src = str(source).lower().strip()
    if src not in _VALID_PHOTO_SOURCES:
        return False
    cfg = load_config()
    cfg["photo_source"] = src
    save_config(cfg)
    return True


def login(nip, password):
    """Login ke SUPER-I APP, dengan handling 401 yang jelas."""
    try:
        req = urllib.request.Request(AUTH_URL,
            data=json.dumps({"nip": nip, "password": password}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if not data.get("success"):
            raise Exception(data.get("message", "Login gagal"))
        return data["data"]["access_token"], data["data"]["user"]
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            err_data = json.loads(body)
            msg = err_data.get("message", "")
        except Exception:
            msg = e.reason if hasattr(e, 'reason') else str(e)
        if e.code == 401:
            raise Exception(f"NIP atau password salah! ({msg or 'Unauthorized'}). Cek kembali kredensial di .superi_config.json atau jalankan [S] Setup untuk perbarui.")
        raise Exception(f"HTTP {e.code}: {msg or e.reason}")
    except urllib.error.URLError as e:
        raise Exception(f"Tidak bisa terhubung ke server: {e.reason}. Cek koneksi internet / VPN PLN.")


def api_get(token, path, params=None):
    url = f"{API_BASE}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def api_delete(token, path):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def _infer_data_type_from_path(path: str) -> str:
    if "tegangan-trafo" in path:
        return "tegangan-trafo"
    if "beban-trafo" in path:
        return "beban-trafo"
    return "beban-penyulang"


def _verify_tegangan_photo_upload(token, data_dict, result):
    """Verify that a successful voltage input stored both readable images."""
    verification = {"ok": False, "error": "record tegangan tidak ditemukan"}
    record_id = (result.get("data") or {}).get("id")
    if not record_id:
        return verification

    try:
        date_str = f"{int(data_dict['tahun']):04d}-{int(data_dict['bulan']) + 1:02d}-{int(data_dict['tanggal']):02d}"
        gi_id = load_config().get("gi_id", "222")
        record = None
        for attempt in range(3):
            listed = api_get(
                token,
                ENDPOINTS["tegangan-trafo"]["list"],
                {"garduIndukId": gi_id, "date": date_str},
            )
            record = next(
                (
                    entry
                    for item in listed.get("data", {}).get("items", [])
                    for entry in item.get("tegangan", [])
                    if entry.get("id") == record_id
                ),
                None,
            )
            if record:
                break
            if attempt < 2:
                time.sleep(1)
        if not record:
            return verification

        uris = {
            "HV": (record.get("fotoHV") or {}).get("uri"),
            "MV": (record.get("fotoMV") or {}).get("uri"),
        }
        missing = [name for name, uri in uris.items() if not uri]
        if missing:
            verification["error"] = f"URI foto {'/'.join(missing)} tidak dibuat server"
            verification["uris"] = uris
            return verification

        sizes = {}
        for name, uri in uris.items():
            req = urllib.request.Request(
                f"{BASE_URL}/api{uri}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
            if not content.startswith(b"\xff\xd8") or len(content) < 1000:
                verification["error"] = f"media foto {name} bukan JPEG valid"
                verification["uris"] = uris
                return verification
            sizes[name] = len(content)

        return {"ok": True, "uris": uris, "sizes": sizes}
    except Exception as exc:
        verification["error"] = f"verifikasi media gagal: {exc}"
        return verification


def api_post_multipart(token, path, data_dict, file_bytes, file_field, num_photos, item_name=None):
    """
    POST multipart dengan foto dari pool/manual per-item.

    - Content bytes: dari photo/manual/{data_type}/{ITEM}/ random (jika manual mode + item_name)
      atau dari photo/pool/ 1 foto untuk semua (jika pool mode)
      + varian blur/kabur/asli/noisy_gelap random 40/20/10/15/15
    - Filename upload beban memakai humanizer fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg.
      Khusus tegangan, nama part transport wajib fotoHV.jpg dan fotoMV.jpg seperti APK GAMA;
      server tetap menyimpannya dengan nama acak fotoHV/fotoMV_YYYY-MM-DD_<hex>.jpg.

    OFF: sudah di-skip di batch_fill_periode (statusCB==OFF skip), foto OFF tetap disimpan tapi tidak dipakai input.
    Foto tidak dihapus setelah dipakai (read-only random choice).
    """
    # Jangan mengubah payload milik caller saat membuang metadata internal.
    data_dict = dict(data_dict)
    # _item_name_hint adalah internal only, jangan ikut ke JSON payload (server reject 400 jika ada property unknown)
    item_name = item_name or data_dict.pop("_item_name_hint", None)

    url = f"{API_BASE}{path}"
    inner = json.dumps(data_dict)

    bd = hu.rand_boundary() if hu else BOUNDARY
    foto_ts_for_name = None
    if data_dict.get("foto", {}).get("date"):
        foto_ts_for_name = data_dict["foto"]["date"]
    elif data_dict.get("fotoHV", {}).get("date"):
        foto_ts_for_name = data_dict["fotoHV"]["date"]

    data_type_hint = _infer_data_type_from_path(path)
    photo_source = get_photo_source()

    # Content harus mirip aplikasi asli: STRICT 720x720 baseline, no EXIF, varian blur/kabur/asli.
    if hu:
        if num_photos > 1:
            # Tegangan: HV dari .../hv/, MV dari .../mv/ terpisah (manual mode), distinct & size beda — STRICT 720x720
            jb1 = hu.rand_jpeg_bytes(target_w=720, target_h=720, item_name=item_name, data_type=data_type_hint, subtype="HV", photo_source=photo_source)
            jb2 = hu.rand_jpeg_bytes(target_w=720, target_h=720, item_name=item_name, data_type=data_type_hint, subtype="MV", photo_source=photo_source)
            # Pastikan SHA beda & size beda minimal 500 byte (2 foto berbeda seperti aplikasi asli)
            try:
                import hashlib
                tries = 0
                while (jb1 == jb2 or hashlib.sha256(jb1).hexdigest() == hashlib.sha256(jb2).hexdigest() or abs(len(jb1)-len(jb2)) < 500) and tries < 12:
                    # Coba variant berbeda untuk MV — tetap 720x720
                    jb2 = hu.rand_jpeg_bytes(target_w=720, target_h=720, item_name=item_name, data_type=data_type_hint, subtype="MV", photo_source=photo_source)
                    tries += 1
                # Jika masih sama, pakai pair yang sudah ensure distinct
                if jb1 == jb2 or hashlib.sha256(jb1).hexdigest() == hashlib.sha256(jb2).hexdigest():
                    jb1, jb2 = hu.rand_jpeg_pair(target_w=720, target_h=720, item_name=item_name, data_type=data_type_hint, photo_source=photo_source)
            except:
                pass
            jpeg_pool = [jb1, jb2]
        else:
            jpeg_pool = [hu.rand_jpeg_bytes(target_w=720, target_h=720, item_name=item_name, data_type=data_type_hint, photo_source=photo_source)]
    else:
        jpeg_pool = [file_bytes]

    body_parts = [f'--{bd}\r\nContent-Disposition: form-data; name="data"\r\n\r\n{inner}\r\n'.encode()]

    for i in range(num_photos):
        if hu:
            if num_photos > 1 and i == 1 and "fotoMV" in data_dict:
                fn_ts = data_dict.get("fotoMV", {}).get("date") or foto_ts_for_name
                subtype = "MV"
            elif num_photos > 1 and i == 0:
                fn_ts = data_dict.get("fotoHV", {}).get("date") or foto_ts_for_name
                subtype = "HV"
            else:
                fn_ts = foto_ts_for_name
                subtype = None
            fname = hu.rand_filename(fn_ts, idx=i, data_type=data_type_hint, subtype=subtype)
            fbytes = jpeg_pool[i % len(jpeg_pool)]
        else:
            # fallback manual-like filename
            import uuid as _uuid
            date_part = data_dict.get("foto", {}).get("date", "")[:10] or "2026-07-15"
            hex16 = _uuid.uuid4().hex[:16]
            if "tegangan" in data_type_hint:
                pref = f"foto{'MV' if i==1 else 'HV'}"
                fname = f"{pref}_{date_part}_{hex16[:12]}.jpg"
            elif "beban-trafo" in data_type_hint:
                fname = f"fotoBebanTrafo_{date_part}_{hex16}.jpg"
            else:
                fname = f"fotoBebanPenyulang_{date_part}_{hex16}.jpg"
            fbytes = file_bytes if isinstance(file_bytes, bytes) else file_bytes

        # Backend tegangan menentukan slot foto dari filename part seperti APK GAMA.
        # Nama acak project tetap dipakai oleh server pada URI file yang tersimpan.
        if data_type_hint == "tegangan-trafo" and num_photos > 1:
            fname = "fotoMV.jpg" if i == 1 else "fotoHV.jpg"

        # Pastikan filename HV & MV tidak sama untuk endpoint selain tegangan.
        if data_type_hint != "tegangan-trafo" and num_photos > 1 and i == 1:
            # Cek duplicate filename dengan part sebelumnya
            prev_fname = ""
            try:
                # Cari filename sebelumnya di body_parts
                for part in body_parts[::-1]:
                    if b'filename="' in part:
                        prev_fname = part.split(b'filename="')[1].split(b'"')[0].decode()
                        break
            except:
                pass
            if prev_fname and fname == prev_fname:
                fname = fname.replace(".jpg", "_2.jpg")

        body_parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{fname}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
        body_parts.append(fbytes if isinstance(fbytes, bytes) else fbytes)
        body_parts.append(b'\r\n')
    body_parts.append(f'--{bd}--\r\n'.encode())
    body = b''.join(body_parts)

    hdrs = {
        "Content-Type": f"multipart/form-data; boundary={bd}",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": hu.rand_user_agent() if hu else "okhttp/4.12.0",
    }

    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            result = json.loads(resp.read())
        if result.get("success") and data_type_hint == "tegangan-trafo":
            result["_photo_upload"] = _verify_tegangan_photo_upload(token, data_dict, result)
        return status, result
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"message": str(e)}

# ============================================================
# MENU SYSTEM
# ============================================================

def fetch_history_bulk(token, data_type, gi_id, date_str, days_back=None, _cache={}):
    """
    Fetch N hari data SEKALI saja, return dict dengan semua data periode dan weekday/weekend flag.
    days_back default dari config (history_days, fallback 7).
    Reuse hasil ini untuk multiple item agar tidak refetch.
    
    Cached per (data_type, gi_id, date_str, days_back) — call kedua di hari yang sama instant.
    """
    if days_back is None:
        days_back = get_history_days()
    cache_key = (data_type, gi_id, date_str, days_back)
    if cache_key in _cache:
        return _cache[cache_key]
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta, datetime as dt
    from collections import defaultdict
    
    today = dt.strptime(date_str, "%Y-%m-%d")
    
    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    path = paths[data_type]
    
    def fetch_day(offset):
        d = today - timedelta(days=offset)
        return d.weekday() >= 5, api_get(token, path, {"garduIndukId": gi_id, "date": d.strftime("%Y-%m-%d")})
    
    # Fetch parallel (8 workers, server-friendly)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_day, range(1, days_back + 1)))
    
    # Build cache: item_id → periode → values
    cache = {}
    for is_weekend, result in results:
        items = result.get("data", {}).get("items", [])
        for it in items:
            item_id = it["id"]
            if item_id not in cache:
                cache[item_id] = {
                    "name": it["nama"],
                    "statusCB": it.get("statusCB"),
                    "periode_data": defaultdict(lambda: {"all": [], "weekday": [], "weekend": []})
                }
            
            if data_type == "tegangan-trafo":
                for e in it.get("tegangan", []):
                    periode = e["periode"]
                    cache[item_id]["periode_data"][periode]["all"].append(e)
                    if is_weekend:
                        cache[item_id]["periode_data"][periode]["weekend"].append(e)
                    else:
                        cache[item_id]["periode_data"][periode]["weekday"].append(e)
            else:
                if it.get("statusCB") == "OFF":
                    continue
                for e in it.get("beban", []):
                    periode = e["periode"]
                    val = e["beban"]
                    cache[item_id]["periode_data"][periode]["all"].append(val)
                    if is_weekend:
                        cache[item_id]["periode_data"][periode]["weekend"].append(val)
                    else:
                        cache[item_id]["periode_data"][periode]["weekday"].append(val)
    
    _cache[cache_key] = cache
    return cache

def smart_suggest_from_cache(cache, item_id, periode, target_is_weekend):
    """Hitung smart suggest dari cache (no API call). Untuk beban penyulang/trafo."""
    if item_id not in cache:
        return None, None
    
    pdata = cache[item_id]["periode_data"].get(periode)
    if not pdata or not pdata["all"]:
        return None, None
    
    all_vals = pdata["all"]
    if target_is_weekend:
        pattern_vals = pdata["weekend"] if pdata["weekend"] else all_vals
        pattern_type = "weekend"
    else:
        pattern_vals = pdata["weekday"] if pdata["weekday"] else all_vals
        pattern_type = "weekday"
    
    base_avg = sum(all_vals) / len(all_vals)
    pattern_avg = sum(pattern_vals) / len(pattern_vals)
    smart_avg = 0.5 * pattern_avg + 0.5 * base_avg
    
    suggested = round(smart_avg / 5) * 5
    
    if pattern_vals:
        p_min, p_max = min(pattern_vals), max(pattern_vals)
        suggested = max(p_min, min(p_max, suggested))
    
    return int(suggested), f"{pattern_type} avg {pattern_avg:.0f}A"


def smart_suggest_tegangan_from_cache(cache, item_id, periode, target_is_weekend):
    """Hitung smart suggest TEGANGAN dari cache (per-periode, weekday/weekend aware).
    
    Aturan pembulatan MV per trafo:
    - TRAFO PS 1 / TRAFO PS 2: bulat (0 desimal, mis. 385, 390)
    - TRAFO 1: 1 desimal (mis. 20.3, 20.4)
    - TRAFO 2 / TRAFO 3 / lainnya: 2 desimal (mis. 20.43)
    
    Aturan HV trafo PS (engineering rule):
    - HV TRAFO PS 1 = MV TRAFO 1 (sisi 20kV trafo sumber)
    - HV TRAFO PS 2 = MV TRAFO 3 (sisi 20kV trafo sumber)
    
    Returns: (mv_suggest, hv_suggest, info_str) atau (None, None, None)
    """
    if item_id not in cache:
        return None, None, None
    
    pdata = cache[item_id]["periode_data"].get(periode)
    if not pdata or not pdata["all"]:
        return None, None, None
    
    nama = cache[item_id].get("name", "").upper()
    
    # Tentukan jumlah desimal MV berdasar nama trafo
    if "PS" in nama:
        mv_decimals = 0  # TRAFO PS 1/2 → bulat
    elif nama == "TRAFO 1":
        mv_decimals = 1  # TRAFO 1 → 1 desimal
    else:
        mv_decimals = 2  # default (TRAFO 2/3) → 2 desimal
    
    all_entries = pdata["all"]
    if target_is_weekend:
        pattern_entries = pdata["weekend"] if pdata["weekend"] else all_entries
        pattern_type = "weekend"
    else:
        pattern_entries = pdata["weekday"] if pdata["weekday"] else all_entries
        pattern_type = "weekday"
    
    # Extract MV & HV values
    all_mv = [e["mv"] for e in all_entries]
    all_hv = [e["hv"] for e in all_entries]
    pat_mv = [e["mv"] for e in pattern_entries]
    pat_hv = [e["hv"] for e in pattern_entries]
    
    # MV: rata-rata weighted (50% pattern + 50% base), pembulatan per aturan trafo
    base_mv = sum(all_mv) / len(all_mv)
    pattern_mv = sum(pat_mv) / len(pat_mv)
    smart_mv = 0.5 * pattern_mv + 0.5 * base_mv
    smart_mv = round(smart_mv, mv_decimals)
    
    # Clamp MV ke range histori, lalu round ulang sesuai aturan
    if pat_mv:
        smart_mv = max(min(pat_mv), min(max(pat_mv), smart_mv))
        smart_mv = round(smart_mv, mv_decimals)
    
    # Kalau 0 desimal, pastikan tipe int
    if mv_decimals == 0:
        smart_mv = int(smart_mv)
    
    # HV: aturan engineering PS — HV PS = MV trafo sumber
    if "PS" in nama:
        # Cari trafo sumber: PS 1 → TRAFO 1, PS 2 → TRAFO 3
        if "1" in nama:
            source_target = "TRAFO 1"
        elif "2" in nama:
            source_target = "TRAFO 3"
        else:
            source_target = None
        
        # Cari MV trafo sumber di cache untuk periode yang sama
        source_mv = None
        if source_target:
            for sid, sdata in cache.items():
                if sdata.get("name", "").upper() == source_target:
                    src_p = sdata["periode_data"].get(periode)
                    if src_p and src_p["all"]:
                        # Pakai logika weekday/weekend yang sama
                        if target_is_weekend:
                            src_pat = src_p["weekend"] if src_p["weekend"] else src_p["all"]
                        else:
                            src_pat = src_p["weekday"] if src_p["weekday"] else src_p["all"]
                        src_mv_vals = [e["mv"] for e in src_pat]
                        src_all_mv = [e["mv"] for e in src_p["all"]]
                        if src_mv_vals:
                            base_src = sum(src_all_mv) / len(src_all_mv)
                            pat_src = sum(src_mv_vals) / len(src_mv_vals)
                            source_mv = 0.5 * pat_src + 0.5 * base_src
                            # Bulatkan sesuai aturan trafo sumber
                            src_decimals = 1 if source_target == "TRAFO 1" else 2
                            source_mv = round(source_mv, src_decimals)
                            # Clamp
                            source_mv = max(min(src_mv_vals), min(max(src_mv_vals), source_mv))
                            source_mv = round(source_mv, src_decimals)
                    break
        
        if source_mv is not None:
            smart_hv = source_mv
            info = f"{pattern_type} MV={pattern_mv:.0f} | HV=MV {source_target}={source_mv} ({len(pat_mv)}d)"
        else:
            # Fallback: pakai histori HV PS sendiri (lama)
            base_hv = sum(all_hv) / len(all_hv)
            pattern_hv = sum(pat_hv) / len(pat_hv)
            smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
            smart_hv = round(smart_hv, 2)
            if pat_hv:
                smart_hv = max(min(pat_hv), min(max(pat_hv), smart_hv))
                smart_hv = round(smart_hv, 2)
            info = f"{pattern_type} MV={pattern_mv:.0f} HV={pattern_hv:.2f} (fallback {len(pat_mv)}d)"
    else:
        # Trafo biasa: HV ~150kV, integer
        base_hv = sum(all_hv) / len(all_hv)
        pattern_hv = sum(pat_hv) / len(pat_hv)
        smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
        smart_hv = round(smart_hv)
        if pat_hv:
            smart_hv = max(min(pat_hv), min(max(pat_hv), smart_hv))
        smart_hv = int(smart_hv)
        info = f"{pattern_type} MV={pattern_mv:.2f} HV={pattern_hv:.0f} ({len(pat_mv)}d)"
    
    return smart_mv, smart_hv, info

def smart_suggest_value(token, data_type, item_id, periode, date_str, days_back=None, gi_id=None):
    """
    Smart suggest berdasarkan:
    1. Weekday vs weekend pattern
    2. N hari historis (default dari config: history_days, fallback 7)
    3. Range clamping
    4. Kelipatan 5 untuk beban
    """
    from datetime import timedelta, datetime as dt
    from concurrent.futures import ThreadPoolExecutor

    if days_back is None:
        days_back = get_history_days()
    if gi_id is None:
        try:
            gi_id = load_config().get("gi_id", 222)
        except:
            gi_id = 222
    
    today = dt.strptime(date_str, "%Y-%m-%d")
    is_target_weekend = today.weekday() >= 5
    
    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
    }
    
    def fetch_day(offset):
        d = today - timedelta(days=offset)
        return offset, d, d.weekday() >= 5, api_get(token, paths[data_type], 
            {"garduIndukId": gi_id, "date": d.strftime("%Y-%m-%d")})
    
    all_vals = []
    weekday_vals = []
    weekend_vals = []
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_day, range(1, days_back + 1)))
    
    for offset, d, d_is_weekend, result in results:
        items = result.get("data", {}).get("items", [])
        for it in items:
            if it["id"] != item_id or it.get("statusCB") == "OFF":
                continue
            for e in it.get("beban", []):
                if e["periode"] == periode:
                    val = e["beban"]
                    all_vals.append(val)
                    if d_is_weekend:
                        weekend_vals.append(val)
                    else:
                        weekday_vals.append(val)
    
    if not all_vals:
        return None, None
    
    # Smart formula: 50% pattern + 50% base
    base_avg = sum(all_vals) / len(all_vals)
    
    if is_target_weekend:
        pattern_vals = weekend_vals if weekend_vals else all_vals
        pattern_type = "weekend"
    else:
        pattern_vals = weekday_vals if weekday_vals else all_vals
        pattern_type = "weekday"
    
    pattern_avg = sum(pattern_vals) / len(pattern_vals)
    smart_avg = 0.5 * pattern_avg + 0.5 * base_avg
    
    # Round ke kelipatan 5
    suggested = round(smart_avg / 5) * 5
    
    # Clamp ke range historis pattern
    if pattern_vals:
        p_min, p_max = min(pattern_vals), max(pattern_vals)
        suggested = max(p_min, min(p_max, suggested))
    
    return int(suggested), f"{pattern_type} avg {pattern_avg:.0f}A"

def clear():
    os.system('clear' if os.name != 'nt' else 'cls')

# Terminal colors
C = {
    'R': '\033[0m',      # Reset
    'B': '\033[1m',      # Bold
    'D': '\033[2m',      # Dim
    'G': '\033[92m',     # Green
    'Y': '\033[93m',     # Yellow
    'RE': '\033[91m',    # Red
    'C': '\033[96m',     # Cyan
    'M': '\033[95m',     # Magenta
    'W': '\033[97m',     # White
    'BG': '\033[44m',    # Blue background
}

def header(title):
    w = 60
    print(f"{C['C']}{'━' * w}")
    print(f"  {C['B']}{C['W']}{title}{C['R']}")
    print(f"{C['C']}{'━' * w}{C['R']}")

def sub_header(title):
    print(f"\n  {C['C']}▸ {C['B']}{title}{C['R']}")
    print(f"  {C['D']}{'─' * 50}{C['R']}")

def status_bar(user, gi_id, date_str):
    """Status bar di bawah header."""
    if user:
        print(f"  {C['D']}┌─────────────────────────────────────────────────────┐{C['R']}")
        print(f"  {C['D']}│{C['R']}  {C['G']}●{C['R']} {C['B']}{user['namaLengkap']}{C['R']} {C['D']}({', '.join(user['roles'])}){C['R']}")
        print(f"  {C['D']}│{C['R']}  📍 GI: {gi_id}  📅 {date_str}")
        print(f"  {C['D']}└─────────────────────────────────────────────────────┘{C['R']}")
    else:
        print(f"  {C['D']}┌─────────────────────────────────────────────────────┐{C['R']}")
        print(f"  {C['D']}│{C['R']}  {C['RE']}○{C['R']} Belum login  📅 {date_str}")
        print(f"  {C['D']}└─────────────────────────────────────────────────────┘{C['R']}")

def menu(title, options):
    """Tampilkan menu dan return pilihan user."""
    while True:
        clear()
        header(title)
        for i, (key, desc) in enumerate(options, 1):
            print(f"  [{i}] {desc}")
        print(f"  [0] Keluar")
        print()
        try:
            choice = input("  Pilih > ").strip()
            if choice == '0':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except (ValueError, IndexError):
            pass
        print(f"  {C['RE']}✗ Pilihan tidak valid!{C['R']}")

def input_with_default(prompt, default=""):
    if default:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"  {prompt}: ").strip()

def confirm(msg):
    return input(f"  {msg} {C['D']}(y/n){C['R']}: ").strip().lower() == 'y'

# ============================================================
# WORKFLOW
# ============================================================

def setup_config():
    """Setup kredensial pertama kali."""
    clear()
    header("⚙  SETUP KREDENSIAL")
    print()
    print(f"  {C['D']}Kredensial akan disimpan di ~/.superi_config.json{C['R']}")
    print(f"  {C['D']}Gardu Induk akan otomatis terdeteksi dari profil.{C['R']}")
    print()

    # --- SUPER-I APP ---
    print(f"  {C['M']}{C['B']}1. SUPER-I APP{C['R']} {C['D']}(super-i-app.plnes.co.id){C['R']}")
    nip = input(f"  {C['B']}NIP{C['R']}        : ").strip()
    password = input(f"  {C['B']}Password{C['R']}   : ").strip()
    print()

    # --- Portal APD Jakarta ---
    print(f"  {C['M']}{C['B']}2. Portal APD Jakarta{C['R']} {C['D']}(10.3.187.6/apdjakarta){C['R']}")
    print(f"  {C['D']}Untuk sinkronisasi data. Kosongkan jika tidak dipakai.{C['R']}")
    portal_user = input(f"  {C['B']}Username{C['R']}   : ").strip()
    portal_password = input(f"  {C['B']}Password{C['R']}   : ").strip()

    # Pertahankan config lama (gi_id, portal_url, portal_gi_id) jika ada
    config = load_config()
    config["nip"] = nip
    config["password"] = password
    if portal_user:
        config["portal_user"] = portal_user
    if portal_password:
        config["portal_password"] = portal_password
    # Default Portal APD jika belum diset
    config.setdefault("portal_url", "http://10.3.187.6/apdjakarta")
    config.setdefault("portal_gi_id", "143")
    config.setdefault("gi_id", "222")

    save_config(config)
    print()
    print(f"  {C['G']}✓ Konfigurasi tersimpan!{C['R']}")
    if portal_user and portal_password:
        print(f"  {C['G']}✓ Portal APD siap untuk sinkronisasi{C['R']}")
    else:
        print(f"  {C['Y']}⚠ Credentials Portal APD belum lengkap — sync tidak aktif{C['R']}")
    input(f"  {C['D']}[Enter untuk lanjut...]{C['R']}")

def do_login(config):
    """Login, return token, user info, dan gi_id. Handling 401 dengan petunjuk jelas."""
    nip = config.get("nip")
    password = config.get("password")
    if not nip or not password:
        print(f"  {C['RE']}✗ Konfigurasi belum di-setup. Jalankan setup dulu.{C['R']}")
        print(f"  {C['D']}  File: {CONFIG_FILE}{C['R']}")
        print(f"  {C['D']}  Atau pilih [S] Setup di menu.{C['R']}")
        return None, None, None
    
    try:
        token, user = login(nip, password)
        
        # Auto-detect GI ID dari lokasi absensi
        req = urllib.request.Request(
            f"{API_BASE}/absensi/info?timezone=Asia/Jakarta",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            info = json.loads(resp.read())["data"]
            loc = info.get("absenLocation", {})
            coords = loc.get("coordinates", [])
            gi_name = coords[0].get("nama", "") if coords else ""
        
        # Cari GI ID dari data beban penyulang
        gi_id = config.get("gi", 222)  # fallback
        if gi_name:
            try:
                req2 = urllib.request.Request(
                    f"{API_BASE}/gama/opgi-20kv/operator-gi/beban-penyulang?garduIndukId=222&date={datetime.now().strftime('%Y-%m-%d')}",
                    headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    items = json.loads(resp2.read())["data"].get("items", [])
                    for item in items:
                        g = item.get("garduInduk", {})
                        if g.get("nama") == gi_name:
                            gi_id = g.get("id", gi_id)
                            break
            except:
                pass  # use fallback
        
        return token, user, gi_id
    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "password salah" in err_str.lower() or "unauthorized" in err_str.lower() or "NIP" in err_str:
            print(f"  {C['RE']}✗ Login gagal (401 Unauthorized):{C['R']}")
            print(f"  {C['Y']}  Penyebab: NIP atau password di config salah / kadaluarsa{C['R']}")
            print(f"  {C['D']}  NIP di config: {nip}{C['R']}")
            print(f"  {C['D']}  File: {CONFIG_FILE}{C['R']}")
            print()
            print(f"  {C['B']}Solusi:{C['R']}")
            print(f"    1. Pilih {C['C']}[S] Setup{C['R']} untuk input NIP/password baru")
            print(f"    2. Atau edit manual file .superi_config.json")
            print(f"    3. Pastikan NIP tanpa spasi, password sesuai akun PLN")
            print(f"    4. Cek apakah akun masih aktif & sudah clock-in di SUPER-I")
        else:
            print(f"  {C['RE']}✗ Login gagal: {e}{C['R']}")
        return None, None, None

def show_data(token, data_type, gi_id, date_str):
    """Tampilkan data dan periode kosong."""
    ep = ENDPOINTS[data_type]
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result["data"].get("items", [])
    
    if not items:
        print(f"  {C['Y']}Tidak ada data untuk {date_str}{C['R']}")
        return
    
    clear()
    header(f"📊 {ep['label']} · {date_str}")
    print()
    
    if ui:
        for ln in ui.render_data_view(items, data_type):
            print(ln)
        # Footer summary
        data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
        total_filled = sum(len(it.get(data_key, [])) for it in items)
        total_empty = len(items) * 24 - total_filled
        print()
        print(f"  {C['D']}{ui.render_data_summary(len(items), total_filled, total_empty)}{C['R']}")
    else:
        for item in items:
            nama = item.get("nama", "?")
            data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
            entries = item.get(data_key, [])
            periods = sorted([e["periode"] for e in entries])
            print(f"  [{item.get('id', '?')}] {nama} - {len(periods)}/24")
    
    print()
    input(f"  {C['D']}[Enter untuk kembali...]{C['R']}")

def input_single(token, data_type, gi_id, date_str, user_info):
    """Input data untuk satu target spesifik."""
    ep = ENDPOINTS[data_type]
    
    # Ambil daftar item
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result["data"].get("items", [])
    
    if not items:
        print(f"  Tidak ada item untuk {date_str}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    clear()
    header(f"✏  INPUT {ep['label']}")
    print()
    
    # Tampilkan daftar item (aligned table)
    if ui:
        for ln in ui.render_item_table(items, data_type):
            print(ln)
    else:
        for i, item in enumerate(items, 1):
            nama = item.get("nama", "?")
            data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
            periods = [e["periode"] for e in item.get(data_key, [])]
            print(f"  [{i}] {nama} - {len(periods)}/24")
    print()
    
    try:
        idx = int(input("  Pilih nomor item: ").strip()) - 1
        if idx < 0 or idx >= len(items):
            print(f"  {C['RE']}✗ Pilihan tidak valid!{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")
            return
    except ValueError:
        print(f"  {C['RE']}✗ Pilihan tidak valid!{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    item = items[idx]
    item_id = item["id"]
    nama = item["nama"]
    
    # Tolak CB OFF
    if item.get('statusCB') == 'OFF':
        print(f"\n  ⛔ {nama} CB OFF — tidak bisa input beban!")
        print("  (Circuit Breaker mati, tidak ada arus)")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
    entries = item.get(data_key, [])
    periods_filled = [e["periode"] for e in entries]
    empty_periods = [p for p in range(24) if p not in periods_filled]
    
    print(f"\n  Target: {nama} (ID:{item_id})")

    # Tampilkan data existing (compact)
    if entries:
        print(f"  {C['D']}Data existing:{C['R']}")
        if ui:
            for ln in ui.render_existing_data(entries, data_type):
                print(ln)
        else:
            for e in sorted(entries, key=lambda x: x["periode"]):
                if data_type == "tegangan-trafo":
                    print(f"    P{e['periode']:02d}: HV={e['hv']}kV, MV={e['mv']}kV")
                else:
                    print(f"    P{e['periode']:02d}: {e['beban']}A")
    
    if not empty_periods:
        print(f"\n  ✓ Semua periode sudah terisi (24/24)!")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    print(f"\n  Periode kosong: {empty_periods}")
    
    # Pilih periode
    try:
        per = int(input("  Periode yang akan diisi: ").strip())
        if per not in empty_periods and per not in range(24):
            print(f"  {C['RE']}✗ Periode tidak valid!{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")
            return
    except ValueError:
        print(f"  {C['RE']}✗ Periode tidak valid!{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    # Input nilai dengan saran SMART (weekday/weekend, histori N hari, kelipatan 5)
    suggested = ""
    suggested_mv = ""
    suggested_hv = ""
    
    if data_type == "tegangan-trafo":
        # Tegangan: tetap pakai logic lama (periode sebelumnya)
        if entries:
            sorted_entries = sorted(entries, key=lambda x: x["periode"])
            prev_entry = None
            for e in reversed(sorted_entries):
                if e["periode"] < per:
                    prev_entry = e
                    break
            if not prev_entry:
                prev_entry = sorted_entries[-1]
            prev_hv = prev_entry["hv"]
            prev_mv = prev_entry["mv"]
            suggested_mv = f"{prev_mv}"
            suggested_hv = f"{prev_hv}"
            print(f"    → Saran dari P{prev_entry['periode']:02d}: MV={prev_mv}kV, HV={prev_hv}kV")
    else:
        # Beban: SMART SUGGEST (weekday/weekend aware) — pakai gi_id dari config biar tidak hardcoded 222
        sys.stdout.write(f"    🧠 Menganalisis pola {get_history_days()} hari... ")
        sys.stdout.flush()
        smart_val, info = smart_suggest_value(token, data_type, item_id, per, date_str, gi_id=gi_id)
        if smart_val is not None:
            suggested = f" [smart: {smart_val}A]"
            sys.stdout.write(f"\r    {C['G']}✓{C['R']} Smart suggest: {smart_val}A ({info}){' ' * 6}\n")
        else:
            sys.stdout.write(f"\r    {C['Y']}•{C['R']} Smart suggest tidak tersedia{' ' * 6}\n")
            # Fallback ke periode sebelumnya
            if entries:
                sorted_entries = sorted(entries, key=lambda x: x["periode"])
                prev_entry = None
                for e in reversed(sorted_entries):
                    if e["periode"] < per:
                        prev_entry = e
                        break
                if not prev_entry:
                    prev_entry = sorted_entries[-1]
                prev_val = prev_entry["beban"]
                suggested = f" [P{prev_entry['periode']:02d}: {prev_val}A]"
            else:
                suggested = f" [tidak ada data]"
    
    if data_type == "tegangan-trafo":
        mv_str = input(f"  {C['B']}{'MV (kV)':<14}{C['R']} [{suggested_mv}]: ").strip()
        mv = float(mv_str) if mv_str else float(suggested_mv)
        hv_str = input(f"  {C['B']}{'HV (kV)':<14}{C['R']} [{suggested_hv}]: ").strip()
        hv = float(hv_str) if hv_str else float(suggested_hv)
        value = mv
        extra_values = {"hv": hv}
    else:
        val_str = input(f"  {C['B']}{'Nilai (A)':<14}{C['R']}{suggested}: ").strip()
        if not val_str and suggested:
            val_str = suggested.split(": ")[1].replace("A]", "")
        value = float(val_str)
        extra_values = {}
    
    if not confirm(f"\n  Input {nama} periode {per}: {value}{ep['unit']}?"):
        print(f"  {C['Y']}⊘ Dibatalkan.{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    durasi = _human_durasi(data_type)
    data_dict = {
        ep["id_field"]: item_id,
        "timezone": "Asia/Jakarta",
        "periode": per,
        "tanggal": dt.day,
        "bulan": dt.month - 1,
        "tahun": dt.year,
        "durasi": durasi,
        ep["value_field"]: value,
    }

    if data_type == "tegangan-trafo":
        fotoHV, fotoMV = _human_foto_pair_dicts(date_str, per, durasi)
        data_dict["hv"] = extra_values.get("hv", 150)
        data_dict["fotoHV"] = fotoHV
        data_dict["fotoMV"] = fotoMV
    else:
        data_dict["foto"] = _human_foto_dict(date_str, per, durasi, data_type)

    print("\n  Mengirim...")
    # Foto: per-item sesuai jika manual mode, 1 foto semua jika pool mode, filename tetap humanizer
    status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"], item_name=nama)
    
    if result.get("success"):
        photo_check = result.get("_photo_upload")
        if photo_check and not photo_check.get("ok"):
            print(f"  {C['Y']}⚠ NILAI TERSIMPAN! ID: {result['data'].get('id')}, tetapi foto gagal{C['R']}")
            print(f"  {C['RE']}✗ {photo_check.get('error')}{C['R']}")
        else:
            print(f"  {C['G']}✓ BERHASIL! ID: {result['data'].get('id')}{C['R']}")
    else:
        msg = result.get("message", str(result))
        if isinstance(msg, list):
            msg = ", ".join(msg)
        print(f"  {C['RE']}✗ Gagal ({status}): {msg}{C['R']}")
    
    print()
    input(f"  {C['D']}[Enter untuk kembali...]{C['R']}")

def offer_portal_sync(data_type, periodes, date_str):
    """Tanya operator apakah mau sync ke Portal PLN setelah batch fill sukses.
    
    Args:
        data_type: "beban-penyulang" | "beban-trafo" | "tegangan-trafo"
        periodes: list of int (jam-jam yang baru saja diinput, mis. [9] atau [9,10,11])
        date_str: "YYYY-MM-DD"
    """
    print()
    print(f"  {'─' * 55}")
    ans = input("  🔄 Sync data ini ke Portal PLN sekarang? (y/N): ").strip().lower()
    if ans != 'y':
        print("  ℹ Lewatkan sync. Bisa di-sync nanti dengan: superi sync")
        return
    
    # Map type ke format superi_sync (--type)
    sync_type_map = {
        "beban-penyulang": "penyulang",
        "beban-trafo": "trafo",
        "tegangan-trafo": "tegangan",
    }
    sync_type = sync_type_map[data_type]
    
    # Cek credentials Portal PLN
    try:
        import superi_sync
    except ImportError as e:
        print(f"  ✗ Modul superi_sync tidak ditemukan: {e}")
        return
    
    if not superi_sync.PORTAL_USER or not superi_sync.PORTAL_PASS:
        print(f"  {C['RE']}✗ Credentials Portal PLN belum diset di .superi_config.json{C['R']}")
        print("    Tambahkan: portal_user, portal_password")
        return
    
    # Tentukan rentang jam (kalau periodes berdekatan, pakai start-end; kalau tidak, sync satu-satu)
    print(f"\n  🔄 Menjalankan sync ke Portal PLN...")
    sorted_p = sorted(periodes)
    
    # Sync per jam (lebih aman, output jelas)
    all_ok = True
    for p in sorted_p:
        ok = superi_sync.do_sync(sync_type, p, p, date_str, dry_run=False)
        if not ok:
            all_ok = False
    
    if all_ok:
        print(f"\n  ✓ Sync ke Portal PLN selesai untuk {len(sorted_p)} jam")
    else:
        print(f"\n  ⚠ Sebagian sync gagal — cek log di atas")

def sync_portal_menu(date_str):
    """Sub-menu standalone: sync data SUPER-I → Portal APD (tanpa batch fill).

    Parity dengan offer_portal_sync tapi dipanggil langsung dari menu utama
    untuk re-sync periode yang sudah terisi di SUPER-I.
    """
    clear()
    header("🔄 SYNC KE PORTAL APD")
    print()
    print(f"  {C['D']}Sumber: SUPER-I APP  →  Tujuan: Portal APD Jakarta{C['R']}")
    print(f"  {C['D']}Tanggal: {date_str}{C['R']}")
    print()

    sub_header("Pilih jenis data")
    print(f"  {C['C']}[1]{C['R']} Beban Penyulang  (32 feeder)")
    print(f"  {C['C']}[2]{C['R']} Beban Trafo      (3 trafo)")
    print(f"  {C['C']}[3]{C['R']} Tegangan Trafo   (5 trafo, MV+HV)")
    print(f"  {C['C']}[4]{C['R']} SEMUA")
    print(f"  {C['D']}[0]{C['R']} Kembali")
    choice = input(f"  {C['B']}Pilih ▸ {C['R']}").strip()

    type_map = {"1": ["penyulang"], "2": ["trafo"], "3": ["tegangan"], "4": ["penyulang", "trafo", "tegangan"]}
    if choice not in type_map:
        return
    types = type_map[choice]

    # Jam
    jam_input = input_with_default("Jam (HH atau HH-HH, enter=semua)", "0-23")
    try:
        if "-" in jam_input:
            js, je = map(int, jam_input.split("-"))
        else:
            js = je = int(jam_input)
        js = max(0, min(23, js))
        je = max(0, min(23, je))
    except ValueError:
        print(f"  {C['RE']}✗ Format jam salah{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return

    date_input = input_with_default("Tanggal", date_str)

    # Cek modul + kredensial Portal APD
    try:
        import superi_sync
    except ImportError as e:
        print(f"  {C['RE']}✗ Modul superi_sync tidak ditemukan: {e}{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    if not superi_sync.PORTAL_USER or not superi_sync.PORTAL_PASS:
        print(f"  {C['RE']}✗ Credentials Portal APD belum diset di .superi_config.json{C['R']}")
        print(f"  {C['D']}  Setup via menu [S]{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return

    # Dry-run preview
    sub_header("DRY-RUN PREVIEW")
    for dt in types:
        superi_sync.do_sync(dt, js, je, date_input, dry_run=True)
    print()

    # Konfirmasi live
    if not confirm(f"{C['Y']}Lanjut LIVE SYNC?{C['R']}"):
        print(f"  {C['Y']}⊘ Dibatalkan — bisa di-sync nanti{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return

    sub_header("LIVE SYNC")
    all_ok = True
    for dt in types:
        ok = superi_sync.do_sync(dt, js, je, date_input, dry_run=False)
        if not ok:
            all_ok = False
    print()
    if all_ok:
        print(f"  {C['G']}✓ Sync ke Portal APD selesai{C['R']}")
    else:
        print(f"  {C['Y']}⚠ Sebagian sync gagal — cek detail di atas{C['R']}")
    input(f"  {C['D']}[Enter untuk kembali...]{C['R']}")

def batch_fill(token, data_type, gi_id, date_str, user_info):
    """Isi semua periode kosong untuk satu item."""
    ep = ENDPOINTS[data_type]
    
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result["data"].get("items", [])
    
    clear()
    header(f"⚡ BATCH FILL · {ep['label']}")
    print()
    
    if ui:
        for ln in ui.render_item_table(items, data_type):
            print(ln)
    else:
        for i, item in enumerate(items, 1):
            data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
            periods = [e["periode"] for e in item.get(data_key, [])]
            print(f"  [{i}] {item['nama']} - {len(periods)}/24")

    print()
    try:
        idx = int(input("  Pilih nomor item: ").strip()) - 1
        if idx < 0 or idx >= len(items):
            return
    except ValueError:
        return
    
    item = items[idx]
    
    # Tolak CB OFF
    if item.get('statusCB') == 'OFF':
        print(f"\n  ⛔ {item['nama']} CB OFF — tidak bisa input beban!")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
    entries = item.get(data_key, [])
    periods_filled = [e["periode"] for e in entries]
    empty_periods = [p for p in range(24) if p not in periods_filled]
    
    if not empty_periods:
        print(f"\n  ✓ {item['nama']} sudah 24/24!")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    # Hitung nilai dari periode terisi tertinggi (suggest value)
    # Untuk beban: pakai SMART SUGGEST (weekday/weekend aware)
    if entries:
        sorted_entries = sorted(entries, key=lambda x: x["periode"])
        last_entry = sorted_entries[-1]
        if data_type == "tegangan-trafo":
            last_mv = last_entry["mv"]
            last_hv = last_entry["hv"]
        else:
            last_val = last_entry["beban"]
    
    print(f"\n  Target: {item['nama']} ({len(empty_periods)} periode kosong)")
    print(f"  Periode: {empty_periods}")
    
    if data_type == "tegangan-trafo":
        # Tegangan: SMART SUGGEST per-periode (rata-rata histori, bukan copy periode sebelumnya)
        today = datetime.strptime(date_str, "%Y-%m-%d")
        is_weekend = today.weekday() >= 5
        day_label = "Weekend" if is_weekend else "Weekday"
        
        print(f"    🧠 Menganalisis pola {get_history_days()} hari ({day_label})...")
        cache = fetch_history_bulk(token, data_type, gi_id, date_str)
        
        # Hitung suggest per-periode
        teg_suggestions = {}
        for per in empty_periods:
            mv, hv, info = smart_suggest_tegangan_from_cache(cache, item["id"], per, is_weekend)
            teg_suggestions[per] = (mv, hv, info)
        
        # Tampilkan tabel
        print(f"\n  {'Periode':<10}{'MV':>8}{'HV':>8}  {'Info'}")
        print(f"  {'─' * 55}")
        for per in empty_periods:
            mv, hv, info = teg_suggestions[per]
            if mv is not None:
                print(f"  P{per:02d}       {mv:>8}{hv:>8}  {info}")
            else:
                print(f"  P{per:02d}       {'?':>8}{'?':>8}  (tidak ada histori)")
        
        # Edit?
        edit = input("\n  Edit nilai? (y/N): ").strip().lower()
        if edit == 'y':
            for per in empty_periods:
                mv_cur, hv_cur, _ = teg_suggestions[per]
                mv_str = input(f"  P{per:02d} MV [{mv_cur}]: ").strip()
                hv_str = input(f"  P{per:02d} HV [{hv_cur}]: ").strip()
                teg_suggestions[per] = (
                    float(mv_str) if mv_str else mv_cur,
                    float(hv_str) if hv_str else hv_cur,
                    "edited"
                )
        
        # Filter valid
        valid_periods = [p for p in empty_periods if teg_suggestions[p][0] is not None]
        if not valid_periods:
            print(f"  {C['RE']}✗ Tidak ada nilai valid!{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")
            return
        
        if not confirm(f"\n  Isi {len(valid_periods)} periode tegangan {item['nama']}?"):
            return

        # batch per-item (beda jam, 1 item) -> reset tiap jam agar tetap spacing 10-20s jika di-run secepatnya per jam
        # tapi untuk beda periode, gap antar jam tidak krusial, jadi cukup reset per periode
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        success = 0
        fail = 0
        total = len(valid_periods)
        for i, per in enumerate(valid_periods, 1):
            if hu and hasattr(hu, "reset_foto_sequence"):
                try:
                    hu.reset_foto_sequence(date_str, per)
                except Exception:
                    pass
            mv, hv, _ = teg_suggestions[per]
            durasi = _human_durasi(data_type)
            fotoHV, fotoMV = _human_foto_pair_dicts(date_str, per, durasi)
            data_dict = {
                ep["id_field"]: item["id"],
                "timezone": "Asia/Jakarta",
                "periode": per,
                "tanggal": dt.day,
                "bulan": dt.month - 1,
                "tahun": dt.year,
                "durasi": durasi,
                ep["value_field"]: mv,
                "hv": hv,
                "fotoHV": fotoHV,
                "fotoMV": fotoMV,
            }
            # Foto: random dari manual (per-item) atau pool (1 foto semua) + varian blur/kabur/asli, filename tetap humanizer
            status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"], item_name=item["nama"])
            ok = result.get("success")
            photo_check = result.get("_photo_upload")
            # Log foto source untuk transparansi anti-robotik
            foto_log = ""
            try:
                if hu and hasattr(hu, "get_last_meta"):
                    meta = hu.get_last_meta()
                    src_bn = meta.get("src_basename", "")[:32]
                    var = meta.get("variant", "")
                    src_mode = meta.get("source_mode", "")
                    if src_bn:
                        foto_log = f" | 📷 {src_bn} [{var}] ({src_mode})"
            except:
                pass
            if ok and photo_check and not photo_check.get("ok"):
                # Hapus record foto gagal agar tidak jadi sampah MISSING uri
                try:
                    rec_id = (result.get("data") or {}).get("id")
                    if rec_id:
                        api_delete(token, f"{ep['delete']}/{rec_id}")
                except Exception:
                    pass
                detail = f"FOTO GAGAL: {photo_check.get('error', '?')} -> dihapus"
                ok = False
            else:
                detail = f"MV={mv} HV={hv}{foto_log}" if ok else str(result.get("message", "?"))[:30]
            if ui:
                sys.stdout.write("\r" + ui.fmt_progress_line(i, total, f"P{per:02d}", ok=ok, detail=detail))
                sys.stdout.flush()
            if ok:
                success += 1
            else:
                fail += 1
            if i < total:
                _human_sleep(0.8, 3.2)
        if ui:
            sys.stdout.write("\n")
        print()
        print(ui.render_summary_box(success, fail, total, "tegangan") if ui
              else f"  ✓ {success}/{total} berhasil!")
        
        # Tawarkan sync ke Portal PLN
        if success > 0:
            offer_portal_sync(data_type, valid_periods, date_str)
        
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    else:
        # Beban: SMART SUGGEST untuk satu nilai yang dipakai di semua periode kosong
        # Pakai periode pertama kosong sebagai referensi — pakai gi_id biar tidak hardcoded 222
        ref_periode = empty_periods[0]
        print(f"    🧠 Menganalisis pola {get_history_days()} hari untuk P{ref_periode:02d}...")
        smart_val, info = smart_suggest_value(token, data_type, item["id"], ref_periode, date_str, gi_id=gi_id)
        if smart_val is not None:
            print(f"    → Smart suggest: {smart_val}A ({info})")
            val_str = input(f"  Nilai (Ampere) [smart: {smart_val}]: ").strip()
            value = float(val_str) if val_str else smart_val
        elif entries:
            print(f"    → Fallback ke P{last_entry['periode']:02d}: {last_val}A")
            val_str = input(f"  Nilai (Ampere) [P{last_entry['periode']:02d}: {last_val}]: ").strip()
            value = float(val_str) if val_str else last_val
        else:
            val_str = input(f"  Nilai (Ampere): ").strip()
            value = float(val_str)
    
    if not confirm(f"\n  Isi {len(empty_periods)} periode dgn nilai {value}{ep['unit']}?"):
        return

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    success = 0
    fail = 0
    total = len(empty_periods)
    for i, per in enumerate(empty_periods, 1):
        # Untuk batch per-item (beda jam), reset tracker per periode agar spacing historis tetap terjaga
        if hu and hasattr(hu, "reset_foto_sequence"):
            try:
                hu.reset_foto_sequence(date_str, per)
            except Exception:
                pass
        durasi = _human_durasi(data_type)
        data_dict = {
            ep["id_field"]: item["id"],
            "timezone": "Asia/Jakarta",
            "periode": per,
            "tanggal": dt.day,
            "bulan": dt.month - 1,
            "tahun": dt.year,
            "durasi": durasi,
            ep["value_field"]: value,
            "foto": _human_foto_dict(date_str, per, durasi, data_type),
        }
        status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"], item_name=item["nama"])
        ok = result.get("success")
        foto_log = ""
        try:
            if hu and hasattr(hu, "get_last_meta"):
                meta = hu.get_last_meta()
                src_bn = meta.get("src_basename", "")[:32]
                var = meta.get("variant", "")
                src_mode = meta.get("source_mode", "")
                if src_bn:
                    foto_log = f" | 📷 {src_bn} [{var}] ({src_mode})"
        except:
            pass
        detail = f"{value}A{foto_log}" if ok else str(result.get("message", "?"))[:30]
        if ui:
            sys.stdout.write("\r" + ui.fmt_progress_line(i, total, f"P{per:02d}", ok=ok, detail=detail))
            sys.stdout.flush()
        if ok:
            success += 1
        else:
            fail += 1
        if i < total:
            _human_sleep(0.8, 3.2)
    if ui:
        sys.stdout.write("\n")
    print()
    print(ui.render_summary_box(success, fail, total, "beban") if ui
          else f"  ✓ {success}/{total} berhasil!")
    
    # Tawarkan sync ke Portal PLN
    if success > 0:
        offer_portal_sync(data_type, empty_periods, date_str)
    
    input(f"  {C['D']}[Enter]{C['R']}")

# ============================================================
# MAIN MENU
# ============================================================

def batch_fill_periode(token, data_type, gi_id, date_str, user_info):
    """Batch fill per periode: pilih 1 jam → isi semua item kosong di jam itu sekaligus."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta
    from collections import defaultdict
    
    ep = ENDPOINTS[data_type]
    clear()
    header(f"⚡ BATCH per JAM · {ep['label']}")
    
    # Fetch data hari ini
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result.get("data", {}).get("items", [])
    if not items:
        print("  Tidak ada data.")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    # Hitung item kosong per periode
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
    empty_by_periode = {}
    for p in range(24):
        empty_items = []
        for it in items:
            if it.get("statusCB") == "OFF":
                continue
            entries = it.get(data_key, [])
            filled_periods = [e["periode"] for e in entries]
            if p not in filled_periods:
                empty_items.append(it)
        empty_by_periode[p] = empty_items
    
    # Tampilkan grid periode (hanya yang masih kosong)
    empty_periods_list = [p for p in range(24) if empty_by_periode[p]]
    full_count = 24 - len(empty_periods_list)
    print(f"\n  {C['D']}Periode kosong ({len(empty_periods_list)} jam) — {full_count} jam sudah penuh{C['R']}")
    if empty_periods_list:
        print("  " + "─" * 40)
        for p in empty_periods_list:
            count = len(empty_by_periode[p])
            print(f"  P{p:02d}:00  | {count:3d} item | ⚡ Bisa batch")

    if not empty_periods_list:
        print(f"\n  {C['G']}✓ Semua periode sudah penuh!{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    # Pilih periode
    try:
        per = int(input("\n  Pilih periode (jam): ").strip())
        if per < 0 or per > 23:
            print(f"  {C['RE']}✗ Periode harus 0-23!{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")
            return
    except ValueError:
        return
    
    empty_items = empty_by_periode[per]
    if not empty_items:
        print(f"\n  ✓ Periode P{per:02d} sudah penuh!")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    print(f"\n  ⚡ Periode P{per:02d}:00 — {len(empty_items)} item kosong")
    print(f"  {'─' * 50}")
    
    # Fetch smart suggest untuk semua item (parallel)
    today = datetime.strptime(date_str, "%Y-%m-%d")
    is_weekend = today.weekday() >= 5
    day_label = "Weekend" if is_weekend else "Weekday"
    
    suggestions = {}
    
    # Fetch history cache untuk SEMUA tipe (termasuk tegangan)
    print(f"  🧠 Menganalisis pola {get_history_days()} hari ({day_label})...")
    cache = fetch_history_bulk(token, data_type, gi_id, date_str)
    
    if data_type != "tegangan-trafo":
        for it in empty_items:
            val, info = smart_suggest_from_cache(cache, it["id"], per, is_weekend)
            suggestions[it["id"]] = (val, info)
    
    # Bangun rows suggest lalu render tabel sekali (aligned)
    suggest_rows = []
    for i, it in enumerate(empty_items, 1):
        if data_type == "tegangan-trafo":
            mv, hv, info = smart_suggest_tegangan_from_cache(cache, it["id"], per, is_weekend)
            if mv is not None:
                suggest_rows.append((i, it["nama"], f"MV={mv} HV={hv}", info))
                suggestions[it["id"]] = (mv, hv)
            else:
                suggest_rows.append((i, it["nama"], "?", "(tidak ada histori)"))
                suggestions[it["id"]] = (None, None)
        else:
            val, info = suggestions.get(it["id"], (None, None))
            if val is not None:
                suggest_rows.append((i, it["nama"], f"{val}A", info))
            else:
                suggest_rows.append((i, it["nama"], "?A", "(tidak ada data)"))

    print()
    if ui:
        for ln in ui.render_suggest_table(suggest_rows):
            print(ln)
    else:
        print(f"  {'No':<4}{'Nama':<18}{'Suggest':<14}Info")
        for no, nama, val, info in suggest_rows:
            print(f"  {no:<4}{str(nama)[:18]:<18}{val:<14}{info}")
    
    # Konfirmasi / edit
    print(f"\n  {'─' * 55}")
    
    if data_type == "tegangan-trafo":
        edit = input("  Edit nilai? (y/N): ").strip().lower()
        if edit == 'y':
            for it in empty_items:
                mv_cur, hv_cur = suggestions.get(it["id"], (None, None))
                if mv_cur is None:
                    mv_str = input(f"  {it['nama']} MV (kV): ").strip()
                    hv_str = input(f"  {it['nama']} HV (kV): ").strip()
                    suggestions[it["id"]] = (float(mv_str), float(hv_str))
                else:
                    mv_str = input(f"  {it['nama']} MV [{mv_cur}]: ").strip()
                    hv_str = input(f"  {it['nama']} HV [{hv_cur}]: ").strip()
                    suggestions[it["id"]] = (
                        float(mv_str) if mv_str else mv_cur,
                        float(hv_str) if hv_str else hv_cur
                    )
    else:
        edit = input("  Edit nilai? (y/N): ").strip().lower()
        if edit == 'y':
            for it in empty_items:
                cur_val, _ = suggestions.get(it["id"], (None, None))
                prompt = f"  {it['nama']} [{cur_val}A]: " if cur_val else f"  {it['nama']}: "
                new_val = input(prompt).strip()
                if new_val:
                    suggestions[it["id"]] = (float(new_val), None)
    
    # Filter item yang punya suggest valid
    valid_items = []
    for it in empty_items:
        s = suggestions.get(it["id"])
        if s and s[0] is not None:
            valid_items.append(it)
    
    if not valid_items:
        print(f"  {C['RE']}✗ Tidak ada item dengan nilai valid!{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    if not confirm(f"\n  Input {len(valid_items)} item di periode P{per:02d}?"):
        print(f"  {C['Y']}⊘ Dibatalkan.{C['R']}")
        input(f"  {C['D']}[Enter]{C['R']}")
        return
    
    # Reset tracker foto agar gap 10-20s antar item dalam periode yang sama berlaku
    if hu and hasattr(hu, "reset_foto_sequence"):
        try:
            hu.reset_foto_sequence(date_str, per)
        except Exception:
            pass

    # Submit semua (live progress)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    success = 0
    fail = 0
    total = len(valid_items)
    failures = []  # (nama, reason)

    shuffled_items = _human_shuffled(valid_items)
    for i, it in enumerate(shuffled_items, 1):
        s = suggestions[it["id"]]
        durasi = _human_durasi(data_type)
        data_dict = {
            ep["id_field"]: it["id"],
            "timezone": "Asia/Jakarta",
            "periode": per,
            "tanggal": dt.day,
            "bulan": dt.month - 1,
            "tahun": dt.year,
            "durasi": durasi,
        }
        if data_type == "tegangan-trafo":
            mv_val, hv_val = s
            fotoHV, fotoMV = _human_foto_pair_dicts(date_str, per, durasi)
            data_dict[ep["value_field"]] = mv_val
            data_dict["hv"] = hv_val
            data_dict["fotoHV"] = fotoHV
            data_dict["fotoMV"] = fotoMV
            detail = f"MV={mv_val} HV={hv_val}"
        else:
            value = s[0]
            data_dict[ep["value_field"]] = value
            data_dict["foto"] = _human_foto_dict(date_str, per, durasi, data_type)
            detail = f"{value}A"

        try:
            # Foto: random per-item manual (sesuai) atau pool (1 foto semua) + varian blur/kabur/asli
            # Filename tetap humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg
            # OFF sudah skip di empty_by_periode, foto tidak dihapus setelah dipakai (read-only)
            status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"], item_name=it["nama"])
            ok = result.get("success")
            photo_check = result.get("_photo_upload")
            if not ok:
                reason = str(result.get("message", "error"))[:30]
                failures.append((it["nama"], reason))
                detail = reason
            else:
                # Untuk tegangan: foto harus ada uri, jika tidak -> treat as gagal + hapus record agar bisa retry
                if photo_check and not photo_check.get("ok"):
                    # Hapus record yang foto gagal agar tidak jadi sampah MISSING uri
                    try:
                        rec_id = (result.get("data") or {}).get("id")
                        if rec_id:
                            api_delete(token, f"{ep['delete']}/{rec_id}")
                    except Exception:
                        pass
                    failures.append((it["nama"], f"nilai tersimpan tapi FOTO GAGAL: {photo_check.get('error', 'foto gagal')}"))
                    detail = "FOTO GAGAL -> dihapus, akan retry"
                    ok = False  # anggap gagal agar retry / tidak dihitung success
                else:
                    # Tambah info foto source untuk transparansi (manual vs pool + varian + basename)
                    try:
                        if hu and hasattr(hu, "get_last_meta"):
                            meta = hu.get_last_meta()
                            src_bn = meta.get("src_basename", "")[:24]
                            var = meta.get("variant", "")
                            if src_bn:
                                detail = f"{detail} | 📷 {src_bn} [{var}]"
                    except:
                        pass
        except Exception as e:
            ok = False
            failures.append((it["nama"], str(e)[:30]))
            detail = str(e)[:30]

        if ui:
            sys.stdout.write("\r" + ui.fmt_progress_line(i, total, it["nama"][:10], ok=ok, detail=detail))
            sys.stdout.flush()
        if ok:
            success += 1
        else:
            fail += 1
        if i < total:
            _human_sleep(0.8, 3.2)
    if ui:
        sys.stdout.write("\n")

    for nama, reason in failures:
        print(f"  {C['RE']}✗ {nama}: {reason}{C['R']}")

    print()
    print(ui.render_summary_box(success, fail, total, ep["label"]) if ui
          else f"\n  Ringkasan: ✓ {success} berhasil" + (f"  ✗ {fail} gagal" if fail else ""))
    
    # Tawarkan sync ke Portal PLN (periode tunggal: per)
    if success > 0:
        offer_portal_sync(data_type, [per], date_str)
    
    input(f"  {C['D']}[Enter]{C['R']}")

CRON_MARKER = "# SUPER-I-AUTO"
WIN_TASK_PREFIX = "SUPER-I-Auto"
WIN_TASK_NAME = "SUPER-I-Auto-Input"  # legacy single task name, untuk backward compat

# ============================================================
# RANDOM MINUTE 3-38 (super aman, anti-robotik)
# 38 + 110s jitter + 5 menit runtime = selesai max 44 menit, sisa 15 menit buffer
# Hindari kelipatan 5 (5,10,15,20,25,30,35) biar ga keliatan robot
# ============================================================
def _random_minute():
    """Return random menit 3-38, hindari kelipatan 5 biar ga robotik."""
    candidates = [n for n in range(3, 39) if n % 5 != 0]
    return random.choice(candidates)


def _expand_window_to_hours(start, end):
    """Expand window jam ke list jam aktif, respect lintas hari.
    
    Misal:
      22-5  => [22,23,0,1,2,3,4,5] (8 jam)
      09-17 => [9,10,11,12,13,14,15,16,17] (9 jam)
      00-23 => [0..23] (24 jam, full day)
      22-22 => [22] (1 jam doang)
    """
    start = int(start) % 24
    end = int(end) % 24
    hours = []
    h = start
    while True:
        hours.append(h)
        if h == end:
            break
        h = (h + 1) % 24
        # safety: max 24 iterasi
        if len(hours) > 24:
            break
    return hours


def _cron_paths():
    """Return (py, script, log) untuk cron."""
    py = os.path.join(SCRIPT_DIR, ".venv", "bin", "python3")
    script = os.path.join(SCRIPT_DIR, "superi_auto.py")
    log = os.path.join(SCRIPT_DIR, "auto_log.txt")
    if not os.path.exists(py):
        py = sys.executable
    return py, script, log


def _generate_cron_lines(window_start=None, window_end=None):
    """Generate N baris cron random berdasarkan window jam.
    
    N = jumlah jam aktif (misal 22-5 = 8 baris).
    Tiap baris: M H * * * py script >> log 2>&1 # SUPER-I-AUTO
    Menit M random 3-38 beda tiap jam.
    """
    cfg = load_config()
    if window_start is None:
        window_start = cfg.get("auto_window_start", 22)
    if window_end is None:
        window_end = cfg.get("auto_window_end", 5)
    py, script, log = _cron_paths()
    hours = _expand_window_to_hours(window_start, window_end)
    lines = []
    for h in hours:
        m = _random_minute()
        lines.append(f"{m} {h} * * * {py} {script} >> {log} 2>&1 {CRON_MARKER}")
    return lines


def _cron_command():
    """DEPRECATED: single line cron lama (5 * * * *), untuk backward-compat doc saja.
    Sekarang pakai _generate_cron_lines() yang N baris random.
    """
    py, script, log = _cron_paths()
    return f"5 * * * * {py} {script} >> {log} 2>&1 {CRON_MARKER}"


def cron_is_installed():
    """Cek apakah cron job sudah terpasang (ada minimal 1 baris dengan marker)."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        return CRON_MARKER in result.stdout
    except Exception:
        return False


def cron_install(window_start=None, window_end=None):
    """Pasang N cron job random (macOS/Linux). N = jumlah jam window."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        # Hapus semua baris lama SUPER-I-AUTO
        lines = [l for l in existing.splitlines() if CRON_MARKER not in l]
        # Generate baru N baris sesuai window
        new_lines = _generate_cron_lines(window_start, window_end)
        lines.extend(new_lines)
        new_crontab = "\n".join(lines) + "\n"
        proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
        return proc.returncode == 0, proc.stderr
    except Exception as e:
        return False, str(e)


def cron_count_installed():
    """Hitung berapa baris cron dengan marker yang terpasang."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            return 0
        return sum(1 for l in result.stdout.splitlines() if CRON_MARKER in l)
    except Exception:
        return 0


def cron_uninstall():
    """Hapus semua cron job SUPER-I-AUTO."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            return True, ""
        lines = [l for l in result.stdout.splitlines() if CRON_MARKER not in l]
        new_crontab = ("\n".join(lines) + "\n") if lines else ""
        proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
        return proc.returncode == 0, proc.stderr
    except Exception as e:
        return False, str(e)

# --- Windows Task Scheduler (8 task, tiap jam beda menit 3-38) ---
def _win_task_names_for_window(window_start=None, window_end=None):
    """Return list (task_name, hour) untuk window saat ini."""
    cfg = load_config()
    if window_start is None:
        window_start = cfg.get("auto_window_start", 22)
    if window_end is None:
        window_end = cfg.get("auto_window_end", 5)
    hours = _expand_window_to_hours(window_start, window_end)
    return [(f"{WIN_TASK_PREFIX}-{h:02d}", h) for h in hours]


def _generate_win_tasks(window_start=None, window_end=None):
    """Generate list (task_name, hour, minute) untuk N task, menit random 3-38 beda tiap jam."""
    cfg = load_config()
    if window_start is None:
        window_start = cfg.get("auto_window_start", 22)
    if window_end is None:
        window_end = cfg.get("auto_window_end", 5)
    hours = _expand_window_to_hours(window_start, window_end)
    tasks = []
    for h in hours:
        m = _random_minute()
        task_name = f"{WIN_TASK_PREFIX}-{h:02d}"
        tasks.append((task_name, h, m))
    return tasks


def win_task_is_installed():
    """Cek apakah minimal 1 task dengan prefix terpasang (atau legacy single task)."""
    try:
        # Cek legacy single
        result = subprocess.run(["schtasks", "/query", "/tn", WIN_TASK_NAME],
                                capture_output=True, text=True)
        if result.returncode == 0:
            return True
        # Cek prefix multi-task
        result2 = subprocess.run(["schtasks", "/query", "/fo", "list"],
                                 capture_output=True, text=True)
        if WIN_TASK_PREFIX in result2.stdout:
            return True
        # Fallback: cek satu per satu untuk window default
        for task_name, _ in _win_task_names_for_window():
            r = subprocess.run(["schtasks", "/query", "/tn", task_name],
                               capture_output=True, text=True)
            if r.returncode == 0:
                return True
        return False
    except Exception:
        return False


def win_task_count_installed():
    """Hitung berapa task dengan prefix yang terpasang."""
    count = 0
    # Legacy
    try:
        result = subprocess.run(["schtasks", "/query", "/tn", WIN_TASK_NAME],
                                capture_output=True, text=True)
        if result.returncode == 0:
            count += 1
    except Exception:
        pass
    # Multi
    for task_name, _ in _win_task_names_for_window():
        try:
            r = subprocess.run(["schtasks", "/query", "/tn", task_name],
                               capture_output=True, text=True)
            if r.returncode == 0:
                count += 1
        except Exception:
            pass
    return count


def win_task_install(window_start=None, window_end=None):
    """Pasang N Windows Task Scheduler, tiap jam beda menit random 3-38 (anti-robotik)."""
    bat = os.path.join(SCRIPT_DIR, "superi.bat")
    task_log = os.path.join(SCRIPT_DIR, "auto_task_log.txt")
    task_cmd = f'cmd /c cd /d "{SCRIPT_DIR}" && "{bat}" auto >> "{task_log}" 2>&1'
    tasks = _generate_win_tasks(window_start, window_end)
    ok_count = 0
    last_msg = ""
    for task_name, h, m in tasks:
        try:
            time_str = f"{h:02d}:{m:02d}"
            # Hapus dulu kalau sudah ada
            subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"],
                           capture_output=True, text=True)
            proc = subprocess.run([
                "schtasks", "/create", "/tn", task_name,
                "/tr", task_cmd,
                "/sc", "daily",
                "/st", time_str,
                "/f"
            ], capture_output=True, text=True)
            if proc.returncode == 0:
                ok_count += 1
                last_msg = proc.stdout
            else:
                last_msg = proc.stderr or proc.stdout
        except Exception as e:
            last_msg = str(e)
    # Legacy single cleanup kalau masih ada
    try:
        subprocess.run(["schtasks", "/delete", "/tn", WIN_TASK_NAME, "/f"],
                       capture_output=True, text=True)
    except Exception:
        pass
    return ok_count == len(tasks), f"{ok_count}/{len(tasks)} terpasang: {last_msg}" if ok_count < len(tasks) else f"{ok_count} task terpasang"


def win_task_uninstall():
    """Hapus semua task dengan prefix SUPER-I-Auto-* + legacy single."""
    deleted = 0
    last_msg = ""
    # Hapus multi-task untuk semua 24 jam (bersihkan total, bukan cuma window saat ini)
    for h in range(24):
        task_name = f"{WIN_TASK_PREFIX}-{h:02d}"
        try:
            proc = subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"],
                                  capture_output=True, text=True)
            if proc.returncode == 0:
                deleted += 1
            last_msg = proc.stderr or proc.stdout
        except Exception as e:
            last_msg = str(e)
    # Hapus legacy single
    try:
        proc = subprocess.run(["schtasks", "/delete", "/tn", WIN_TASK_NAME, "/f"],
                              capture_output=True, text=True)
        if proc.returncode == 0:
            deleted += 1
    except Exception as e:
        last_msg = str(e)
    return True, f"{deleted} task dihapus: {last_msg}" if deleted else "Tidak ada task terpasang"

def scheduler_is_installed():
    """Cek apakah scheduler (cron/task) sudah terpasang sesuai OS."""
    if platform.system() == "Windows":
        return win_task_is_installed()
    return cron_is_installed()

def scheduler_install_menu():
    """Menu install/hapus jadwal otomatis sesuai OS - random 3-38 menit per jam, N baris/task sesuai window."""
    is_win = platform.system() == "Windows"
    os_name = "Windows Task Scheduler" if is_win else "cron"
    installed = scheduler_is_installed()
    cfg = load_config()
    win_start = cfg.get("auto_window_start", 22)
    win_end = cfg.get("auto_window_end", 5)
    hours = _expand_window_to_hours(win_start, win_end)
    
    clear()
    header(f"⚙  JADWAL OTOMATIS · {os_name}")
    print()
    print(f"  {C['D']}Window saat ini: {win_start:02d}:00-{win_end:02d}:00 = {len(hours)} jam ({', '.join(f'{h:02d}' for h in hours)}){C['R']}")
    print(f"  {C['D']}Setiap jam dapat menit random 3-38 (anti menit 5 exact robot) + jitter 2-110 detik{C['R']}")
    print(f"  {C['D']}Jaminan: menit max 38 + jitter 110s + runtime 5 menit = selesai max 44, sisa 15 menit buffer{C['R']}")
    print()
    if installed:
        cnt = win_task_count_installed() if is_win else cron_count_installed()
        print(f"  {C['G']}● Jadwal otomatis SUDAH terpasang ({cnt} jadwal){C['R']}")
        if is_win:
            print(f"  {C['D']}N task: {WIN_TASK_PREFIX}-HH (HH={', '.join(f'{h:02d}' for h in hours)}) daily HH:MM random{C['R']}")
        else:
            print(f"  {C['D']}N baris cron sesuai window, tiap jam menit random 3-38{C['R']}")
    else:
        print(f"  {C['RE']}○ Jadwal otomatis BELUM terpasang{C['R']}")
    print()
    print(f"  {C['C']}[1]{C['R']} {'Pasang ulang (regenerate menit random)' if installed else 'Pasang'} jadwal otomatis ({len(hours)} jadwal)")
    if installed:
        print(f"  {C['C']}[2]{C['R']} {C['RE']}Hapus{C['R']} jadwal otomatis")
        if is_win:
            print(f"  {C['C']}[3]{C['R']} 📋 Lihat daftar task terpasang")
        else:
            print(f"  {C['C']}[3]{C['R']} 📋 Lihat crontab terpasang")
    print(f"  {C['RE']}[0]{C['R']} Kembali")
    print()
    print(f"  {C['D']}{'─' * 56}{C['R']}")
    choice = input(f"  {C['B']}Pilih ▸ {C['R']}").strip()
    
    if choice == '1':
        print(f"\n  {C['Y']}Memasang {len(hours)} jadwal (menit random 3-38, window {win_start:02d}-{win_end:02d})...{C['R']}")
        # Preview yang akan dipasang
        preview_lines = _generate_cron_lines(win_start, win_end) if not is_win else []
        preview_tasks = _generate_win_tasks(win_start, win_end) if is_win else []
        if is_win:
            for t_name, h, m in preview_tasks:
                print(f"  {C['D']}  {t_name} -> {h:02d}:{m:02d} daily{C['R']}")
        else:
            for line in preview_lines:
                # tampilkan M H
                parts = line.split()
                print(f"  {C['D']}  {parts[0]} {parts[1]} * * * auto (menit {parts[0]} jam {parts[1]}){C['R']}")
        print()
        if is_win:
            ok, msg = win_task_install(win_start, win_end)
        else:
            ok, msg = cron_install(win_start, win_end)
        if ok:
            print(f"  {C['G']}✓ Jadwal otomatis terpasang! {msg}{C['R']}")
            print(f"  {C['D']}Menit acak 3-38 per jam, tiap install beda-beda (mirip setting manual operator).{C['R']}")
            print(f"  {C['D']}Pastikan Auto Mode AKTIF + komputer menyala di window jam.{C['R']}")
            if is_win:
                print(f"  {C['D']}Log Task: {os.path.join(SCRIPT_DIR, 'auto_task_log.txt')}{C['R']}")
            else:
                print(f"  {C['D']}Cek: crontab -l{C['R']}")
        else:
            print(f"  {C['RE']}✗ Gagal: {msg}{C['R']}")
            if not is_win:
                print(f"  {C['D']}Di macOS, Terminal mungkin perlu izin 'Full Disk Access' di System Settings.{C['R']}")
        input(f"\n  {C['D']}[Enter]{C['R']}")
    elif choice == '2' and installed:
        print(f"\n  {C['Y']}Menghapus jadwal...{C['R']}")
        if is_win:
            ok, msg = win_task_uninstall()
        else:
            ok, msg = cron_uninstall()
        if ok:
            print(f"  {C['G']}✓ {msg}{C['R']}")
        else:
            print(f"  {C['RE']}✗ Gagal: {msg}{C['R']}")
        input(f"\n  {C['D']}[Enter]{C['R']}")
    elif choice == '3' and installed:
        print()
        if is_win:
            print(f"  {C['B']}Daftar task terpasang:{C['R']}")
            for h in range(24):
                task_name = f"{WIN_TASK_PREFIX}-{h:02d}"
                try:
                    r = subprocess.run(["schtasks", "/query", "/tn", task_name, "/fo", "list", "/v"],
                                       capture_output=True, text=True)
                    if r.returncode == 0:
                        print(f"  {C['G']}● {task_name}{C['R']}")
                        for line in r.stdout.splitlines()[:8]:
                            print(f"    {line}")
                except Exception:
                    pass
            # legacy
            try:
                r = subprocess.run(["schtasks", "/query", "/tn", WIN_TASK_NAME, "/fo", "list"],
                                   capture_output=True, text=True)
                if r.returncode == 0:
                    print(f"  {C['Y']}⚠ Legacy masih ada: {WIN_TASK_NAME}{C['R']}")
            except Exception:
                pass
        else:
            print(f"  {C['B']}Crontab terpasang:{C['R']}")
            try:
                r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                for line in r.stdout.splitlines():
                    if CRON_MARKER in line or "superi_auto" in line:
                        marker = f"{C['G']}●{C['R']}" if CRON_MARKER in line else f"{C['Y']}○{C['R']}"
                        print(f"  {marker} {line}")
            except Exception as e:
                print(f"  {C['RE']}✗ {e}{C['R']}")
        input(f"\n  {C['D']}[Enter]{C['R']}")

def auto_mode_menu():
    """Menu pengaturan Auto Mode (input + sync terjadwal)."""
    while True:
        clear()
        header("⏰ AUTO MODE  ·  Input & Sync Terjadwal")
        cfg = load_config()
        enabled = cfg.get("auto_enabled", False)
        win_start = cfg.get("auto_window_start", 22)
        win_end = cfg.get("auto_window_end", 5)
        types = cfg.get("auto_types", ["penyulang", "trafo", "tegangan"])
        sync_portal = cfg.get("auto_sync_portal", True)
        retry_attempts = cfg.get("auto_retry_attempts", 5)
        retry_delay = cfg.get("auto_retry_delay", 10)
        
        print()
        print(f"  {C['D']}┌─────────────────────────────────────────────────────┐{C['R']}")
        if enabled:
            print(f"  {C['D']}│{C['R']}  {C['G']}● AKTIF{C['R']}  {C['D']}— terjadwal otomatis di window jam{C['R']}")
        else:
            print(f"  {C['D']}│{C['R']}  {C['RE']}○ NONAKTIF{C['R']}  {C['D']}— tidak akan jalan walau cron memanggil{C['R']}")
        print(f"  {C['D']}│{C['R']}  ⏱  Window     : {win_start:02d}:00 - {win_end:02d}:00")
        print(f"  {C['D']}│{C['R']}  📋 Tipe       : {', '.join(types)}")
        print(f"  {C['D']}│{C['R']}  🔄 Sync Portal: {'YES' if sync_portal else 'NO'}")
        print(f"  {C['D']}│{C['R']}  🛡  Retry Guard: {retry_attempts}x, jeda {retry_delay}s")
        print(f"  {C['D']}└─────────────────────────────────────────────────────┘{C['R']}")
        print()
        
        print(f"  {C['M']}{C['B']}AKSI{C['R']}")
        if enabled:
            print(f"  {C['C']}[1]{C['R']} {C['RE']}Nonaktifkan{C['R']} Auto Mode")
        else:
            print(f"  {C['C']}[1]{C['R']} {C['G']}Aktifkan{C['R']} Auto Mode")
        print(f"  {C['C']}[2]{C['R']} Atur Window Jam (mulai-akhir)")
        print(f"  {C['C']}[3]{C['R']} Pilih Tipe Data")
        print(f"  {C['C']}[4]{C['R']} Toggle Sync Portal APD ({'ON' if sync_portal else 'OFF'})")
        print(f"  {C['C']}[5]{C['R']} 🧪 Test Sekarang (dry-run jam ini)")
        print(f"  {C['C']}[6]{C['R']} 📜 Lihat Log Aktivitas")
        print()
        print(f"  {C['M']}{C['B']}SETUP TERJADWAL{C['R']}")
        _sched_on = scheduler_is_installed()
        _sched_badge = f"{C['G']}TERPASANG{C['R']}" if _sched_on else f"{C['RE']}BELUM{C['R']}"
        print(f"  {C['C']}[7]{C['R']} ⚙  Pasang/Hapus Jadwal Otomatis [{_sched_badge}]")
        print(f"  {C['C']}[8]{C['R']} 📖 Panduan manual cron / Task Scheduler")
        print()
        print(f"  {C['RE']}[0]{C['R']} Kembali ke menu utama")
        print()
        print(f"  {C['D']}{'─' * 56}{C['R']}")
        
        choice = input(f"  {C['B']}Pilih ▸ {C['R']}").strip()
        
        if choice == '0':
            return
        elif choice == '1':
            cfg["auto_enabled"] = not enabled
            cfg.setdefault("auto_window_start", 22)
            cfg.setdefault("auto_window_end", 5)
            cfg.setdefault("auto_types", ["penyulang", "trafo", "tegangan"])
            cfg.setdefault("auto_sync_portal", True)
            cfg.setdefault("auto_retry_attempts", 5)
            cfg.setdefault("auto_retry_delay", 10)
            save_config(cfg)
            status = f"{C['G']}AKTIF{C['R']}" if cfg["auto_enabled"] else f"{C['RE']}NONAKTIF{C['R']}"
            print(f"\n  ✓ Auto Mode sekarang {status}")
            input(f"  {C['D']}[Enter]{C['R']}")
        elif choice == '2':
            print()
            print(f"  {C['D']}Window jam = rentang waktu auto mode aktif{C['R']}")
            print(f"  {C['D']}Contoh: 22-5 = jalan jam 22:00 sampai 05:00 (lintas hari){C['R']}")
            print(f"  {C['D']}Sekarang: {win_start:02d}:00-{win_end:02d}:00 = {len(_expand_window_to_hours(win_start, win_end))} jam aktif{C['R']}")
            print(f"  {C['D']}Setelah ganti window, jadwal cron/task yang sudah terpasang harus dipasang ulang biar ngikut jam baru{C['R']}")
            try:
                s = int(input(f"  Mulai (jam 0-23) [{win_start}]: ").strip() or win_start)
                e = int(input(f"  Akhir (jam 0-23) [{win_end}]: ").strip() or win_end)
                if 0 <= s <= 23 and 0 <= e <= 23:
                    old_hours = _expand_window_to_hours(win_start, win_end)
                    new_hours = _expand_window_to_hours(s, e)
                    cfg["auto_window_start"] = s
                    cfg["auto_window_end"] = e
                    save_config(cfg)
                    print(f"\n  {C['G']}✓ Window: {s:02d}:00 - {e:02d}:00 = {len(new_hours)} jam ({', '.join(f'{h:02d}' for h in new_hours)}){C['R']}")
                    # Jika jadwal sudah terpasang dan window berubah, tawarkan reinstall
                    if scheduler_is_installed() and old_hours != new_hours:
                        print(f"  {C['Y']}Jadwal lama {len(old_hours)} jadwal, baru {len(new_hours)} jadwal. Perlu pasang ulang biar ngikut jam baru.{C['R']}")
                        ans = input(f"  Pasang ulang jadwal sekarang? (Y/n): ").strip().lower()
                        if ans in ("", "y", "yes"):
                            is_win = platform.system() == "Windows"
                            print(f"  {C['Y']}Memasang ulang...{C['R']}")
                            if is_win:
                                ok, msg = win_task_install(s, e)
                            else:
                                ok, msg = cron_install(s, e)
                            if ok:
                                print(f"  {C['G']}✓ Jadwal terpasang ulang: {msg}{C['R']}")
                            else:
                                print(f"  {C['RE']}✗ Gagal pasang ulang: {msg}{C['R']}")
                else:
                    print(f"\n  {C['RE']}✗ Jam harus 0-23{C['R']}")
            except ValueError:
                print(f"\n  {C['RE']}✗ Input tidak valid{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")
        elif choice == '3':
            print()
            print(f"  {C['D']}Pilih tipe data yang akan di-input otomatis (pisah dengan koma){C['R']}")
            print(f"  {C['D']}Contoh: penyulang,trafo,tegangan{C['R']}")
            current = ",".join(types)
            new_types = input(f"  Tipe [{current}]: ").strip() or current
            valid = [t.strip() for t in new_types.split(",") if t.strip() in ["penyulang", "trafo", "tegangan"]]
            if valid:
                cfg["auto_types"] = valid
                save_config(cfg)
                print(f"\n  {C['G']}✓ Tipe diset: {', '.join(valid)}{C['R']}")
            else:
                print(f"\n  {C['RE']}✗ Tidak ada tipe valid{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")
        elif choice == '4':
            cfg["auto_sync_portal"] = not sync_portal
            save_config(cfg)
            status = f"{C['G']}ON{C['R']}" if cfg["auto_sync_portal"] else f"{C['RE']}OFF{C['R']}"
            print(f"\n  ✓ Sync Portal: {status}")
            input(f"  {C['D']}[Enter]{C['R']}")
        elif choice == '5':
            print(f"\n  {C['Y']}🧪 Test dry-run jam {datetime.now().hour:02d}:00...{C['R']}\n")
            try:
                import superi_auto
                superi_auto.run_auto(force_jam=datetime.now().hour, dry_run=True)
            except Exception as e:
                print(f"  {C['RE']}✗ Error: {e}{C['R']}")
            input(f"\n  {C['D']}[Enter]{C['R']}")
        elif choice == '6':
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_log.txt")
            if os.path.exists(log_path):
                clear()
                header("📜 LOG AKTIVITAS AUTO")
                print()
                with open(log_path) as f:
                    lines = f.readlines()
                # Tampilkan 40 baris terakhir
                for line in lines[-40:]:
                    print(f"  {line.rstrip()}")
                print(f"\n  {C['D']}File: {log_path}{C['R']}")
            else:
                print(f"\n  {C['Y']}⚠ Belum ada log. Jalankan test dulu (menu 5).{C['R']}")
            input(f"\n  {C['D']}[Enter]{C['R']}")
        elif choice == '7':
            scheduler_install_menu()
        elif choice == '8':
            clear()
            header("📖 PANDUAN SETUP TERJADWAL")
            print()
            print(f"  {C['M']}{C['B']}🍎 macOS / Linux (cron){C['R']}\n")
            print(f"  {C['D']}1. Buka terminal, ketik:{C['R']}")
            print(f"     {C['C']}crontab -e{C['R']}\n")
            print(f"  {C['D']}2. Tambahkan baris (jalan tiap jam menit ke-5):{C['R']}")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            print(f"     {C['G']}5 * * * * {script_dir}/.venv/bin/python3 {script_dir}/superi_auto.py{C['R']}\n")
            print(f"  {C['D']}3. Simpan & keluar (Ctrl+O, Enter, Ctrl+X di nano){C['R']}\n")
            print(f"  {C['D']}Auto mode internal cek window jam jadi cuma eksekusi di rentang yang diset.{C['R']}\n")
            print(f"  {C['M']}{C['B']}🪟 Windows (Task Scheduler){C['R']}\n")
            print(f"  {C['D']}1. Buka {C['B']}Task Scheduler{C['R']} {C['D']}(cari di Start Menu){C['R']}")
            print(f"  {C['D']}2. Create Basic Task → Daily, repeat every 5 minutes{C['R']}")
            print(f"  {C['D']}3. Action: Start a program{C['R']}")
            print(f"     {C['D']}- Program  : {C['C']}superi.bat{C['R']}")
            print(f"     {C['D']}- Arguments: {C['C']}auto{C['R']}")
            print(f"     {C['D']}- Start in : folder project{C['R']}\n")
            print(f"  {C['D']}4. Centang \"Wake the computer to run this task\"{C['R']}\n")
            print(f"  {C['Y']}{C['B']}⚠ SYARAT WAJIB:{C['R']}")
            print(f"  {C['D']}  • Komputer menyala & tidak sleep{C['R']}")
            print(f"  {C['D']}  • Akun SUPER-I sudah clock-in (absen masuk){C['R']}")
            print(f"  {C['D']}  • Terhubung jaringan internal PLN + internet{C['R']}\n")
            print(f"  {C['D']}Detail lengkap: AUTO_MODE.md di folder project{C['R']}")
            input(f"\n  {C['D']}[Enter]{C['R']}")
        else:
            print(f"\n  {C['RE']}✗ Pilihan tidak valid{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")

def photo_settings_menu():
    """Menu pengaturan foto source: manual (per-item sesuai) vs pool (1 foto untuk semua).

    - Manual: content dari photo/manual/{tipe}/{ITEM}/ (random per item + hv/mv terpisah) + varian blur/kabur/asli
    - Pool: content dari photo/pool/ 1 foto untuk semua input (fallback generic)
    - Filename upload TETAP humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg (bukan basename manual)
    - Foto tidak dihapus setelah dipakai (read-only random choice)
    - OFF tetap simpan 84 foto tapi skip input saat CB OFF
    """
    while True:
        clear()
        header("⚙ PENGATURAN FOTO & POOL")
        cfg = load_config()
        photo_src = get_photo_source()
        hist_days = get_history_days()

        # pool stats
        pool_stats = {"pool": 0, "total_manual": 0, "manual": {"beban-penyulang": {"folders":0,"files":0},"beban-trafo":{"folders":0,"files":0},"tegangan-trafo":{"folders":0,"hv":0,"mv":0,"total":0}}}
        try:
            if hu and hasattr(hu, "get_pool_stats"):
                pool_stats = hu.get_pool_stats()
        except Exception:
            pass

        manual_bp = pool_stats.get("manual", {}).get("beban-penyulang", {})
        manual_bt = pool_stats.get("manual", {}).get("beban-trafo", {})
        manual_tt = pool_stats.get("manual", {}).get("tegangan-trafo", {})
        total_manual = pool_stats.get("total_manual", 0)
        pool_cnt = pool_stats.get("pool", 0)

        # Badge source
        if photo_src == "manual":
            src_badge = f"{C['G']}MANUAL{C['R']} (per-item sesuai input)"
            src_desc = "Foto per penyulang/trafo: random dari folder item + hv/mv terpisah + varian blur/kabur/asli"
        else:
            src_badge = f"{C['Y']}POOL{C['R']} (1 foto untuk semua)"
            src_desc = "1 foto generic di photo/pool/ dipakai untuk semua item, re-encode beda SHA tiap upload"

        print(f"  {C['D']}┌─ Sumber Foto ─────────────────────────────────────┐{C['R']}")
        print(f"  {C['D']}│{C['R']}  Saat ini : {src_badge}")
        print(f"  {C['D']}│{C['R']}  {C['D']}{src_desc}{C['R']}")
        print(f"  {C['D']}│{C['R']}  Filename : {C['C']}fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg{C['R']} ({C['D']}humanizer tetap, bukan basename manual{C['R']})")
        print(f"  {C['D']}│{C['R']}  OFF      : 7 penyulang CB OFF tetap simpan 84 foto tapi skip input (read-only, tidak dihapus)")
        print(f"  {C['D']}└─────────────────────────────────────────────────┘{C['R']}")
        print()
        print(f"  {C['D']}┌─ Statistik Pool ──────────────────────────────────┐{C['R']}")
        print(f"  {C['D']}│{C['R']}  Pool generic    : {C['G']}{pool_cnt}{C['R']} file di {C['D']}photo/pool/{C['R']}")
        print(f"  {C['D']}│{C['R']}  Manual penyulang: {C['G']}{manual_bp.get('folders',0)}{C['R']} folder / {C['G']}{manual_bp.get('files',0)}{C['R']} foto (25 ON + 7 OFF tetap)")
        print(f"  {C['D']}│{C['R']}  Manual beban    : {C['G']}{manual_bt.get('folders',0)}{C['R']} folder / {C['G']}{manual_bt.get('files',0)}{C['R']} foto (TRAFO_1/2/3)")
        print(f"  {C['D']}│{C['R']}  Manual tegangan : {C['G']}{manual_tt.get('folders',0)}{C['R']} trafo / HV {C['G']}{manual_tt.get('hv',0)}{C['R']} + MV {C['G']}{manual_tt.get('mv',0)}{C['R']} = {C['G']}{manual_tt.get('total',0)}{C['R']} foto")
        print(f"  {C['D']}│{C['R']}  Total manual    : {C['G']}{total_manual}{C['R']} foto")
        print(f"  {C['D']}│{C['R']}  History         : {C['G']}{hist_days}{C['R']} hari")
        print(f"  {C['D']}└─────────────────────────────────────────────────┘{C['R']}")
        print()
        print(f"  {C['M']}{C['B']}AKSI{C['R']}")
        print(f"  {C['C']}[1]{C['R']} Ganti Sumber Foto (pool ↔ manual)")
        print(f"  {C['C']}[2]{C['R']} Ganti History Days (3/7/14)")
        print(f"  {C['C']}[3]{C['R']} Lihat Detail Pool per Item")
        print(f"  {C['C']}[4]{C['R']} Validasi Foto Manual (scan 500+ file)")
        print()
        print(f"  {C['M']}{C['B']}INFO{C['R']}")
        print(f"  {C['C']}[5]{C['R']} Panduan: Cara foto manual anti-robotik")
        print(f"  {C['C']}[6]{C['R']} Test Foto Random (lihat varian blur/kabur/asli)")
        print()
        print(f"  {C['RE']}[0]{C['R']} Kembali ke menu utama")
        print()
        print(f"  {C['D']}{'─' * 56}{C['R']}")

        choice = input(f"  {C['B']}Pilih ▸ {C['R']}").strip().lower()

        if choice == '0':
            return
        elif choice == '1':
            print()
            print(f"  {C['B']}Pilih sumber foto:{C['R']}")
            print(f"  {C['C']}pool{C['R']}   = 1 foto generic di photo/pool/ untuk semua input (fallback cepat)")
            print(f"  {C['C']}manual{C['R']} = per-item sesuai input (random dari folder item + hv/mv terpisah + varian blur/kabur/asli)")
            print(f"  {C['D']}Filename upload tetap humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg (bukan basename manual){C['R']}")
            print(f"  {C['D']}Foto tidak dihapus setelah dipakai (read-only random choice){C['R']}")
            print(f"  {C['D']}OFF tetap simpan tapi skip input saat CB OFF{C['R']}")
            print(f"  Saat ini: {photo_src}")
            new_src = input(f"  Sumber baru (pool/manual) [batal]: ").strip().lower()
            if new_src in ("pool", "manual"):
                if set_photo_source(new_src):
                    print(f"\n  {C['G']}✓ Foto source diubah ke {new_src.upper()}{C['R']}")
                    if new_src == "manual":
                        print(f"  {C['D']}  → Per-item: random dari photo/manual/{{tipe}}/{{ITEM}}/ + hv/mv terpisah{C['R']}")
                        print(f"  {C['D']}  → Varian: asli 40%, blur_ringan 20%, blur_berat 10%, kabur_glare 15%, noisy_gelap 15%{C['R']}")
                        print(f"  {C['D']}  → OFF 7 penyulang tetap ada tapi skip input CB OFF{C['R']}")
                    else:
                        print(f"  {C['D']}  → 1 foto generic di photo/pool/ untuk semua input{C['R']}")
                        print(f"  {C['D']}  → Re-encode 720x720 crop ±5% + pixel jitter + quality 82-93 beda SHA tiap upload{C['R']}")
                else:
                    print(f"  {C['RE']}✗ Gagal ubah source{C['R']}")
            else:
                print(f"  {C['Y']}⊘ Dibatalkan{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")
        elif choice == '2':
            print()
            print(f"  {C['D']}History days = berapa hari ke belakang untuk smart suggest{R['C']}")
            print(f"  Valid: 3, 7, 14 (default 7)")
            print(f"  Saat ini: {hist_days}")
            new_hist = input(f"  History baru (3/7/14) [batal]: ").strip()
            if new_hist in ("3", "7", "14"):
                cfg["history_days"] = int(new_hist)
                save_config(cfg)
                print(f"  {C['G']}✓ History days diubah ke {new_hist}{C['R']}")
            else:
                if new_hist:
                    print(f"  {C['RE']}✗ Invalid, harus 3/7/14{C['R']}")
                else:
                    print(f"  {C['Y']}⊘ Dibatalkan{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")
        elif choice == '3':
            # Detail pool per item
            clear()
            header("📁 DETAIL POOL PER ITEM")
            try:
                base_manual = os.path.join(SCRIPT_DIR, "photo", "manual")
                if not os.path.isdir(base_manual):
                    print(f"  {C['RE']}Folder photo/manual/ tidak ada{C['R']}")
                else:
                    # beban-penyulang
                    print(f"\n  {C['M']}{C['B']}BEBAN PENYULANG (32 = 25 ON + 7 OFF){C['R']}")
                    bp_path = os.path.join(base_manual, "beban-penyulang")
                    if os.path.isdir(bp_path):
                        # load mapping untuk CB info
                        off_names = set()
                        try:
                            import json
                            mapping_path = os.path.join(base_manual, "NAMA_MAPPING.json")
                            if os.path.isfile(mapping_path):
                                with open(mapping_path, 'r') as f:
                                    mp = json.load(f)
                                for k,v in mp.get("beban-penyulang", {}).items():
                                    if v.get("cb")=="OFF":
                                        off_names.add(k)
                        except:
                            pass
                        for folder in sorted(os.listdir(bp_path)):
                            full = os.path.join(bp_path, folder)
                            if not os.path.isdir(full):
                                continue
                            cnt = 0
                            try:
                                cnt = len([f for f in os.listdir(full) if f.lower().endswith(('.jpg','.jpeg','.png'))])
                            except:
                                pass
                            is_off = folder in off_names
                            badge = f"{C['Y']}OFF{C['R']}" if is_off else f"{C['G']}ON{C['R']}"
                            print(f"    {folder:<22} : {cnt:>3} foto [{badge}] {'(skip CB OFF, tetap simpan)' if is_off else ''}")
                    # beban-trafo
                    print(f"\n  {C['M']}{C['B']}BEBAN TRAFO (3){C['R']}")
                    bt_path = os.path.join(base_manual, "beban-trafo")
                    if os.path.isdir(bt_path):
                        for folder in sorted(os.listdir(bt_path)):
                            full = os.path.join(bt_path, folder)
                            if not os.path.isdir(full):
                                continue
                            cnt = len([f for f in os.listdir(full) if f.lower().endswith(('.jpg','.jpeg','.png'))]) if os.path.isdir(full) else 0
                            print(f"    {folder:<22} : {cnt:>3} foto")

                    # tegangan
                    print(f"\n  {C['M']}{C['B']}TEGANGAN TRAFO (5 trafo × hv/mv terpisah){C['R']}")
                    tt_path = os.path.join(base_manual, "tegangan-trafo")
                    if os.path.isdir(tt_path):
                        for trafo in sorted(os.listdir(tt_path)):
                            trafo_full = os.path.join(tt_path, trafo)
                            if not os.path.isdir(trafo_full):
                                continue
                            hv_path = os.path.join(trafo_full, "hv")
                            mv_path = os.path.join(trafo_full, "mv")
                            cnt_hv = len([f for f in os.listdir(hv_path) if f.lower().endswith(('.jpg','.jpeg','.png'))]) if os.path.isdir(hv_path) else 0
                            cnt_mv = len([f for f in os.listdir(mv_path) if f.lower().endswith(('.jpg','.jpeg','.png'))]) if os.path.isdir(mv_path) else 0
                            print(f"    {trafo:<12} : HV {cnt_hv:>2} foto  MV {cnt_mv:>2} foto  (pisah folder, tidak perlu rename)")

                    print(f"\n  {C['D']}Total manual: {total_manual} foto, pool generic: {pool_cnt} file{C['R']}")
                    print(f"  {C['D']}Foto tidak dihapus setelah dipakai (read-only random){C['R']}")
            except Exception as e:
                print(f"  {C['RE']}Error: {e}{C['R']}")
            input(f"\n  {C['D']}[Enter]{C['R']}")
        elif choice == '4':
            # Validasi foto manual
            print()
            print(f"  {C['Y']}Menjalankan validasi foto manual (scan 500+ file)...{C['R']}")
            try:
                import subprocess
                import sys
                script = os.path.join(SCRIPT_DIR, "tools", "validate_manual_pool.py")
                if os.path.isfile(script):
                    result = subprocess.run([sys.executable, script], cwd=SCRIPT_DIR)
                else:
                    print(f"  {C['RE']}tools/validate_manual_pool.py belum ada, jalankan manual:{C['R']}")
                    print(f"  {C['D']}python3 -c \"import superi_humanizer as hu; print(hu.get_pool_stats())\"{C['R']}")
                    # fallback simple stats
                    if hu and hasattr(hu, "get_pool_stats"):
                        print(f"  {hu.get_pool_stats()}")
            except Exception as e:
                print(f"  {C['RE']}Validasi error: {e}{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")
        elif choice == '5':
            clear()
            header("📖 PANDUAN FOTO MANUAL ANTI-ROBOTIK")
            print(f"""
  {C['B']}Kenapa per-item?{C['R']}
  - Kalau pakai 1 foto untuk semua (pool mode), visual sama semua → mudah terdeteksi robotik
  - Per-item manual: CASABLANCA4 beda dengan LABORATORIUM, sesuai panel fisik asli

  {C['B']}Foto diambil bagaimana?{C['R']}
  - Per penyulang 2-3 foto: close-up (30-50cm), wide (1m), 45° sudut
  - Per beban trafo 2 foto: full panel + close meter
  - Per tegangan trafo: HV dan MV pisah folder (hv/ & mv/), tiap sisi 2 foto
  - HP mode biasa, jangan portrait blur bawaan, size >100KB ideal
  - Taruh di: photo/manual/{{tipe}}/{{NAMA}}/ (auto random per input)

  {C['B']}Varian blur/kabur/asli?{C['R']}
  - Saat input CLI, dari folder item tersebut di-random 1 foto
  - Lalu di-apply varian random: asli 40%, blur ringan 20%, blur berat 10%,
    kabur glare 15% (pantulan lampu), noisy gelap 15% (cocok jam 00-06)
  - Crop center square 720x720 jitter ±5% + pixel jitter 2-6 titik
  - Re-encode baseline JPEG quality 82-93, exif=b'', progressive=False
  - Size 20-60KB (match audit server 14-51KB avg 27KB)
  - Filename upload TETAP humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg
    (bukan basename manual seperti WhatsApp Image...)

  {C['B']}OFF handling:{C['R']}
  - 7 penyulang CB OFF (FISIOTERAPI, RONTGEN, REFLEXY, HERBAL, PINSET, KOPEL_*)
    foto tetap simpan 84 file, tapi skip input saat CB OFF (read-only)

  {C['B']}Foto dihapus setelah dipakai?{C['R']}
  - TIDAK. File asli tetap di disk, hanya dibaca random tiap input
  - Bisa dipakai lagi periode berikutnya, SHA beda karena varian+crop

  {C['B']}Pool vs Manual:{C['R']}
  - pool  : 1 foto di photo/pool/ untuk semua (fallback cepat, untuk demo)
           re-encode beda SHA tiap upload tapi visual sama
  - manual: per-item sesuai (random dari folder item + hv/mv terpisah)
           visual beda per penyulang, lebih natural, rekomendasi utama

  {C['B']}Setting:{C['R']}
  - CLI: [T] Settings → [1] Ganti Sumber Foto (pool/manual)
  - Config: .superi_config.json key photo_source
  - Default: pool (backward compat)
""")
            input(f"  {C['D']}[Enter]{C['R']}")
        elif choice == '6':
            # Test foto random
            clear()
            header("🧪 TEST FOTO RANDOM + VARIAN")
            try:
                if not hu:
                    print(f"  {C['RE']}Humanizer tidak tersedia (PIL mungkin belum install){C['R']}")
                    input(f"  {C['D']}[Enter]{C['R']}")
                    continue

                print(f"  Test random pick dari pool (source={photo_src}):\n")
                # test beban-penyulang
                test_items = ["CASABLANCA4", "LABORATORIUM", "TRAFO 1"]
                for item_name in test_items:
                    data_type = "beban-penyulang" if "CASABLANCA" in item_name or item_name in ["LABORATORIUM"] else "beban-trafo"
                    if item_name.startswith("TRAFO"):
                        data_type = "beban-trafo"
                    cnt = 0
                    try:
                        cnt = hu.get_manual_count(item_name, data_type)
                    except:
                        cnt = 0
                    print(f"  {C['B']}{item_name}{C['R']} ({data_type}) - pool: {cnt} foto")
                    for i in range(3):
                        try:
                            b = hu.rand_jpeg_bytes(item_name=item_name, data_type=data_type, photo_source=photo_src)
                            meta = hu.get_last_meta()
                            src_bn = meta.get("src_basename","")[:28]
                            var = meta.get("variant","")
                            smode = meta.get("source_mode","")
                            print(f"    [{i+1}] {len(b)}B src={src_bn} [{var}] ({smode})")
                        except Exception as e:
                            print(f"    [{i+1}] Error: {e}")

                # test tegangan hv/mv terpisah
                print(f"\n  {C['B']}Tegangan TRAFO 1 HV/MV terpisah:{C['R']}")
                for sub in ["HV","MV"]:
                    try:
                        b = hu.rand_jpeg_bytes(item_name="TRAFO 1", data_type="tegangan-trafo", subtype=sub, photo_source=photo_src)
                        meta = hu.get_last_meta()
                        src_bn = meta.get("src_basename","")[:28]
                        var = meta.get("variant","")
                        folder = meta.get("folder_label","")
                        print(f"    {sub}: {len(b)}B src={src_bn} [{var}] folder={folder}")
                    except Exception as e:
                        print(f"    {sub} Error: {e}")

                print(f"\n  {C['D']}Filename upload tetap humanizer (bukan basename manual):{C['R']}")
                if hasattr(hu, "rand_filename"):
                    from datetime import timezone, timedelta
                    import datetime as _dt
                    sample_dt = _dt.datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%dT%H:%M:%S.123Z")
                    for dtype in ["beban-penyulang","beban-trafo","tegangan-trafo"]:
                        fn = hu.rand_filename(sample_dt, idx=0, data_type=dtype, subtype="HV" if "tegangan" in dtype else None)
                        print(f"    {dtype}: {fn}")

                print(f"\n  {C['G']}Test selesai. Foto tidak dihapus, tetap di disk (read-only random).{C['R']}")
            except Exception as e:
                print(f"  {C['RE']}Error test: {e}{C['R']}")
                import traceback
                traceback.print_exc()
            input(f"  {C['D']}[Enter]{C['R']}")
        else:
            print(f"\n  {C['RE']}✗ Pilihan tidak valid{C['R']}")
            input(f"  {C['D']}[Enter]{C['R']}")


def main():
    # CLI flag: superi_app.py --logout [opts]
    if any(a in sys.argv for a in ("--logout", "--lo")):
        # filter args after --logout
        try:
            idx = sys.argv.index("--logout")
        except ValueError:
            try:
                idx = sys.argv.index("--lo")
            except ValueError:
                idx = 1
        extra = sys.argv[idx + 1 :] if idx + 1 < len(sys.argv) else []
        cmd_logout_cli(extra)
        return

    config = load_config()
    
    # Setup jika belum ada config
    if not config.get("nip"):
        setup_config()
        config = load_config()
    
    token = None
    user = None
    gi_id = None  # auto-detected saat login
    
    # Auto-login saat startup
    token, user, gi_id = do_login(config)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    _enable_win_vt100()   # Windows VT100 for \r live-progress

    while True:
        clear()
        header("⚡ SUPER-I APP  ·  Data Input & Sync Tool")
        status_bar(user, gi_id, date_str)
        print()

        # Menu 2 kolom: LIHAT + INPUT
        print(f"  {C['M']}{C['B']}LIHAT DATA{C['R']}                    {C['M']}{C['B']}INPUT MANUAL{C['R']}")
        print(f"  {C['C']}[1]{C['R']} Beban Penyulang        {C['C']}[4]{C['R']} Beban Penyulang")
        print(f"  {C['C']}[2]{C['R']} Beban Trafo            {C['C']}[5]{C['R']} Beban Trafo")
        print(f"  {C['C']}[3]{C['R']} Tegangan Trafo         {C['C']}[6]{C['R']} Tegangan Trafo")
        print()

        # Batch
        print(f"  {C['Y']}{C['B']}BATCH per ITEM{C['R']}             {C['Y']}{C['B']}BATCH per JAM{C['R']} {C['G']}(+ Sync Portal){C['R']}")
        print(f"  {C['C']}[7]{C['R']} Beban Penyulang        {C['C']}[A]{C['R']} Beban Penyulang")
        print(f"  {C['C']}[8]{C['R']} Beban Trafo            {C['C']}[B]{C['R']} Beban Trafo")
        print(f"  {C['C']}[9]{C['R']} Tegangan Trafo         {C['C']}[C]{C['R']} Tegangan Trafo")
        print()

        # Lain
        _photo_src = get_photo_source()
        _photo_badge = f"{C['G']}{_photo_src.upper()}{C['R']}" if _photo_src=="manual" else f"{C['Y']}{_photo_src.upper()}{C['R']}"
        print(f"  {C['D']}{C['B']}PENGATURAN{C['R']}")
        print(f"  {C['C']}[G]{C['R']} Ganti Tanggal   {C['C']}[L]{C['R']} Login Ulang   {C['C']}[O]{C['R']} Logout   {C['C']}[S]{C['R']} Setup   {C['RE']}[0]{C['R']} Keluar")
        print(f"  {C['C']}[T]{C['R']} 📸 Foto Source [{_photo_badge}]  {C['D']}({ 'per-item sesuai' if _photo_src=='manual' else '1 foto semua' }, varian blur/kabur/asli){C['R']}")
        print()
        # Auto mode status
        _auto_cfg = load_config()
        _auto_on = _auto_cfg.get("auto_enabled", False)
        _auto_badge = f"{C['G']}ON{C['R']}" if _auto_on else f"{C['RE']}OFF{C['R']}"
        print(f"  {C['C']}[P]{C['R']} 🔄 Sync ke Portal APD    {C['C']}[D]{C['R']} ⏰ Auto Mode [{_auto_badge}]")
        print()
        print(f"  {C['D']}{'─' * 56}{C['R']}")

        choice = input(f"  {C['B']}Pilih ▸ {C['R']}").strip().lower()

        if choice == '0':
            print(f"\n  {C['G']}✓ Selamat bekerja!{C['R']}\n")
            break
        
        # Login if needed
        if choice in '123456789abc' and not token:
            print("\n  Login...")
            token, user, gi_id = do_login(config)
            if not token:
                input(f"  {C['D']}[Enter]{C['R']}")
                continue
        
        try:
            if choice == 'g':
                date_str = input("  Tanggal (YYYY-MM-DD): ").strip() or date_str
            elif choice == 'l':
                token, user, gi_id = do_login(config)
                input(f"  {C['D']}[Enter]{C['R']}")
            elif choice == 's':
                setup_config()
                config = load_config()
                token = None
            elif choice == '1':
                show_data(token, "beban-penyulang", gi_id, date_str)
            elif choice == '2':
                show_data(token, "beban-trafo", gi_id, date_str)
            elif choice == '3':
                show_data(token, "tegangan-trafo", gi_id, date_str)
            elif choice == '4':
                input_single(token, "beban-penyulang", gi_id, date_str, user)
            elif choice == '5':
                input_single(token, "beban-trafo", gi_id, date_str, user)
            elif choice == '6':
                input_single(token, "tegangan-trafo", gi_id, date_str, user)
            elif choice == '7':
                batch_fill(token, "beban-penyulang", gi_id, date_str, user)
            elif choice == '8':
                batch_fill(token, "beban-trafo", gi_id, date_str, user)
            elif choice == '9':
                batch_fill(token, "tegangan-trafo", gi_id, date_str, user)
            elif choice == 'a':
                batch_fill_periode(token, "beban-penyulang", gi_id, date_str, user)
            elif choice == 'b':
                batch_fill_periode(token, "beban-trafo", gi_id, date_str, user)
            elif choice == 'c':
                batch_fill_periode(token, "tegangan-trafo", gi_id, date_str, user)
            elif choice == 't':
                photo_settings_menu()
                config = load_config()
            elif choice == 'd':
                auto_mode_menu()
                config = load_config()
            elif choice == 'p':
                sync_portal_menu(date_str)
            elif choice == 'o':
                did_logout, new_cfg = do_logout_interactive(current_user=user)
                if did_logout:
                    # Token RAM dibuang, config reload, user harus setup ulang
                    token = None
                    user = None
                    gi_id = None
                    config = new_cfg if isinstance(new_cfg, dict) else load_config()
        except Exception as e:
            print(f"\n  ✗ Error: {e}")
            input(f"  {C['D']}[Enter]{C['R']}")

if __name__ == "__main__":
    main()
