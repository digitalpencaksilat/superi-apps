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
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
BASE_URL = "https://super-i-app.plnes.co.id"
API_BASE = f"{BASE_URL}/api"
AUTH_URL = f"{API_BASE}/auth/login-mobile"
BOUNDARY = "----FormBoundary7MA4YWxkTrZu0gW"
CONFIG_FILE = os.path.expanduser("~/.superi_config.json")

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
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(cfg):
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
    Returns: (mv_suggest, hv_suggest, info_str) atau (None, None, None)
    """
    if item_id not in cache:
        return None, None, None
    
    pdata = cache[item_id]["periode_data"].get(periode)
    if not pdata or not pdata["all"]:
        return None, None, None
    
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
    
    # MV: rata-rata weighted (50% pattern + 50% base), round 2 desimal
    base_mv = sum(all_mv) / len(all_mv)
    pattern_mv = sum(pat_mv) / len(pat_mv)
    smart_mv = 0.5 * pattern_mv + 0.5 * base_mv
    smart_mv = round(smart_mv, 2)
    
    # Clamp MV ke range historis
    if pat_mv:
        smart_mv = max(min(pat_mv), min(max(pat_mv), smart_mv))
        smart_mv = round(smart_mv, 2)
    
    # HV: rata-rata weighted, round integer
    base_hv = sum(all_hv) / len(all_hv)
    pattern_hv = sum(pat_hv) / len(pat_hv)
    smart_hv = 0.5 * pattern_hv + 0.5 * base_hv
    smart_hv = round(smart_hv)
    
    # Clamp HV ke range
    if pat_hv:
        smart_hv = max(min(pat_hv), min(max(pat_hv), smart_hv))
    
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

def header(title):
    print("╔" + "═" * 58 + "╗")
    print(f"║  {title:<54}  ║")
    print("╚" + "═" * 58 + "╝")

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
        print("  ✗ Pilihan tidak valid!")

def input_with_default(prompt, default=""):
    if default:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"  {prompt}: ").strip()

def confirm(msg):
    return input(f"  {msg} (y/n): ").strip().lower() == 'y'

# ============================================================
# WORKFLOW
# ============================================================

def setup_config():
    """Setup kredensial pertama kali."""
    clear()
    header("SETUP AWAL")
    print("  Masukkan kredensial SUPER-I APP (disimpan di ~/.superi_config.json)")
    print("  Gardu Induk akan otomatis terdeteksi dari profil.")
    print()
    nip = input("  NIP: ").strip()
    password = input("  Password: ").strip()
    
    config = {"nip": nip, "password": password}
    save_config(config)
    print()
    print("  ✓ Konfigurasi tersimpan!")
    input("  Tekan Enter untuk lanjut...")

def do_login(config):
    """Login, return token, user info, dan gi_id."""
    nip = config.get("nip")
    password = config.get("password")
    if not nip or not password:
        print("  ✗ Konfigurasi belum di-setup. Jalankan setup dulu.")
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
        print(f"  ✗ Login gagal: {e}")
        return None, None, None

def show_data(token, data_type, gi_id, date_str):
    """Tampilkan data dan periode kosong."""
    ep = ENDPOINTS[data_type]
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result["data"].get("items", [])
    
    if not items:
        print(f"  Tidak ada data untuk {date_str}")
        return
    
    clear()
    header(f"{ep['label']} - {date_str}")
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
    input("  Tekan Enter untuk kembali...")

def input_single(token, data_type, gi_id, date_str, user_info):
    """Input data untuk satu target spesifik."""
    ep = ENDPOINTS[data_type]
    
    # Ambil daftar item
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result["data"].get("items", [])
    
    if not items:
        print(f"  Tidak ada item untuk {date_str}")
        input("  Tekan Enter...")
        return
    
    clear()
    header(f"INPUT {ep['label']}")
    print()
    
    # Tampilkan daftar item
    for i, item in enumerate(items, 1):
        nama = item.get("nama", "?")
        item_id = item.get("id", "?")
        data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
        entries = item.get(data_key, [])
        periods = [e["periode"] for e in entries]
        empty = [p for p in range(24) if p not in periods]
        
        # Tandai CB OFF - skip untuk input
        cb_off = item.get('statusCB') == 'OFF'
        tag = " ⛔ CB OFF - SKIP" if cb_off else ""
        print(f"  [{i}] {nama} (ID:{item_id}) - {len(periods)}/24 terisi{tag}")
        if empty and not cb_off:
            print(f"      Kosong: {empty}")
    print()
    
    try:
        idx = int(input("  Pilih nomor item: ").strip()) - 1
        if idx < 0 or idx >= len(items):
            print("  ✗ Tidak valid!")
            input("  Tekan Enter...")
            return
    except ValueError:
        print("  ✗ Tidak valid!")
        input("  Tekan Enter...")
        return
    
    item = items[idx]
    item_id = item["id"]
    nama = item["nama"]
    
    # Tolak CB OFF
    if item.get('statusCB') == 'OFF':
        print(f"\n  ⛔ {nama} CB OFF — tidak bisa input beban!")
        print("  (Circuit Breaker mati, tidak ada arus)")
        input("  Tekan Enter...")
        return
    
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
    entries = item.get(data_key, [])
    periods_filled = [e["periode"] for e in entries]
    empty_periods = [p for p in range(24) if p not in periods_filled]
    
    print(f"\n  Target: {nama} (ID:{item_id})")
    
    # Tampilkan data existing untuk referensi
    if entries:
        print(f"  Data existing:")
        if data_type == "tegangan-trafo":
            for e in sorted(entries, key=lambda x: x["periode"]):
                print(f"    P{e['periode']:02d}: HV={e['hv']}kV, MV={e['mv']}kV")
        else:
            for e in sorted(entries, key=lambda x: x["periode"]):
                print(f"    P{e['periode']:02d}: {e['beban']}A")
        
        if data_type == "beban-penyulang" or data_type == "beban-trafo":
            values = [e["beban"] for e in entries]
            avg = sum(values) / len(values)
            print(f"    Range: {min(values)}-{max(values)}A | Rata2: {avg:.0f}A")
    
    if not empty_periods:
        print(f"\n  ✓ Semua periode sudah terisi (24/24)!")
        input("  Tekan Enter...")
        return
    
    print(f"\n  Periode kosong: {empty_periods}")
    
    # Pilih periode
    try:
        per = int(input("  Periode yang akan diisi: ").strip())
        if per not in empty_periods and per not in range(24):
            print("  ✗ Periode tidak valid!")
            input("  Tekan Enter...")
            return
    except ValueError:
        print("  ✗ Tidak valid!")
        input("  Tekan Enter...")
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
        print(f"    🧠 Menganalisis pola 14 hari...")
        smart_val, info = smart_suggest_value(token, data_type, item_id, per, date_str)
        if smart_val is not None:
            suggested = f" [smart: {smart_val}A]"
            print(f"    → Smart suggest: {smart_val}A ({info})")
        else:
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
        mv_str = input(f"  MV (kV) [suggested: {suggested_mv}]: ").strip()
        mv = float(mv_str) if mv_str else float(suggested_mv)
        hv_str = input(f"  HV (kV) [suggested: {suggested_hv}]: ").strip()
        hv = float(hv_str) if hv_str else float(suggested_hv)
        value = mv
        extra_values = {"hv": hv}
    else:
        val_str = input(f"  Nilai (Ampere){suggested}: ").strip()
        if not val_str and suggested:
            val_str = suggested.split(": ")[1].replace("A]", "")
        value = float(val_str)
        extra_values = {}
    
    if not confirm(f"\n  Input {nama} periode {per}: {value}{ep['unit']}?"):
        print("  Dibatalkan.")
        input("  Tekan Enter...")
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
        print(f"  ✓ BERHASIL! ID: {result['data'].get('id')}")
    else:
        msg = result.get("message", str(result))
        if isinstance(msg, list):
            msg = ", ".join(msg)
        print(f"  ✗ Gagal ({status}): {msg}")
    
    print()
    input("  Tekan Enter untuk kembali...")

def batch_fill(token, data_type, gi_id, date_str, user_info):
    """Isi semua periode kosong untuk satu item."""
    ep = ENDPOINTS[data_type]
    
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result["data"].get("items", [])
    
    clear()
    header(f"BATCH FILL {ep['label']}")
    print()
    
    for i, item in enumerate(items, 1):
        data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
        entries = item.get(data_key, [])
        periods = [e["periode"] for e in entries]
        empty = [p for p in range(24) if p not in periods]
        cb_off = item.get('statusCB') == 'OFF'
        tag = " ⛔ SKIP" if cb_off else ""
        print(f"  [{i}] {item['nama']} - {len(periods)}/24, kosong: {empty if empty else '∅'}{tag}")
    
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
        input("  Tekan Enter...")
        return
    
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
    entries = item.get(data_key, [])
    periods_filled = [e["periode"] for e in entries]
    empty_periods = [p for p in range(24) if p not in periods_filled]
    
    if not empty_periods:
        print(f"\n  ✓ {item['nama']} sudah 24/24!")
        input("  Tekan Enter...")
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
        # Tegangan: tetap pakai logic lama
        if entries:
            print(f"    → Saran dari P{last_entry['periode']:02d}: MV={last_mv}kV, HV={last_hv}kV")
            mv_str = input(f"  MV (kV) [P{last_entry['periode']:02d}: {last_mv}]: ").strip()
            mv = float(mv_str) if mv_str else last_mv
            hv_str = input(f"  HV (kV) [P{last_entry['periode']:02d}: {last_hv}]: ").strip()
            hv = float(hv_str) if hv_str else last_hv
        else:
            mv_str = input(f"  MV (kV): ").strip()
            mv = float(mv_str)
            hv_str = input(f"  HV (kV): ").strip()
            hv = float(hv_str)
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
    
    if not confirm(f"\n  Isi {len(empty_periods)} periode dgn nilai {mv if data_type == 'tegangan-trafo' else value}{ep['unit']}?"):
        return
    
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    success = 0
    for per in empty_periods:
        data_dict = {
            ep["id_field"]: item["id"],
            "timezone": "Asia/Jakarta",
            "periode": per,
            "tanggal": dt.day,
            "bulan": dt.month - 1,
            "tahun": dt.year,
            "durasi": 0.1,
            ep["value_field"]: mv if data_type == "tegangan-trafo" else value,
        }
        if data_type == "tegangan-trafo":
            data_dict["hv"] = hv
            data_dict["fotoHV"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
            data_dict["fotoMV"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
        else:
            data_dict["foto"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
        
        status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"])
        if result.get("success"):
            success += 1
            print(f"    P{per:02d} ✓")
        else:
            msg = result.get("message", "?")
            print(f"    P{per:02d} ✗ ({msg[:50]})")
    
    print(f"\n  ✓ {success}/{len(empty_periods)} berhasil!")
    input("  Tekan Enter...")

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
    header(f"⚡ Batch Fill per Jam — {ep['label']}")
    
    # Fetch data hari ini
    result = api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result.get("data", {}).get("items", [])
    if not items:
        print("  Tidak ada data.")
        input("  Tekan Enter...")
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
    
    # Tampilkan grid periode
    print("\n  Periode | Kosong | Status")
    print("  " + "─" * 40)
    has_empty = False
    for p in range(24):
        count = len(empty_by_periode[p])
        if count > 0:
            has_empty = True
            print(f"  P{p:02d}:00  | {count:3d} item | ⚡ Bisa batch")
        else:
            print(f"  P{p:02d}:00  |   0 item | ✓ Penuh")
    
    if not has_empty:
        print("\n  ✓ Semua periode sudah penuh!")
        input("  Tekan Enter...")
        return
    
    # Pilih periode
    try:
        per = int(input("\n  Pilih periode (jam): ").strip())
        if per < 0 or per > 23:
            print("  ✗ Periode harus 0-23!")
            input("  Tekan Enter...")
            return
    except ValueError:
        return
    
    empty_items = empty_by_periode[per]
    if not empty_items:
        print(f"\n  ✓ Periode P{per:02d} sudah penuh!")
        input("  Tekan Enter...")
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
    
    # Tampilkan tabel dengan suggest
    print(f"\n  {'No':<4}{'Nama':<20}{'Suggest':<12}{'Info'}")
    print(f"  {'─' * 55}")
    
    for i, it in enumerate(empty_items, 1):
        nama = it["nama"][:18]
        if data_type == "tegangan-trafo":
            # Smart suggest tegangan per-periode dari histori (rata-rata, BUKAN copy periode sebelumnya)
            mv, hv, info = smart_suggest_tegangan_from_cache(cache, it["id"], per, is_weekend)
            if mv is not None:
                print(f"  {i:<4}{nama:<20}MV={mv} HV={hv}  {info}")
                suggestions[it["id"]] = (mv, hv)
            else:
                print(f"  {i:<4}{nama:<20}?           (tidak ada histori)")
                suggestions[it["id"]] = (None, None)
        else:
            val, info = suggestions.get(it["id"], (None, None))
            if val is not None:
                print(f"  {i:<4}{nama:<20}{val:>5}A      {info}")
            else:
                print(f"  {i:<4}{nama:<20}    ?A      (tidak ada data)")
    
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
        print("  ✗ Tidak ada item dengan nilai valid!")
        input("  Tekan Enter...")
        return
    
    if not confirm(f"\n  Input {len(valid_items)} item di periode P{per:02d}?"):
        print("  Dibatalkan.")
        input("  Tekan Enter...")
        return
    
    # Submit semua
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    success = 0
    fail = 0
    
    for it in valid_items:
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
        else:
            value = s[0]
            data_dict[ep["value_field"]] = value
            data_dict["foto"] = {"date": f"{date_str}T{per:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
        
        try:
            status, result = api_post_multipart(token, ep["input"], data_dict, DUMMY_JPEG, ep["file_field"], ep["num_photos"])
            if result.get("success"):
                success += 1
                print(f"    ✓ {it['nama']}")
            else:
                fail += 1
                print(f"    ✗ {it['nama']}: {result.get('message', 'error')}")
        except Exception as e:
            fail += 1
            print(f"    ✗ {it['nama']}: {e}")
    
    print(f"\n  ═══════════════════════════════")
    print(f"  ✓ Berhasil: {success} | ✗ Gagal: {fail}")
    input("  Tekan Enter...")

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
    
    while True:
        clear()
        header("SUPER-I APP - Data Input Tool")
        
        # Tampilkan status
        if token and user:
            print(f"  User: {user['namaLengkap']} | Role: {', '.join(user['roles'])}")
            print(f"  GI: {gi_id} | Tanggal: {date_str}")
        else:
            print(f"  GI: {gi_id} | Tanggal: {date_str}")
            print(f"  NIP: {config.get('nip', '?')}")
        print()
        
        print("  ═══════════ DATA ═══════════")
        print("  [1] Lihat Beban Penyulang")
        print("  [2] Lihat Beban Trafo")
        print("  [3] Lihat Tegangan Trafo")
        print()
        print("  ═══════════ INPUT ═══════════")
        print("  [4] Input Beban Penyulang")
        print("  [5] Input Beban Trafo")
        print("  [6] Input Tegangan Trafo")
        print()
        print("  ═══════════ BATCH (per Item) ═══════════")
        print("  [7] Batch Fill Beban Penyulang")
        print("  [8] Batch Fill Beban Trafo")
        print("  [9] Batch Fill Tegangan Trafo")
        print()
        print("  ═══════════ BATCH (per Periode/Jam) ═══════════")
        print("  [A] Batch Fill Beban Penyulang per Jam")
        print("  [B] Batch Fill Beban Trafo per Jam")
        print("  [C] Batch Fill Tegangan Trafo per Jam")
        print()
        print("  ═══════════ LAIN ═══════════")
        print("  [G] Ganti Tanggal")
        print("  [L] Login Ulang")
        print("  [S] Setup Ulang Kredensial")
        print("  [0] Keluar")
        print()
        
        choice = input("  Pilih > ").strip().lower()
        
        if choice == '0':
            print("\n  Selamat bekerja!")
            break
        
        # Login if needed
        if choice in '123456789abc' and not token:
            print("\n  Login...")
            token, user, gi_id = do_login(config)
            if not token:
                input("  Tekan Enter...")
                continue
        
        try:
            if choice == 'g':
                date_str = input("  Tanggal (YYYY-MM-DD): ").strip() or date_str
            elif choice == 'l':
                token, user, gi_id = do_login(config)
                input("  Tekan Enter...")
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
        except Exception as e:
            print(f"\n  ✗ Error: {e}")
            input("  Tekan Enter...")

if __name__ == "__main__":
    main()
