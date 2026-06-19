#!/usr/bin/env python3
"""
SUPER-I APP - Auto Input & Sync Module
======================================
Modul otomatis untuk input data + sync ke Portal APD tanpa interaksi user.
Cocok untuk dijadwalkan via cron (macOS/Linux) atau Task Scheduler (Windows).

Fitur:
- Smart-suggest per-periode (rata-rata histori, weekday/weekend aware)
- Aturan pembulatan MV per trafo (PS=bulat, TRAFO 1=1 desimal, lain=2 desimal)
- HV PS = MV trafo sumber (PS1=TRAFO 1, PS2=TRAFO 3)
- Safety guard: skip nilai anomali (di luar range historis ±20%)
- Window jam: hanya jalan di rentang waktu tertentu (mis. 22:00-05:00)
- Logging ke file (auto_log.txt)
- Bisa di-disable via config (auto_enabled: false)

Usage:
  superi auto                   # jalan untuk jam saat ini (sesuai window)
  superi auto --jam 23          # paksa jalan jam 23 (abaikan window)
  superi auto --types penyulang,trafo,tegangan  # tipe spesifik
  superi auto --dry-run         # preview tanpa input/sync
  superi auto --disable         # nonaktifkan auto mode
  superi auto --enable          # aktifkan auto mode

Config tambahan di .superi_config.json:
  "auto_enabled": true,
  "auto_window_start": 22,    # jam mulai (0-23)
  "auto_window_end": 5,        # jam akhir (0-23, boleh < start untuk lintas hari)
  "auto_types": ["penyulang", "trafo", "tegangan"],
  "auto_sync_portal": true     # auto sync ke Portal APD setelah input
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import superi_app as a
import superi_sync as s

CONFIG_FILE = os.path.join(SCRIPT_DIR, ".superi_config.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "auto_log.txt")

# ============================================================
# LOGGING
# ============================================================
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ============================================================
# CONFIG
# ============================================================
def load_cfg():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_cfg(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ============================================================
# WINDOW CHECK
# ============================================================
def in_window(now_hour, start, end):
    """Cek apakah jam sekarang masuk window aktif.
    
    Window lintas hari (mis. 22-5): aktif kalau jam >= 22 ATAU jam <= 5.
    Window normal (mis. 9-17): aktif kalau 9 <= jam <= 17.
    """
    if start <= end:
        return start <= now_hour <= end
    else:
        return now_hour >= start or now_hour <= end

# ============================================================
# SAFETY GUARD
# ============================================================
def is_anomaly(value, hist_values, threshold=0.20):
    """Cek apakah nilai berada di luar range ±threshold dari histori.
    Return (True, reason) kalau anomali, (False, '') kalau normal.
    """
    if not hist_values or value is None:
        return False, ""
    
    avg = sum(hist_values) / len(hist_values)
    if avg == 0:
        return False, ""
    
    deviation = abs(value - avg) / abs(avg)
    if deviation > threshold:
        return True, f"deviasi {deviation*100:.0f}% dari rata-rata histori {avg:.1f}"
    return False, ""

# ============================================================
# AUTO INPUT (per tipe per jam)
# ============================================================
def auto_input_jam(token, data_type, gi_id, date_str, periode, dry_run=False):
    """Auto input semua item untuk 1 tipe data, 1 jam.
    Return: dict {success, fail, skipped, anomaly, items: [...]}
    """
    ep = a.ENDPOINTS[data_type]
    
    # Fetch data hari ini untuk cek mana yang sudah/belum terisi
    result = a.api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
    items = result.get("data", {}).get("items", [])
    if not items:
        log(f"  Tidak ada item {data_type}", "WARN")
        return {"success": 0, "fail": 0, "skipped": 0, "anomaly": 0, "items": []}
    
    # Filter item yang belum terisi di periode ini & status ON
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
    targets = []
    for it in items:
        if it.get("statusCB") == "OFF":
            continue
        entries = it.get(data_key, [])
        if periode not in [e["periode"] for e in entries]:
            targets.append(it)
    
    if not targets:
        log(f"  {ep['label']} P{periode:02d}: semua sudah terisi, skip")
        return {"success": 0, "fail": 0, "skipped": len(items), "anomaly": 0, "items": []}
    
    # Fetch cache histori (sekali untuk semua target)
    cache = a.fetch_history_bulk(token, data_type, gi_id, date_str)
    is_weekend = datetime.strptime(date_str, "%Y-%m-%d").weekday() >= 5
    
    success = fail = anomaly = 0
    item_logs = []
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    
    for it in targets:
        nama = it["nama"]
        item_id = it["id"]
        
        # Hitung suggest
        if data_type == "tegangan-trafo":
            mv, hv, info = a.smart_suggest_tegangan_from_cache(cache, item_id, periode, is_weekend)
            if mv is None:
                log(f"  [SKIP] {nama} P{periode:02d}: no histori", "WARN")
                fail += 1
                continue
            
            # Anomaly check (MV)
            pdata = cache[item_id]["periode_data"].get(periode, {})
            hist_mv = [e["mv"] for e in pdata.get("all", [])]
            is_anom, reason = is_anomaly(mv, hist_mv)
            if is_anom:
                log(f"  [ANOMALY] {nama} P{periode:02d}: MV={mv} ({reason})", "WARN")
                anomaly += 1
                continue
            
            value_log = f"MV={mv} HV={hv}"
            data_dict = {
                ep["id_field"]: item_id,
                "timezone": "Asia/Jakarta",
                "periode": periode,
                "tanggal": dt.day, "bulan": dt.month - 1, "tahun": dt.year,
                "durasi": 0.1,
                ep["value_field"]: mv, "hv": hv,
                "fotoHV": {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846},
                "fotoMV": {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846},
            }
        else:
            val, info = a.smart_suggest_from_cache(cache, item_id, periode, is_weekend)
            if val is None:
                log(f"  [SKIP] {nama} P{periode:02d}: no histori", "WARN")
                fail += 1
                continue
            
            # Anomaly check
            pdata = cache[item_id]["periode_data"].get(periode, {})
            hist_vals = pdata.get("all", [])
            is_anom, reason = is_anomaly(val, hist_vals)
            if is_anom:
                log(f"  [ANOMALY] {nama} P{periode:02d}: val={val} ({reason})", "WARN")
                anomaly += 1
                continue
            
            value_log = f"{val}{ep['unit']}"
            data_dict = {
                ep["id_field"]: item_id,
                "timezone": "Asia/Jakarta",
                "periode": periode,
                "tanggal": dt.day, "bulan": dt.month - 1, "tahun": dt.year,
                "durasi": 0.1,
                ep["value_field"]: val,
                "foto": {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846},
            }
        
        if dry_run:
            log(f"  [DRY] {nama} P{periode:02d}: {value_log}")
            success += 1
            item_logs.append({"nama": nama, "value": value_log, "ok": True})
            continue
        
        # Submit
        try:
            status, resp = a.api_post_multipart(token, ep["input"], data_dict, a.DUMMY_JPEG, ep["file_field"], ep["num_photos"])
            if resp.get("success"):
                log(f"  [OK] {nama} P{periode:02d}: {value_log}")
                success += 1
                item_logs.append({"nama": nama, "value": value_log, "ok": True})
            else:
                msg = resp.get("message", "?")
                log(f"  [FAIL] {nama} P{periode:02d}: {msg}", "ERROR")
                fail += 1
                item_logs.append({"nama": nama, "value": value_log, "ok": False, "err": str(msg)[:80]})
        except Exception as e:
            log(f"  [FAIL] {nama} P{periode:02d}: {e}", "ERROR")
            fail += 1
        
        time.sleep(0.1)  # rate limit
    
    return {"success": success, "fail": fail, "skipped": 0, "anomaly": anomaly, "items": item_logs}

# ============================================================
# MAIN AUTO
# ============================================================
def run_auto(force_jam=None, types=None, dry_run=False):
    """Jalankan auto input & sync untuk jam sekarang (atau force_jam)."""
    cfg = load_cfg()
    
    # Cek auto enabled
    if not cfg.get("auto_enabled", False) and force_jam is None:
        log("Auto mode tidak aktif. Aktifkan dengan: superi auto --enable", "WARN")
        return False
    
    # Tentukan jam
    now = datetime.now()
    jam = force_jam if force_jam is not None else now.hour
    date_str = now.strftime("%Y-%m-%d")
    
    # Cek window
    if force_jam is None:
        win_start = cfg.get("auto_window_start", 22)
        win_end = cfg.get("auto_window_end", 5)
        if not in_window(jam, win_start, win_end):
            log(f"Jam {jam:02d}:00 di luar window aktif ({win_start:02d}:00-{win_end:02d}:00). Skip.", "INFO")
            return False
    
    # Tentukan tipe
    if types is None:
        types = cfg.get("auto_types", ["penyulang", "trafo", "tegangan"])
    
    log("=" * 60)
    log(f"AUTO MODE: jam {jam:02d}:00, date {date_str}, types={','.join(types)}, dry_run={dry_run}")
    log("=" * 60)
    
    # Login SUPER-I
    nip = cfg.get("nip")
    password = cfg.get("password")
    if not nip or not password:
        log("Kredensial SUPER-I belum diset. Jalankan: superi cli → [S] Setup", "ERROR")
        return False
    
    try:
        token, user = a.login(nip, password)
        log(f"SUPER-I login OK: {user.get('namaLengkap')}")
    except Exception as e:
        log(f"SUPER-I login gagal: {e}", "ERROR")
        return False
    
    gi_id = cfg.get("gi_id", 222)
    type_map = {"penyulang": "beban-penyulang", "trafo": "beban-trafo", "tegangan": "tegangan-trafo"}
    
    total = {"success": 0, "fail": 0, "skipped": 0, "anomaly": 0}
    successful_types = []
    
    for t in types:
        full_type = type_map.get(t)
        if not full_type:
            continue
        log(f"\n→ {full_type.upper()}")
        result = auto_input_jam(token, full_type, gi_id, date_str, jam, dry_run=dry_run)
        for k in total:
            total[k] += result[k]
        if result["success"] > 0:
            successful_types.append(t)
    
    log("\n" + "=" * 60)
    log(f"INPUT SELESAI: ✓{total['success']} ✗{total['fail']} ⊘{total['skipped']} ⚠{total['anomaly']}")
    
    # Auto sync ke Portal APD
    if not dry_run and cfg.get("auto_sync_portal", True) and successful_types:
        if cfg.get("portal_user") and cfg.get("portal_password"):
            log(f"\n→ SYNC ke Portal APD (jam {jam:02d}, types={','.join(successful_types)})")
            for t in successful_types:
                try:
                    ok = s.do_sync(t, jam, jam, date_str, dry_run=False)
                    if not ok:
                        log(f"  Sync {t} ada error", "WARN")
                except Exception as e:
                    log(f"  Sync {t} gagal: {e}", "ERROR")
        else:
            log("Portal APD credentials belum diset, skip sync", "WARN")
    
    log("=" * 60)
    log("AUTO MODE selesai\n")
    return total["fail"] == 0

# ============================================================
# COMMANDS
# ============================================================
def cmd_enable():
    cfg = load_cfg()
    cfg["auto_enabled"] = True
    cfg.setdefault("auto_window_start", 22)
    cfg.setdefault("auto_window_end", 5)
    cfg.setdefault("auto_types", ["penyulang", "trafo", "tegangan"])
    cfg.setdefault("auto_sync_portal", True)
    save_cfg(cfg)
    print(f"\n  ✓ Auto mode AKTIF")
    print(f"  Window: {cfg['auto_window_start']:02d}:00 - {cfg['auto_window_end']:02d}:00")
    print(f"  Types : {', '.join(cfg['auto_types'])}")
    print(f"  Sync  : {'YES' if cfg['auto_sync_portal'] else 'NO'}\n")

def cmd_disable():
    cfg = load_cfg()
    cfg["auto_enabled"] = False
    save_cfg(cfg)
    print(f"\n  ⊘ Auto mode NONAKTIF\n")

def cmd_status():
    cfg = load_cfg()
    enabled = cfg.get("auto_enabled", False)
    print(f"\n  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  AUTO MODE STATUS: {'✓ AKTIF' if enabled else '⊘ NONAKTIF'}")
    print(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if enabled:
        print(f"  Window: {cfg.get('auto_window_start',22):02d}:00 - {cfg.get('auto_window_end',5):02d}:00")
        print(f"  Types : {', '.join(cfg.get('auto_types', []))}")
        print(f"  Sync  : {'YES' if cfg.get('auto_sync_portal', True) else 'NO'}")
    print(f"  Log   : {LOG_FILE}\n")

def main():
    args = sys.argv[1:]
    
    if "--help" in args or "-h" in args:
        print(__doc__)
        return
    
    if "--enable" in args:
        cmd_enable()
        return
    if "--disable" in args:
        cmd_disable()
        return
    if "--status" in args:
        cmd_status()
        return
    
    # Parse opsi
    force_jam = None
    types = None
    dry_run = "--dry-run" in args
    
    for i, arg in enumerate(args):
        if arg == "--jam" and i + 1 < len(args):
            force_jam = int(args[i + 1])
        elif arg == "--types" and i + 1 < len(args):
            types = [t.strip() for t in args[i + 1].split(",")]
    
    success = run_auto(force_jam=force_jam, types=types, dry_run=dry_run)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
