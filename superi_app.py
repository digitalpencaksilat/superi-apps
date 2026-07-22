#!/usr/bin/env python3
"""
SUPER-I APP - Interactive Data Input (Rich Edition - Tema Kuning)
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
    import superi_console as sc
except Exception:
    sc = None

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
    if sc is not None:
        try:
            if hasattr(sc, "_enable_win_vt100"):
                sc._enable_win_vt100()
                return
        except Exception:
            pass
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


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
    clear()
    header("🚪 LOGOUT AKUN")
    _cprint("")
    cfg = load_config()
    nip = cfg.get("nip", "")
    has_portal = bool(cfg.get("portal_user") and cfg.get("portal_password"))
    auto_on = cfg.get("auto_enabled", False)
    sched_on = scheduler_is_installed()
    os_name = "Task Scheduler" if platform.system() == "Windows" else "cron"
    if current_user and isinstance(current_user, dict):
        nama = current_user.get("namaLengkap", "?")
        _cprint(f"  [bold]Akun aktif:[/] {nama} [dim]({nip})[/]")
    elif nip:
        _cprint(f"  [bold]Akun aktif:[/] {nip}")
    else:
        _warn("Tidak ada akun tersimpan di config")
        _dim("Token di RAM akan dibuang, tapi tidak ada kredensial file yang dihapus.")
        print()
        if sc and hasattr(sc, 'pause'):
            sc.pause()
        else:
            input("  [Enter]")
        return False, cfg
    _cprint("")
    _cprint("  [bold bright_yellow]Yang akan terjadi saat logout:[/]")
    _dim(f"  {'─'*44}")
    _cprint(f"  [bold red]  ✗ Hapus:[/] NIP + Password SUPER-I")
    if has_portal:
        _cprint(f"  [bold red]  ✗ Hapus:[/] Portal APD (user + password)")
    else:
        _dim("  · Portal APD belum diset")
    _cprint(f"  [bold green]  ✓ Keep:[/] GI ID, Portal URL, history_days")
    _cprint(f"  [bold red]  ✗ Auto Mode:[/] {'AKTIF -> akan OTOMATIS NONAKTIF' if auto_on else 'sudah nonaktif'}")
    sched_msg = 'TERPASANG -> akan OTOMATIS DIHAPUS' if sched_on else 'belum terpasang'
    _cprint(f"  [bold red]  ✗ Scheduler {os_name}:[/] {sched_msg}")
    _dim("  · Token RAM: dibuang (perlu Login Ulang / Setup)")
    _dim("  · Backup: .superi_config.json.bak akan dibuat")
    _cprint("")
    keep_portal = False
    keep_sched = False
    if has_portal:
        ans = sc.prompt_ask("Tetap simpan kredensial Portal APD?", default="n") if sc else input("  Tetap simpan kredensial Portal APD? (y/N): ").strip().lower()
        keep_portal = str(ans).lower() in ("y","yes","true","1") if sc else (ans == 'y')
    if sched_on:
        ans2 = sc.prompt_ask(f"Hapus jadwal {os_name}?", default="y") if sc else input(f"  Hapus jadwal {os_name}? (Y/n): ").strip().lower()
        keep_sched = str(ans2).lower() in ("n","no") if sc else (ans2 == 'n')
    print()
    if sc:
        final = sc.confirm_ask("Yakin logout & hapus kredensial?", default=False)
    else:
        final = input("  Yakin logout & hapus kredensial? (y/N): ").strip().lower() == 'y'
    if not final:
        _warn("Logout dibatalkan.")
        if sc and hasattr(sc, 'pause'):
            sc.pause()
        else:
            input("  [Enter]")
        return False, cfg
    _cprint("")
    _cprint("  [bold yellow]Melakukan logout...[/]")
    bak_path = backup_config()
    if bak_path:
        _dim(f"  · Backup dibuat: {os.path.basename(bak_path)}")
    status = clear_credentials(purge_all=False, keep_portal=keep_portal, keep_scheduler=keep_sched)
    new_cfg = load_config()
    _ok("Kredensial SUPER-I dihapus")
    if not keep_portal and has_portal:
        _ok("Kredensial Portal APD dihapus")
    elif keep_portal:
        _dim("  · Kredensial Portal APD dipertahankan")
    if status.get("auto_status") is None:
        _ok("Auto Mode OTOMATIS NONAKTIF")
    if sched_on and not keep_sched:
        if not scheduler_is_installed():
            _ok(f"Scheduler {os_name} OTOMATIS DIHAPUS")
        else:
            _warn(f"Gagal hapus {os_name}, silakan hapus manual")
    _cprint("")
    _ok("Logout berhasil!")
    _dim("  Token di RAM sudah dibuang.")
    _dim("  Gunakan [S] Setup untuk login akun baru")
    _cprint("")
    _dim("  Untuk login ulang: NIP + password baru akan diminta")
    _cprint("")
    if sc and hasattr(sc, 'pause'):
        sc.pause()
    else:
        input("  [Enter untuk kembali ke menu...]")
    return True, new_cfg

def cmd_logout_cli(argv):
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
        _warn("Tidak ada config ditemukan, tidak ada yang perlu di-logout")
        return True
    if not force_yes:
        print()
        _cprint("  [bold yellow]LOGOUT[/]")
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
            _warn("Dibatalkan")
            return False
    bak = backup_config()
    if bak:
        print(f"  Backup: {bak}")
    status = clear_credentials(purge_all=purge_all, keep_portal=keep_portal, keep_scheduler=keep_sched)
    if purge_all:
        _ok("Config file dihapus total (purge)")
    else:
        _ok("Kredensial SUPER-I dihapus, auto_enabled=False")
        if not keep_portal and has_portal:
            _ok("Portal kredensial dihapus")
        if sched_on and not keep_sched:
            if not scheduler_is_installed():
                _ok("Scheduler dihapus")
            else:
                _warn("Scheduler gagal dihapus (cek permission)")
    print()
    _ok("Logout berhasil. Login ulang: jalankan superi cli → [S] Setup")
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
      + varian asli/blur/noisy random 45/25/15/15
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
    """Clear screen - Rich yellow edition."""
    if sc is not None:
        try:
            sc.clear()
            return
        except Exception:
            pass
    os.system('clear' if os.name != 'nt' else 'cls')

# Backwards compat C dict - ANSI fallback, yellow primary (tema kuning #FFC107)
C = {
    'R': '\033[0m',
    'B': '\033[1m',
    'D': '\033[2m',
    'G': '\033[92m',
    'Y': '\033[93m',
    'RE': '\033[91m',
    'C': '\033[93m',
    'M': '\033[93m',
    'W': '\033[97m',
    'BG': '\033[43m',
}

def _cprint(msg):
    if sc is not None and getattr(sc, 'console', None):
        try:
            sc.console.print(msg)
            return
        except Exception:
            pass
    import re as _re
    clean = _re.sub(r'\[.*?\]', '', msg)
    print(clean)

def _ok(msg):
    if sc is not None:
        try:
            if hasattr(sc, 'ok'):
                sc.ok(msg)
                return
        except Exception:
            pass
    _cprint(f"[bold green]✓ {msg}[/]")

def _err(msg):
    if sc is not None:
        try:
            if hasattr(sc, 'err'):
                sc.err(msg)
                return
        except Exception:
            pass
    _cprint(f"[bold red]✗ {msg}[/]")

def _warn(msg):
    if sc is not None:
        try:
            if hasattr(sc, 'warn_msg'):
                sc.warn_msg(msg)
                return
        except Exception:
            pass
    _cprint(f"[bold bright_yellow]⚠ {msg}[/]")

def _dim(msg):
    if sc is not None and getattr(sc, 'console', None):
        try:
            sc.console.print(f"[dim]{msg}[/]")
            return
        except Exception:
            pass
    print(f"  {msg}")

def header(title):
    if sc is not None:
        try:
            sc.header(title)
            return
        except Exception:
            pass
    w = 60
    print(f"{'━'*w}")
    print(f"  {title}")
    print(f"{'━'*w}")

def sub_header(title):
    if sc is not None:
        try:
            sc.sub_header(title)
            return
        except Exception:
            pass
    print(f"\n  ▸ {title}")
    print(f"  {'─'*50}")

def status_bar(user, gi_id, date_str):
    if sc is not None:
        try:
            sc.status_bar(user, gi_id, date_str)
            return
        except Exception:
            pass
    if user:
        print(f"  ┌─────────────────────────────────────────────────────┐")
        print(f"  │  ● {user['namaLengkap']} ({', '.join(user['roles'])})")
        print(f"  │  📍 GI: {gi_id}  📅 {date_str}")
        print(f"  └─────────────────────────────────────────────────────┘")
    else:
        print(f"  ┌─────────────────────────────────────────────────────┐")
        print(f"  │  ○ Belum login  📅 {date_str}")
        print(f"  └─────────────────────────────────────────────────────┘")

def menu(title, options):
    while True:
        clear()
        header(title)
        for i, (key, desc) in enumerate(options, 1):
            if sc is not None and getattr(sc, 'console', None):
                try:
                    sc.console.print(f"  [bold bright_yellow][{i}][/] {desc}")
                except Exception:
                    print(f"  [{i}] {desc}")
            else:
                print(f"  [{i}] {desc}")
        if sc is not None and getattr(sc, 'console', None):
            try:
                sc.console.print("  [dim][0] Keluar[/]")
            except Exception:
                print("  [0] Keluar")
        else:
            print("  [0] Keluar")
        print()
        try:
            if sc is not None:
                choice = sc.prompt_ask("Pilih", default="0")
            else:
                choice = input("  Pilih > ").strip()
            if choice == '0':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except (ValueError, IndexError):
            pass
        if sc is not None:
            try:
                sc.warn_msg("Pilihan tidak valid!")
            except Exception:
                print("  ✗ Pilihan tidak valid!")
        else:
            print("  ✗ Pilihan tidak valid!")

def input_with_default(prompt, default=""):
    if sc is not None:
        try:
            return sc.prompt_ask(prompt, default=default if default else None)
        except Exception:
            pass
    if default:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"  {prompt}: ").strip()

def confirm(msg):
    if sc is not None:
        try:
            return sc.confirm_ask(msg, default=False)
        except Exception:
            pass
    return input(f"  {msg} (y/n): ").strip().lower() == 'y'



def _rich_print_table(items, data_type, date_str=None, kind="item"):
    if ui and sc and getattr(sc, 'console', None):
        try:
            if getattr(sc, 'RICH_AVAILABLE', False):
                if kind == "item" and hasattr(ui, "item_table_rich"):
                    t = ui.item_table_rich(items, data_type)
                    sc.console.print(t)
                    return True
                if kind == "data" and hasattr(ui, "data_view_rich"):
                    t = ui.data_view_rich(items, data_type, date_str)
                    sc.console.print(t)
                    return True
                if kind == "suggest" and hasattr(ui, "suggest_table_rich"):
                    t = ui.suggest_table_rich(items)
                    sc.console.print(t)
                    return True
                if kind == "suggest_pool" and hasattr(ui, "suggest_table_with_pool_rich"):
                    t = ui.suggest_table_with_pool_rich(items)
                    sc.console.print(t)
                    return True
                if kind == "existing" and hasattr(ui, "existing_data_rich"):
                    t = ui.existing_data_rich(items, data_type)
                    sc.console.print(t)
                    return True
        except Exception:
            pass
    return False

def _print_summary_rich(success, fail, total, label):
    if sc and getattr(sc, 'console', None):
        try:
            if ui and hasattr(ui, "summary_panel_rich"):
                panel = ui.summary_panel_rich(success, fail, total, label)
                sc.console.print(panel)
                return
            sc.summary_box(success, fail, total, label)
            return
        except Exception:
            pass
    if ui:
        try:
            print(ui.render_summary_box(success, fail, total, label))
            return
        except Exception:
            pass
    print(f"  Ringkasan {label}: {success}/{total}")

def _get_suggestion_table_rows_for_display(rows):
    if not _rich_print_table(rows, None, kind="suggest"):
        if ui:
            for ln in ui.render_suggest_table(rows):
                print(ln)
        else:
            print(f"  {'No':<4}{'Nama':<18}{'Suggest':<14}Info")
            for no, nama, val, info in rows:
                print(f"  {no:<4}{str(nama)[:18]:<18}{val:<14}{info}")


# ============================================================
# WORKFLOW
# ============================================================



def setup_config():
    """Setup kredensial pertama kali."""
    clear()
    header("⚙  SETUP KREDENSIAL")
    print()
    _cprint(f"  [dim]Kredensial akan disimpan di ~/.superi_config.json[/]")
    _cprint(f"  [dim]Gardu Induk akan otomatis terdeteksi dari profil.[/]")
    print()

    # --- SUPER-I APP ---
    _cprint(f"  [bold magenta][bold]1. SUPER-I APP[/] [dim](super-i-app.plnes.co.id)[/]")
    nip = input_with_default('NIP', '')
    password = sc.prompt_ask('Password', password=True) if sc and hasattr(sc, 'prompt_ask') else input('  Password   : ').strip()
    print()

    # --- Portal APD Jakarta ---
    _cprint(f"  [bold magenta][bold]2. Portal APD Jakarta[/] [dim](10.3.187.6/apdjakarta)[/]")
    _cprint(f"  [dim]Untuk sinkronisasi data. Kosongkan jika tidak dipakai.[/]")
    portal_user = input_with_default('Portal Username', '')
    portal_password = sc.prompt_ask('Portal Password', password=True) if sc and hasattr(sc, 'prompt_ask') else input('  Portal Password : ').strip()

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
    _cprint(f"  [bold green]✓ Konfigurasi tersimpan![/]")
    if portal_user and portal_password:
        _cprint(f"  [bold green]✓ Portal APD siap untuk sinkronisasi[/]")
    else:
        _cprint(f"  [bold bright_yellow]⚠ Credentials Portal APD belum lengkap — sync tidak aktif[/]")
    sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')

def do_login(config):
    """Login, return token, user info, dan gi_id. Handling 401 dengan petunjuk jelas."""
    nip = config.get("nip")
    password = config.get("password")
    if not nip or not password:
        _cprint(f"  [bold red]✗ Konfigurasi belum di-setup. Jalankan setup dulu.[/]")
        _cprint(f"  [dim]  File: {CONFIG_FILE}[/]")
        _cprint(f"  [dim]  Atau pilih [S] Setup di menu.[/]")
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
            _cprint(f"  [bold red]✗ Login gagal (401 Unauthorized):[/]")
            _cprint(f"  [bold bright_yellow]  Penyebab: NIP atau password di config salah / kadaluarsa[/]")
            _cprint(f"  [dim]  NIP di config: {nip}[/]")
            _cprint(f"  [dim]  File: {CONFIG_FILE}[/]")
            print()
            _cprint(f"  [bold]Solusi:[/]")
            _cprint(f"    1. Pilih [bold bright_yellow][S] Setup[/] untuk input NIP/password baru")
            print(f"    2. Atau edit manual file .superi_config.json")
            print(f"    3. Pastikan NIP tanpa spasi, password sesuai akun PLN")
            print(f"    4. Cek apakah akun masih aktif & sudah clock-in di SUPER-I")
        else:
            _cprint(f"  [bold red]✗ Login gagal: {e}[/]")
        return None, None, None

def show_data(token, data_type, gi_id, date_str):
    """Tampilkan data dan periode kosong."""
    ep = ENDPOINTS[data_type]
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result["data"].get("items", [])
    
    if not items:
        _cprint(f"  [bold bright_yellow]Tidak ada data untuk {date_str}[/]")
        return
    
    clear()
    header(f"📊 {ep['label']} · {date_str}")
    if sc and getattr(sc, 'console', None):
        try:
            sc.console.print()
        except Exception:
            print()
    else:
        print()

    if not _rich_print_table(items, data_type, date_str, kind="data"):
        if ui:
            for ln in ui.render_data_view(items, data_type):
                print(ln)
            data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
            total_filled = sum(len(it.get(data_key, [])) for it in items)
            total_empty = len(items) * 24 - total_filled
            print()
            _cprint(f"  [dim]{ui.render_data_summary(len(items), total_filled, total_empty)}[/]")
        else:
            for item in items:
                nama = item.get("nama", "?")
                data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
                entries = item.get(data_key, [])
                periods = sorted([e["periode"] for e in entries])
                print(f"  [{item.get('id', '?')}] {nama} - {len(periods)}/24")
    else:
        data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
        total_filled = sum(len(it.get(data_key, [])) for it in items)
        if ui:
            try:
                summary_line = ui.render_data_summary(len(items), total_filled, len(items)*24-total_filled)
                if sc and getattr(sc, 'console', None):
                    sc.console.print(f"\n  [dim]{summary_line}[/]")
                else:
                    print(f"\n  {summary_line}")
            except Exception:
                pass

    if sc and getattr(sc, 'console', None):
        try:
            sc.console.print()
            sc.pause()
        except Exception:
            input("  [Enter untuk kembali...]")
    else:
        print()
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')

def input_single(token, data_type, gi_id, date_str, user_info, selected_item=None, show_header=True):
    """Input data untuk satu target spesifik."""
    ep = ENDPOINTS[data_type]

    if selected_item is None:
        result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
        items = result["data"].get("items", [])
        if not items:
            print(f"  Tidak ada item untuk {date_str}")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
            return
        if show_header:
            clear()
            header(f"✏  INPUT {ep['label']}")
            print()
        if not _rich_print_table(items, data_type, kind="item"):
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
                raise ValueError
        except ValueError:
            _cprint(f"  [bold red]✗ Pilihan tidak valid![/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
            return
        item = items[idx]
    else:
        item = selected_item
    item_id = item["id"]
    nama = item["nama"]
    
    # Tolak CB OFF
    if item.get('statusCB') == 'OFF':
        print(f"\n  ⛔ {nama} CB OFF — tidak bisa input beban!")
        print("  (Circuit Breaker mati, tidak ada arus)")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        return
    
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
    entries = item.get(data_key, [])
    periods_filled = [e["periode"] for e in entries]
    empty_periods = [p for p in range(24) if p not in periods_filled]
    
    print(f"\n  Target: {nama} (ID:{item_id})")

    # Tampilkan data existing (compact) - Rich yellow
    if entries:
        if sc and getattr(sc, 'console', None):
            try:
                sc.console.print("  [dim]Data existing:[/]")
            except Exception:
                _cprint(f"  [dim]Data existing:[/]")
        else:
            _cprint(f"  [dim]Data existing:[/]")
        if not _rich_print_table(entries, data_type, kind="existing"):
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
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        return
    
    print(f"\n  Periode kosong: {empty_periods}")
    
    # Pilih periode
    try:
        per = int(input("  Periode yang akan diisi: ").strip())
        if per not in empty_periods and per not in range(24):
            _cprint(f"  [bold red]✗ Periode tidak valid![/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
            return
    except ValueError:
        _cprint(f"  [bold red]✗ Periode tidak valid![/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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
            sys.stdout.write(f"\r    [bold green]✓[/] Smart suggest: {smart_val}A ({info}){' ' * 6}\n")
        else:
            sys.stdout.write(f"\r    [bold bright_yellow]•[/] Smart suggest tidak tersedia{' ' * 6}\n")
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
        mv_str = input_with_default(f"  [bold]{'MV (kV)':<14}[/] [{suggested_mv}]: ").strip()
        mv = float(mv_str) if mv_str else float(suggested_mv)
        hv_str = input_with_default(f"  [bold]{'HV (kV)':<14}[/] [{suggested_hv}]: ").strip()
        hv = float(hv_str) if hv_str else float(suggested_hv)
        value = mv
        extra_values = {"hv": hv}
    else:
        val_str = input_with_default(f"  [bold]{'Nilai (A)':<14}[/]{suggested}: ").strip()
        if not val_str and suggested:
            val_str = suggested.split(": ")[1].replace("A]", "")
        value = float(val_str)
        extra_values = {}
    
    if not confirm(f"\n  Input {nama} periode {per}: {value}{ep['unit']}?"):
        _cprint(f"  [bold bright_yellow]⊘ Dibatalkan.[/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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
            _cprint(f"  [bold bright_yellow]⚠ NILAI TERSIMPAN! ID: {result['data'].get('id')}, tetapi foto gagal[/]")
            _cprint(f"  [bold red]✗ {photo_check.get('error')}[/]")
        else:
            _cprint(f"  [bold green]✓ BERHASIL! ID: {result['data'].get('id')}[/]")
    else:
        msg = result.get("message", str(result))
        if isinstance(msg, list):
            msg = ", ".join(msg)
        _cprint(f"  [bold red]✗ Gagal ({status}): {msg}[/]")
    
    print()
    sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')

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
        _cprint(f"  [bold red]✗ Credentials Portal PLN belum diset di .superi_config.json[/]")
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
    _cprint(f"  [dim]Sumber: SUPER-I APP  →  Tujuan: Portal APD Jakarta[/]")
    _cprint(f"  [dim]Tanggal: {date_str}[/]")
    print()

    sub_header("Pilih jenis data")
    _cprint(f"  [bold bright_yellow][1][/] Beban Penyulang  (32 feeder)")
    _cprint(f"  [bold bright_yellow][2][/] Beban Trafo      (3 trafo)")
    _cprint(f"  [bold bright_yellow][3][/] Tegangan Trafo   (5 trafo, MV+HV)")
    _cprint(f"  [bold bright_yellow][4][/] SEMUA")
    _cprint(f"  [dim][0][/] Kembali")
    choice = sc.prompt_ask('Pilih', default='0') if sc else input('  Pilih ▸ ').strip().lower()

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
        _cprint(f"  [bold red]✗ Format jam salah[/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        return

    date_input = input_with_default("Tanggal", date_str)

    # Cek modul + kredensial Portal APD
    try:
        import superi_sync
    except ImportError as e:
        _cprint(f"  [bold red]✗ Modul superi_sync tidak ditemukan: {e}[/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        return
    if not superi_sync.PORTAL_USER or not superi_sync.PORTAL_PASS:
        _cprint(f"  [bold red]✗ Credentials Portal APD belum diset di .superi_config.json[/]")
        _cprint(f"  [dim]  Setup via menu [S][/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        return

    # Dry-run preview
    sub_header("DRY-RUN PREVIEW")
    for dt in types:
        superi_sync.do_sync(dt, js, je, date_input, dry_run=True)
    print()

    # Konfirmasi live
    if not confirm(f"[bold bright_yellow]Lanjut LIVE SYNC?[/]"):
        _cprint(f"  [bold bright_yellow]⊘ Dibatalkan — bisa di-sync nanti[/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        return

    sub_header("LIVE SYNC")
    all_ok = True
    for dt in types:
        ok = superi_sync.do_sync(dt, js, je, date_input, dry_run=False)
        if not ok:
            all_ok = False
    print()
    if all_ok:
        _cprint(f"  [bold green]✓ Sync ke Portal APD selesai[/]")
    else:
        _cprint(f"  [bold bright_yellow]⚠ Sebagian sync gagal — cek detail di atas[/]")
    sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')

def batch_fill(token, data_type, gi_id, date_str, user_info):
    """Isi semua periode kosong untuk satu item."""
    ep = ENDPOINTS[data_type]
    
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result["data"].get("items", [])
    
    clear()
    header(f"⚡ BATCH FILL · {ep['label']}")
    print()
    
    if not _rich_print_table(items, data_type, kind="item"):
        if ui:
            for ln in ui.render_item_table(items, data_type):
                print(ln)
        else:
            for i, item in enumerate(items, 1):
                data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
                periods = [e["periode"] for e in item.get(data_key, [])]
                print(f"  [{i}] {item['nama']} - {len(periods)}/24")

    if sc and getattr(sc, 'console', None):
        try:
            sc.console.print()
        except Exception:
            print()
    else:
        print()
    try:
        if sc is not None:
            idx_str = sc.prompt_ask("Pilih nomor item")
            idx = int(idx_str) - 1
        else:
            idx = int(input("  Pilih nomor item: ").strip()) - 1
        if idx < 0 or idx >= len(items):
            return
    except ValueError:
        return
    
    item = items[idx]
    
    # Tolak CB OFF
    if item.get('statusCB') == 'OFF':
        print(f"\n  ⛔ {item['nama']} CB OFF — tidak bisa input beban!")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        return
    
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
    entries = item.get(data_key, [])
    periods_filled = [e["periode"] for e in entries]
    empty_periods = [p for p in range(24) if p not in periods_filled]
    
    if not empty_periods:
        print(f"\n  ✓ {item['nama']} sudah 24/24!")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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
            _cprint(f"  [bold red]✗ Tidak ada nilai valid![/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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
            if sc and getattr(sc, 'console', None) and getattr(sc, 'RICH_AVAILABLE', False):
                try:
                    sc.console.print(f"  [{'green' if ok else 'red'}]{'[OK]' if ok else '[FAIL]' } P{per:02d} {detail[:60]}[/]")
                except Exception:
                    if ui:
                        sys.stdout.write("\r" + ui.fmt_progress_line(i, total, f"P{per:02d}", ok=ok, detail=detail))
                        sys.stdout.flush()
            else:
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
        _print_summary_rich(success, fail, total, "tegangan")
        
        # Tawarkan sync ke Portal PLN
        if success > 0:
            offer_portal_sync(data_type, valid_periods, date_str)
        
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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
    _print_summary_rich(success, fail, total, "beban")
    
    # Tawarkan sync ke Portal PLN
    if success > 0:
        offer_portal_sync(data_type, empty_periods, date_str)
    
    sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')

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
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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
    
    # Tampilkan grid periode (hanya yang masih kosong) - Rich yellow
    empty_periods_list = [p for p in range(24) if empty_by_periode[p]]
    full_count = 24 - len(empty_periods_list)
    if sc and getattr(sc, 'console', None):
        sc.console.print(f"\n  [dim]Periode kosong ({len(empty_periods_list)} jam) — {full_count} jam sudah penuh[/]")
        if empty_periods_list:
            sc.console.print(f"  [dim]{'─' * 40}[/]")
            for p in empty_periods_list:
                cnt = len(empty_by_periode[p])
                sc.console.print(f"  [bold bright_yellow]P{p:02d}:00[/]  | {cnt:3d} item | ⚡ Bisa batch")
    else:
        _cprint(f"\n  [dim]Periode kosong ({len(empty_periods_list)} jam) — {full_count} jam sudah penuh[/]")
        if empty_periods_list:
            print("  " + "─" * 40)
            for p in empty_periods_list:
                count = len(empty_by_periode[p])
                print(f"  P{p:02d}:00  | {count:3d} item | ⚡ Bisa batch")

    if not empty_periods_list:
        _cprint(f"\n  [bold green]✓ Semua periode sudah penuh![/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        return
    
    # Pilih periode
    try:
        per = int(input("\n  Pilih periode (jam): ").strip())
        if per < 0 or per > 23:
            _cprint(f"  [bold red]✗ Periode harus 0-23![/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
            return
    except ValueError:
        return
    
    empty_items = empty_by_periode[per]
    if not empty_items:
        print(f"\n  ✓ Periode P{per:02d} sudah penuh!")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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

    if sc and getattr(sc, 'console', None):
        try:
            sc.console.print()
        except Exception:
            print()
    else:
        print()
    _get_suggestion_table_rows_for_display(suggest_rows)
    
    # Konfirmasi / edit
    if sc and getattr(sc, 'console', None):
        try:
            sc.console.print(f"\n  [dim]{'─' * 55}[/]")
        except Exception:
            print(f"\n  {'─' * 55}")
    else:
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
        _cprint(f"  [bold red]✗ Tidak ada item dengan nilai valid![/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        return
    
    if not confirm(f"\n  Input {len(valid_items)} item di periode P{per:02d}?"):
        _cprint(f"  [bold bright_yellow]⊘ Dibatalkan.[/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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

        if sc and getattr(sc, 'console', None) and getattr(sc, 'RICH_AVAILABLE', False):
            try:
                sc.console.print(f"  [{'green' if ok else 'red'}]{it['nama'][:12]} {'OK' if ok else 'FAIL'} {detail[:50]}[/]")
            except Exception:
                if ui:
                    sys.stdout.write("\r" + ui.fmt_progress_line(i, total, it["nama"][:10], ok=ok, detail=detail))
                    sys.stdout.flush()
        else:
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
        _cprint(f"  [bold red]✗ {nama}: {reason}[/]")

    print()
    _print_summary_rich(success, fail, total, ep["label"])
    
    # Tawarkan sync ke Portal PLN (periode tunggal: per)
    if success > 0:
        offer_portal_sync(data_type, [per], date_str)
    
    if sc:
        try:
            sc.pause()
        except Exception:
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
    else:
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')

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


def cron_install(window_start=None, window_end=None, planned_lines=None):
    """Pasang N cron job random (macOS/Linux). N = jumlah jam window."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        # Hapus semua baris lama SUPER-I-AUTO
        lines = [l for l in existing.splitlines() if CRON_MARKER not in l]
        # Generate baru N baris sesuai window
        new_lines = list(planned_lines) if planned_lines is not None else _generate_cron_lines(window_start, window_end)
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


def win_task_install(window_start=None, window_end=None, planned_tasks=None):
    """Pasang N Windows Task Scheduler, tiap jam beda menit random 3-38 (anti-robotik)."""
    bat = os.path.join(SCRIPT_DIR, "superi.bat")
    task_log = os.path.join(SCRIPT_DIR, "auto_task_log.txt")
    task_cmd = f'cmd /c cd /d "{SCRIPT_DIR}" && "{bat}" auto >> "{task_log}" 2>&1'
    tasks = list(planned_tasks) if planned_tasks is not None else _generate_win_tasks(window_start, window_end)
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
    _cprint(f"  [dim]Window saat ini: {win_start:02d}:00-{win_end:02d}:00 = {len(hours)} jam ({', '.join(f'{h:02d}' for h in hours)})[/]")
    _cprint(f"  [dim]Setiap jam dapat menit random 3-38 (anti menit 5 exact robot) + jitter 2-110 detik[/]")
    _cprint(f"  [dim]Jaminan: menit max 38 + jitter 110s + runtime 5 menit = selesai max 44, sisa 15 menit buffer[/]")
    print()
    if installed:
        cnt = win_task_count_installed() if is_win else cron_count_installed()
        _cprint(f"  [bold green]● Jadwal otomatis SUDAH terpasang ({cnt} jadwal)[/]")
        if is_win:
            _cprint(f"  [dim]N task: {WIN_TASK_PREFIX}-HH (HH={', '.join(f'{h:02d}' for h in hours)}) daily HH:MM random[/]")
        else:
            _cprint(f"  [dim]N baris cron sesuai window, tiap jam menit random 3-38[/]")
    else:
        _cprint(f"  [bold red]○ Jadwal otomatis BELUM terpasang[/]")
    print()
    _cprint(f"  [bold bright_yellow][1][/] {'Pasang ulang (regenerate menit random)' if installed else 'Pasang'} jadwal otomatis ({len(hours)} jadwal)")
    if installed:
        _cprint(f"  [bold bright_yellow][2][/] [bold red]Hapus[/] jadwal otomatis")
        if is_win:
            _cprint(f"  [bold bright_yellow][3][/] 📋 Lihat daftar task terpasang")
        else:
            _cprint(f"  [bold bright_yellow][3][/] 📋 Lihat crontab terpasang")
    _cprint(f"  [bold red][0][/] Kembali")
    print()
    _cprint(f"  [dim]{'─' * 56}[/]")
    choice = sc.prompt_ask('Pilih', default='0') if sc else input('  Pilih ▸ ').strip().lower()
    
    if choice == '1':
        _cprint(f"\n  [bold bright_yellow]Memasang {len(hours)} jadwal (menit random 3-38, window {win_start:02d}-{win_end:02d})...[/]")
        # Preview yang akan dipasang
        preview_lines = _generate_cron_lines(win_start, win_end) if not is_win else []
        preview_tasks = _generate_win_tasks(win_start, win_end) if is_win else []
        if is_win:
            for t_name, h, m in preview_tasks:
                _cprint(f"  [dim]  {t_name} -> {h:02d}:{m:02d} daily[/]")
        else:
            for line in preview_lines:
                # tampilkan M H
                parts = line.split()
                _cprint(f"  [dim]  {parts[0]} {parts[1]} * * * auto (menit {parts[0]} jam {parts[1]})[/]")
        print()
        if is_win:
            ok, msg = win_task_install(win_start, win_end)
        else:
            ok, msg = cron_install(win_start, win_end)
        if ok:
            _cprint(f"  [bold green]✓ Jadwal otomatis terpasang! {msg}[/]")
            _cprint(f"  [dim]Menit acak 3-38 per jam, tiap install beda-beda (mirip setting manual operator).[/]")
            _cprint(f"  [dim]Pastikan Auto Mode AKTIF + komputer menyala di window jam.[/]")
            if is_win:
                _cprint(f"  [dim]Log Task: {os.path.join(SCRIPT_DIR, 'auto_task_log.txt')}[/]")
            else:
                _cprint(f"  [dim]Cek: crontab -l[/]")
        else:
            _cprint(f"  [bold red]✗ Gagal: {msg}[/]")
            if not is_win:
                _cprint(f"  [dim]Di macOS, Terminal mungkin perlu izin 'Full Disk Access' di System Settings.[/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
    elif choice == '2' and installed:
        _cprint(f"\n  [bold bright_yellow]Menghapus jadwal...[/]")
        if is_win:
            ok, msg = win_task_uninstall()
        else:
            ok, msg = cron_uninstall()
        if ok:
            _cprint(f"  [bold green]✓ {msg}[/]")
        else:
            _cprint(f"  [bold red]✗ Gagal: {msg}[/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
    elif choice == '3' and installed:
        print()
        if is_win:
            _cprint(f"  [bold]Daftar task terpasang:[/]")
            for h in range(24):
                task_name = f"{WIN_TASK_PREFIX}-{h:02d}"
                try:
                    r = subprocess.run(["schtasks", "/query", "/tn", task_name, "/fo", "list", "/v"],
                                       capture_output=True, text=True)
                    if r.returncode == 0:
                        _cprint(f"  [bold green]● {task_name}[/]")
                        for line in r.stdout.splitlines()[:8]:
                            print(f"    {line}")
                except Exception:
                    pass
            # legacy
            try:
                r = subprocess.run(["schtasks", "/query", "/tn", WIN_TASK_NAME, "/fo", "list"],
                                   capture_output=True, text=True)
                if r.returncode == 0:
                    _cprint(f"  [bold bright_yellow]⚠ Legacy masih ada: {WIN_TASK_NAME}[/]")
            except Exception:
                pass
        else:
            _cprint(f"  [bold]Crontab terpasang:[/]")
            try:
                r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                for line in r.stdout.splitlines():
                    if CRON_MARKER in line or "superi_auto" in line:
                        marker = f"[bold green]●[/]" if CRON_MARKER in line else f"[bold bright_yellow]○[/]"
                        print(f"  {marker} {line}")
            except Exception as e:
                _cprint(f"  [bold red]✗ {e}[/]")
        sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')

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
        _cprint(f"  [dim]┌─────────────────────────────────────────────────────┐[/]")
        if enabled:
            _cprint(f"  [dim]│[/]  [bold green]● AKTIF[/]  [dim]— terjadwal otomatis di window jam[/]")
        else:
            _cprint(f"  [dim]│[/]  [bold red]○ NONAKTIF[/]  [dim]— tidak akan jalan walau cron memanggil[/]")
        _cprint(f"  [dim]│[/]  ⏱  Window     : {win_start:02d}:00 - {win_end:02d}:00")
        _cprint(f"  [dim]│[/]  📋 Tipe       : {', '.join(types)}")
        _cprint(f"  [dim]│[/]  🔄 Sync Portal: {'YES' if sync_portal else 'NO'}")
        _cprint(f"  [dim]│[/]  🛡  Retry Guard: {retry_attempts}x, jeda {retry_delay}s")
        _cprint(f"  [dim]└─────────────────────────────────────────────────────┘[/]")
        print()
        
        _cprint(f"  [bold magenta][bold]AKSI[/]")
        if enabled:
            _cprint(f"  [bold bright_yellow][1][/] [bold red]Nonaktifkan[/] Auto Mode")
        else:
            _cprint(f"  [bold bright_yellow][1][/] [bold green]Aktifkan[/] Auto Mode")
        _cprint(f"  [bold bright_yellow][2][/] Atur Window Jam (mulai-akhir)")
        _cprint(f"  [bold bright_yellow][3][/] Pilih Tipe Data")
        _cprint(f"  [bold bright_yellow][4][/] Toggle Sync Portal APD ({'ON' if sync_portal else 'OFF'})")
        _cprint(f"  [bold bright_yellow][5][/] 🧪 Test Sekarang (dry-run jam ini)")
        _cprint(f"  [bold bright_yellow][6][/] 📜 Lihat Log Aktivitas")
        print()
        _cprint(f"  [bold magenta][bold]SETUP TERJADWAL[/]")
        _sched_on = scheduler_is_installed()
        _sched_badge = f"[bold green]TERPASANG[/]" if _sched_on else f"[bold red]BELUM[/]"
        _cprint(f"  [bold bright_yellow][7][/] ⚙  Pasang/Hapus Jadwal Otomatis [{_sched_badge}]")
        _cprint(f"  [bold bright_yellow][8][/] 📖 Panduan manual cron / Task Scheduler")
        print()
        _cprint(f"  [bold red][0][/] Kembali ke menu utama")
        print()
        _cprint(f"  [dim]{'─' * 56}[/]")
        
        choice = sc.prompt_ask('Pilih', default='0') if sc else input('  Pilih ▸ ').strip().lower()
        
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
            status = f"[bold green]AKTIF[/]" if cfg["auto_enabled"] else f"[bold red]NONAKTIF[/]"
            print(f"\n  ✓ Auto Mode sekarang {status}")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '2':
            print()
            _cprint(f"  [dim]Window jam = rentang waktu auto mode aktif[/]")
            _cprint(f"  [dim]Contoh: 22-5 = jalan jam 22:00 sampai 05:00 (lintas hari)[/]")
            _cprint(f"  [dim]Sekarang: {win_start:02d}:00-{win_end:02d}:00 = {len(_expand_window_to_hours(win_start, win_end))} jam aktif[/]")
            _cprint(f"  [dim]Setelah ganti window, jadwal cron/task yang sudah terpasang harus dipasang ulang biar ngikut jam baru[/]")
            try:
                s = int(input(f"  Mulai (jam 0-23) [{win_start}]: ").strip() or win_start)
                e = int(input(f"  Akhir (jam 0-23) [{win_end}]: ").strip() or win_end)
                if 0 <= s <= 23 and 0 <= e <= 23:
                    old_hours = _expand_window_to_hours(win_start, win_end)
                    new_hours = _expand_window_to_hours(s, e)
                    cfg["auto_window_start"] = s
                    cfg["auto_window_end"] = e
                    save_config(cfg)
                    _cprint(f"\n  [bold green]✓ Window: {s:02d}:00 - {e:02d}:00 = {len(new_hours)} jam ({', '.join(f'{h:02d}' for h in new_hours)})[/]")
                    # Jika jadwal sudah terpasang dan window berubah, tawarkan reinstall
                    if scheduler_is_installed() and old_hours != new_hours:
                        _cprint(f"  [bold bright_yellow]Jadwal lama {len(old_hours)} jadwal, baru {len(new_hours)} jadwal. Perlu pasang ulang biar ngikut jam baru.[/]")
                        ans = input(f"  Pasang ulang jadwal sekarang? (Y/n): ").strip().lower()
                        if ans in ("", "y", "yes"):
                            is_win = platform.system() == "Windows"
                            _cprint(f"  [bold bright_yellow]Memasang ulang...[/]")
                            if is_win:
                                ok, msg = win_task_install(s, e)
                            else:
                                ok, msg = cron_install(s, e)
                            if ok:
                                _cprint(f"  [bold green]✓ Jadwal terpasang ulang: {msg}[/]")
                            else:
                                _cprint(f"  [bold red]✗ Gagal pasang ulang: {msg}[/]")
                else:
                    _cprint(f"\n  [bold red]✗ Jam harus 0-23[/]")
            except ValueError:
                _cprint(f"\n  [bold red]✗ Input tidak valid[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '3':
            print()
            _cprint(f"  [dim]Pilih tipe data yang akan di-input otomatis (pisah dengan koma)[/]")
            _cprint(f"  [dim]Contoh: penyulang,trafo,tegangan[/]")
            current = ",".join(types)
            new_types = input(f"  Tipe [{current}]: ").strip() or current
            valid = [t.strip() for t in new_types.split(",") if t.strip() in ["penyulang", "trafo", "tegangan"]]
            if valid:
                cfg["auto_types"] = valid
                save_config(cfg)
                _cprint(f"\n  [bold green]✓ Tipe diset: {', '.join(valid)}[/]")
            else:
                _cprint(f"\n  [bold red]✗ Tidak ada tipe valid[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '4':
            cfg["auto_sync_portal"] = not sync_portal
            save_config(cfg)
            status = f"[bold green]ON[/]" if cfg["auto_sync_portal"] else f"[bold red]OFF[/]"
            print(f"\n  ✓ Sync Portal: {status}")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '5':
            _cprint(f"\n  [bold bright_yellow]🧪 Test dry-run jam {datetime.now().hour:02d}:00...[/]\n")
            try:
                import superi_auto
                superi_auto.run_auto(force_jam=datetime.now().hour, dry_run=True)
            except Exception as e:
                _cprint(f"  [bold red]✗ Error: {e}[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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
                _cprint(f"\n  [dim]File: {log_path}[/]")
            else:
                _cprint(f"\n  [bold bright_yellow]⚠ Belum ada log. Jalankan test dulu (menu 5).[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '7':
            scheduler_install_menu()
        elif choice == '8':
            clear()
            header("📖 PANDUAN SETUP TERJADWAL")
            print()
            _cprint(f"  [bold magenta][bold]🍎 macOS / Linux (cron)[/]\n")
            _cprint(f"  [dim]1. Buka terminal, ketik:[/]")
            _cprint(f"     [bold bright_yellow]crontab -e[/]\n")
            _cprint(f"  [dim]2. Tambahkan baris (jalan tiap jam menit ke-5):[/]")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            _cprint(f"     [bold green]5 * * * * {script_dir}/.venv/bin/python3 {script_dir}/superi_auto.py[/]\n")
            _cprint(f"  [dim]3. Simpan & keluar (Ctrl+O, Enter, Ctrl+X di nano)[/]\n")
            _cprint(f"  [dim]Auto mode internal cek window jam jadi cuma eksekusi di rentang yang diset.[/]\n")
            _cprint(f"  [bold magenta][bold]🪟 Windows (Task Scheduler)[/]\n")
            _cprint(f"  [dim]1. Buka [bold]Task Scheduler[/] [dim](cari di Start Menu)[/]")
            _cprint(f"  [dim]2. Create Basic Task → Daily, repeat every 5 minutes[/]")
            _cprint(f"  [dim]3. Action: Start a program[/]")
            _cprint(f"     [dim]- Program  : [bold bright_yellow]superi.bat[/]")
            _cprint(f"     [dim]- Arguments: [bold bright_yellow]auto[/]")
            _cprint(f"     [dim]- Start in : folder project[/]\n")
            _cprint(f"  [dim]4. Centang \"Wake the computer to run this task\"[/]\n")
            _cprint(f"  [bold bright_yellow][bold]⚠ SYARAT WAJIB:[/]")
            _cprint(f"  [dim]  • Komputer menyala & tidak sleep[/]")
            _cprint(f"  [dim]  • Akun SUPER-I sudah clock-in (absen masuk)[/]")
            _cprint(f"  [dim]  • Terhubung jaringan internal PLN + internet[/]\n")
            _cprint(f"  [dim]Detail lengkap: AUTO_MODE.md di folder project[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        else:
            _cprint(f"\n  [bold red]✗ Pilihan tidak valid[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')

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
            src_badge = f"[bold green]MANUAL[/] (per-item sesuai input)"
            src_desc = "Foto per penyulang/trafo: random dari folder item + hv/mv terpisah + varian blur/kabur/asli"
        else:
            src_badge = f"[bold bright_yellow]POOL[/] (1 foto untuk semua)"
            src_desc = "1 foto generic di photo/pool/ dipakai untuk semua item, re-encode beda SHA tiap upload"

        _cprint(f"  [dim]┌─ Sumber Foto ─────────────────────────────────────┐[/]")
        _cprint(f"  [dim]│[/]  Saat ini : {src_badge}")
        _cprint(f"  [dim]│[/]  [dim]{src_desc}[/]")
        _cprint(f"  [dim]│[/]  Filename : [bold bright_yellow]fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg[/] ([dim]humanizer tetap, bukan basename manual[/])")
        _cprint(f"  [dim]│[/]  OFF      : 7 penyulang CB OFF tetap simpan 84 foto tapi skip input (read-only, tidak dihapus)")
        _cprint(f"  [dim]└─────────────────────────────────────────────────┘[/]")
        print()
        _cprint(f"  [dim]┌─ Statistik Pool ──────────────────────────────────┐[/]")
        _cprint(f"  [dim]│[/]  Pool generic    : [bold green]{pool_cnt}[/] file di [dim]photo/pool/[/]")
        _cprint(f"  [dim]│[/]  Manual penyulang: [bold green]{manual_bp.get('folders',0)}[/] folder / [bold green]{manual_bp.get('files',0)}[/] foto (25 ON + 7 OFF tetap)")
        _cprint(f"  [dim]│[/]  Manual beban    : [bold green]{manual_bt.get('folders',0)}[/] folder / [bold green]{manual_bt.get('files',0)}[/] foto (TRAFO_1/2/3)")
        _cprint(f"  [dim]│[/]  Manual tegangan : [bold green]{manual_tt.get('folders',0)}[/] trafo / HV [bold green]{manual_tt.get('hv',0)}[/] + MV [bold green]{manual_tt.get('mv',0)}[/] = [bold green]{manual_tt.get('total',0)}[/] foto")
        _cprint(f"  [dim]│[/]  Total manual    : [bold green]{total_manual}[/] foto")
        _cprint(f"  [dim]│[/]  History         : [bold green]{hist_days}[/] hari")
        _cprint(f"  [dim]└─────────────────────────────────────────────────┘[/]")
        print()
        _cprint(f"  [bold magenta][bold]AKSI[/]")
        _cprint(f"  [bold bright_yellow][1][/] Ganti Sumber Foto (pool ↔ manual)")
        _cprint(f"  [bold bright_yellow][2][/] Ganti History Days (3/7/14)")
        _cprint(f"  [bold bright_yellow][3][/] Lihat Detail Pool per Item")
        _cprint(f"  [bold bright_yellow][4][/] Validasi Foto Manual (scan 500+ file)")
        print()
        _cprint(f"  [bold magenta][bold]INFO[/]")
        _cprint(f"  [bold bright_yellow][5][/] Panduan: Cara foto manual anti-robotik")
        _cprint(f"  [bold bright_yellow][6][/] Test Foto Random (lihat varian blur/kabur/asli)")
        print()
        _cprint(f"  [bold red][0][/] Kembali ke menu utama")
        print()
        _cprint(f"  [dim]{'─' * 56}[/]")

        choice = sc.prompt_ask('Pilih', default='0') if sc else input('  Pilih ▸ ').strip().lower()

        if choice == '0':
            return
        elif choice == '1':
            print()
            _cprint(f"  [bold]Pilih sumber foto:[/]")
            _cprint(f"  [bold bright_yellow]pool[/]   = 1 foto generic di photo/pool/ untuk semua input (fallback cepat)")
            _cprint(f"  [bold bright_yellow]manual[/] = per-item sesuai input (random dari folder item + hv/mv terpisah + varian asli/blur/noisy)")
            _cprint(f"  [dim]Filename upload tetap humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg (bukan basename manual)[/]")
            _cprint(f"  [dim]Foto tidak dihapus setelah dipakai (read-only random choice)[/]")
            _cprint(f"  [dim]OFF tetap simpan tapi skip input saat CB OFF[/]")
            print(f"  Saat ini: {photo_src}")
            new_src = input(f"  Sumber baru (pool/manual) [batal]: ").strip().lower()
            if new_src in ("pool", "manual"):
                if set_photo_source(new_src):
                    _cprint(f"\n  [bold green]✓ Foto source diubah ke {new_src.upper()}[/]")
                    if new_src == "manual":
                        _cprint(f"  [dim]  → Per-item: random dari photo/manual/{{tipe}}/{{ITEM}}/ + hv/mv terpisah[/]")
                        _cprint(f"  [dim]  → Varian: asli 45%, blur_ringan 25%, blur_berat 15%, noisy_gelap 15%[/]")
                        _cprint(f"  [dim]  → OFF 7 penyulang tetap ada tapi skip input CB OFF[/]")
                    else:
                        _cprint(f"  [dim]  → 1 foto generic di photo/pool/ untuk semua input[/]")
                        _cprint(f"  [dim]  → Re-encode 720x720 crop ±5% + pixel jitter + quality 82-93 beda SHA tiap upload[/]")
                else:
                    _cprint(f"  [bold red]✗ Gagal ubah source[/]")
            else:
                _cprint(f"  [bold bright_yellow]⊘ Dibatalkan[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '2':
            print()
            _cprint(f"  [dim]History days = berapa hari ke belakang untuk smart suggest{R['C']}")
            print(f"  Valid: 3, 7, 14 (default 7)")
            print(f"  Saat ini: {hist_days}")
            new_hist = input(f"  History baru (3/7/14) [batal]: ").strip()
            if new_hist in ("3", "7", "14"):
                cfg["history_days"] = int(new_hist)
                save_config(cfg)
                _cprint(f"  [bold green]✓ History days diubah ke {new_hist}[/]")
            else:
                if new_hist:
                    _cprint(f"  [bold red]✗ Invalid, harus 3/7/14[/]")
                else:
                    _cprint(f"  [bold bright_yellow]⊘ Dibatalkan[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '3':
            # Detail pool per item
            clear()
            header("📁 DETAIL POOL PER ITEM")
            try:
                base_manual = os.path.join(SCRIPT_DIR, "photo", "manual")
                if not os.path.isdir(base_manual):
                    _cprint(f"  [bold red]Folder photo/manual/ tidak ada[/]")
                else:
                    # beban-penyulang
                    _cprint(f"\n  [bold magenta][bold]BEBAN PENYULANG (32 = 25 ON + 7 OFF)[/]")
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
                            badge = f"[bold bright_yellow]OFF[/]" if is_off else f"[bold green]ON[/]"
                            print(f"    {folder:<22} : {cnt:>3} foto [{badge}] {'(skip CB OFF, tetap simpan)' if is_off else ''}")
                    # beban-trafo
                    _cprint(f"\n  [bold magenta][bold]BEBAN TRAFO (3)[/]")
                    bt_path = os.path.join(base_manual, "beban-trafo")
                    if os.path.isdir(bt_path):
                        for folder in sorted(os.listdir(bt_path)):
                            full = os.path.join(bt_path, folder)
                            if not os.path.isdir(full):
                                continue
                            cnt = len([f for f in os.listdir(full) if f.lower().endswith(('.jpg','.jpeg','.png'))]) if os.path.isdir(full) else 0
                            print(f"    {folder:<22} : {cnt:>3} foto")

                    # tegangan
                    _cprint(f"\n  [bold magenta][bold]TEGANGAN TRAFO (5 trafo × hv/mv terpisah)[/]")
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

                    _cprint(f"\n  [dim]Total manual: {total_manual} foto, pool generic: {pool_cnt} file[/]")
                    _cprint(f"  [dim]Foto tidak dihapus setelah dipakai (read-only random)[/]")
            except Exception as e:
                _cprint(f"  [bold red]Error: {e}[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '4':
            # Validasi foto manual
            print()
            _cprint(f"  [bold bright_yellow]Menjalankan validasi foto manual (scan 500+ file)...[/]")
            try:
                import subprocess
                import sys
                script = os.path.join(SCRIPT_DIR, "tools", "validate_manual_pool.py")
                if os.path.isfile(script):
                    result = subprocess.run([sys.executable, script], cwd=SCRIPT_DIR)
                else:
                    _cprint(f"  [bold red]tools/validate_manual_pool.py belum ada, jalankan manual:[/]")
                    _cprint(f"  [dim]python3 -c \"import superi_humanizer as hu; print(hu.get_pool_stats())\"[/]")
                    # fallback simple stats
                    if hu and hasattr(hu, "get_pool_stats"):
                        print(f"  {hu.get_pool_stats()}")
            except Exception as e:
                _cprint(f"  [bold red]Validasi error: {e}[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '5':
            clear()
            header("📖 PANDUAN FOTO MANUAL ANTI-ROBOTIK")
            print(f"""
  [bold]Kenapa per-item?[/]
  - Kalau pakai 1 foto untuk semua (pool mode), visual sama semua → mudah terdeteksi robotik
  - Per-item manual: CASABLANCA4 beda dengan LABORATORIUM, sesuai panel fisik asli

  [bold]Foto diambil bagaimana?[/]
  - Per penyulang 2-3 foto: close-up (30-50cm), wide (1m), 45° sudut
  - Per beban trafo 2 foto: full panel + close meter
  - Per tegangan trafo: HV dan MV pisah folder (hv/ & mv/), tiap sisi 2 foto
  - HP mode biasa, jangan portrait blur bawaan, size >100KB ideal
  - Taruh di: photo/manual/{{tipe}}/{{NAMA}}/ (auto random per input)

  [bold]Varian blur/asli/noisy?[/]
  - Saat input CLI, dari folder item tersebut di-random 1 foto
  - Lalu di-apply varian random: asli 45%, blur ringan 25%, blur berat 15%,
    noisy gelap 15% (cocok jam 00-06)
  - Crop center square 720x720 jitter ±5% + pixel jitter 2-6 titik
  - Re-encode baseline JPEG quality 82-93, exif=b'', progressive=False
  - Size 20-60KB (match audit server 14-51KB avg 27KB)
  - Filename upload TETAP humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg
    (bukan basename manual seperti WhatsApp Image...)

  [bold]OFF handling:[/]
  - 7 penyulang CB OFF (FISIOTERAPI, RONTGEN, REFLEXY, HERBAL, PINSET, KOPEL_*)
    foto tetap simpan 84 file, tapi skip input saat CB OFF (read-only)

  [bold]Foto dihapus setelah dipakai?[/]
  - TIDAK. File asli tetap di disk, hanya dibaca random tiap input
  - Bisa dipakai lagi periode berikutnya, SHA beda karena varian+crop

  [bold]Pool vs Manual:[/]
  - pool  : 1 foto di photo/pool/ untuk semua (fallback cepat, untuk demo)
           re-encode beda SHA tiap upload tapi visual sama
  - manual: per-item sesuai (random dari folder item + hv/mv terpisah)
           visual beda per penyulang, lebih natural, rekomendasi utama

  [bold]Setting:[/]
  - CLI: [T] Settings → [1] Ganti Sumber Foto (pool/manual)
  - Config: .superi_config.json key photo_source
  - Default: pool (backward compat)
""")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        elif choice == '6':
            # Test foto random
            clear()
            header("🧪 TEST FOTO RANDOM + VARIAN")
            try:
                if not hu:
                    _cprint(f"  [bold red]Humanizer tidak tersedia (PIL mungkin belum install)[/]")
                    sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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
                    _cprint(f"  [bold]{item_name}[/] ({data_type}) - pool: {cnt} foto")
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
                _cprint(f"\n  [bold]Tegangan TRAFO 1 HV/MV terpisah:[/]")
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

                _cprint(f"\n  [dim]Filename upload tetap humanizer (bukan basename manual):[/]")
                if hasattr(hu, "rand_filename"):
                    from datetime import timezone, timedelta
                    import datetime as _dt
                    sample_dt = _dt.datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%dT%H:%M:%S.123Z")
                    for dtype in ["beban-penyulang","beban-trafo","tegangan-trafo"]:
                        fn = hu.rand_filename(sample_dt, idx=0, data_type=dtype, subtype="HV" if "tegangan" in dtype else None)
                        print(f"    {dtype}: {fn}")

                _cprint(f"\n  [bold green]Test selesai. Foto tidak dihapus, tetap di disk (read-only random).[/]")
            except Exception as e:
                _cprint(f"  [bold red]Error test: {e}[/]")
                import traceback
                traceback.print_exc()
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
        else:
            _cprint(f"\n  [bold red]✗ Pilihan tidak valid[/]")
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')


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

    # Fullscreen Textual is the default only for the interactive CLI. Classic
    # Rich output remains available for non-TTY sessions and `--classic`.
    try:
        from superi_tui import can_run_fullscreen, run_tui
        if can_run_fullscreen():
            run_tui()
            return
    except ImportError:
        pass

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

        # Menu 2 kolom: LIHAT + INPUT - Rich yellow theme
        _photo_src = get_photo_source()
        _auto_cfg = load_config()
        _auto_on = _auto_cfg.get("auto_enabled", False)

        if sc and getattr(sc, 'console', None):
            try:
                sc.console.print("  [bold magenta]LIHAT DATA[/]                    [bold magenta]INPUT MANUAL[/]")
                sc.console.print("  [bold bright_yellow][1][/] Beban Penyulang        [bold bright_yellow][4][/] Beban Penyulang")
                sc.console.print("  [bold bright_yellow][2][/] Beban Trafo            [bold bright_yellow][5][/] Beban Trafo")
                sc.console.print("  [bold bright_yellow][3][/] Tegangan Trafo         [bold bright_yellow][6][/] Tegangan Trafo")
                sc.console.print()
                sc.console.print("  [bold bright_yellow]BATCH per ITEM[/]             [bold bright_yellow]BATCH per JAM[/] [green](+ Sync Portal)[/]")
                sc.console.print("  [bold bright_yellow][7][/] Beban Penyulang        [bold bright_yellow][A][/] Beban Penyulang")
                sc.console.print("  [bold bright_yellow][8][/] Beban Trafo            [bold bright_yellow][B][/] Beban Trafo")
                sc.console.print("  [bold bright_yellow][9][/] Tegangan Trafo         [bold bright_yellow][C][/] Tegangan Trafo")
                sc.console.print()
                sc.console.print("  [bold dim]PENGATURAN[/]")
                photo_badge = f"[bold green]{_photo_src.upper()}[/]" if _photo_src=="manual" else f"[bold yellow]{_photo_src.upper()}[/]"
                sc.console.print(f"  [bold bright_yellow][G][/] Ganti Tanggal   [bold bright_yellow][L][/] Login Ulang   [bold bright_yellow][O][/] Logout   [bold bright_yellow][S][/] Setup   [bold red][0][/] Keluar")
                sc.console.print(f"  [bold bright_yellow][T][/] Foto Source [{photo_badge}]  [dim]({ 'per-item sesuai' if _photo_src=='manual' else '1 foto semua' }, varian blur/kabur/asli)[/]")
                sc.console.print()
                auto_badge = "[bold green]ON[/]" if _auto_on else "[bold red]OFF[/]"
                sc.console.print(f"  [bold bright_yellow][P][/] Sync ke Portal APD    [bold bright_yellow][D][/] Auto Mode [{auto_badge}]")
                sc.console.print()
                sc.console.print(f"  [dim]{'─' * 56}[/]")
                choice = sc.prompt_ask("Pilih", default="0").lower()
            except Exception:
                _cprint(f"  [bold magenta][bold]LIHAT DATA[/]                    [bold magenta][bold]INPUT MANUAL[/]")
                _cprint(f"  [bold bright_yellow][1][/] Beban Penyulang        [bold bright_yellow][4][/] Beban Penyulang")
                _cprint(f"  [bold bright_yellow][2][/] Beban Trafo            [bold bright_yellow][5][/] Beban Trafo")
                _cprint(f"  [bold bright_yellow][3][/] Tegangan Trafo         [bold bright_yellow][6][/] Tegangan Trafo")
                print()
                _cprint(f"  [bold bright_yellow][bold]BATCH per ITEM[/]             [bold bright_yellow][bold]BATCH per JAM[/] [bold green](+ Sync Portal)[/]")
                _cprint(f"  [bold bright_yellow][7][/] Beban Penyulang        [bold bright_yellow][A][/] Beban Penyulang")
                _cprint(f"  [bold bright_yellow][8][/] Beban Trafo            [bold bright_yellow][B][/] Beban Trafo")
                _cprint(f"  [bold bright_yellow][9][/] Tegangan Trafo         [bold bright_yellow][C][/] Tegangan Trafo")
                print()
                _photo_badge = f"[bold green]{_photo_src.upper()}[/]" if _photo_src=="manual" else f"[bold bright_yellow]{_photo_src.upper()}[/]"
                _cprint(f"  [dim][bold]PENGATURAN[/]")
                _cprint(f"  [bold bright_yellow][G][/] Ganti Tanggal   [bold bright_yellow][L][/] Login Ulang   [bold bright_yellow][O][/] Logout   [bold bright_yellow][S][/] Setup   [bold red][0][/] Keluar")
                _cprint(f"  [bold bright_yellow][T][/] Foto Source [{_photo_badge}]  [dim]({ 'per-item sesuai' if _photo_src=='manual' else '1 foto semua' }, varian blur/kabur/asli)[/]")
                print()
                _auto_badge = f"[bold green]ON[/]" if _auto_on else f"[bold red]OFF[/]"
                _cprint(f"  [bold bright_yellow][P][/] Sync ke Portal APD    [bold bright_yellow][D][/] Auto Mode [{_auto_badge}]")
                print()
                _cprint(f"  [dim]{'─' * 56}[/]")
                choice = sc.prompt_ask('Pilih', default='0') if sc else input('  Pilih ▸ ').strip().lower()
        else:
            _cprint(f"  [bold magenta][bold]LIHAT DATA[/]                    [bold magenta][bold]INPUT MANUAL[/]")
            _cprint(f"  [bold bright_yellow][1][/] Beban Penyulang        [bold bright_yellow][4][/] Beban Penyulang")
            _cprint(f"  [bold bright_yellow][2][/] Beban Trafo            [bold bright_yellow][5][/] Beban Trafo")
            _cprint(f"  [bold bright_yellow][3][/] Tegangan Trafo         [bold bright_yellow][6][/] Tegangan Trafo")
            print()
            _cprint(f"  [bold bright_yellow][bold]BATCH per ITEM[/]             [bold bright_yellow][bold]BATCH per JAM[/] [bold green](+ Sync Portal)[/]")
            _cprint(f"  [bold bright_yellow][7][/] Beban Penyulang        [bold bright_yellow][A][/] Beban Penyulang")
            _cprint(f"  [bold bright_yellow][8][/] Beban Trafo            [bold bright_yellow][B][/] Beban Trafo")
            _cprint(f"  [bold bright_yellow][9][/] Tegangan Trafo         [bold bright_yellow][C][/] Tegangan Trafo")
            print()
            _photo_badge = f"[bold green]{_photo_src.upper()}[/]" if _photo_src=="manual" else f"[bold bright_yellow]{_photo_src.upper()}[/]"
            _cprint(f"  [dim][bold]PENGATURAN[/]")
            _cprint(f"  [bold bright_yellow][G][/] Ganti Tanggal   [bold bright_yellow][L][/] Login Ulang   [bold bright_yellow][O][/] Logout   [bold bright_yellow][S][/] Setup   [bold red][0][/] Keluar")
            _cprint(f"  [bold bright_yellow][T][/] Foto Source [{_photo_badge}]  [dim]({ 'per-item sesuai' if _photo_src=='manual' else '1 foto semua' }, varian blur/kabur/asli)[/]")
            print()
            _auto_badge = f"[bold green]ON[/]" if _auto_on else f"[bold red]OFF[/]"
            _cprint(f"  [bold bright_yellow][P][/] Sync ke Portal APD    [bold bright_yellow][D][/] Auto Mode [{_auto_badge}]")
            print()
            _cprint(f"  [dim]{'─' * 56}[/]")
            choice = sc.prompt_ask('Pilih', default='0') if sc else input('  Pilih ▸ ').strip().lower()

        if choice == '0':
            _cprint(f"\n  [bold green]✓ Selamat bekerja![/]\n")
            break
        
        # Login if needed
        if choice in '123456789abc' and not token:
            print("\n  Login...")
            token, user, gi_id = do_login(config)
            if not token:
                sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
                continue
        
        try:
            if choice == 'g':
                date_str = input("  Tanggal (YYYY-MM-DD): ").strip() or date_str
            elif choice == 'l':
                token, user, gi_id = do_login(config)
                sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')
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
            sc.pause() if sc and hasattr(sc, 'pause') else input('  [Enter]')

if __name__ == "__main__":
    main()
