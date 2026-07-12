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
  "auto_sync_portal": true,    # auto sync ke Portal APD setelah input
  "auto_retry_attempts": 5,    # ulangi input gagal/kosong sampai verifikasi terisi
  "auto_retry_delay": 10       # jeda antar retry (detik)
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if _stdout_reconfigure:
    _stdout_reconfigure(encoding="utf-8", errors="replace")
_stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if _stderr_reconfigure:
    _stderr_reconfigure(encoding="utf-8", errors="replace")

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
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))
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


def clamp_to_history(value, hist_values):
    """Clamp nilai ke range histori kalau histori tersedia."""
    if value is None or not hist_values:
        return value
    return max(min(hist_values), min(max(hist_values), value))


def fallback_beban_from_cache(cache, item_id):
    """Fallback beban kalau histori periode target kosong: rata-rata semua periode item."""
    if item_id not in cache:
        return None, None
    vals = []
    for pdata in cache[item_id]["periode_data"].values():
        vals.extend(pdata.get("all", []))
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None
    val = round((sum(vals) / len(vals)) / 5) * 5
    val = int(clamp_to_history(val, vals))
    return val, vals


def fallback_tegangan_from_cache(cache, item_id):
    """Fallback tegangan kalau histori periode target kosong: rata-rata semua periode item."""
    if item_id not in cache:
        return None, None, None, None
    nama = cache[item_id].get("name", "").upper()
    if "PS" in nama:
        mv_decimals = 0
    elif nama == "TRAFO 1":
        mv_decimals = 1
    else:
        mv_decimals = 2
    entries = []
    for pdata in cache[item_id]["periode_data"].values():
        entries.extend(pdata.get("all", []))
    entries = [e for e in entries if e.get("mv") is not None and e.get("hv") is not None]
    if not entries:
        return None, None, None, None
    mv_vals = [e["mv"] for e in entries]
    hv_vals = [e["hv"] for e in entries]
    mv = round(sum(mv_vals) / len(mv_vals), mv_decimals)
    mv = round(clamp_to_history(mv, mv_vals), mv_decimals)
    if mv_decimals == 0:
        mv = int(mv)
    hv = sum(hv_vals) / len(hv_vals)
    if "PS" in nama:
        hv = round(clamp_to_history(hv, hv_vals), 2)
    else:
        hv = int(round(clamp_to_history(round(hv), hv_vals)))
    return mv, hv, mv_vals, hv_vals


# ============================================================
# AGREGASI BEBAN TRAFO DARI PENYULANG
# ============================================================
def _normalize_name(value):
    return "".join(str(value or "").upper().split())


def calculate_trafo_loads(penyulang_items, trafo_items, periode):
    """Jumlahkan penyulang aktif per trafo; periode kosong bernilai 0 A."""
    trafo_by_id = {str(x["id"]): x for x in trafo_items if x.get("id") is not None}
    trafo_by_name = {_normalize_name(x.get("nama")): x for x in trafo_items if x.get("nama")}
    calculations = {
        str(x["id"]): {"trafo": x, "total": 0, "contributors": [], "fallbacks": []}
        for x in trafo_items if x.get("id") is not None
    }
    unmapped = []
    for feeder in penyulang_items:
        if str(feeder.get("statusCB", "")).strip().upper() != "ON":
            continue
        relation = feeder.get("trafo") or {}
        trafo = trafo_by_id.get(str(relation.get("id"))) if relation.get("id") is not None else None
        if trafo is None:
            trafo = trafo_by_name.get(_normalize_name(relation.get("nama")))
        if trafo is None:
            unmapped.append(feeder.get("nama", "?"))
            continue
        entries = [x for x in feeder.get("beban", []) if x.get("periode") == periode]
        raw_value = entries[-1].get("beban") if entries else None
        try:
            value = float(raw_value) if raw_value is not None else 0
        except (TypeError, ValueError):
            value = 0
        calc = calculations[str(trafo["id"])]
        calc["total"] += value
        calc["contributors"].append({"nama": feeder.get("nama", "?"), "value": value})
        if not entries or raw_value is None:
            calc["fallbacks"].append(feeder.get("nama", "?"))
    for calc in calculations.values():
        if isinstance(calc["total"], float) and calc["total"].is_integer():
            calc["total"] = int(calc["total"])
    return calculations, unmapped


def auto_input_trafo_from_penyulang(token, gi_id, date_str, periode, dry_run=False, max_attempts=5, retry_delay=10):
    """Input beban trafo dari akumulasi penyulang aktif yang tersimpan di SUPER-I."""
    feeder_ep = a.ENDPOINTS["beban-penyulang"]
    trafo_ep = a.ENDPOINTS["beban-trafo"]
    params = {"garduIndukId": gi_id, "date": date_str}
    max_attempts = max(1, int(max_attempts or 1))
    retry_delay = max(1, int(retry_delay or 1))
    feeders = a.api_get(token, feeder_ep["list"], params).get("data", {}).get("items", [])
    trafos = a.api_get(token, trafo_ep["list"], params).get("data", {}).get("items", [])
    if not feeders or not trafos:
        log("  Data penyulang atau trafo tidak tersedia; kalkulasi dibatalkan", "ERROR")
        return {"success": 0, "fail": len(trafos) or 1, "skipped": 0, "anomaly": 0, "items": []}
    calculations, unmapped = calculate_trafo_loads(feeders, trafos, periode)
    if unmapped:
        log(f"  [UNMAPPED] Penyulang aktif tanpa relasi trafo: {', '.join(unmapped)}", "WARN")
    existing = {str(x.get("id")) for x in trafos if any(e.get("periode") == periode for e in x.get("beban", []))}
    targets = {key: calc for key, calc in calculations.items() if key not in existing}
    if not targets:
        log(f"  Beban Trafo P{periode:02d}: semua sudah terisi, skip")
        return {"success": 0, "fail": 0, "skipped": len(trafos), "anomaly": 0, "items": []}
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    item_logs = []
    success = 0
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log(f"  Retry Beban Trafo P{periode:02d} attempt {attempt}/{max_attempts}: {len(targets)} item belum terisi", "WARN")
        for calc in targets.values():
            trafo = calc["trafo"]
            fallback = f", fallback 0A: {', '.join(calc['fallbacks'])}" if calc["fallbacks"] else ""
            value_log = f"{calc['total']}Ampere ({len(calc['contributors'])} penyulang aktif{fallback})"
            payload = {
                "trafoId": trafo["id"], "timezone": "Asia/Jakarta", "periode": periode,
                "tanggal": dt.day, "bulan": dt.month - 1, "tahun": dt.year, "durasi": 0.1,
                "beban": calc["total"],
                "foto": {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846},
            }
            if dry_run:
                log(f"  [DRY] {trafo.get('nama', '?')} P{periode:02d}: {value_log}")
                item_logs.append({"nama": trafo.get("nama", "?"), "value": value_log, "ok": True})
                continue
            try:
                _, resp = a.api_post_multipart(token, trafo_ep["input"], payload, a.DUMMY_JPEG, trafo_ep["file_field"], trafo_ep["num_photos"])
                if resp.get("success"):
                    log(f"  [OK] {trafo.get('nama', '?')} P{periode:02d}: {value_log}")
                else:
                    log(f"  [FAIL] {trafo.get('nama', '?')} P{periode:02d}: {resp.get('message', '?')}", "ERROR")
            except Exception as exc:
                log(f"  [FAIL] {trafo.get('nama', '?')} P{periode:02d}: {exc}", "ERROR")
            time.sleep(0.1)
        if dry_run:
            success = len(targets)
            targets = {}
            break
        refreshed = a.api_get(token, trafo_ep["list"], params).get("data", {}).get("items", [])
        filled = {str(x.get("id")) for x in refreshed if any(e.get("periode") == periode for e in x.get("beban", []))}
        remaining = {key: calc for key, calc in targets.items() if key not in filled}
        success += len(targets) - len(remaining)
        targets = remaining
        if not targets:
            log(f"  [VERIFY] Beban Trafo P{periode:02d}: semua hasil akumulasi sudah terisi")
            break
        if attempt < max_attempts:
            log(f"  [RETRY] Beban Trafo P{periode:02d}: masih kosong {len(targets)} item, tunggu {retry_delay}s", "WARN")
            time.sleep(retry_delay)
    if targets:
        log(f"  [GIVE UP] Beban Trafo P{periode:02d}: {len(targets)} hasil gagal disimpan", "ERROR")
    return {"success": success, "fail": len(targets), "skipped": len(existing), "anomaly": 0, "items": item_logs}


# ============================================================
# AUTO INPUT (per tipe per jam)
# ============================================================
def auto_input_jam(token, data_type, gi_id, date_str, periode, dry_run=False, max_attempts=5, retry_delay=10):
    """Auto input semua item untuk 1 tipe data, 1 jam.
    Return: dict {success, fail, skipped, anomaly, items: [...]}
    """
    ep = a.ENDPOINTS[data_type]
    max_attempts = max(1, int(max_attempts or 1))
    retry_delay = max(1, int(retry_delay or 1))
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"

    def missing_targets():
        """Fetch ulang data terbaru; return item ON yang periode ini belum terisi."""
        result = a.api_get(token, ep["list"], {"garduIndukId": gi_id, "date": date_str})
        items = result.get("data", {}).get("items", [])
        if not items:
            return None, []
        targets = []
        for it in items:
            if it.get("statusCB") == "OFF":
                continue
            entries = it.get(data_key, [])
            if periode not in [e.get("periode") for e in entries]:
                targets.append(it)
        return items, targets
    
    # Fetch data hari ini untuk cek mana yang sudah/belum terisi
    items, targets = missing_targets()
    if not items:
        log(f"  Tidak ada item {data_type}", "WARN")
        return {"success": 0, "fail": 0, "skipped": 0, "anomaly": 0, "items": []}
    
    if not targets:
        log(f"  {ep['label']} P{periode:02d}: semua sudah terisi, skip")
        return {"success": 0, "fail": 0, "skipped": len(items), "anomaly": 0, "items": []}
    
    # Fetch cache histori (sekali untuk semua target)
    cache = a.fetch_history_bulk(token, data_type, gi_id, date_str)
    is_weekend = datetime.strptime(date_str, "%Y-%m-%d").weekday() >= 5
    
    success = fail = anomaly = 0
    item_logs = []
    dt = datetime.strptime(date_str, "%Y-%m-%d")

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log(f"  Retry {ep['label']} P{periode:02d} attempt {attempt}/{max_attempts}: {len(targets)} item belum terisi", "WARN")

        attempt_fail = 0
        attempt_anomaly = 0

        for it in targets:
            nama = it["nama"]
            item_id = it["id"]

            # Hitung suggest
            if data_type == "tegangan-trafo":
                mv, hv, info = a.smart_suggest_tegangan_from_cache(cache, item_id, periode, is_weekend)
                if mv is None:
                    mv, hv, fallback_mv_hist, fallback_hv_hist = fallback_tegangan_from_cache(cache, item_id)
                    if mv is None:
                        log(f"  [SKIP] {nama} P{periode:02d}: no histori sama sekali", "WARN")
                        attempt_fail += 1
                        item_logs.append({"nama": nama, "ok": False, "err": "no histori"})
                        continue
                    log(f"  [FALLBACK] {nama} P{periode:02d}: pakai rata-rata semua periode", "WARN")
                else:
                    fallback_mv_hist = None
                    fallback_hv_hist = None

                # Anomaly check (MV)
                pdata = cache[item_id]["periode_data"].get(periode, {})
                hist_mv = [e["mv"] for e in pdata.get("all", [])] or (fallback_mv_hist or [])
                is_anom, reason = is_anomaly(mv, hist_mv)
                if is_anom:
                    old_mv = mv
                    mv = clamp_to_history(mv, hist_mv)
                    log(f"  [ANOMALY] {nama} P{periode:02d}: MV={old_mv} → clamp {mv} ({reason})", "WARN")
                    attempt_anomaly += 1

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
                    val, fallback_hist_vals = fallback_beban_from_cache(cache, item_id)
                    if val is None:
                        log(f"  [SKIP] {nama} P{periode:02d}: no histori sama sekali", "WARN")
                        attempt_fail += 1
                        item_logs.append({"nama": nama, "ok": False, "err": "no histori"})
                        continue
                    log(f"  [FALLBACK] {nama} P{periode:02d}: pakai rata-rata semua periode", "WARN")
                else:
                    fallback_hist_vals = None

                # Anomaly check
                pdata = cache[item_id]["periode_data"].get(periode, {})
                hist_vals = pdata.get("all", []) or (fallback_hist_vals or [])
                is_anom, reason = is_anomaly(val, hist_vals)
                if is_anom:
                    old_val = val
                    val = int(round(clamp_to_history(val, hist_vals) / 5) * 5)
                    log(f"  [ANOMALY] {nama} P{periode:02d}: val={old_val} → clamp {val} ({reason})", "WARN")
                    attempt_anomaly += 1

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
                    item_logs.append({"nama": nama, "value": value_log, "ok": True})
                else:
                    msg = resp.get("message", "?")
                    log(f"  [FAIL] {nama} P{periode:02d}: {msg}", "ERROR")
                    attempt_fail += 1
                    item_logs.append({"nama": nama, "value": value_log, "ok": False, "err": str(msg)[:80]})
            except Exception as e:
                log(f"  [FAIL] {nama} P{periode:02d}: {e}", "ERROR")
                attempt_fail += 1

            time.sleep(0.1)  # rate limit

        if dry_run:
            fail += attempt_fail
            anomaly += attempt_anomaly
            break

        # Guard utama: fetch ulang, baru anggap sukses kalau benar-benar sudah terisi di SUPER-I.
        items, remaining = missing_targets()
        filled_now = len(targets) - len(remaining)
        success += max(0, filled_now)
        if not remaining:
            log(f"  [VERIFY] {ep['label']} P{periode:02d}: semua target sudah terisi")
            break

        targets = remaining
        if attempt < max_attempts:
            log(f"  [RETRY] {ep['label']} P{periode:02d}: masih kosong {len(targets)} item, tunggu {retry_delay}s", "WARN")
            time.sleep(retry_delay)
        else:
            fail += len(targets)
            anomaly += attempt_anomaly
            names = ", ".join([it.get("nama", "?") for it in targets[:8]])
            more = "..." if len(targets) > 8 else ""
            log(f"  [GIVE UP] {ep['label']} P{periode:02d}: {len(targets)} item tetap kosong setelah {max_attempts} attempt: {names}{more}", "ERROR")
    
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
    types = [t for t in ("penyulang", "trafo", "tegangan") if t in types]
    
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
        input_func = auto_input_trafo_from_penyulang if t == "trafo" else auto_input_jam
        if t == "trafo":
            result = input_func(
                token, gi_id, date_str, jam, dry_run=dry_run,
                max_attempts=cfg.get("auto_retry_attempts", 5),
                retry_delay=cfg.get("auto_retry_delay", 10),
            )
        else:
            result = input_func(
                token, full_type, gi_id, date_str, jam, dry_run=dry_run,
                max_attempts=cfg.get("auto_retry_attempts", 5),
                retry_delay=cfg.get("auto_retry_delay", 10),
            )
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
                sync_ok = False
                for attempt in range(1, 4):
                    try:
                        ok = s.do_sync(t, jam, jam, date_str, dry_run=False)
                        if ok:
                            sync_ok = True
                            break
                        log(f"  Sync {t} ada error (attempt {attempt}/3)", "WARN")
                    except Exception as e:
                        log(f"  Sync {t} gagal attempt {attempt}/3: {e}", "ERROR")
                    if attempt < 3:
                        time.sleep(10)
                if not sync_ok:
                    log(f"  Sync {t} gagal final setelah 3 attempt", "ERROR")
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
    cfg.setdefault("auto_retry_attempts", 5)
    cfg.setdefault("auto_retry_delay", 10)
    save_cfg(cfg)
    print(f"\n  ✓ Auto mode AKTIF")
    print(f"  Window: {cfg['auto_window_start']:02d}:00 - {cfg['auto_window_end']:02d}:00")
    print(f"  Types : {', '.join(cfg['auto_types'])}")
    print(f"  Sync  : {'YES' if cfg['auto_sync_portal'] else 'NO'}\n")
    print(f"  Retry : {cfg['auto_retry_attempts']}x, jeda {cfg['auto_retry_delay']}s\n")

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
        print(f"  Retry : {cfg.get('auto_retry_attempts', 5)}x, jeda {cfg.get('auto_retry_delay', 10)}s")
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
