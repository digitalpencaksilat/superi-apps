#!/usr/bin/env python3
"""
SUPER-I APP → Portal PLN Sync Tool
====================================
Otomatis fetch data dari SUPER-I APP API lalu sync ke Portal PLN APD Jakarta.

Usage:
  superi sync                    # Menu interaktif
  superi sync --type all --jam 08       # Sync semua tipe jam 08
  superi sync --type penyulang --jam 09  # Sync beban penyulang jam 09
  superi sync --type trafo --jam 08-10   # Sync beban trafo jam 08 s/d 10
  superi sync --type tegangan --jam 08   # Sync tegangan trafo jam 08
  superi sync --dry-run                  # Preview tanpa nulis

Tanggal default: hari ini. Override: --date 2026-06-19
"""

import json
import sys
import time
import os
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, List, Optional, Tuple

__version__ = "1.0.0"

# ============ PATHS ============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import cli_render  # shared pure-string render helpers (fmt_progress_bar, render_sync_summary, …)

# ============ CONFIG LOADER ============
# Credentials & config dibaca dari .superi_config.json (gitignored).
# Gunakan .superi_config.example.json sebagai template.
def _load_config():
    cfg_path = os.path.join(SCRIPT_DIR, ".superi_config.json")
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r") as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"  \033[91m✗ Gagal membaca .superi_config.json: {e}\033[0m")
    return cfg

_CFG = _load_config()

def _get(key: str, env_key: str, default: str = "") -> str:
    """Priority: ENV var → config file → default."""
    return os.environ.get(env_key) or _CFG.get(key) or default

# ============ SUPER-I API CONFIG ============
SUPER_I_API = "https://super-i-app.plnes.co.id/api"
SUPER_I_AUTH = f"{SUPER_I_API}/auth/login-mobile"
SUPER_I_NIP = _get("nip", "SUPERI_NIP")
SUPER_I_PASS = _get("password", "SUPERI_PASSWORD")
SUPER_I_GI_ID = int(_get("gi_id", "SUPERI_GI_ID", "222"))  # GI MANGGARAI di SUPER-I

SUPER_I_ENDPOINTS = {
    "penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
    "trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
    "tegangan": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
}

# ============ PORTAL PLN CONFIG ============
PORTAL_URL = _get("portal_url", "PORTAL_URL", "http://10.3.187.6/apdjakarta")
PORTAL_USER = _get("portal_user", "PORTAL_USER")
PORTAL_PASS = _get("portal_password", "PORTAL_PASSWORD")
PORTAL_GI_ID = _get("portal_gi_id", "PORTAL_GI_ID", "143")  # GI MANGGARAI di Portal PLN

PORTAL_ENDPOINTS = {
    "penyulang": {
        "get": "/opdistbeban/beban_penyulang_c/get_beban_penyulang",
        "update": "/opdistbeban/beban_penyulang_c/update_beban",
    },
    "trafo": {
        "get": "/opdistbeban/beban_trafo_c/get_beban_trafo",
        "update": "/opdistbeban/beban_trafo_c/update_beban",
    },
    "tegangan": {
        "get": "/opdistbeban/teg_trafo_c/get_teg_trafo",
        "update": "/opdistbeban/teg_trafo_c/update_beban",
    },
}

# ============ UI ============
R = '\033[0m'; B = '\033[1m'; G = '\033[92m'; Y = '\033[93m'; RE = '\033[91m'; C = '\033[96m'; D = '\033[2m'; W = '\033[97m'

def header(t):
    bar = '━' * 60
    print(f"\n{C}{bar}{R}\n  {B}{W}{t}{R}\n{C}{bar}{R}")
def ok(t): print(f"  {G}✓ {t}{R}")
def err(t): print(f"  {RE}✗ {t}{R}")
def info(t): print(f"  {C}ℹ {t}{R}")
def warn(t): print(f"  {Y}⚠ {t}{R}")

# ============ PROGRESS (compact, mirip superi cli) ============
# Helper render (fmt_progress_bar, render_sync_summary) ada di cli_render.py (shared, pure-string).

def live_progress(done, total, name=""):
    """Progress bar 1-baris yang di-overwrite (\\r + erase-to-end \\033[K). Plain, tanpa ANSI — mirip cli fmt_progress_line."""
    nm = name[:18].ljust(18) if name else ""
    tail = f"  {nm}" if nm else ""
    sys.stdout.write(f"\r  {cli_render.fmt_progress_bar(done, total)}{tail} ✓\033[K")
    sys.stdout.flush()

def summary_box(label, ok_count, fail_count, skip_count, total):
    """Box ringkasan sync — pakai cli_render.render_sync_summary, plain (tanpa ANSI, mirip cli render_summary_box)."""
    for line in cli_render.render_sync_summary(label, ok_count, fail_count, skip_count, total):
        print(line)

# ============ SUPER-I API CLIENT ============
def superi_login() -> Optional[str]:
    """Login ke SUPER-I API, return token."""
    try:
        req = urllib.request.Request(SUPER_I_AUTH,
            data=json.dumps({"nip": SUPER_I_NIP, "password": SUPER_I_PASS}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.loads(resp.read())
        if d.get("success"):
            return d["data"]["access_token"]
    except Exception as e:
        err(f"SUPER-I login error: {e}")
    return None

def superi_get(path: str, token: str, params: dict = None):
    """GET request ke SUPER-I API."""
    url = f"{SUPER_I_API}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def fetch_superi_data(data_type: str, token: str, date_str: str) -> Dict:
    """
    Fetch data dari SUPER-I API.
    Returns: {nama: [val_per_jam_0..23], ...} untuk beban
             {nama: {mv: [...], hv: [...]}, ...} untuk tegangan
    """
    ep = SUPER_I_ENDPOINTS[data_type]
    status, data = superi_get(ep, token, params={"garduIndukId": SUPER_I_GI_ID, "date": date_str})
    
    if status != 200:
        err(f"SUPER-I fetch failed: HTTP {status}")
        return {}
    
    items = data.get("data", {}).get("items", [])
    result = {}
    
    for item in items:
        nama = item.get("nama", "").strip()
        if not nama:
            continue
        
        if data_type == "tegangan":
            entries = item.get("tegangan", [])
            mv = [None] * 24
            hv = [None] * 24
            for e in entries:
                p = e.get("periode", -1)
                if 0 <= p < 24:
                    mv[p] = e.get("mv")
                    hv[p] = e.get("hv")
            result[nama] = {"mv": mv, "hv": hv}
        else:
            entries = item.get("beban", [])
            jams = [None] * 24
            for e in entries:
                p = e.get("periode", -1)
                if 0 <= p < 24:
                    jams[p] = e.get("beban")
            result[nama] = jams
    
    return result

# ============ PORTAL PLN CLIENT ============
try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

class PortalPLN:
    def __init__(self):
        if not REQUESTS_OK:
            raise ImportError("requests library needed. Run: .venv/bin/pip install requests")
        self.session = requests.Session()
    
    def login(self) -> bool:
        try:
            r = self.session.post(f"{PORTAL_URL}/login/validate",
                data={'userid': PORTAL_USER, 'password': PORTAL_PASS},
                allow_redirects=True, timeout=10)
            return r.status_code == 200
        except:
            return False
    
    def fetch_grid(self, data_type: str, date_str: str) -> Dict:
        ep = PORTAL_ENDPOINTS[data_type]["get"]
        try:
            r = self.session.get(f"{PORTAL_URL}{ep}",
                params={'gi': PORTAL_GI_ID, 'dt1': f"{date_str} 00:00:00"}, timeout=15)
            if r.status_code != 200:
                return {}
            data = r.json()
            grid = {}
            for row in data:
                key = row.get('feeder') or row.get('no_trafo') or ''
                key = key.strip()
                if key:
                    grid[key] = row
            return grid
        except:
            return {}
    
    def update_cell(self, data_type: str, rowdata: Dict, col: str, value) -> bool:
        ep = PORTAL_ENDPOINTS[data_type]["update"]
        params = {'col': col}
        for k, v in rowdata.items():
            params[k] = '' if v is None else v
        params[col] = value
        try:
            r = self.session.get(f"{PORTAL_URL}{ep}", params=params, timeout=10)
            if r.status_code == 200:
                resp = r.json()
                return resp.get('status') == 'success'
        except:
            pass
        return False

# ============ SYNC ENGINE ============
def do_sync(data_type: str, jam_start: int, jam_end: int, date_str: str, dry_run: bool = True):
    """Full sync: fetch SUPER-I → push Portal PLN."""
    
    type_labels = {"penyulang": "Beban Penyulang", "trafo": "Beban Trafo", "tegangan": "Tegangan Trafo"}
    header(f"SYNC {type_labels[data_type]}")
    
    # 1. SUPER-I: fetch
    info("SUPER-I APP: Logging in...")
    token = superi_login()
    if not token:
        err("SUPER-I login failed")
        return False
    ok("SUPER-I login OK")
    
    info(f"SUPER-I APP: Fetching {data_type} data...")
    superi_data = fetch_superi_data(data_type, token, date_str)
    if not superi_data:
        err("No data from SUPER-I")
        return False
    ok(f"Got {len(superi_data)} items from SUPER-I")
    
    # 2. Portal PLN: login + fetch grid
    info("Portal PLN: Logging in...")
    pln = PortalPLN()
    if not pln.login():
        err("Portal PLN login failed")
        return False
    ok("Portal PLN login OK")
    
    info("Portal PLN: Fetching grid...")
    grid = pln.fetch_grid(data_type, date_str)
    if not grid:
        err("Portal PLN grid fetch failed")
        return False
    ok(f"Got {len(grid)} items from Portal PLN")
    
    # 3. Sync
    mode = f"{Y}DRY-RUN{R}" if dry_run else f"{G}LIVE{R}"
    n_hours = jam_end - jam_start + 1
    cells_per_item = (n_hours * 2) if data_type == "tegangan" else n_hours
    total_cells = len(superi_data) * cells_per_item
    info(f"Mode {mode} · Jam {jam_start:02d}-{jam_end:02d} · {len(superi_data)} item · {total_cells} cell")
    print()

    updates = 0; errors = 0; skipped = 0
    error_list = []
    dry_samples = []
    done = 0

    # Build normalized lookup for grid (handle name variations like "TRAFO PS 1" vs "TRAFO PS1")
    def _normalize(s: str) -> str:
        return ''.join(s.upper().split())  # remove all whitespace + uppercase

    grid_normalized = {_normalize(k): (k, v) for k, v in grid.items()}

    for name, values in superi_data.items():
        # Try exact match first, then normalized
        rowdata = None
        if name in grid:
            rowdata = grid[name]
        else:
            norm = _normalize(name)
            if norm in grid_normalized:
                _, rowdata = grid_normalized[norm]

        if rowdata is None:
            # item tidak ada di grid Portal → semua cell-nya skip
            skipped += cells_per_item
            done += cells_per_item
            if not dry_run:
                live_progress(done, total_cells, name)
            continue

        if data_type == "tegangan":
            mv_vals = values.get("mv", [])
            hv_vals = values.get("hv", [])
            for h in range(jam_start, jam_end + 1):
                # MV → j column
                if h < len(mv_vals) and mv_vals[h] is not None:
                    col = f"j{h:02d}"
                    existing = rowdata.get(col)
                    if existing is not None and abs(float(existing) - float(mv_vals[h])) < 0.001:
                        skipped += 1
                    elif dry_run:
                        updates += 1
                        if len(dry_samples) < 6:
                            dry_samples.append(f"{name} {col}(MV): {existing} → {mv_vals[h]}")
                    else:
                        if pln.update_cell(data_type, rowdata, col, mv_vals[h]):
                            updates += 1
                        else:
                            errors += 1; error_list.append(f"{name} {col}(MV)={mv_vals[h]}")
                        time.sleep(0.05)
                else:
                    skipped += 1
                done += 1
                if not dry_run:
                    live_progress(done, total_cells, name)

                # HV → k column
                if h < len(hv_vals) and hv_vals[h] is not None:
                    col = f"k{h:02d}"
                    existing = rowdata.get(col)
                    if existing is not None and abs(float(existing) - float(hv_vals[h])) < 0.001:
                        skipped += 1
                    elif dry_run:
                        updates += 1
                        if len(dry_samples) < 6:
                            dry_samples.append(f"{name} {col}(HV): {existing} → {hv_vals[h]}")
                    else:
                        if pln.update_cell(data_type, rowdata, col, hv_vals[h]):
                            updates += 1
                        else:
                            errors += 1; error_list.append(f"{name} {col}(HV)={hv_vals[h]}")
                        time.sleep(0.05)
                else:
                    skipped += 1
                done += 1
                if not dry_run:
                    live_progress(done, total_cells, name)
        else:
            jams = values if isinstance(values, list) else []
            for h in range(jam_start, jam_end + 1):
                if h >= len(jams) or jams[h] is None:
                    skipped += 1
                    done += 1
                    if not dry_run:
                        live_progress(done, total_cells, name)
                    continue
                col = f"j{h:02d}"
                existing = rowdata.get(col)
                if existing is not None and str(existing) == str(jams[h]):
                    skipped += 1
                elif dry_run:
                    updates += 1
                    if len(dry_samples) < 6:
                        dry_samples.append(f"{name} {col}: {existing} → {jams[h]}")
                else:
                    if pln.update_cell(data_type, rowdata, col, jams[h]):
                        updates += 1
                    else:
                        errors += 1; error_list.append(f"{name} {col}={jams[h]}")
                    time.sleep(0.05)
                done += 1
                if not dry_run:
                    live_progress(done, total_cells, name)

    # akhiri bar live, lalu ringkasan
    if not dry_run:
        print()
    summary_box(type_labels[data_type], updates, errors, skipped, total_cells)
    if dry_run and dry_samples:
        print(f"  {D}Contoh perubahan:{R}")
        for s in dry_samples:
            print(f"    {C}{s}{R}")
    if error_list:
        warn(f"{len(error_list)} error: " + "; ".join(error_list[:5]) + (" …" if len(error_list) > 5 else ""))
    return errors == 0

# Menu interaktif sudah dipindah ke superi_app.py (superi cli → [P] Sync ke Portal APD).
# superi_sync.py sekarang library: do_sync() dipanggil cli/web/auto.
# Non-interactive: superi sync --type ... --jam ... --dry-run

# ============ CLI ARGS ============
def main():
    args = sys.argv[1:]
    
    if '--help' in args or '-h' in args:
        print(__doc__)
        sys.exit(0)
    
    if '--version' in args or '-v' in args:
        print(f"superi sync v{__version__}")
        sys.exit(0)
    
    # Parse args
    data_type = None
    jam_start = 0; jam_end = 23
    date_str = datetime.now().strftime("%Y-%m-%d")
    dry_run = '--dry-run' in args
    
    for i, a in enumerate(args):
        if a == '--type' and i+1 < len(args):
            t = args[i+1]
            if t == 'all':
                data_type = 'all'
            elif t in ('penyulang', 'trafo', 'tegangan'):
                data_type = t
        elif a == '--jam' and i+1 < len(args):
            v = args[i+1]
            if '-' in v:
                jam_start, jam_end = map(int, v.split('-'))
            else:
                jam_start = jam_end = int(v)
        elif a == '--date' and i+1 < len(args):
            date_str = args[i+1]
    
    # Non-interactive mode (untuk script/cron: superi sync --type ... --jam ...)
    if data_type:
        types = ["penyulang", "trafo", "tegangan"] if data_type == 'all' else [data_type]
        for dt in types:
            success = do_sync(dt, jam_start, jam_end, date_str, dry_run=dry_run)
            if not success and not dry_run:
                sys.exit(1)
        sys.exit(0)

    # No args → arahkan ke superi cli (menu sync sekarang di cli)
    print(f"\n  Menu sync sekarang tergabung di SUPER-I CLI.")
    print(f"  Jalankan:  superi cli   →  pilih [P] Sync ke Portal APD")
    print(f"  Atau non-interactive: superi sync --type all --jam 08 --dry-run\n")
    sys.exit(0)

if __name__ == '__main__':
    main()
