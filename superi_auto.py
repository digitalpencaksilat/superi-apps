#!/usr/bin/env python3
"""
SUPER-I APP - Auto Input & Sync Module (Rich Edition - Tema Kuning)
====================================================================
Modul otomatis untuk input data + sync ke Portal APD tanpa interaksi user.

Fitur:
- Smart-suggest per-periode (rata-rata histori, weekday/weekend aware)
- Aturan pembulatan MV per trafo (PS=bulat, TRAFO 1=1 desimal, lain=2 desimal)
- HV PS = MV trafo sumber (PS1=TRAFO 1, PS2=TRAFO 3)
- Safety guard: skip nilai anomali (di luar range historis ±20%)
- Window jam: hanya jalan di rentang waktu tertentu (mis. 22:00-05:00)
- Logging dual: console Rich tema kuning + file auto_log.txt plain
- Bisa di-disable via config (auto_enabled: false)

Usage:
  superi auto                   # jalan untuk jam saat ini (sesuai window)
  superi auto --jam 23          # paksa jalan jam 23 (abaikan window)
  superi auto --types penyulang,trafo,tegangan  # tipe spesifik
  superi auto --dry-run         # preview tanpa input/sync
  superi auto --disable         # nonaktifkan auto mode
  superi auto --enable          # aktifkan auto mode
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

try:
    import superi_humanizer as hu
except Exception:
    hu = None

# Rich console (tema kuning)
try:
    import superi_console as sc
    console = sc.console
    RICH_AUTO = sc.RICH_AVAILABLE
except ImportError:
    try:
        from rich.console import Console
        from rich.theme import Theme
        _theme = Theme({"ok": "bold green", "err": "bold red", "warn": "bold yellow", "info": "cyan"})
        console = Console(theme=_theme, highlight=False)
        RICH_AUTO = True
        sc = None
    except ImportError:
        console = None
        RICH_AUTO = False
        sc = None

CONFIG_FILE = os.path.join(SCRIPT_DIR, ".superi_config.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "auto_log.txt")


def _h_durasi(data_type="beban-penyulang"):
    if hu:
        return hu.rand_durasi_for_type(data_type)
    import random
    if "tegangan" in data_type:
        return round(random.uniform(8.0, 35.0) / 60.0, 8)
    return round(random.uniform(2.0, 7.0) / 60.0, 8)


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
    import random
    addrs = [
        ("Jl. Swadaya 1 No.36, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213095, 106.846073),
        ("Gis 150 Kv Manggarai, Jl. Swadaya 1 No.21, RT.12/RW.10, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213208, 106.845899),
    ]
    addr, lat, lon = addrs[0]
    lat = round(lat + random.uniform(-0.00008, 0.00008), 7)
    lon = round(lon + random.uniform(-0.00008, 0.00008), 7)
    return {"date": _h_foto_date(date_str, periode, durasi_min, data_type), "address": addr, "latitude": lat, "longitude": lon}


def _h_foto_pair_dicts(date_str, periode, durasi_min=None):
    if hu:
        return hu.rand_foto_pair_dicts(date_str, periode, durasi_min)
    ts1, ts2 = _h_foto_pair(date_str, periode, durasi_min)
    base = "Jl. Swadaya 1 No.36, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia"
    return (
        {"date": ts1, "address": base, "latitude": -6.213095, "longitude": 106.846073},
        {"date": ts2, "address": base, "latitude": -6.213098, "longitude": 106.846075},
    )


def _h_sleep(a=0.6, b=2.2):
    if hu:
        hu.human_sleep(a, b)
    else:
        time.sleep(0.35)


def _h_jittered(v, f=0.35):
    return hu.jittered(v, f) if hu else v


def _h_shuffled(seq):
    return hu.shuffled(seq) if hu else list(seq)


def _h_initial_jitter():
    if hu and hu.rand_initial_jitter:
        sec = hu.rand_initial_jitter(110)
        log(f"Jitter awal {sec:.1f}s biar tidak seperti robot (cron anti-exact)", "INFO")
        time.sleep(sec)


def _get_jpeg_single():
    return hu.rand_jpeg_bytes(target_w=720, target_h=720) if hu else a.DUMMY_JPEG


def _get_jpeg_pair():
    if hu:
        return hu.rand_jpeg_pair(target_w=720, target_h=720)
    return a.DUMMY_JPEG, a.DUMMY_JPEG

# ============================================================
# LOGGING - Rich themed yellow + plain file
# ============================================================
def log(msg, level="INFO"):
    """Log dual: console Rich tema kuning + file auto_log.txt plain (tanpa ANSI)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plain_line = f"[{ts}] [{level}] {msg}"

    # File plain (always no ANSI, for cron / cat parsing)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(plain_line + "\n")
    except Exception:
        pass

    # Console colored jika terminal interaktif
    if RICH_AUTO and console and console.is_terminal:
        level_colors = {
            "INFO": "cyan",
            "WARN": "bold bright_yellow",
            "ERROR": "bold red",
            "DRY": "magenta",
            "OK": "bold green",
        }
        lstyle = level_colors.get(level, "white")
        # Shorten prefix for auto mode readability
        try:
            if level == "INFO" and not msg.startswith("["):
                console.print(f"[dim][{ts}][/] [{lstyle}]{level}[/] {msg}")
            elif level in ("OK", "WARN", "ERROR", "DRY", "RETRY", "VERIFY", "FALLBACK", "ANOMALY", "SKIP", "FAIL", "GIVE UP", "RETRY-FOTO", "UNMAPPED"):
                # For status-like messages, show icon + colored
                icon_map = {
                    "OK": "✓", "WARN": "⚠", "ERROR": "✗", "DRY": "≡",
                    "RETRY": "↻", "VERIFY": "✔", "FALLBACK": "⇣", "ANOMALY": "⚡",
                    "SKIP": "⊘", "FAIL": "✗", "GIVE UP": "✗", "RETRY-FOTO": "📷", "UNMAPPED": "⚠"
                }
                # Extract base level from message prefix like [OK] or use level
                actual_level = level
                # Try extract [XXX] pattern
                if msg.strip().startswith("[") and "]" in msg[:20]:
                    bracket = msg.strip().split("]")[0].strip("[")
                    if bracket in icon_map or bracket in level_colors:
                        actual_level = bracket
                ic = icon_map.get(actual_level, "•")
                console.print(f"  [{lstyle}]{ic} {msg.strip()}[/]")
            else:
                console.print(f"[dim][{ts}][/] [{lstyle}]{level}[/] {msg}")
        except Exception:
            try:
                print(plain_line)
            except UnicodeEncodeError:
                print(plain_line.encode("ascii", "replace").decode("ascii"))
    else:
        # Non-rich or non-TTY (cron) -> plain print (no ANSI)
        try:
            print(plain_line)
        except UnicodeEncodeError:
            print(plain_line.encode("ascii", "replace").decode("ascii"))

# ============================================================
# CONFIG
# ============================================================
def load_cfg():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cfg(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

# ============================================================
# WINDOW CHECK
# ============================================================
def in_window(now_hour, start, end):
    """Cek apakah jam sekarang masuk window aktif."""
    if start <= end:
        return start <= now_hour <= end
    else:
        return now_hour >= start or now_hour <= end

# ============================================================
# SAFETY GUARD
# ============================================================
def is_anomaly(value, hist_values, threshold=0.20):
    """Cek apakah nilai berada di luar range ±threshold dari histori."""
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
    """Clamp nilai ke range histori."""
    if value is None or not hist_values:
        return value
    return max(min(hist_values), min(max(hist_values), value))


def fallback_beban_from_cache(cache, item_id):
    """Fallback beban kalau histori periode target kosong."""
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
    """Fallback tegangan kalau histori periode target kosong."""
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
    """Input beban trafo dari akumulasi penyulang aktif."""
    feeder_ep = a.ENDPOINTS["beban-penyulang"]
    trafo_ep = a.ENDPOINTS["beban-trafo"]
    params = {"garduIndukId": gi_id, "date": date_str}
    max_attempts = max(1, int(max_attempts or 1))
    retry_delay = max(1, int(retry_delay or 1))
    feeders = a.api_get(token, feeder_ep["list"], params).get("data", {}).get("items", [])
    trafos = a.api_get(token, trafo_ep["list"], params).get("data", {}).get("items", [])
    if not feeders or not trafos:
        log("Data penyulang atau trafo tidak tersedia; kalkulasi dibatalkan", "ERROR")
        return {"success": 0, "fail": len(trafos) or 1, "skipped": 0, "anomaly": 0, "items": []}
    calculations, unmapped = calculate_trafo_loads(feeders, trafos, periode)
    if unmapped:
        log(f"[UNMAPPED] Penyulang aktif tanpa relasi trafo: {', '.join(unmapped)}", "WARN")
    existing = {str(x.get("id")) for x in trafos if any(e.get("periode") == periode for e in x.get("beban", []))}
    targets = {key: calc for key, calc in calculations.items() if key not in existing}
    if not targets:
        log(f"Beban Trafo P{periode:02d}: semua sudah terisi, skip")
        return {"success": 0, "fail": 0, "skipped": len(trafos), "anomaly": 0, "items": []}
    if hu and hasattr(hu, "reset_foto_sequence"):
        try:
            hu.reset_foto_sequence(date_str, periode)
        except Exception:
            pass
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    item_logs = []
    success = 0
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log(f"[RETRY] Beban Trafo P{periode:02d} attempt {attempt}/{max_attempts}: {len(targets)} item belum terisi", "WARN")
        calc_list = _h_shuffled(list(targets.values()))
        for calc in calc_list:
            trafo = calc["trafo"]
            fallback = f", fallback 0A: {', '.join(calc['fallbacks'])}" if calc["fallbacks"] else ""
            value_log = f"{calc['total']}Ampere ({len(calc['contributors'])} penyulang aktif{fallback})"
            durasi = _h_durasi("beban-trafo")
            payload = {
                "trafoId": trafo["id"], "timezone": "Asia/Jakarta", "periode": periode,
                "tanggal": dt.day, "bulan": dt.month - 1, "tahun": dt.year, "durasi": durasi,
                "beban": calc["total"],
                "foto": _h_foto_dict(date_str, periode, durasi, "beban-trafo"),
            }
            if dry_run:
                log(f"[DRY] {trafo.get('nama', '?')} P{periode:02d}: {value_log} | foto={payload['foto']['date']} durasi={payload['durasi']}")
                item_logs.append({"nama": trafo.get("nama", "?"), "value": value_log, "ok": True})
                continue
            try:
                _, resp = a.api_post_multipart(token, trafo_ep["input"], payload, _get_jpeg_single(), trafo_ep["file_field"], trafo_ep["num_photos"], trafo.get("nama"))
                if resp.get("success"):
                    log(f"[OK] {trafo.get('nama', '?')} P{periode:02d}: {value_log}")
                else:
                    log(f"[FAIL] {trafo.get('nama', '?')} P{periode:02d}: {resp.get('message', '?')}", "ERROR")
            except Exception as exc:
                log(f"[FAIL] {trafo.get('nama', '?')} P{periode:02d}: {exc}", "ERROR")
            _h_sleep(1.0, 3.6)
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
            log(f"[VERIFY] Beban Trafo P{periode:02d}: semua hasil akumulasi sudah terisi")
            break
        if attempt < max_attempts:
            jd = _h_jittered(float(retry_delay))
            log(f"[RETRY] Beban Trafo P{periode:02d}: masih kosong {len(targets)} item, tunggu {jd:.1f}s", "WARN")
            time.sleep(jd)
    if targets:
        log(f"[GIVE UP] Beban Trafo P{periode:02d}: {len(targets)} hasil gagal disimpan", "ERROR")
    return {"success": success, "fail": len(targets), "skipped": len(existing), "anomaly": 0, "items": item_logs}


# ============================================================
# AUTO INPUT (per tipe per jam)
# ============================================================
def auto_input_jam(token, data_type, gi_id, date_str, periode, dry_run=False, max_attempts=5, retry_delay=10):
    """Auto input semua item untuk 1 tipe data, 1 jam."""
    ep = a.ENDPOINTS[data_type]
    max_attempts = max(1, int(max_attempts or 1))
    retry_delay = max(1, int(retry_delay or 1))
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"

    def missing_targets():
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

    items, targets = missing_targets()
    if not items:
        log(f"Tidak ada item {data_type}", "WARN")
        return {"success": 0, "fail": 0, "skipped": 0, "anomaly": 0, "items": []}

    if not targets:
        log(f"{ep['label']} P{periode:02d}: semua sudah terisi, skip")
        return {"success": 0, "fail": 0, "skipped": len(items), "anomaly": 0, "items": []}

    if hu and hasattr(hu, "reset_foto_sequence"):
        try:
            hu.reset_foto_sequence(date_str, periode)
        except Exception:
            pass

    cache = a.fetch_history_bulk(token, data_type, gi_id, date_str)
    is_weekend = datetime.strptime(date_str, "%Y-%m-%d").weekday() >= 5

    success = fail = anomaly = 0
    item_logs = []
    dt = datetime.strptime(date_str, "%Y-%m-%d")

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log(f"[RETRY] {ep['label']} P{periode:02d} attempt {attempt}/{max_attempts}: {len(targets)} item belum terisi", "WARN")

        attempt_fail = 0
        attempt_anomaly = 0
        attempt_targets = _h_shuffled(targets)

        for it in attempt_targets:
            nama = it["nama"]
            item_id = it["id"]

            if data_type == "tegangan-trafo":
                mv, hv, info = a.smart_suggest_tegangan_from_cache(cache, item_id, periode, is_weekend)
                if mv is None:
                    mv, hv, fallback_mv_hist, fallback_hv_hist = fallback_tegangan_from_cache(cache, item_id)
                    if mv is None:
                        log(f"[SKIP] {nama} P{periode:02d}: no histori sama sekali", "WARN")
                        attempt_fail += 1
                        item_logs.append({"nama": nama, "ok": False, "err": "no histori"})
                        continue
                    log(f"[FALLBACK] {nama} P{periode:02d}: pakai rata-rata semua periode", "WARN")
                else:
                    fallback_mv_hist = None

                pdata = cache[item_id]["periode_data"].get(periode, {})
                hist_mv = [e["mv"] for e in pdata.get("all", [])] or (fallback_mv_hist or [])
                is_anom, reason = is_anomaly(mv, hist_mv)
                if is_anom:
                    old_mv = mv
                    mv = clamp_to_history(mv, hist_mv)
                    log(f"[ANOMALY] {nama} P{periode:02d}: MV={old_mv} → clamp {mv} ({reason})", "WARN")
                    attempt_anomaly += 1

                value_log = f"MV={mv} HV={hv}"
                durasi = _h_durasi(data_type)
                fotoHV, fotoMV = _h_foto_pair_dicts(date_str, periode, durasi)
                data_dict = {
                    ep["id_field"]: item_id,
                    "timezone": "Asia/Jakarta",
                    "periode": periode,
                    "tanggal": dt.day, "bulan": dt.month - 1, "tahun": dt.year,
                    "durasi": durasi,
                    ep["value_field"]: mv, "hv": hv,
                    "fotoHV": fotoHV,
                    "fotoMV": fotoMV,
                }
            else:
                val, info = a.smart_suggest_from_cache(cache, item_id, periode, is_weekend)
                if val is None:
                    val, fallback_hist_vals = fallback_beban_from_cache(cache, item_id)
                    if val is None:
                        log(f"[SKIP] {nama} P{periode:02d}: no histori sama sekali", "WARN")
                        attempt_fail += 1
                        item_logs.append({"nama": nama, "ok": False, "err": "no histori"})
                        continue
                    log(f"[FALLBACK] {nama} P{periode:02d}: pakai rata-rata semua periode", "WARN")
                else:
                    fallback_hist_vals = None

                pdata = cache[item_id]["periode_data"].get(periode, {})
                hist_vals = pdata.get("all", []) or (fallback_hist_vals or [])
                is_anom, reason = is_anomaly(val, hist_vals)
                if is_anom:
                    old_val = val
                    val = int(round(clamp_to_history(val, hist_vals) / 5) * 5)
                    log(f"[ANOMALY] {nama} P{periode:02d}: val={old_val} → clamp {val} ({reason})", "WARN")
                    attempt_anomaly += 1

                value_log = f"{val}{ep['unit']}"
                durasi = _h_durasi(data_type)
                data_dict = {
                    ep["id_field"]: item_id,
                    "timezone": "Asia/Jakarta",
                    "periode": periode,
                    "tanggal": dt.day, "bulan": dt.month - 1, "tahun": dt.year,
                    "durasi": durasi,
                    ep["value_field"]: val,
                    "foto": _h_foto_dict(date_str, periode, durasi, data_type),
                }

            if dry_run:
                fd = data_dict.get("foto", {}).get("date") or data_dict.get("fotoHV", {}).get("date")
                log(f"[DRY] {nama} P{periode:02d}: {value_log} | foto={fd} durasi={data_dict['durasi']}")
                success += 1
                item_logs.append({"nama": nama, "value": value_log, "ok": True})
                continue

            try:
                status, resp = a.api_post_multipart(token, ep["input"], data_dict, _get_jpeg_single(), ep["file_field"], ep["num_photos"], nama)
                if resp.get("success"):
                    photo_check = resp.get("_photo_upload")
                    if photo_check and not photo_check.get("ok"):
                        error = photo_check.get("error", "foto gagal")
                        try:
                            rec_id = (resp.get("data") or {}).get("id")
                            if rec_id:
                                a.api_delete(token, f"{ep['delete']}/{rec_id}")
                                log(f"[RETRY-FOTO] {nama} P{periode:02d}: {error} -> record dihapus, akan retry", "WARN")
                        except Exception:
                            pass
                        attempt_fail += 1
                        item_logs.append({"nama": nama, "value": value_log, "ok": False, "photo_ok": False, "err": error})
                    else:
                        log(f"[OK] {nama} P{periode:02d}: {value_log}")
                        item_logs.append({"nama": nama, "value": value_log, "ok": True, "photo_ok": True})
                else:
                    msg = resp.get("message", "?")
                    log(f"[FAIL] {nama} P{periode:02d}: {msg}", "ERROR")
                    attempt_fail += 1
                    item_logs.append({"nama": nama, "value": value_log, "ok": False, "err": str(msg)[:80]})
            except Exception as e:
                log(f"[FAIL] {nama} P{periode:02d}: {e}", "ERROR")
                attempt_fail += 1

            _h_sleep(1.0, 3.8)

        if dry_run:
            fail += attempt_fail
            anomaly += attempt_anomaly
            break

        items, remaining = missing_targets()
        filled_now = len(targets) - len(remaining)
        success += max(0, filled_now)
        if not remaining:
            log(f"[VERIFY] {ep['label']} P{periode:02d}: semua target sudah terisi")
            break

        targets = remaining
        if attempt < max_attempts:
            jd = _h_jittered(float(retry_delay))
            log(f"[RETRY] {ep['label']} P{periode:02d}: masih kosong {len(targets)} item, tunggu {jd:.1f}s", "WARN")
            time.sleep(jd)
        else:
            fail += len(targets)
            anomaly += attempt_anomaly
            names = ", ".join([it.get("nama", "?") for it in targets[:8]])
            more = "..." if len(targets) > 8 else ""
            log(f"[GIVE UP] {ep['label']} P{periode:02d}: {len(targets)} item tetap kosong setelah {max_attempts} attempt: {names}{more}", "ERROR")

    return {"success": success, "fail": fail, "skipped": 0, "anomaly": anomaly, "items": item_logs}

# ============================================================
# MAIN AUTO
# ============================================================
def run_auto(force_jam=None, types=None, dry_run=False):
    """Jalankan auto input & sync untuk jam sekarang."""
    cfg = load_cfg()

    if not cfg.get("auto_enabled", False) and force_jam is None:
        log("Auto mode tidak aktif. Aktifkan dengan: superi auto --enable", "WARN")
        return False

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    if force_jam is not None:
        jam = force_jam
    else:
        now_before = datetime.now()
        jam = now_before.hour
        _h_initial_jitter()
        now_after = datetime.now()
        if now_after.hour != jam:
            log(f"Jitter nyebrang jam {jam:02d}->{now_after.hour:02d}, tetap pakai logical jam {jam:02d} biar periode benar", "WARN")

    if force_jam is None:
        win_start = cfg.get("auto_window_start", 22)
        win_end = cfg.get("auto_window_end", 5)
        if not in_window(jam, win_start, win_end):
            return False

    if types is None:
        types = cfg.get("auto_types", ["penyulang", "trafo", "tegangan"])
    types = [t for t in ("penyulang", "trafo", "tegangan") if t in types]

    # Rich banner untuk auto mode
    if RICH_AUTO and console and console.is_terminal:
        try:
            from rich.panel import Panel
            from rich.rule import Rule
            console.print()
            console.print(Rule(f"[bold bright_yellow]AUTO MODE · Jam {jam:02d}:00 · {date_str}[/]", style="bright_yellow"))
            dry_badge = "[bold magenta] DRY-RUN [/]" if dry_run else "[bold green] LIVE [/]"
            console.print(f"  Types: [bold bright_yellow]{','.join(types)}[/]  {dry_badge}")
            console.print()
        except Exception:
            pass
    else:
        log("=" * 60)
        log(f"AUTO MODE: jam {jam:02d}:00, date {date_str}, types={','.join(types)}, dry_run={dry_run}")
        log("=" * 60)

    nip = cfg.get("nip")
    password = cfg.get("password")
    if not nip or not password:
        log("Kredensial SUPER-I belum diset.", "ERROR")
        return False

    try:
        token, user = a.login(nip, password)
        log(f"[OK] SUPER-I login OK: {user.get('namaLengkap')}")
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg:
            log(f"SUPER-I login gagal 401: NIP/password salah. Detail: {e}", "ERROR")
            log(f"Solusi: superi cli -> [S] Setup", "ERROR")
        else:
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

        if RICH_AUTO and console and console.is_terminal:
            console.print(f"\n  [bold bright_yellow]→ {full_type.upper()}[/]")
        else:
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

    # Summary dengan Rich Panel
    if RICH_AUTO and console and console.is_terminal:
        try:
            from rich.panel import Panel
            success = total['success']
            fail = total['fail']
            skipped = total['skipped']
            anomaly = total['anomaly']

            summary_text = f"[bold green]✓ {success}[/] berhasil"
            if fail:
                summary_text += f"  [bold red]✗ {fail} gagal[/]"
            if skipped:
                summary_text += f"  [dim]⊘ {skipped} skip[/]"
            if anomaly:
                summary_text += f"  [bold yellow]⚡ {anomaly} anomali[/]"

            border = "green" if fail == 0 else "bright_yellow"
            console.print()
            console.print(Panel(summary_text, title="[bold bright_yellow]Input Selesai[/]", border_style=border, width=62))
        except Exception:
            log(f"\nINPUT SELESAI: ✓{total['success']} ✗{total['fail']} ⊘{total['skipped']} ⚠{total['anomaly']}")
    else:
        log("\n" + "=" * 60)
        log(f"INPUT SELESAI: ✓{total['success']} ✗{total['fail']} ⊘{total['skipped']} ⚠{total['anomaly']}")

    if not dry_run and cfg.get("auto_sync_portal", True) and successful_types:
        if cfg.get("portal_user") and cfg.get("portal_password"):
            if RICH_AUTO and console and console.is_terminal:
                console.print(f"\n  [bold bright_yellow]→ SYNC ke Portal APD (jam {jam:02d}, {','.join(successful_types)})[/]")
            else:
                log(f"\n→ SYNC ke Portal APD (jam {jam:02d}, types={','.join(successful_types)})")
            for t in successful_types:
                sync_ok = False
                for attempt in range(1, 4):
                    try:
                        ok = s.do_sync(t, jam, jam, date_str, dry_run=False)
                        if ok:
                            sync_ok = True
                            break
                        log(f"Sync {t} ada error (attempt {attempt}/3)", "WARN")
                    except Exception as e:
                        log(f"Sync {t} gagal attempt {attempt}/3: {e}", "ERROR")
                    if attempt < 3:
                        time.sleep(_h_jittered(10.0))
                if not sync_ok:
                    log(f"Sync {t} gagal final setelah 3 attempt", "ERROR")
        else:
            log("Portal APD credentials belum diset, skip sync", "WARN")

    if RICH_AUTO and console and console.is_terminal:
        try:
            from rich.rule import Rule
            console.print(Rule("[dim]AUTO MODE selesai[/]", style="dim"))
            console.print()
        except Exception:
            pass
    else:
        log("=" * 60)
        log("AUTO MODE selesai\n")

    return total["fail"] == 0

# ============================================================
# COMMANDS (Rich Edition)
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

    if RICH_AUTO and console:
        try:
            from rich.panel import Panel
            console.print(Panel(
                f"[bold green]✓ Auto mode AKTIF[/]\n"
                f"Window: [bold bright_yellow]{cfg['auto_window_start']:02d}:00 - {cfg['auto_window_end']:02d}:00[/]\n"
                f"Types:  [white]{', '.join(cfg['auto_types'])}[/]\n"
                f"Sync:   {'[bold green]YES[/]' if cfg['auto_sync_portal'] else '[bold red]NO[/]'}\n"
                f"Retry:  {cfg['auto_retry_attempts']}x, jeda {cfg['auto_retry_delay']}s",
                title="[bold bright_yellow]Auto Mode[/]", border_style="green", width=55
            ))
            return
        except Exception:
            pass

    print(f"\n  ✓ Auto mode AKTIF")
    print(f"  Window: {cfg['auto_window_start']:02d}:00 - {cfg['auto_window_end']:02d}:00")
    print(f"  Types : {', '.join(cfg['auto_types'])}")
    print(f"  Sync  : {'YES' if cfg['auto_sync_portal'] else 'NO'}\n")

def cmd_disable():
    cfg = load_cfg()
    cfg["auto_enabled"] = False
    save_cfg(cfg)

    if RICH_AUTO and console:
        try:
            from rich.panel import Panel
            console.print(Panel(f"[dim]⊘ Auto mode NONAKTIF[/]", border_style="dim", width=40))
            return
        except Exception:
            pass
    print(f"\n  ⊘ Auto mode NONAKTIF\n")

def cmd_status():
    cfg = load_cfg()
    enabled = cfg.get("auto_enabled", False)

    if RICH_AUTO and console:
        try:
            from rich.panel import Panel
            from rich.table import Table
            status_badge = "[bold green]● AKTIF[/]" if enabled else "[dim]○ NONAKTIF[/]"
            grid = Table.grid(padding=(0,1))
            grid.add_column(style="bold bright_yellow", width=10)
            grid.add_column(style="white")
            grid.add_row("Status:", status_badge)
            if enabled:
                grid.add_row("Window:", f"{cfg.get('auto_window_start',22):02d}:00 - {cfg.get('auto_window_end',5):02d}:00")
                grid.add_row("Types:", ', '.join(cfg.get('auto_types', [])))
                grid.add_row("Sync:", "YES" if cfg.get('auto_sync_portal', True) else "NO")
                grid.add_row("Retry:", f"{cfg.get('auto_retry_attempts', 5)}x, jeda {cfg.get('auto_retry_delay', 10)}s")
            grid.add_row("Log:", f"[dim]{LOG_FILE}[/]")

            border = "bright_yellow" if enabled else "dim"
            console.print(Panel(grid, title="[bold bright_yellow]Auto Mode Status[/]", border_style=border, width=55))
            return
        except Exception:
            pass

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
        if RICH_AUTO and console:
            try:
                from rich.panel import Panel
                help_text = __doc__ or ""
                console.print(Panel(help_text.strip(), title="[bold bright_yellow]Help - Auto Mode[/]", border_style="bright_yellow", width=80))
                console.print("\n[dim]Tambahan (logout): --logout [--yes] [--purge-all] [--keep-portal] [--keep-scheduler][/]\n")
            except Exception:
                print(__doc__)
        else:
            print(__doc__)
            print("\nTambahan (logout): --logout [--yes] [--purge-all] [--keep-portal] [--keep-scheduler]")
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
    if "--logout" in args or "--lo" in args:
        extra = [a for a in args if a not in ("--logout", "--lo")]
        try:
            a.cmd_logout_cli(extra)
        except AttributeError:
            cfg = load_cfg()
            if "--yes" not in extra and "-y" not in extra:
                if RICH_AUTO and console:
                    try:
                        from rich.prompt import Confirm
                        if not Confirm.ask("  [bold red]Logout akun?[/] Ini akan hapus kredensial + auto OFF + hapus scheduler.", console=console):
                            console.print("  [dim]Dibatalkan.[/]")
                            return
                    except Exception:
                        ans = input("\n  Logout akun? Ini akan hapus kredensial + auto OFF + hapus scheduler.\n  Yakin? (y/N): ").strip().lower()
                        if ans != 'y':
                            print("  Dibatalkan.")
                            return
                else:
                    ans = input("\n  Logout akun? Ini akan hapus kredensial + auto OFF + hapus scheduler.\n  Yakin? (y/N): ").strip().lower()
                    if ans != 'y':
                        print("  Dibatalkan.")
                        return
            keep_portal = "--keep-portal" in extra
            keep_sched = "--keep-scheduler" in extra
            purge = "--purge-all" in extra
            try:
                import shutil
                if os.path.exists(CONFIG_FILE):
                    shutil.copy2(CONFIG_FILE, CONFIG_FILE + ".bak")
            except Exception:
                pass
            if purge:
                for p in [CONFIG_FILE]:
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
            else:
                c = load_cfg()
                for k in ["nip", "password"] + ([] if keep_portal else ["portal_user", "portal_password"]):
                    c.pop(k, None)
                c["auto_enabled"] = False
                save_cfg(c)
            if not keep_sched:
                try:
                    if hasattr(a, "scheduler_is_installed") and a.scheduler_is_installed():
                        if hasattr(a, "cron_uninstall"):
                            a.cron_uninstall()
                except Exception:
                    pass
            if RICH_AUTO and console:
                console.print("\n  [bold green]✓ Logout berhasil. Auto OFF + kredensial dihapus.[/]\n")
            else:
                print("\n  ✓ Logout berhasil. Auto OFF + kredensial dihapus.")
        return

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
