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
except Exception:  # pragma: no cover - fallback if module missing
    ui = None


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

def login(nip, password):
    req = urllib.request.Request(AUTH_URL,
        data=json.dumps({"nip": nip, "password": password}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    if not data.get("success"):
        raise Exception(data.get("message", "Login gagal"))
    return data["data"]["access_token"], data["data"]["user"]

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

def api_post_multipart(token, path, data_dict, file_bytes, file_field, num_photos):
    url = f"{API_BASE}{path}"
    inner = json.dumps(data_dict)
    body_parts = [f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="data"\r\n\r\n{inner}\r\n'.encode()]
    for i in range(num_photos):
        name = f"foto{i+1}.jpg" if num_photos > 1 else "foto.jpg"
        body_parts.append(f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{name}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
        body_parts.append(file_bytes if isinstance(file_bytes, bytes) else file_bytes)
        body_parts.append(b'\r\n')
    body_parts.append(f'--{BOUNDARY}--\r\n'.encode())
    body = b''.join(body_parts)
    
    req = urllib.request.Request(url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}", "Authorization": f"Bearer {token}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# ============================================================
# MENU SYSTEM
# ============================================================

def fetch_history_bulk(token, data_type, gi_id, date_str, days_back=14, _cache={}):
    """
    Fetch 14 hari data SEKALI saja, return dict dengan semua data periode dan weekday/weekend flag.
    Reuse hasil ini untuk multiple item agar tidak refetch.
    
    Cached per (data_type, gi_id, date_str) — call kedua di hari yang sama instant.
    """
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

def smart_suggest_value(token, data_type, item_id, periode, date_str, days_back=14):
    """
    Smart suggest berdasarkan:
    1. Weekday vs weekend pattern
    2. 14 hari historis
    3. Range clamping
    4. Kelipatan 5 untuk beban
    """
    from datetime import timedelta, datetime as dt
    from concurrent.futures import ThreadPoolExecutor
    
    today = dt.strptime(date_str, "%Y-%m-%d")
    is_target_weekend = today.weekday() >= 5
    
    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
    }
    
    def fetch_day(offset):
        d = today - timedelta(days=offset)
        return offset, d, d.weekday() >= 5, api_get(token, paths[data_type], 
            {"garduIndukId": 222, "date": d.strftime("%Y-%m-%d")})
    
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
    """Login, return token, user info, dan gi_id."""
    nip = config.get("nip")
    password = config.get("password")
    if not nip or not password:
        print(f"  {C['RE']}✗ Konfigurasi belum di-setup. Jalankan setup dulu.{C['R']}")
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
    
    for item in items:
        nama = item.get("nama", "?")
        item_id = item.get("id", "?")
        data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
        entries = item.get(data_key, [])
        periods = sorted([e["periode"] for e in entries])
        empty = [p for p in range(24) if p not in periods]
        
        if data_type == "tegangan-trafo":
            is_ps = "PS" if item.get("isPS") else "GI"
            if entries:
                mv_vals = [e["mv"] for e in entries]
                hv_vals = [e["hv"] for e in entries]
                print(f"  [{item_id}] {nama} ({is_ps}) | MV:{min(mv_vals):.1f}-{max(mv_vals):.1f}kV HV:{min(hv_vals)}-{max(hv_vals)}kV | {len(periods)}/24")
            else:
                print(f"  [{item_id}] {nama} ({is_ps}) | 0/24")
        else:
            i_max = item.get("iMax", "?")
            trafo = item.get("trafo", {}).get("nama", "")
            status = item.get("statusCB", "")
            extra = f"iMax={i_max}A"
            if trafo:
                extra += f" | {trafo}"
            if status:
                extra += f" | CB={status}"
            if entries:
                values = [e["beban"] for e in entries]
                print(f"  [{item_id}] {nama} ({extra}) | {min(values)}-{max(values)}A | {len(periods)}/24")
            else:
                print(f"  [{item_id}] {nama} ({extra}) | 0/24")
        
        if empty:
            print(f"       Kosong: {empty}")
    
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
    
    # Input nilai dengan saran SMART (weekday/weekend, 14h history, kelipatan 5)
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
        # Beban: SMART SUGGEST (weekday/weekend aware)
        sys.stdout.write(f"    🧠 Menganalisis pola 14 hari... ")
        sys.stdout.flush()
        smart_val, info = smart_suggest_value(token, data_type, item_id, per, date_str)
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
    
    # Build data
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    data_dict = {
        ep["id_field"]: item_id,
        "timezone": "Asia/Jakarta",
        "periode": per,
        "tanggal": dt.day,
        "bulan": dt.month - 1,
        "tahun": dt.year,
        "durasi": 0.1,
        ep["value_field"]: value,
    }
    
    if data_type == "tegangan-trafo":
        data_dict["hv"] = extra_values.get("hv", 150)
        data_dict["fotoHV"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
        data_dict["fotoMV"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
    else:
        data_dict["foto"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
    
    print("\n  Mengirim...")
    status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"])
    
    if result.get("success"):
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
        
        print(f"    🧠 Menganalisis pola 14 hari ({day_label})...")
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
        
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        success = 0
        fail = 0
        total = len(valid_periods)
        for i, per in enumerate(valid_periods, 1):
            mv, hv, _ = teg_suggestions[per]
            data_dict = {
                ep["id_field"]: item["id"],
                "timezone": "Asia/Jakarta",
                "periode": per,
                "tanggal": dt.day,
                "bulan": dt.month - 1,
                "tahun": dt.year,
                "durasi": 0.1,
                ep["value_field"]: mv,
                "hv": hv,
                "fotoHV": {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846},
                "fotoMV": {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846},
            }
            status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"])
            ok = result.get("success")
            detail = f"MV={mv} HV={hv}" if ok else str(result.get("message", "?"))[:30]
            if ui:
                sys.stdout.write("\r" + ui.fmt_progress_line(i, total, f"P{per:02d}", ok=ok, detail=detail))
                sys.stdout.flush()
            if ok:
                success += 1
            else:
                fail += 1
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
        # Pakai periode pertama kosong sebagai referensi
        ref_periode = empty_periods[0]
        print(f"    🧠 Menganalisis pola 14 hari untuk P{ref_periode:02d}...")
        smart_val, info = smart_suggest_value(token, data_type, item["id"], ref_periode, date_str)
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
        data_dict = {
            ep["id_field"]: item["id"],
            "timezone": "Asia/Jakarta",
            "periode": per,
            "tanggal": dt.day,
            "bulan": dt.month - 1,
            "tahun": dt.year,
            "durasi": 0.1,
            ep["value_field"]: value,
            "foto": {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846},
        }
        status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"])
        ok = result.get("success")
        detail = f"{value}A" if ok else str(result.get("message", "?"))[:30]
        if ui:
            sys.stdout.write("\r" + ui.fmt_progress_line(i, total, f"P{per:02d}", ok=ok, detail=detail))
            sys.stdout.flush()
        if ok:
            success += 1
        else:
            fail += 1
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
    print(f"  🧠 Menganalisis pola 14 hari ({day_label})...")
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
    
    # Submit semua (live progress)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    success = 0
    fail = 0
    total = len(valid_items)
    failures = []  # (nama, reason)

    for i, it in enumerate(valid_items, 1):
        s = suggestions[it["id"]]
        data_dict = {
            ep["id_field"]: it["id"],
            "timezone": "Asia/Jakarta",
            "periode": per,
            "tanggal": dt.day,
            "bulan": dt.month - 1,
            "tahun": dt.year,
            "durasi": 0.1,
        }
        if data_type == "tegangan-trafo":
            mv_val, hv_val = s
            data_dict[ep["value_field"]] = mv_val
            data_dict["hv"] = hv_val
            data_dict["fotoHV"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
            data_dict["fotoMV"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
            detail = f"MV={mv_val} HV={hv_val}"
        else:
            value = s[0]
            data_dict[ep["value_field"]] = value
            data_dict["foto"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
            detail = f"{value}A"

        try:
            status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"])
            ok = result.get("success")
            if not ok:
                reason = str(result.get("message", "error"))[:30]
                failures.append((it["nama"], reason))
                detail = reason
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
    if ui:
        sys.stdout.write("\n")

    # Detail failures (di baris sendiri agar tidak tertimpa \r)
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

def _cron_command():
    """Baris cron untuk auto mode."""
    py = os.path.join(SCRIPT_DIR, ".venv", "bin", "python3")
    script = os.path.join(SCRIPT_DIR, "superi_auto.py")
    log = os.path.join(SCRIPT_DIR, "auto_log.txt")
    # Fallback kalau venv tidak ada
    if not os.path.exists(py):
        py = sys.executable
    return f"5 * * * * {py} {script} >> {log} 2>&1 {CRON_MARKER}"

def cron_is_installed():
    """Cek apakah cron job sudah terpasang."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        return CRON_MARKER in result.stdout
    except Exception:
        return False

def cron_install():
    """Pasang cron job (macOS/Linux)."""
    try:
        # Ambil crontab existing
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        # Hapus baris lama SUPER-I-AUTO kalau ada
        lines = [l for l in existing.splitlines() if CRON_MARKER not in l]
        lines.append(_cron_command())
        new_crontab = "\n".join(lines) + "\n"
        # Tulis balik
        proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
        return proc.returncode == 0, proc.stderr
    except Exception as e:
        return False, str(e)

def cron_uninstall():
    """Hapus cron job."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            return True, ""  # tidak ada crontab
        lines = [l for l in result.stdout.splitlines() if CRON_MARKER not in l]
        new_crontab = ("\n".join(lines) + "\n") if lines else ""
        proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
        return proc.returncode == 0, proc.stderr
    except Exception as e:
        return False, str(e)

# --- Windows Task Scheduler ---
WIN_TASK_NAME = "SUPER-I-Auto-Input"

def win_task_is_installed():
    try:
        result = subprocess.run(["schtasks", "/query", "/tn", WIN_TASK_NAME],
                                capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def win_task_install():
    """Pasang Windows Task Scheduler (tiap 5 menit, window dicek internal)."""
    bat = os.path.join(SCRIPT_DIR, "superi.bat")
    task_log = os.path.join(SCRIPT_DIR, "auto_task_log.txt")
    task_cmd = f'cmd /c cd /d "{SCRIPT_DIR}" && "{bat}" auto >> "{task_log}" 2>&1'
    try:
        # Jalankan tiap 5 menit. superi_auto.py sendiri yang cek window jam dan skip duplikat.
        proc = subprocess.run([
            "schtasks", "/create", "/tn", WIN_TASK_NAME,
            "/tr", task_cmd,
            "/sc", "minute", "/mo", "5",
            "/f"
        ], capture_output=True, text=True)
        return proc.returncode == 0, proc.stderr or proc.stdout
    except Exception as e:
        return False, str(e)

def win_task_uninstall():
    try:
        proc = subprocess.run(["schtasks", "/delete", "/tn", WIN_TASK_NAME, "/f"],
                              capture_output=True, text=True)
        return proc.returncode == 0, proc.stderr or proc.stdout
    except Exception as e:
        return False, str(e)

def scheduler_is_installed():
    """Cek apakah scheduler (cron/task) sudah terpasang sesuai OS."""
    if platform.system() == "Windows":
        return win_task_is_installed()
    return cron_is_installed()

def scheduler_install_menu():
    """Menu install/hapus jadwal otomatis sesuai OS."""
    is_win = platform.system() == "Windows"
    os_name = "Windows Task Scheduler" if is_win else "cron"
    installed = scheduler_is_installed()
    
    clear()
    header(f"⚙  JADWAL OTOMATIS · {os_name}")
    print()
    if installed:
        print(f"  {C['G']}● Jadwal otomatis SUDAH terpasang{C['R']}")
        print(f"  {C['D']}Sistem akan memanggil auto mode tiap 5 menit (window dicek internal).{C['R']}")
    else:
        print(f"  {C['RE']}○ Jadwal otomatis BELUM terpasang{C['R']}")
    print()
    print(f"  {C['C']}[1]{C['R']} {'Pasang ulang' if installed else 'Pasang'} jadwal otomatis")
    if installed:
        print(f"  {C['C']}[2]{C['R']} {C['RE']}Hapus{C['R']} jadwal otomatis")
    print(f"  {C['RE']}[0]{C['R']} Kembali")
    print()
    print(f"  {C['D']}{'─' * 56}{C['R']}")
    choice = input(f"  {C['B']}Pilih ▸ {C['R']}").strip()
    
    if choice == '1':
        print(f"\n  {C['Y']}Memasang jadwal...{C['R']}")
        if is_win:
            ok, msg = win_task_install()
        else:
            ok, msg = cron_install()
        if ok:
            print(f"  {C['G']}✓ Jadwal otomatis terpasang!{C['R']}")
            print(f"  {C['D']}Sistem akan jalankan auto mode tiap 5 menit.{C['R']}")
            print(f"  {C['D']}Pastikan Auto Mode AKTIF + komputer menyala di window jam.{C['R']}")
            print(f"  {C['D']}Log Task Scheduler: {os.path.join(SCRIPT_DIR, 'auto_task_log.txt')}{C['R']}")
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
            print(f"  {C['G']}✓ Jadwal otomatis dihapus{C['R']}")
        else:
            print(f"  {C['RE']}✗ Gagal: {msg}{C['R']}")
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
            try:
                s = int(input(f"  Mulai (jam 0-23) [{win_start}]: ").strip() or win_start)
                e = int(input(f"  Akhir (jam 0-23) [{win_end}]: ").strip() or win_end)
                if 0 <= s <= 23 and 0 <= e <= 23:
                    cfg["auto_window_start"] = s
                    cfg["auto_window_end"] = e
                    save_config(cfg)
                    print(f"\n  {C['G']}✓ Window: {s:02d}:00 - {e:02d}:00{C['R']}")
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

def main():
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
        print(f"  {C['D']}{C['B']}PENGATURAN{C['R']}")
        print(f"  {C['C']}[G]{C['R']} Ganti Tanggal   {C['C']}[L]{C['R']} Login Ulang   {C['C']}[S]{C['R']} Setup   {C['RE']}[0]{C['R']} Keluar")
        print()
        # Auto mode status
        _auto_cfg = load_config()
        _auto_on = _auto_cfg.get("auto_enabled", False)
        _auto_badge = f"{C['G']}ON{C['R']}" if _auto_on else f"{C['RE']}OFF{C['R']}"
        print(f"  {C['C']}[D]{C['R']} ⏰ Auto Mode [{_auto_badge}]")
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
            elif choice == 'd':
                auto_mode_menu()
                config = load_config()
        except Exception as e:
            print(f"\n  ✗ Error: {e}")
            input(f"  {C['D']}[Enter]{C['R']}")

if __name__ == "__main__":
    main()
