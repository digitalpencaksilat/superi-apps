#!/usr/bin/env python3
"""
SUPER-I APP - Web Dashboard
============================
Flask web app untuk monitoring dan input data SUPER-I APP.
Akses: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import urllib.request
import urllib.error
import json
import os
import sys
from datetime import datetime
from functools import wraps
import base64

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import superi_app as _cli

try:
    import superi_humanizer as hu
except Exception:
    hu = None


def _h_durasi(data_type="beban-penyulang"):
    if hu:
        return hu.rand_durasi_for_type(data_type)
    import random as _r
    if "tegangan" in data_type:
        return round(_r.uniform(8.0, 35.0) / 60.0, 8)
    return round(_r.uniform(2.0, 7.0) / 60.0, 8)


def _h_foto_date(date_str, periode, durasi_min=None, data_type="beban-penyulang"):
    if hu:
        return hu.rand_foto_datetime(date_str, periode, durasi_min)
    return f"{date_str}T{periode:02d}:00:00.000Z"


def _h_foto_pair(date_str, periode, durasi_min=None):
    if hu:
        return hu.rand_foto_pair(date_str, periode, durasi_min)
    ts = f"{date_str}T{periode:02d}:00:00.000Z"
    return ts, ts


def _h_foto_dict(date_str, periode, durasi_min=None, data_type="beban-penyulang"):
    if hu:
        return hu.rand_foto_dict(data_type=data_type, date_str=date_str, periode=periode, durasi_min=durasi_min)
    import random as _r
    base_addr = "Jl. Swadaya 1 No.36, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia"
    return {"date": _h_foto_date(date_str, periode, durasi_min, data_type), "address": base_addr, "latitude": -6.213095 + _r.uniform(-0.00008, 0.00008), "longitude": 106.846073 + _r.uniform(-0.00008, 0.00008)}


def _h_foto_pair_dicts(date_str, periode, durasi_min=None):
    if hu:
        return hu.rand_foto_pair_dicts(date_str, periode, durasi_min)
    ts1, ts2 = _h_foto_pair(date_str, periode, durasi_min)
    base = "Jl. Swadaya 1 No.36, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia"
    return (
        {"date": ts1, "address": base, "latitude": -6.213095, "longitude": 106.846073},
        {"date": ts2, "address": base, "latitude": -6.213098, "longitude": 106.846075},
    )


def _h_boundary():
    return hu.rand_boundary() if hu else BOUNDARY


def _h_filename(foto_ts, idx=0, data_type="beban-penyulang", subtype=None):
    if hu:
        return hu.rand_filename(foto_ts, idx=idx, data_type=data_type, subtype=subtype)
    import uuid as _uuid
    date_part = (foto_ts or "")[:10] or "2026-07-15"
    hex16 = _uuid.uuid4().hex[:16]
    if "tegangan" in data_type:
        pref = f"foto{subtype or ('MV' if idx==1 else 'HV')}"
        return f"{pref}_{date_part}_{hex16[:12]}.jpg"
    elif "beban-trafo" in data_type:
        return f"fotoBebanTrafo_{date_part}_{hex16}.jpg"
    return f"fotoBebanPenyulang_{date_part}_{hex16}.jpg"


def _h_user_agent():
    return hu.rand_user_agent() if hu else "okhttp/4.12.0"


app = Flask(__name__)

def _get_flask_secret():
    """Persist secret_key agar session tidak hilang tiap restart.
    Prioritas: env FLASK_SECRET_KEY > file .flask_secret > generate + simpan.
    """
    # 1. Env var
    env_key = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if env_key:
        return env_key.encode() if len(env_key) < 64 else env_key

    # 2. File .flask_secret
    secret_file = os.path.join(SCRIPT_DIR, ".flask_secret")
    if os.path.exists(secret_file):
        try:
            with open(secret_file, "r") as f:
                val = f.read().strip()
            if val:
                return val.encode() if len(val) < 256 else bytes.fromhex(val) if all(c in "0123456789abcdefABCDEF" for c in val) else val.encode()
        except Exception:
            pass

    # 3. Generate baru + simpan
    new_secret = os.urandom(32)
    try:
        with open(secret_file, "w") as f:
            f.write(new_secret.hex())
        try:
            os.chmod(secret_file, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return new_secret

app.secret_key = _get_flask_secret()

BASE_URL = "https://super-i-app.plnes.co.id"
API_BASE = f"{BASE_URL}/api"
BOUNDARY = "----FormBoundary7MA4YWxkTrZu0gW"

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

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def login(nip, password):
    """Login ke SUPER-I APP. Return (token, user) atau (None, None, error_msg)"""
    try:
        req = urllib.request.Request(
            f"{API_BASE}/auth/login-mobile",
            data=json.dumps({"nip": nip, "password": password}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("success"):
            return data["data"]["access_token"], data["data"]["user"]
        # Server responded tapi success=False (misal pesan validation)
        msg = data.get("message", "Login gagal")
        print(f"Login failed: {msg}")
        return None, None
    except urllib.error.HTTPError as e:
        # 401 = NIP/password salah - kasih pesan yang jelas
        try:
            body = e.read().decode()
            err_data = json.loads(body)
            server_msg = err_data.get("message", "")
            if e.code == 401:
                print(f"Login 401 Unauthorized: {server_msg or 'NIP atau password salah'}")
            else:
                print(f"Login HTTP {e.code}: {server_msg}")
        except Exception:
            if e.code == 401:
                print(f"Login 401 Unauthorized: NIP atau password salah")
            else:
                print(f"Login HTTP {e.code}: {e.reason}")
        return None, None
    except Exception as e:
        print(f"Login error: {e}")
        return None, None

def api_get(token, path, params=None):
    """GET request ke SUPER-I API."""
    try:
        url = f"{API_BASE}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def _teg_mv_decimals(name: str) -> int:
    """Aturan pembulatan MV tegangan per trafo (parity dengan superi_app.py).

    - TRAFO PS 1 / TRAFO PS 2 → 0 desimal (bulat: 385, 390)
    - TRAFO 1                → 1 desimal (20.3, 20.4)
    - TRAFO 2 / 3 / lainnya  → 2 desimal (20.43)
    """
    n = (name or "").upper()
    if "PS" in n:
        return 0
    if n == "TRAFO 1":
        return 1
    return 2


def _round_mv(name: str, mv_avg: float):
    """Bulatkan MV sesuai aturan trafo. Return int kalau 0 desimal, float kalau lain."""
    decimals = _teg_mv_decimals(name)
    rounded = round(mv_avg, decimals)
    if decimals == 0:
        return int(rounded)
    return rounded


def learn_pattern(token, gi_id, data_type, item_id, days_back=None):
    """
    Belajar pola beban/tegangan per periode dari data historis (N hari, default dari config).
    PARITY dengan CLI superior_app.py smart_suggest_from_cache / smart_suggest_tegangan_from_cache.

    Perbedaan dari versi lama:
    - N hari (default config history_days, fallback 7; boleh 3/7/14)
    - Weekday/weekend aware (50% pattern + 50% base)
    - Round kelipatan 5 untuk beban, aturan trafo untuk tegangan MV
    - Clamp ke range histori pattern
    - Fallback: kalau periode target kosong, pakai rata-rata semua periode

    Return dict: {periode: {avg, min, max, samples, ...}}
    """
    if days_back is None:
        days_back = _cli.get_history_days()
    from collections import defaultdict
    from datetime import datetime, timedelta
    from concurrent.futures import ThreadPoolExecutor

    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    path = paths[data_type]

    today = datetime.now()
    is_target_weekend = today.weekday() >= 5

    # Build cache per-periode: {periode: {all: [], weekday: [], weekend: []}}
    pattern = defaultdict(lambda: {
        "all": [], "weekday": [], "weekend": [],
        "mv_all": [], "mv_weekday": [], "mv_weekend": [],
        "hv_all": [], "hv_weekday": [], "hv_weekend": [],
    })
    item_name = ""

    def fetch_day(offset):
        d = today - timedelta(days=offset)
        return d.weekday() >= 5, api_get(token, path, {"garduIndukId": gi_id, "date": d.strftime("%Y-%m-%d")})

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_day, range(1, days_back + 1)))

    for is_weekend, result in results:
        items = result.get("data", {}).get("items", [])
        for it in items:
            if it["id"] != item_id:
                continue
            if not item_name:
                item_name = it.get("nama", "")
            if data_type == "tegangan-trafo":
                for e in it.get("tegangan", []):
                    p = e["periode"]
                    pattern[p]["mv_all"].append(e["mv"])
                    pattern[p]["hv_all"].append(e["hv"])
                    if is_weekend:
                        pattern[p]["mv_weekend"].append(e["mv"])
                        pattern[p]["hv_weekend"].append(e["hv"])
                    else:
                        pattern[p]["mv_weekday"].append(e["mv"])
                        pattern[p]["hv_weekday"].append(e["hv"])
            else:
                if it.get("statusCB") == "OFF":
                    continue
                for e in it.get("beban", []):
                    p = e["periode"]
                    val = e["beban"]
                    pattern[p]["all"].append(val)
                    if is_weekend:
                        pattern[p]["weekend"].append(val)
                    else:
                        pattern[p]["weekday"].append(val)

    # Hitung smart suggest per periode
    result = {}
    for periode, data in pattern.items():
        if data_type == "tegangan-trafo":
            all_mv = data["mv_all"]
            all_hv = data["hv_all"]
            if not all_mv:
                continue
            if is_target_weekend:
                pat_mv = data["mv_weekend"] if data["mv_weekend"] else all_mv
                pat_hv = data["hv_weekend"] if data["hv_weekend"] else all_hv
            else:
                pat_mv = data["mv_weekday"] if data["mv_weekday"] else all_mv
                pat_hv = data["hv_weekday"] if data["hv_weekday"] else all_hv

            # MV: 50% pattern + 50% base
            base_mv = sum(all_mv) / len(all_mv)
            pattern_mv = sum(pat_mv) / len(pat_mv)
            smart_mv = 0.5 * pattern_mv + 0.5 * base_mv
            smart_mv = _round_mv(item_name, smart_mv)
            # Clamp ke range pattern
            if pat_mv:
                smart_mv = max(min(pat_mv), min(max(pat_mv), smart_mv))
                smart_mv = _round_mv(item_name, smart_mv)

            # HV: PS → 2 desimal, lainnya integer
            if "PS" in (item_name or "").upper():
                base_hv = sum(all_hv) / len(all_hv)
                pattern_hv = sum(pat_hv) / len(pat_hv)
                smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
                smart_hv = round(smart_hv, 2)
                if pat_hv:
                    smart_hv = max(min(pat_hv), min(max(pat_hv), smart_hv))
                    smart_hv = round(smart_hv, 2)
            else:
                base_hv = sum(all_hv) / len(all_hv)
                pattern_hv = sum(pat_hv) / len(pat_hv)
                smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
                smart_hv = round(smart_hv)
                if pat_hv:
                    smart_hv = max(min(pat_hv), min(max(pat_hv), smart_hv))
                smart_hv = int(smart_hv)

            result[periode] = {
                "mv_avg": smart_mv,
                "mv_min": min(all_mv), "mv_max": max(all_mv),
                "hv_avg": smart_hv,
                "hv_min": min(all_hv), "hv_max": max(all_hv),
                "samples": len(all_mv),
                "pattern_type": "weekend" if is_target_weekend else "weekday",
            }
        else:
            all_vals = data["all"]
            if not all_vals:
                continue
            if is_target_weekend:
                pat_vals = data["weekend"] if data["weekend"] else all_vals
            else:
                pat_vals = data["weekday"] if data["weekday"] else all_vals

            base_avg = sum(all_vals) / len(all_vals)
            pattern_avg = sum(pat_vals) / len(pat_vals)
            smart_avg = 0.5 * pattern_avg + 0.5 * base_avg
            suggested = round(smart_avg / 5) * 5
            if pat_vals:
                suggested = max(min(pat_vals), min(max(pat_vals), suggested))

            result[periode] = {
                "avg": int(suggested),
                "raw_avg": round(smart_avg, 1),
                "min": min(all_vals), "max": max(all_vals),
                "samples": len(all_vals),
                "pattern_type": "weekend" if is_target_weekend else "weekday",
                "pattern_avg": round(pattern_avg, 1),
                "pattern_samples": len(pat_vals),
            }

    # Fallback: kalau ada periode yang kosong (tidak ada histori), isi dengan rata-rata semua periode
    if not result:
        # Coba kumpulkan semua nilai dari semua periode
        if data_type == "tegangan-trafo":
            all_mvs = []
            all_hvs = []
            for pdata in pattern.values():
                all_mvs.extend(pdata["mv_all"])
                all_hvs.extend(pdata["hv_all"])
            if all_mvs:
                mv_fb = _round_mv(item_name, sum(all_mvs) / len(all_mvs))
                mv_fb = max(min(all_mvs), min(max(all_mvs), mv_fb))
                mv_fb = _round_mv(item_name, mv_fb)
                if "PS" in (item_name or "").upper():
                    hv_fb = round(sum(all_hvs) / len(all_hvs), 2)
                else:
                    hv_fb = int(round(sum(all_hvs) / len(all_hvs)))
                result[-1] = {
                    "mv_avg": mv_fb, "hv_avg": hv_fb,
                    "samples": len(all_mvs), "fallback": True,
                    "note": "Fallback: rata-rata semua periode (periode target kosong)",
                }
        else:
            all_vals = []
            for pdata in pattern.values():
                all_vals.extend(pdata["all"])
            if all_vals:
                val_fb = round((sum(all_vals) / len(all_vals)) / 5) * 5
                val_fb = int(max(min(all_vals), min(max(all_vals), val_fb)))
                result[-1] = {
                    "avg": val_fb,
                    "raw_avg": round(sum(all_vals) / len(all_vals), 1),
                    "min": min(all_vals), "max": max(all_vals),
                    "samples": len(all_vals), "fallback": True,
                    "note": "Fallback: rata-rata semua periode (periode target kosong)",
                }

    return result

def _infer_data_type_from_path_web(path: str) -> str:
    if "tegangan" in path:
        return "tegangan-trafo"
    if "beban-trafo" in path:
        return "beban-trafo"
    return "beban-penyulang"


def api_post_multipart(
    token, path, data_dict, file_bytes, file_field, num_photos, item_name=None
):
    """Gunakan uploader inti agar format dan verifikasi foto konsisten di CLI/Web/Auto."""
    return _cli.api_post_multipart(
        token,
        path,
        data_dict,
        file_bytes,
        file_field,
        num_photos,
        item_name=item_name,
    )

def api_delete(token, path):
    """DELETE request."""
    try:
        url = f"{API_BASE}{path}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="DELETE")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def login_required(f):
    """Decorator untuk require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "token" not in session or "user" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def index():
    """Redirect ke dashboard."""
    if "token" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Halaman login. Error 401 kasih pesan jelas."""
    if request.method == "POST":
        nip = request.form.get("nip", "").strip()
        password = request.form.get("password", "").strip()
        
        if not nip or not password:
            return render_template("login.html", error="NIP dan password tidak boleh kosong")
        
        token, user = login(nip, password)
        if token and user:
            session["token"] = token
            session["user"] = user
            # NOTE: password & nip sengaja TIDAK disimpan di session lagi (security fix)
            return redirect(url_for("dashboard"))
        
        return render_template("login.html", 
            error="Login gagal (401 Unauthorized): NIP atau password salah. "
                  "Pastikan NIP tanpa spasi, password sesuai akun PLN, "
                  "dan akun masih aktif & sudah clock-in.",
            error_detail=f"NIP: {nip}")
    
    return render_template("login.html")


def _disable_auto_on_logout():
    """Helper: auto-disable cron & auto mode saat logout (3-lapis safety).
    Lapis 1: set auto_enabled=False di config file.
    Lapis 2: nip/password sudah tidak ada di session, tapi config creds dipertahankan
              untuk login ulang mudah (hanya flag yang dimatikan di web logout).
              Untuk CLI logout nanti ada wipe terpisah.
    Lapis 3: uninstall cron / task scheduler (best-effort).
    """
    try:
        cfg = _load_config()
        # Lapis 1: matikan flag
        if cfg.get("auto_enabled"):
            cfg["auto_enabled"] = False
            _save_config(cfg)
    except Exception:
        pass

    # Lapis 3: scheduler uninstall (best-effort, jangan bikin logout gagal)
    try:
        if hasattr(_cli, "scheduler_is_installed") and _cli.scheduler_is_installed():
            if hasattr(_cli, "cron_uninstall"):
                _cli.cron_uninstall()
            if hasattr(_cli, "win_task_uninstall"):
                try:
                    _cli.win_task_uninstall()
                except Exception:
                    pass
    except Exception:
        pass


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Logout: auto-disable cron/auto + clear session.
    Support GET (backward compat) + POST (lebih aman).
    """
    _disable_auto_on_logout()
    session.clear()
    return redirect(url_for("login_page", logged_out=1))


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """API logout untuk AJAX/SPA call (return JSON)."""
    _disable_auto_on_logout()
    session.clear()
    return jsonify({"success": True, "message": "Logout berhasil. Auto mode & cron dinonaktifkan."})

@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard utama."""
    token = session["token"]
    user = session["user"]
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    # Fetch data beban penyulang
    penyulang_data = api_get(token, "/gama/opgi-20kv/operator-gi/beban-penyulang", 
        {"garduIndukId": _get_gi_id(), "date": date_str})
    
    trafo_data = api_get(token, "/gama/opgi-20kv/operator-gi/beban-trafo",
        {"garduIndukId": _get_gi_id(), "date": date_str})
    
    tegangan_data = api_get(token, "/gama/opgi-20kv/operator-gi/tegangan-trafo",
        {"garduIndukId": _get_gi_id(), "date": date_str})
    
    return render_template("dashboard.html", 
        user=user,
        date_str=date_str,
        penyulang_data=penyulang_data.get("data", {}).get("items", []),
        trafo_data=trafo_data.get("data", {}).get("items", []),
        tegangan_data=tegangan_data.get("data", {}).get("items", []))

@app.route("/api/data/input", methods=["POST"])
@login_required
def api_input():
    """API untuk input data."""
    token = session["token"]
    data = request.get_json()
    
    data_type = data.get("type")  # beban-penyulang, beban-trafo, tegangan-trafo
    item_id = data.get("item_id")
    periode = data.get("periode")
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    if data_type == "tegangan-trafo":
        mv = data.get("mv")
        hv = data.get("hv")
        endpoint = "/gama/opgi-20kv/operator-gi/tegangan-trafo/input"
        file_field = "files"
        num_photos = 2
        id_field = "trafoId"
        value_field = "mv"
    elif data_type == "beban-trafo":
        value = data.get("value")
        endpoint = "/gama/opgi-20kv/operator-gi/beban-trafo/input"
        file_field = "file"
        num_photos = 1
        id_field = "trafoId"
        value_field = "beban"
    else:  # beban-penyulang
        value = data.get("value")
        endpoint = "/gama/opgi-20kv/operator-gi/beban-penyulang/input"
        file_field = "file"
        num_photos = 1
        id_field = "penyulangId"
        value_field = "beban"
    
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    durasi = _h_durasi(data_type)
    body_data = {
        id_field: item_id,
        "timezone": "Asia/Jakarta",
        "periode": periode,
        "tanggal": dt.day,
        "bulan": dt.month - 1,
        "tahun": dt.year,
        "durasi": durasi,
        value_field: mv if data_type == "tegangan-trafo" else value,
    }

    if data_type == "tegangan-trafo":
        fotoHV, fotoMV = _h_foto_pair_dicts(date_str, periode, durasi)
        body_data["hv"] = hv
        body_data["fotoHV"] = fotoHV
        body_data["fotoMV"] = fotoMV
    else:
        body_data["foto"] = _h_foto_dict(date_str, periode, durasi, data_type)
    
    status, result = api_post_multipart(token, endpoint, body_data, DUMMY_JPEG, file_field, num_photos)
    
    if result.get("success"):
        return jsonify({"success": True, "id": result["data"].get("id"), "message": "Data berhasil disimpan"})
    
    msg = result.get("message", "Error tidak diketahui")
    if isinstance(msg, list):
        msg = ", ".join(msg)
    return jsonify({"success": False, "message": msg}), 400

@app.route("/api/data/delete", methods=["POST"])
@login_required
def api_delete_entry():
    """API untuk delete data."""
    token = session["token"]
    data = request.get_json()
    data_type = data.get("type")
    entry_id = data.get("entry_id")
    
    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    
    result = api_delete(token, f"{paths[data_type]}/{entry_id}")
    
    if result.get("success"):
        return jsonify({"success": True, "message": "Data berhasil dihapus"})
    
    return jsonify({"success": False, "message": result.get("message", "Error")}), 400

@app.route("/api/data/refresh", methods=["GET"])
@login_required
def api_refresh():
    """API untuk refresh data (AJAX)."""
    token = session["token"]
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    data_type = request.args.get("type")  # penyulang, trafo, tegangan
    
    paths = {
        "penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    
    result = api_get(token, paths[data_type], {"garduIndukId": _get_gi_id(), "date": date_str})
    return jsonify(result.get("data", {}).get("items", []))

@app.route("/api/data/pattern", methods=["GET"])
@login_required
def api_pattern():
    """API untuk mendapatkan pola beban dari data historis."""
    token = session["token"]
    data_type = request.args.get("type")  # beban-penyulang, beban-trafo, tegangan-trafo
    item_id = request.args.get("item_id", type=int)
    days = request.args.get("days", 7, type=int)
    
    pattern = learn_pattern(token, _get_gi_id(), data_type, item_id, days)
    return jsonify({"success": True, "pattern": pattern})

@app.route("/api/data/batch-input", methods=["POST"])
@login_required
def api_batch_input():
    """API untuk batch input — bisa per-item (multiple periods) atau per-periode (multiple items).
    Support dry_run=true untuk preview tanpa submit (parity dengan CLI --dry-run).
    """
    token = session["token"]
    data = request.get_json()
    
    data_type = data.get("type")
    mode = data.get("mode", "per-item")  # "per-item" atau "per-periode"
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    dry_run = data.get("dry_run", False)
    
    results = []
    
    if mode == "per-periode":
        # Batch per periode: 1 jam, banyak item sekaligus
        items = data.get("items")  # list of {item_id, value, mv, hv}
        periode = data.get("periode")

        if not items or not isinstance(items, list):
            return jsonify({"success": False, "message": "Items harus list"}), 400

        # Reset timeline untuk gap 10-20s antar item dalam periode yang sama
        if hu and hasattr(hu, "reset_foto_sequence"):
            try:
                hu.reset_foto_sequence(date_str, periode)
            except Exception:
                pass

        for it in items:
            item_id = it.get("item_id")
            item_name = it.get("nama") or it.get("item_name") or it.get("name")  # untuk resolver foto manual per-item
            
            if data_type == "tegangan-trafo":
                endpoint = "/gama/opgi-20kv/operator-gi/tegangan-trafo/input"
                file_field = "files"
                num_photos = 2
                id_field = "trafoId"
            elif data_type == "beban-trafo":
                endpoint = "/gama/opgi-20kv/operator-gi/beban-trafo/input"
                file_field = "file"
                num_photos = 1
                id_field = "trafoId"
            else:
                endpoint = "/gama/opgi-20kv/operator-gi/beban-penyulang/input"
                file_field = "file"
                num_photos = 1
                id_field = "penyulangId"
            
            if dry_run:
                val_label = f"MV={it.get('mv')} HV={it.get('hv')}" if data_type == "tegangan-trafo" else f"{it.get('value')}A"
                results.append({"item_id": item_id, "success": True, "dry_run": True, "value": val_label})
                continue
            
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            durasi = _h_durasi(data_type)
            body_data = {
                id_field: item_id,
                "timezone": "Asia/Jakarta",
                "periode": periode,
                "tanggal": dt.day,
                "bulan": dt.month - 1,
                "tahun": dt.year,
                "durasi": durasi,
            }

            if data_type == "tegangan-trafo":
                fotoHV, fotoMV = _h_foto_pair_dicts(date_str, periode, durasi)
                body_data["mv"] = it.get("mv")
                body_data["hv"] = it.get("hv")
                body_data["fotoHV"] = fotoHV
                body_data["fotoMV"] = fotoMV
            else:
                body_data["beban"] = it.get("value")
                body_data["foto"] = _h_foto_dict(date_str, periode, durasi, data_type)

            # Pass item_name agar resolver foto manual per-item bisa match (fix bug pool generic terus)
            # Kalau tidak ada nama, tetap jalan pakai pool generic
            status, result = api_post_multipart(token, endpoint, body_data, DUMMY_JPEG, file_field, num_photos, item_name=item_name)
            if result.get("success"):
                results.append({"item_id": item_id, "success": True, "id": result["data"].get("id")})
            else:
                results.append({"item_id": item_id, "success": False, "message": result.get("message")})

    else:
        item_id = data.get("item_id")
        item_name = data.get("item_name") or data.get("nama") or data.get("name")  # untuk resolver foto manual per-item
        periods = data.get("periods")

        if not periods or not isinstance(periods, list):
            return jsonify({"success": False, "message": "Periods harus list"}), 400

        for p in periods:
            periodo = p.get("periode")

            if data_type == "tegangan-trafo":
                endpoint = "/gama/opgi-20kv/operator-gi/tegangan-trafo/input"
                file_field = "files"
                num_photos = 2
                id_field = "trafoId"
            elif data_type == "beban-trafo":
                endpoint = "/gama/opgi-20kv/operator-gi/beban-trafo/input"
                file_field = "file"
                num_photos = 1
                id_field = "trafoId"
            else:
                endpoint = "/gama/opgi-20kv/operator-gi/beban-penyulang/input"
                file_field = "file"
                num_photos = 1
                id_field = "penyulangId"

            if dry_run:
                val_label = f"MV={p.get('mv')} HV={p.get('hv')}" if data_type == "tegangan-trafo" else f"{p.get('value')}A"
                results.append({"periode": periodo, "success": True, "dry_run": True, "value": val_label})
                continue

            dt = datetime.strptime(date_str, "%Y-%m-%d")
            durasi = _h_durasi(data_type)
            body_data = {
                id_field: item_id,
                "timezone": "Asia/Jakarta",
                "periode": periodo,
                "tanggal": dt.day,
                "bulan": dt.month - 1,
                "tahun": dt.year,
                "durasi": durasi,
            }

            if data_type == "tegangan-trafo":
                fotoHV, fotoMV = _h_foto_pair_dicts(date_str, periodo, durasi)
                body_data["mv"] = p.get("mv")
                body_data["hv"] = p.get("hv")
                body_data["fotoHV"] = fotoHV
                body_data["fotoMV"] = fotoMV
            else:
                body_data["beban"] = p.get("value")
                body_data["foto"] = _h_foto_dict(date_str, periodo, durasi, data_type)

            status, result = api_post_multipart(token, endpoint, body_data, DUMMY_JPEG, file_field, num_photos, item_name=item_name)
            if result.get("success"):
                results.append({"periode": periodo, "success": True, "id": result["data"].get("id")})
            else:
                results.append({"periode": periodo, "success": False, "message": result.get("message")})

    return jsonify({"success": True, "results": results, "dry_run": dry_run})

@app.route("/api/data/smart-suggest", methods=["GET"])
@login_required
def api_smart_suggest():
    """
    Smart suggest value berdasarkan:
    1. Rata-rata 7 hari periode sama
    2. Weekday vs Weekend pattern
    3. Trend dari jam sebelumnya hari ini
    
    Formula: 40% base + 40% weekday/weekend + 20% trend
    """
    token = session["token"]
    data_type = request.args.get("type")  # beban-penyulang, beban-trafo
    item_id = request.args.get("item_id", type=int)
    periode = request.args.get("periode", type=int)
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    prev_periode_val = request.args.get("prev_val", type=float, default=None)  # nilai P sebelumnya hari ini
    
    from collections import defaultdict
    from datetime import timedelta
    
    path = "/gama/opgi-20kv/operator-gi/beban-penyulang" if data_type == "beban-penyulang" else \
           "/gama/opgi-20kv/operator-gi/beban-trafo"

    today = datetime.strptime(date_str, "%Y-%m-%d")
    is_weekend = today.weekday() >= 5

    hist_days = _cli.get_history_days()

    # Kumpulkan data N hari untuk pattern yang robust
    base_vals = []  # rata-rata N hari periode sama
    weekday_vals = []  # rata-rata weekday periode sama
    weekend_vals = []  # rata-rata weekend periode sama

    for offset in range(1, hist_days + 1):
        d = today - timedelta(days=offset)
        date_key = d.strftime("%Y-%m-%d")
        d_is_weekend = d.weekday() >= 5
        
        result = api_get(token, path, {"garduIndukId": _get_gi_id(), "date": date_key})
        items = result.get("data", {}).get("items", [])
        
        for it in items:
            if it["id"] != item_id or it.get("statusCB") == "OFF":
                continue
            
            for e in it.get("beban", []):
                if e["periode"] == periode:
                    val = e["beban"]
                    base_vals.append(val)
                    
                    if d_is_weekend:
                        weekend_vals.append(val)
                    else:
                        weekday_vals.append(val)
    
    # Hitung rata-rata per faktor
    base_avg = sum(base_vals) / len(base_vals) if base_vals else 0
    
    if is_weekend:
        pattern_avg = sum(weekend_vals) / len(weekend_vals) if weekend_vals else base_avg
    else:
        pattern_avg = sum(weekday_vals) / len(weekday_vals) if weekday_vals else base_avg
    
    # Faktor trend (kalau ada nilai jam sebelumnya hari ini)
    trend_factor = 1.0
    # Hitung rata-rata P-1 7 hari (parallel)
    prev_vals = []
    if prev_periode_val is not None and prev_periode_val > 0:
        from concurrent.futures import ThreadPoolExecutor
        
        def fetch_prev_day(offset):
            d = today - timedelta(days=offset)
            return api_get(token, path, {"garduIndukId": _get_gi_id(), "date": d.strftime("%Y-%m-%d")})
        
        with ThreadPoolExecutor(max_workers=min(hist_days, 8)) as executor:
            results = list(executor.map(fetch_prev_day, range(1, hist_days + 1)))
        
        for result in results:
            items = result.get("data", {}).get("items", [])
            for it in items:
                if it["id"] == item_id:
                    for e in it.get("beban", []):
                        if e["periode"] == periode - 1:
                            prev_vals.append(e["beban"])
        
        if prev_vals:
            prev_avg = sum(prev_vals) / len(prev_vals)
            if prev_avg > 0:
                trend_factor = prev_periode_val / prev_avg  # berapa kali naik dibanding biasanya
    
    # Formula: 40% base + 40% pattern + 20% trend
    smart_value = (0.4 * base_avg) + (0.4 * pattern_avg) + (0.2 * pattern_avg * trend_factor)
    
    # Round ke kelipatan 5
    suggested = round(smart_value / 5) * 5
    
    # Clamp ke range historis (min-max)
    all_historical = base_vals + weekday_vals + weekend_vals
    if all_historical:
        min_val = min(all_historical)
        max_val = max(all_historical)
        suggested = max(min_val, min(max_val, suggested))
    
    return jsonify({
        "success": True,
        "suggested": suggested,
        "breakdown": {
            "base_avg": round(base_avg, 1),
            "pattern_avg": round(pattern_avg, 1),
            "trend_factor": round(trend_factor, 2),
            "is_weekend": is_weekend,
            "samples": len(base_vals)
        }
    })

@app.route("/api/data/batch-pattern", methods=["GET"])
@login_required
def api_batch_pattern():
    """API untuk get pola semua item di satu periode (smart: weekday/weekend aware)."""
    token = session["token"]
    data_type = request.args.get("type")
    periode = request.args.get("periode", type=int)
    days = request.args.get("days", _cli.get_history_days(), type=int)  # default dari config
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    from collections import defaultdict
    from datetime import timedelta
    
    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    
    today = datetime.strptime(date_str, "%Y-%m-%d")
    is_target_weekend = today.weekday() >= 5
    
    # Fetch parallel untuk semua tanggal (drastis lebih cepat dari sequential)
    from concurrent.futures import ThreadPoolExecutor
    
    def fetch_day(offset):
        d = today - timedelta(days=offset)
        return offset, d, d.weekday() >= 5, api_get(token, paths[data_type], 
            {"garduIndukId": _get_gi_id(), "date": d.strftime("%Y-%m-%d")})
    
    # Kumpulkan: semua, weekday, weekend (separate)
    item_patterns = defaultdict(lambda: {
        "all_values": [], "weekday_values": [], "weekend_values": [],
        "mv_values": [], "hv_values": [],
        "mv_weekday": [], "mv_weekend": [],
        "hv_weekday": [], "hv_weekend": [],
    })
    item_names = {}  # id → nama trafo (untuk aturan pembulatan MV)
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        results_list = list(executor.map(fetch_day, range(1, days + 1)))
    
    for offset, d, d_is_weekend, result in results_list:
        items = result.get("data", {}).get("items", [])
        for it in items:
            # Simpan nama untuk aturan pembulatan MV
            item_names[it["id"]] = it.get("nama", "")
            if data_type == "tegangan-trafo":
                for e in it.get("tegangan", []):
                    if e["periode"] == periode:
                        item_patterns[it["id"]]["mv_values"].append(e["mv"])
                        item_patterns[it["id"]]["hv_values"].append(e["hv"])
                        if d_is_weekend:
                            item_patterns[it["id"]]["mv_weekend"].append(e["mv"])
                            item_patterns[it["id"]]["hv_weekend"].append(e["hv"])
                        else:
                            item_patterns[it["id"]]["mv_weekday"].append(e["mv"])
                            item_patterns[it["id"]]["hv_weekday"].append(e["hv"])
            else:
                if it.get("statusCB") == "OFF":
                    continue
                for e in it.get("beban", []):
                    if e["periode"] == periode:
                        v = e["beban"]
                        item_patterns[it["id"]]["all_values"].append(v)
                        if d_is_weekend:
                            item_patterns[it["id"]]["weekend_values"].append(v)
                        else:
                            item_patterns[it["id"]]["weekday_values"].append(v)
    
    # Hitung smart suggest per item
    patterns = {}
    for item_id, data in item_patterns.items():
        if data_type == "tegangan-trafo":
            mvs = data["mv_values"]
            if mvs:
                nama = item_names.get(item_id, "")
                hvs = data["hv_values"]
                # 50% pattern + 50% base (parity dengan CLI smart_suggest_tegangan_from_cache)
                if is_target_weekend:
                    pat_mv = data["mv_weekend"] if data["mv_weekend"] else mvs
                    pat_hv = data["hv_weekend"] if data["hv_weekend"] else hvs
                else:
                    pat_mv = data["mv_weekday"] if data["mv_weekday"] else mvs
                    pat_hv = data["hv_weekday"] if data["hv_weekday"] else hvs

                base_mv = sum(mvs) / len(mvs)
                pattern_mv = sum(pat_mv) / len(pat_mv)
                smart_mv = 0.5 * pattern_mv + 0.5 * base_mv
                mv_rounded = _round_mv(nama, smart_mv)
                if pat_mv:
                    mv_rounded = max(min(pat_mv), min(max(pat_mv), mv_rounded))
                    mv_rounded = _round_mv(nama, mv_rounded)

                base_hv = sum(hvs) / len(hvs)
                pattern_hv = sum(pat_hv) / len(pat_hv)
                smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
                if "PS" in nama.upper():
                    hv_rounded = round(smart_hv, 2)
                    if pat_hv:
                        hv_rounded = max(min(pat_hv), min(max(pat_hv), hv_rounded))
                        hv_rounded = round(hv_rounded, 2)
                else:
                    hv_rounded = round(smart_hv)
                    if pat_hv:
                        hv_rounded = max(min(pat_hv), min(max(pat_hv), hv_rounded))
                    hv_rounded = int(hv_rounded)

                patterns[str(item_id)] = {
                    "mv_avg": mv_rounded,
                    "hv_avg": hv_rounded,
                    "samples": len(mvs),
                    "pattern_type": "weekend" if is_target_weekend else "weekday",
                }
        else:
            all_vals = data["all_values"]
            if not all_vals:
                # Fallback: kalau periode target kosong, pakai rata-rata semua periode
                # Kumpulkan semua nilai dari semua periode untuk item ini
                fb_vals = []
                for offset, d, d_is_weekend, result in results_list:
                    items = result.get("data", {}).get("items", [])
                    for it in items:
                        if it["id"] != item_id or it.get("statusCB") == "OFF":
                            continue
                        for e in it.get("beban", []):
                            fb_vals.append(e["beban"])
                if not fb_vals:
                    continue
                fb_avg = sum(fb_vals) / len(fb_vals)
                fb_suggested = round(fb_avg / 5) * 5
                fb_suggested = max(min(fb_vals), min(max(fb_vals), fb_suggested))
                patterns[str(item_id)] = {
                    "avg": int(fb_suggested),
                    "raw_avg": round(fb_avg, 1),
                    "min": min(fb_vals), "max": max(fb_vals),
                    "samples": len(fb_vals),
                    "pattern_type": "fallback",
                    "fallback": True,
                    "note": "Fallback: rata-rata semua periode (periode target kosong)",
                }
                continue
            
            # Pakai weekday atau weekend pattern sesuai target hari
            if is_target_weekend:
                pattern_vals = data["weekend_values"] if data["weekend_values"] else all_vals
                pattern_label = "weekend"
            else:
                pattern_vals = data["weekday_values"] if data["weekday_values"] else all_vals
                pattern_label = "weekday"
            
            base_avg = sum(all_vals) / len(all_vals)
            pattern_avg = sum(pattern_vals) / len(pattern_vals)
            
            # Smart formula: 50% pattern (weekday/weekend) + 50% base
            smart_avg = 0.5 * pattern_avg + 0.5 * base_avg
            
            # Round ke kelipatan 5
            suggested = round(smart_avg / 5) * 5
            
            # Clamp ke range historis pattern
            if pattern_vals:
                p_min, p_max = min(pattern_vals), max(pattern_vals)
                suggested = max(p_min, min(p_max, suggested))
            
            patterns[str(item_id)] = {
                "avg": int(suggested),
                "raw_avg": round(smart_avg, 1),
                "base_avg": round(base_avg, 1),
                "pattern_avg": round(pattern_avg, 1),
                "pattern_type": pattern_label,
                "min": min(all_vals),
                "max": max(all_vals),
                "samples": len(all_vals),
                "pattern_samples": len(pattern_vals),
            }
    
    return jsonify({"success": True, "patterns": patterns, "is_target_weekend": is_target_weekend})

# Aturan khusus tegangan GI MANGGARAI:
# - TRAFO PS 1 (22244): HV = MV dari TRAFO 1 (22241), MV = genap bulat
# - TRAFO PS 2 (22245): HV = MV dari TRAFO 3 (22243), MV = genap bulat
PS_RULES = {
    22244: {"hv_source": 22241, "name": "TRAFO PS 1"},  # HV dari MV TRAFO 1
    22245: {"hv_source": 22243, "name": "TRAFO PS 2"},  # HV dari MV TRAFO 3
}

@app.route("/api/data/batch-pattern-tegangan", methods=["GET"])
@login_required
def api_batch_pattern_tegangan():
    """
    API khusus tegangan: pola N hari (config) + weekday/weekend + aturan PS1/PS2 dynamic.
    PARITY dengan CLI smart_suggest_tegangan_from_cache + fallback_tegangan_from_cache.

    Logika:
    - N hari historis (default config history_days, fallback 7), weekday/weekend aware (50% pattern + 50% base)
    - MV: pembulatan per trafo (PS=0des, T1=1des, lain=2des), clamp range
    - HV PS1 = MV TRAFO 1 (dinamis lookup di cache), HV PS2 = MV TRAFO 3
    - HV trafo biasa = integer ~150kV
    - Fallback: kalau periode target kosong, pakai rata-rata semua periode
    """
    token = session["token"]
    periode = request.args.get("periode", type=int)
    days = request.args.get("days", _cli.get_history_days(), type=int)
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))

    from collections import defaultdict
    from datetime import timedelta
    from concurrent.futures import ThreadPoolExecutor

    path = "/gama/opgi-20kv/operator-gi/tegangan-trafo"
    today = datetime.strptime(date_str, "%Y-%m-%d")
    is_target_weekend = today.weekday() >= 5

    # Build cache: item_id → {name, periode_data: {periode: {all, weekday, weekend}}}
    cache = {}
    item_names = {}

    def fetch_day(offset):
        d = today - timedelta(days=offset)
        return d.weekday() >= 5, api_get(token, path, {"garduIndukId": _get_gi_id(), "date": d.strftime("%Y-%m-%d")})

    with ThreadPoolExecutor(max_workers=8) as executor:
        results_list = list(executor.map(fetch_day, range(1, days + 1)))

    for is_weekend, result in results_list:
        items = result.get("data", {}).get("items", [])
        for it in items:
            item_id = it["id"]
            item_names[item_id] = it.get("nama", "")
            if item_id not in cache:
                cache[item_id] = {
                    "name": it.get("nama", ""),
                    "periode_data": defaultdict(lambda: {"all": [], "weekday": [], "weekend": []}),
                }
            for e in it.get("tegangan", []):
                p = e["periode"]
                cache[item_id]["periode_data"][p]["all"].append(e)
                if is_weekend:
                    cache[item_id]["periode_data"][p]["weekend"].append(e)
                else:
                    cache[item_id]["periode_data"][p]["weekday"].append(e)

    patterns = {}

    def compute_tegangan(item_id, per, target_weekend):
        """Return (mv, hv, info, is_ps, fallback_used) atau (None, None, None, False, False)."""
        if item_id not in cache:
            return None, None, None, False, False

        pdata = cache[item_id]["periode_data"].get(per)
        nama = cache[item_id].get("name", "").upper()
        is_ps = "PS" in nama

        # Fallback: periode target kosong → pakai rata-rata semua periode
        if not pdata or not pdata["all"]:
            entries = []
            for pd in cache[item_id]["periode_data"].values():
                entries.extend(pd["all"])
            entries = [e for e in entries if e.get("mv") is not None and e.get("hv") is not None]
            if not entries:
                return None, None, None, is_ps, False
            mv_vals = [e["mv"] for e in entries]
            hv_vals = [e["hv"] for e in entries]
            mv = _round_mv(cache[item_id].get("name", ""), sum(mv_vals) / len(mv_vals))
            mv = max(min(mv_vals), min(max(mv_vals), mv))
            mv = _round_mv(cache[item_id].get("name", ""), mv)
            if is_ps:
                hv = round(sum(hv_vals) / len(hv_vals), 2)
            else:
                hv = int(round(sum(hv_vals) / len(hv_vals)))
            return mv, hv, f"FALLBACK avg semua periode ({len(mv_vals)}d)", is_ps, True

        all_entries = pdata["all"]
        if target_weekend:
            pat_entries = pdata["weekend"] if pdata["weekend"] else all_entries
            pattern_type = "weekend"
        else:
            pat_entries = pdata["weekday"] if pdata["weekday"] else all_entries
            pattern_type = "weekday"

        all_mv = [e["mv"] for e in all_entries]
        all_hv = [e["hv"] for e in all_entries]
        pat_mv = [e["mv"] for e in pat_entries]
        pat_hv = [e["hv"] for e in pat_entries]

        # MV: 50% pattern + 50% base
        base_mv = sum(all_mv) / len(all_mv)
        pattern_mv = sum(pat_mv) / len(pat_mv)
        smart_mv = 0.5 * pattern_mv + 0.5 * base_mv
        smart_mv = _round_mv(cache[item_id].get("name", ""), smart_mv)
        if pat_mv:
            smart_mv = max(min(pat_mv), min(max(pat_mv), smart_mv))
            smart_mv = _round_mv(cache[item_id].get("name", ""), smart_mv)

        # HV
        if is_ps:
            # PS1 → TRAFO 1, PS2 → TRAFO 3
            if "1" in nama:
                source_target = "TRAFO 1"
            elif "2" in nama:
                source_target = "TRAFO 3"
            else:
                source_target = None

            source_mv = None
            if source_target:
                for sid, sdata in cache.items():
                    if sdata.get("name", "").upper() == source_target:
                        src_p = sdata["periode_data"].get(per)
                        if src_p and src_p["all"]:
                            if target_weekend:
                                src_pat = src_p["weekend"] if src_p["weekend"] else src_p["all"]
                            else:
                                src_pat = src_p["weekday"] if src_p["weekday"] else src_p["all"]
                            src_mv_vals = [e["mv"] for e in src_pat]
                            src_all_mv = [e["mv"] for e in src_p["all"]]
                            if src_mv_vals:
                                base_src = sum(src_all_mv) / len(src_all_mv)
                                pat_src = sum(src_mv_vals) / len(src_mv_vals)
                                source_mv = 0.5 * pat_src + 0.5 * base_src
                                src_decimals = 1 if source_target == "TRAFO 1" else 2
                                source_mv = round(source_mv, src_decimals)
                                source_mv = max(min(src_mv_vals), min(max(src_mv_vals), source_mv))
                                source_mv = round(source_mv, src_decimals)
                        break

            if source_mv is not None:
                smart_hv = source_mv
                info = f"{pattern_type} HV=MV {source_target}={source_mv} ({len(pat_mv)}d)"
            else:
                # Fallback HV PS
                base_hv = sum(all_hv) / len(all_hv)
                pattern_hv = sum(pat_hv) / len(pat_hv)
                smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
                smart_hv = round(smart_hv, 2)
                if pat_hv:
                    smart_hv = max(min(pat_hv), min(max(pat_hv), smart_hv))
                    smart_hv = round(smart_hv, 2)
                info = f"{pattern_type} HV={pattern_hv:.2f} (fallback {len(pat_mv)}d)"
        else:
            # Trafo biasa: HV ~150kV integer
            base_hv = sum(all_hv) / len(all_hv)
            pattern_hv = sum(pat_hv) / len(pat_hv)
            smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
            smart_hv = round(smart_hv)
            if pat_hv:
                smart_hv = max(min(pat_hv), min(max(pat_hv), smart_hv))
            smart_hv = int(smart_hv)
            info = f"{pattern_type} MV={pattern_mv:.2f} HV={pattern_hv:.0f} ({len(pat_mv)}d)"

        return smart_mv, smart_hv, info, is_ps, False

    for item_id in cache:
        mv, hv, info, is_ps, fallback_used = compute_tegangan(item_id, periode, is_target_weekend)
        if mv is None:
            continue

        nama = cache[item_id].get("name", "")
        note = ""
        if is_ps:
            if "1" in nama.upper():
                src_name = "TRAFO 1"
            elif "2" in nama.upper():
                src_name = "TRAFO 3"
            else:
                src_name = "?"
            # Cari MV trafo sumber untuk ditampilkan di note
            src_mv_display = "?"
            for sid, sdata in cache.items():
                if sdata.get("name", "").upper() == src_name:
                    src_p = sdata["periode_data"].get(periode)
                    if src_p and src_p["all"]:
                        src_all_mv = [e["mv"] for e in src_p["all"]]
                        src_mv_display = _round_mv(sdata.get("name", ""), sum(src_all_mv) / len(src_all_mv))
                    break
            note = f"HV={src_mv_display}kV (dari MV {src_name}), MV bulat"

        patterns[str(item_id)] = {
            "mv_avg": mv,
            "hv_avg": hv,
            "samples": len(cache[item_id]["periode_data"].get(periode, {}).get("all", [])),
            "is_ps": is_ps,
            "note": note,
            "info": info,
            "fallback": fallback_used,
            "pattern_type": "weekend" if is_target_weekend else "weekday",
            "name": nama,
        }

    return jsonify({
        "success": True,
        "patterns": patterns,
        "is_target_weekend": is_target_weekend,
        "days": days,
    })

@app.route("/api/data/sync-portal", methods=["POST"])
@login_required
def api_sync_portal():
    """API endpoint: sync data ke Portal PLN APD Jakarta setelah batch fill."""
    data = request.get_json()
    data_type = data.get("type")  # beban-penyulang, beban-trafo, tegangan-trafo
    periodes = data.get("periodes", [])  # list of int
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    # Map type
    sync_type_map = {
        "beban-penyulang": "penyulang",
        "beban-trafo": "trafo",
        "tegangan-trafo": "tegangan",
    }
    sync_type = sync_type_map.get(data_type)
    if not sync_type or not periodes:
        return jsonify({"success": False, "message": "Missing type or periodes"})
    
    try:
        import superi_sync
        if not superi_sync.PORTAL_USER or not superi_sync.PORTAL_PASS:
            return jsonify({"success": False, "message": "Portal PLN credentials belum diset di .superi_config.json"})
        
        results = []
        for p in sorted(periodes):
            ok = superi_sync.do_sync(sync_type, p, p, date_str, dry_run=False)
            results.append({"periode": p, "success": ok})
        
        all_ok = all(r["success"] for r in results)
        return jsonify({"success": all_ok, "results": results, "message": f"Sync {len(periodes)} periode {'berhasil' if all_ok else 'sebagian gagal'}"})
    except ImportError:
        return jsonify({"success": False, "message": "Module superi_sync tidak tersedia"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ============================================================
# CONFIG SETUP (parity dengan CLI setup_config)
# ============================================================

CONFIG_FILE = os.path.join(SCRIPT_DIR, ".superi_config.json")

def _load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def _get_gi_id() -> int:
    """Ambil gi_id dari config, fallback 222 biar tidak hardcoded di semua tempat."""
    try:
        cfg = _load_config()
        return int(cfg.get("gi_id", 222))
    except Exception:
        return 222

def _save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

@app.route("/setup", methods=["GET", "POST"])
@login_required
def setup_page():
    """Halaman setup kredensial (parity dengan CLI setup_config)."""
    if request.method == "POST":
        cfg = _load_config()
        # Pertahankan keys lama
        nip = request.form.get("nip", "").strip()
        password = request.form.get("password", "").strip()
        portal_user = request.form.get("portal_user", "").strip()
        portal_password = request.form.get("portal_password", "").strip()
        portal_url = request.form.get("portal_url", "").strip()
        portal_gi_id = request.form.get("portal_gi_id", "").strip()
        gi_id = request.form.get("gi_id", "").strip()

        if nip:
            cfg["nip"] = nip
        if password:
            cfg["password"] = password
        if portal_user:
            cfg["portal_user"] = portal_user
        if portal_password:
            cfg["portal_password"] = portal_password
        if portal_url:
            cfg["portal_url"] = portal_url
        if portal_gi_id:
            cfg["portal_gi_id"] = portal_gi_id
        if gi_id:
            cfg["gi_id"] = gi_id
        cfg.setdefault("portal_url", "http://10.3.187.6/apdjakarta")
        cfg.setdefault("portal_gi_id", "143")
        cfg.setdefault("gi_id", "222")
        _save_config(cfg)
        return render_template("setup.html", saved=True, config=cfg, user=session.get("user", {}))
    cfg = _load_config()
    return render_template("setup.html", saved=False, config=cfg, user=session.get("user", {}))

# ============================================================
# AUTO MODE (parity dengan superior_auto.py)
# ============================================================

@app.route("/auto")
@login_required
def auto_page():
    """Halaman Auto Mode: status, enable/disable, config window/jam, dry-run, trigger manual."""
    cfg = _load_config()
    return render_template("auto.html", config=cfg)

@app.route("/api/auto/status", methods=["GET"])
@login_required
def api_auto_status():
    """Status auto mode (parity dengan CLI cmd_status)."""
    cfg = _load_config()
    return jsonify({
        "enabled": cfg.get("auto_enabled", False),
        "window_start": cfg.get("auto_window_start", 22),
        "window_end": cfg.get("auto_window_end", 5),
        "types": cfg.get("auto_types", ["penyulang", "trafo", "tegangan"]),
        "sync_portal": cfg.get("auto_sync_portal", True),
        "retry_attempts": cfg.get("auto_retry_attempts", 5),
        "retry_delay": cfg.get("auto_retry_delay", 10),
        "has_superi_creds": bool(cfg.get("nip") and cfg.get("password")),
        "has_portal_creds": bool(cfg.get("portal_user") and cfg.get("portal_password")),
    })

@app.route("/api/auto/toggle", methods=["POST"])
@login_required
def api_auto_toggle():
    """Enable/disable auto mode (parity dengan cmd_enable/cmd_disable)."""
    cfg = _load_config()
    action = request.get_json().get("action")  # "enable" or "disable"
    if action == "enable":
        cfg["auto_enabled"] = True
        cfg.setdefault("auto_window_start", 22)
        cfg.setdefault("auto_window_end", 5)
        cfg.setdefault("auto_types", ["penyulang", "trafo", "tegangan"])
        cfg.setdefault("auto_sync_portal", True)
        cfg.setdefault("auto_retry_attempts", 5)
        cfg.setdefault("auto_retry_delay", 10)
        _save_config(cfg)
        return jsonify({"success": True, "enabled": True, "message": "Auto mode AKTIF"})
    elif action == "disable":
        cfg["auto_enabled"] = False
        _save_config(cfg)
        return jsonify({"success": True, "enabled": False, "message": "Auto mode NONAKTIF"})
    return jsonify({"success": False, "message": "Invalid action"}), 400

@app.route("/api/auto/config", methods=["POST"])
@login_required
def api_auto_config():
    """Update auto mode config (window, types, retry, sync)."""
    cfg = _load_config()
    data = request.get_json()
    if "window_start" in data:
        cfg["auto_window_start"] = max(0, min(23, int(data["window_start"])))
    if "window_end" in data:
        cfg["auto_window_end"] = max(0, min(23, int(data["window_end"])))
    if "types" in data and isinstance(data["types"], list):
        valid = [t for t in data["types"] if t in ("penyulang", "trafo", "tegangan")]
        if valid:
            cfg["auto_types"] = valid
    if "sync_portal" in data:
        cfg["auto_sync_portal"] = bool(data["sync_portal"])
    if "retry_attempts" in data:
        cfg["auto_retry_attempts"] = max(1, int(data["retry_attempts"]))
    if "retry_delay" in data:
        cfg["auto_retry_delay"] = max(1, int(data["retry_delay"]))
    _save_config(cfg)
    return jsonify({"success": True, "config": {
        "enabled": cfg.get("auto_enabled", False),
        "window_start": cfg.get("auto_window_start", 22),
        "window_end": cfg.get("auto_window_end", 5),
        "types": cfg.get("auto_types", []),
        "sync_portal": cfg.get("auto_sync_portal", True),
        "retry_attempts": cfg.get("auto_retry_attempts", 5),
        "retry_delay": cfg.get("auto_retry_delay", 10),
    }})

@app.route("/api/auto/run", methods=["POST"])
@login_required
def api_auto_run():
    """Trigger auto mode secara manual dari web (parity dengan superior_auto.py run_auto).

    Bisa dry-run (preview tanpa input) atau live.
    """
    data = request.get_json() or {}
    dry_run = data.get("dry_run", False)
    force_jam = data.get("jam")  # int atau None
    types = data.get("types")  # list atau None

    import superi_auto
    try:
        ok = superi_auto.run_auto(force_jam=force_jam, types=types, dry_run=dry_run)
        return jsonify({"success": ok, "dry_run": dry_run, "message": "Auto mode selesai" + (" (DRY-RUN)" if dry_run else "")})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/auto/log", methods=["GET"])
@login_required
def api_auto_log():
    """Baca auto_log.txt (n tail lines)."""
    log_file = os.path.join(SCRIPT_DIR, "auto_log.txt")
    n = request.args.get("n", 50, type=int)
    if not os.path.exists(log_file):
        return jsonify({"success": True, "log": "", "message": "Belum ada log"})
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        tail = lines[-n:] if len(lines) > n else lines
        return jsonify({"success": True, "log": "".join(tail), "total_lines": len(lines)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ============================================================
# DRY-RUN / SCRIPTING API (parity dengan superi_input.py)
# ============================================================

@app.route("/api/data/dry-run", methods=["POST"])
@login_required
def api_dry_run():
    """Preview smart-suggest tanpa submit (parity dengan CLI --dry-run).

    Input: {type, item_id, periode, date}
    Output: {success, suggested, breakdown, info}
    """
    data = request.get_json()
    data_type = data.get("type")
    item_id = data.get("item_id")
    periode = data.get("periode")
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))

    if not data_type or not item_id or periode is None:
        return jsonify({"success": False, "message": "Missing type/item_id/periode"}), 400

    token = session["token"]
    from datetime import datetime as dt
    from concurrent.futures import ThreadPoolExecutor
    from collections import defaultdict
    from datetime import timedelta

    today = dt.strptime(date_str, "%Y-%m-%d")
    is_target_weekend = today.weekday() >= 5

    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    path = paths[data_type]

    # Build cache untuk item ini (semua periode, N hari dari config)
    cache = defaultdict(lambda: {"all": [], "weekday": [], "weekend": []})
    item_name = ""

    def fetch_day(offset):
        d = today - timedelta(days=offset)
        return d.weekday() >= 5, api_get(token, path, {"garduIndukId": _get_gi_id(), "date": d.strftime("%Y-%m-%d")})

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_day, range(1, _cli.get_history_days() + 1)))

    for is_weekend, result in results:
        items = result.get("data", {}).get("items", [])
        for it in items:
            if it["id"] != item_id:
                continue
            if not item_name:
                item_name = it.get("nama", "")
            if data_type == "tegangan-trafo":
                for e in it.get("tegangan", []):
                    p = e["periode"]
                    cache[p]["all"].append(e)
                    if is_weekend:
                        cache[p]["weekend"].append(e)
                    else:
                        cache[p]["weekday"].append(e)
            else:
                if it.get("statusCB") == "OFF":
                    continue
                for e in it.get("beban", []):
                    p = e["periode"]
                    val = e["beban"]
                    cache[p]["all"].append(val)
                    if is_weekend:
                        cache[p]["weekend"].append(val)
                    else:
                        cache[p]["weekday"].append(val)

    pdata = cache.get(periode, {"all": [], "weekday": [], "weekend": []})

    if not pdata["all"]:
        # Fallback: rata-rata semua periode
        all_vals = []
        for pd in cache.values():
            all_vals.extend(pd["all"])
        if not all_vals:
            return jsonify({"success": False, "message": "Tidak ada histori untuk item ini"})
        if data_type == "tegangan-trafo":
            mvs = [e["mv"] for e in all_vals]
            hvs = [e["hv"] for e in all_vals]
            mv = _round_mv(item_name, sum(mvs) / len(mvs))
            mv = max(min(mvs), min(max(mvs), mv))
            mv = _round_mv(item_name, mv)
            if "PS" in item_name.upper():
                hv = round(sum(hvs) / len(hvs), 2)
            else:
                hv = int(round(sum(hvs) / len(hvs)))
            return jsonify({
                "success": True, "dry_run": True,
                "suggested": {"mv": mv, "hv": hv},
                "info": f"FALLBACK avg semua periode ({len(mvs)}d)",
                "samples": len(mvs), "fallback": True,
            })
        else:
            avg = sum(all_vals) / len(all_vals)
            suggested = round(avg / 5) * 5
            suggested = max(min(all_vals), min(max(all_vals), suggested))
            return jsonify({
                "success": True, "dry_run": True,
                "suggested": int(suggested),
                "info": f"FALLBACK avg semua periode ({len(all_vals)}d)",
                "samples": len(all_vals), "fallback": True,
                "breakdown": {"base_avg": round(avg, 1)},
            })

    if data_type == "tegangan-trafo":
        all_entries = pdata["all"]
        if is_target_weekend:
            pat_entries = pdata["weekend"] if pdata["weekend"] else all_entries
        else:
            pat_entries = pdata["weekday"] if pdata["weekday"] else all_entries

        all_mv = [e["mv"] for e in all_entries]
        all_hv = [e["hv"] for e in all_entries]
        pat_mv = [e["mv"] for e in pat_entries]
        pat_hv = [e["hv"] for e in pat_entries]

        base_mv = sum(all_mv) / len(all_mv)
        pattern_mv = sum(pat_mv) / len(pat_mv)
        smart_mv = 0.5 * pattern_mv + 0.5 * base_mv
        smart_mv = _round_mv(item_name, smart_mv)
        if pat_mv:
            smart_mv = max(min(pat_mv), min(max(pat_mv), smart_mv))
            smart_mv = _round_mv(item_name, smart_mv)

        nama_upper = item_name.upper()
        is_ps = "PS" in nama_upper
        if is_ps:
            source_target = "TRAFO 1" if "1" in nama_upper else ("TRAFO 3" if "2" in nama_upper else None)
            # Untuk dry-run tidak perlu lookup source (cukup tampilkan saran)
            base_hv = sum(all_hv) / len(all_hv)
            pattern_hv = sum(pat_hv) / len(pat_hv)
            smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
            smart_hv = round(smart_hv, 2)
            if pat_hv:
                smart_hv = max(min(pat_hv), min(max(pat_hv), smart_hv))
                smart_hv = round(smart_hv, 2)
        else:
            base_hv = sum(all_hv) / len(all_hv)
            pattern_hv = sum(pat_hv) / len(pat_hv)
            smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
            smart_hv = round(smart_hv)
            if pat_hv:
                smart_hv = max(min(pat_hv), min(max(pat_hv), smart_hv))
            smart_hv = int(smart_hv)

        return jsonify({
            "success": True, "dry_run": True,
            "suggested": {"mv": smart_mv, "hv": smart_hv},
            "info": f"{'weekend' if is_target_weekend else 'weekday'} MV={pattern_mv:.2f} HV={pattern_hv:.2f} ({len(pat_mv)}d)",
            "samples": len(all_mv),
            "breakdown": {
                "base_mv": round(base_mv, 2), "pattern_mv": round(pattern_mv, 2),
                "base_hv": round(base_hv, 2), "pattern_hv": round(pattern_hv, 2),
                "is_weekend": is_target_weekend, "is_ps": is_ps,
            },
        })
    else:
        all_vals = pdata["all"]
        if is_target_weekend:
            pat_vals = pdata["weekend"] if pdata["weekend"] else all_vals
        else:
            pat_vals = pdata["weekday"] if pdata["weekday"] else all_vals

        base_avg = sum(all_vals) / len(all_vals)
        pattern_avg = sum(pat_vals) / len(pat_vals)
        smart_avg = 0.5 * pattern_avg + 0.5 * base_avg
        suggested = round(smart_avg / 5) * 5
        if pat_vals:
            suggested = max(min(pat_vals), min(max(pat_vals), suggested))

        return jsonify({
            "success": True, "dry_run": True,
            "suggested": int(suggested),
            "info": f"{'weekend' if is_target_weekend else 'weekday'} avg {pattern_avg:.0f}A",
            "samples": len(all_vals),
            "breakdown": {
                "base_avg": round(base_avg, 1),
                "pattern_avg": round(pattern_avg, 1),
                "is_weekend": is_target_weekend,
                "pattern_samples": len(pat_vals),
            },
        })

@app.route("/api/scripting/input", methods=["POST"])
@login_required
def api_scripting_input():
    """One-shot input API (parity dengan superi_input.py CLI scripting).

    Input: {type, item_id, periode, value/hv/mv, date}
    """
    data = request.get_json()
    data_type = data.get("type")
    item_id = data.get("item_id")
    periode = data.get("periode")
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))

    if not data_type or not item_id or periode is None:
        return jsonify({"success": False, "message": "Missing type/item_id/periode"}), 400

    token = session["token"]
    endpoint_map = {
        "beban-penyulang": ("/gama/opgi-20kv/operator-gi/beban-penyulang/input", "file", 1, "penyulangId", "beban"),
        "beban-trafo": ("/gama/opgi-20kv/operator-gi/beban-trafo/input", "file", 1, "trafoId", "beban"),
        "tegangan-trafo": ("/gama/opgi-20kv/operator-gi/tegangan-trafo/input", "files", 2, "trafoId", "mv"),
    }
    ep = endpoint_map[data_type]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    durasi = _h_durasi(data_type)

    body_data = {
        ep[3]: item_id,
        "timezone": "Asia/Jakarta",
        "periode": periode,
        "tanggal": dt.day, "bulan": dt.month - 1, "tahun": dt.year,
        "durasi": durasi,
        ep[4]: data.get("value") if data_type != "tegangan-trafo" else data.get("mv"),
    }
    if data_type == "tegangan-trafo":
        fotoHV, fotoMV = _h_foto_pair_dicts(date_str, periode, durasi)
        body_data["hv"] = data.get("hv")
        body_data["fotoHV"] = fotoHV
        body_data["fotoMV"] = fotoMV
    else:
        body_data["foto"] = _h_foto_dict(date_str, periode, durasi, data_type)

    status, result = api_post_multipart(token, ep[0], body_data, DUMMY_JPEG, ep[1], ep[2])
    if result.get("success"):
        return jsonify({"success": True, "id": result["data"].get("id"), "message": "Data berhasil disimpan"})
    msg = result.get("message", "Error")
    if isinstance(msg, list):
        msg = ", ".join(msg)
    return jsonify({"success": False, "message": msg}), 400

if __name__ == "__main__":
    import subprocess
    # Auto-kill port 8888 jika bentrok
    try:
        result = subprocess.run(["lsof", "-ti", ":8888"], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                subprocess.run(["kill", "-9", pid], capture_output=True)
            import time
            time.sleep(1)
            print("  ⚠ Port 8888 bentrok — proses lama dihentikan.")
    except Exception:
        pass
    app.run(debug=False, host="127.0.0.1", port=8888)
