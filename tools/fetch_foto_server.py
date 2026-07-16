#!/usr/bin/env python3
"""
Fetch foto asli dari server SUPER-I APP
- Login via .superi_config.json (fallback .bak, env, home)
- List beban-penyulang, beban-trafo, tegangan-trafo per tanggal
- Filter periode 00-06 (sesuai request)
- Download via /api + uri
- Simpan ke photo/server/YYYY-MM-DD/{tipe}/

Usage:
  python3 tools/fetch_foto_server.py --date 2026-07-15 --periode-start 0 --periode-end 6
  python3 tools/fetch_foto_server.py  (auto yesterday yesterday = today-1)
  python3 tools/fetch_foto_server.py --date 2026-07-15 --types beban-penyulang,beban-trafo
  python3 tools/fetch_foto_server.py --workers 12 --out photo/server

Struktur output:
  photo/server/2026-07-15/beban-penyulang/P00_CASABLANCA4_abc123.jpg
  photo/server/2026-07-15/beban-penyulang/P00_CASABLANCA4_abc123.json (sidecar metadata)
  photo/server/2026-07-15/beban-trafo/P03_TRAFO_2_def456.jpg
  photo/server/2026-07-15/tegangan-trafo/P01_TRAFO_1_HV_a1b2c3.jpg + P01_TRAFO_1_MV_...
  photo/server/2026-07-15/summary.json
  photo/server/index.json (global)

Alamat: tetap pakai 13 alamat GI Manggarai untuk input (humanizer),
        foto yang diambil hanya JPEG asli dari server untuk dicek manual.
"""
import argparse
import json
import os
import sys
import re
import hashlib
import time
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(SCRIPT_DIR, ".superi_config.json")
CONFIG_BAK = os.path.join(SCRIPT_DIR, ".superi_config.json.bak")
HOME_CONFIG = os.path.expanduser("~/.superi_config.json")

BASE_URL = "https://super-i-app.plnes.co.id"
API_BASE = f"{BASE_URL}/api"

import urllib.request
import urllib.error

try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Pillow not installed, jpeg validation will be basic. pip install Pillow")


def load_config():
    """Load creds from multiple sources, fallback chain."""
    candidates = [CONFIG_FILE, CONFIG_BAK, HOME_CONFIG]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    cfg = json.load(f)
                if cfg.get("nip") and cfg.get("password"):
                    print(f"Config loaded from: {path}")
                    return cfg
            except Exception as e:
                print(f"Failed load {path}: {e}")
                continue
    # env fallback
    nip = os.environ.get("SUPERI_NIP") or os.environ.get("NIP")
    pwd = os.environ.get("SUPERI_PASSWORD") or os.environ.get("SUPERI_PASS")
    if nip and pwd:
        print("Config from ENV vars")
        return {"nip": nip, "password": pwd, "gi_id": os.environ.get("GI_ID", "222")}
    print(f"Config not found. Checked: {candidates} + env SUPERI_NIP/PASSWORD")
    print("Buat .superi_config.json dari .superi_config.example.json dulu, atau copy dari .bak")
    sys.exit(1)


def load_token():
    cfg = load_config()
    nip = cfg["nip"]
    pwd = cfg["password"]
    req = urllib.request.Request(
        f"{API_BASE}/auth/login-mobile",
        data=json.dumps({"nip": nip, "password": pwd}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"Login HTTP {e.code}: {body}")
        sys.exit(1)
    token = data["data"]["access_token"]
    user = data["data"]["user"]
    gi_id = str(cfg.get("gi_id", "222"))
    print(f"Login OK: {user.get('namaLengkap')} ({nip}) GI={gi_id}")
    return token, gi_id


def api_get(token, path, params=None):
    url = f"{API_BASE}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()[:500]
        except:
            body = str(e)
        print(f"  api_get FAIL {path} {params} HTTP {e.code}: {body[:200]}")
        return {"data": {"items": []}, "error": body}
    except Exception as e:
        print(f"  api_get error {path}: {e}")
        return {"data": {"items": []}, "error": str(e)}


def fetch_image_bytes(token, uri):
    """Fetch image via BASE_URL + /api + uri"""
    url = BASE_URL + "/api" + uri
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            b = resp.read()
            ct = resp.headers.get("Content-Type", "")
            return b, ct, None
    except Exception as e:
        return None, None, str(e)


def sanitize_name(name: str) -> str:
    """Sanitasi nama penyulang/trafo untuk filename: uppercase, alnum+_, max 30 chars."""
    if not name:
        return "UNKNOWN"
    # Replace non-alnum with _
    s = re.sub(r'[^A-Za-z0-9]+', '_', name.strip())
    s = s.strip('_').upper()
    # Potong max 30
    if len(s) > 30:
        s = s[:30]
    return s or "UNKNOWN"


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def save_foto(date_dir_base, data_type, periode, item_nama, subtype, img_bytes, sha_short, uri, meta_extra):
    """
    Simpan foto ke photo/server/YYYY-MM-DD/{tipe}/
    Return saved_path atau None
    """
    tipe_folder = data_type  # beban-penyulang, beban-trafo, tegangan-trafo
    folder = os.path.join(date_dir_base, tipe_folder)
    ensure_dir(folder)

    safe_nama = sanitize_name(item_nama)
    per_str = f"P{periode:02d}"

    if data_type == "tegangan-trafo":
        # contoh: P01_TRAFO_1_HV_a1b2c3.jpg
        base = f"{per_str}_{safe_nama}_{subtype}_{sha_short}"
    else:
        base = f"{per_str}_{safe_nama}_{sha_short}"

    jpg_path = os.path.join(folder, base + ".jpg")
    json_path = os.path.join(folder, base + ".json")

    # Handle duplikat nama file (jika sudah ada, tambahkan counter)
    counter = 1
    orig_jpg = jpg_path
    orig_json = json_path
    while os.path.exists(jpg_path):
        # jika file existing sha sama, skip? cek bytes yang sudah ada
        try:
            with open(jpg_path, 'rb') as f:
                existing = f.read()
            if hashlib.sha256(existing).hexdigest()[:12] == sha_short or existing == img_bytes:
                # sudah ada yang sama persis, jangan timpa, return existing
                # tapi tetap pastikan json ada
                if not os.path.exists(json_path):
                    with open(json_path, 'w', encoding='utf-8') as jf:
                        json.dump(meta_extra, jf, indent=2, ensure_ascii=False)
                return jpg_path, True  # True = skipped duplicate
        except:
            pass
        # beda file tapi nama tabrakan (jarang), tambah suffix
        jpg_path = os.path.join(folder, f"{base}_{counter}.jpg")
        json_path = os.path.join(folder, f"{base}_{counter}.json")
        counter += 1
        if counter > 20:
            break

    # Simpan jpg
    with open(jpg_path, 'wb') as f:
        f.write(img_bytes)
    # Simpan json sidecar
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(meta_extra, jf, indent=2, ensure_ascii=False)

    return jpg_path, False


def main():
    parser = argparse.ArgumentParser(description="Fetch foto asli dari server SUPER-I APP (00-06)")
    parser.add_argument("--date", default=None, help="Tanggal YYYY-MM-DD, default yesterday (1 hari kebelakang)")
    parser.add_argument("--periode-start", type=int, default=0, help="Periode awal (default 0)")
    parser.add_argument("--periode-end", type=int, default=6, help="Periode akhir (default 6) inclusive")
    parser.add_argument("--types", default="beban-penyulang,beban-trafo,tegangan-trafo", help="comma-separated data types")
    parser.add_argument("--out", default=None, help="Output dir, default photo/server di project")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers (default 8)")
    parser.add_argument("--gi", default=None, help="Override GI ID")
    args = parser.parse_args()

    # Determine date: default yesterday
    if args.date:
        target_date = args.date
    else:
        yesterday = datetime.now().date() - timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")

    # Validate date
    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except:
        print(f"Invalid date format: {target_date}, must YYYY-MM-DD")
        sys.exit(1)

    p_start = max(0, min(23, args.periode_start))
    p_end = max(0, min(23, args.periode_end))
    if p_start > p_end:
        p_start, p_end = p_end, p_start
    periode_filter = set(range(p_start, p_end+1))

    types = [t.strip() for t in args.types.split(',') if t.strip()]
    valid_types = {"beban-penyulang", "beban-trafo", "tegangan-trafo"}
    types = [t for t in types if t in valid_types]
    if not types:
        types = list(valid_types)

    out_base = args.out or os.path.join(SCRIPT_DIR, "photo", "server")
    date_dir_base = os.path.join(out_base, target_date)
    ensure_dir(date_dir_base)

    print("="*70)
    print(f"FETCH FOTO SERVER - SUPER-I APP")
    print("="*70)
    print(f"Tanggal        : {target_date} (1 hari kebelakang jika tidak set --date)")
    print(f"Periode filter : {p_start:02d}-{p_end:02d} inclusive -> {sorted(periode_filter)}")
    print(f"Tipe data      : {types}")
    print(f"Output         : {date_dir_base}/{{tipe}}/")
    print(f"Workers        : {args.workers}")
    print(f"Alamat input   : tetap 13 alamat GI Manggarai (humanizer), tidak pakai alamat server")
    print("="*70)

    token, default_gi = load_token()
    gi_id = args.gi or default_gi

    endpoints = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }

    all_foto_tasks = []  # list of dict dengan uri + metadata
    per_type_counts = defaultdict(int)

    for data_type in types:
        if data_type not in endpoints:
            continue
        path = endpoints[data_type]
        print(f"\n[LIST] {data_type} {target_date} GI={gi_id}")
        data = api_get(token, path, {"garduIndukId": gi_id, "date": target_date})
        items = data.get("data", {}).get("items", [])
        print(f"  Items returned: {len(items)}")
        if not items and data.get("error"):
            print(f"  Error: {data.get('error')[:200]}")

        collected = 0
        for it in items:
            item_id = it.get("id")
            nama = it.get("nama", "?")
            if data_type == "tegangan-trafo":
                for teg in it.get("tegangan", []):
                    per = teg.get("periode")
                    if per not in periode_filter:
                        continue
                    for sub, fobj in [("HV", teg.get("fotoHV", {})), ("MV", teg.get("fotoMV", {}))]:
                        uri = fobj.get("uri")
                        if not uri:
                            continue
                        all_foto_tasks.append({
                            "data_type": data_type,
                            "item_id": item_id,
                            "item_nama": nama,
                            "periode": per,
                            "subtype": sub,
                            "uri": uri,
                            "durasi": teg.get("durasi"),
                            "mv": teg.get("mv"),
                            "hv": teg.get("hv"),
                            "foto_date": fobj.get("date", ""),
                            "foto_address": fobj.get("address", ""),
                            "latitude": fobj.get("latitude"),
                            "longitude": fobj.get("longitude"),
                        })
                        collected += 1
                        per_type_counts[data_type] += 1
            else:
                for beb in it.get("beban", []):
                    per = beb.get("periode")
                    if per not in periode_filter:
                        continue
                    foto = beb.get("foto", {})
                    uri = foto.get("uri")
                    if not uri:
                        continue
                    all_foto_tasks.append({
                        "data_type": data_type,
                        "item_id": item_id,
                        "item_nama": nama,
                        "periode": per,
                        "subtype": "",
                        "uri": uri,
                        "durasi": beb.get("durasi"),
                        "beban": beb.get("beban"),
                        "foto_date": foto.get("date", ""),
                        "foto_address": foto.get("address", ""),
                        "latitude": foto.get("latitude"),
                        "longitude": foto.get("longitude"),
                    })
                    collected += 1
                    per_type_counts[data_type] += 1
        print(f"  Collected URIs in filter P{p_start:02d}-P{p_end:02d}: {collected}")

        time.sleep(0.2)

    if not all_foto_tasks:
        print("\nTidak ada foto ditemukan untuk filter tersebut.")
        print("Kemungkinan:")
        print(" - Data periode 00-06 belum diinput operator di tanggal tersebut")
        print(" - Coba tanggal lain atau perluas periode")
        # tetap buat summary kosong
        summary_path = os.path.join(date_dir_base, "summary.json")
        with open(summary_path, 'w') as f:
            json.dump({
                "date": target_date,
                "periode_filter": sorted(list(periode_filter)),
                "types": types,
                "total_uri": 0,
                "message": "No foto found"
            }, f, indent=2)
        print(f"Summary kosong disimpan: {summary_path}")
        return

    total_to_fetch = len(all_foto_tasks)
    print(f"\nTotal foto URI akan di-download: {total_to_fetch}")
    print(f"  breakdown: {dict(per_type_counts)}")
    print(f"  estimasi size: ~{total_to_fetch * 27 / 1024:.1f} MB (avg 27KB per foto)")
    print(f"  output: {date_dir_base}/{{tipe}}/")
    print(f"  mulai download dengan {args.workers} workers...\n")

    saved_results = []
    failed = []
    skipped_dup = 0

    def download_one(task):
        uri = task["uri"]
        b, ct, err = fetch_image_bytes(token, uri)
        if not b:
            return {"task": task, "ok": False, "error": err, "saved_path": None}
        # Validate JPEG header
        if not b.startswith(b"\xff\xd8"):
            return {"task": task, "ok": False, "error": f"Not JPEG, Content-Type={ct}, head={b[:20].hex()}", "saved_path": None}
        # Optional PIL validation
        width = height = 0
        if HAS_PIL:
            try:
                im = Image.open(io.BytesIO(b))
                width, height = im.size
                # quick check valid
            except Exception as e:
                return {"task": task, "ok": False, "error": f"PIL parse fail: {e}", "saved_path": None}

        sha_full = hashlib.sha256(b).hexdigest()
        sha_short = sha_full[:12]
        meta = {
            "uri": uri,
            "item_id": task["item_id"],
            "item_nama": task["item_nama"],
            "data_type": task["data_type"],
            "periode": task["periode"],
            "subtype": task["subtype"],
            "durasi": task.get("durasi"),
            "beban": task.get("beban"),
            "mv": task.get("mv"),
            "hv": task.get("hv"),
            "foto_date_original": task.get("foto_date"),
            "foto_address_original": task.get("foto_address"),
            "latitude_original": task.get("latitude"),
            "longitude_original": task.get("longitude"),
            "sha256": sha_full,
            "sha_short": sha_short,
            "bytes": len(b),
            "content_type": ct,
            "width": width,
            "height": height,
            "fetch_timestamp": datetime.now().isoformat(),
            "note": "Alamat asli disimpan, tapi untuk input nanti tetap pakai 13 alamat GI Manggarai (humanizer)",
        }

        saved_path, was_dup = save_foto(date_dir_base, task["data_type"], task["periode"], task["item_nama"], task["subtype"], b, sha_short, uri, meta)
        if saved_path:
            return {"task": task, "ok": True, "saved_path": saved_path, "was_dup": was_dup, "meta": meta, "bytes": len(b), "width": width, "height": height}
        else:
            return {"task": task, "ok": False, "error": "Save failed", "saved_path": None}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(download_one, t): t for t in all_foto_tasks}
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                res = fut.result()
            except Exception as e:
                res = {"ok": False, "error": str(e), "task": futures[fut], "saved_path": None}

            if res["ok"]:
                saved_results.append(res)
                if res.get("was_dup"):
                    skipped_dup += 1
                # print progress setiap 10 atau last
                if done % 20 == 0 or done == total_to_fetch:
                    print(f"  [{done}/{total_to_fetch}] OK saved: {os.path.basename(res['saved_path'])} ({res.get('bytes')} bytes {res.get('width')}x{res.get('height')})")
                else:
                    # singkat
                    print(f"  [{done}/{total_to_fetch}] OK {res['task']['data_type']} P{res['task']['periode']:02d} {res['task']['item_nama']} {res['task']['subtype']} -> {os.path.basename(res['saved_path'])}", end="\r" if done % 5 == 0 else "\n")
            else:
                failed.append(res)
                print(f"  [{done}/{total_to_fetch}] FAIL {res['task']['data_type']} P{res['task']['periode']:02d} {res['task']['item_nama']} uri={res['task']['uri'][:60]} err={res.get('error')}")

    print("\n" + "="*70)
    print("HASIL DOWNLOAD")
    print("="*70)

    # Group saved by type & periode
    by_type = defaultdict(list)
    by_periode = defaultdict(int)
    size_per_type = defaultdict(int)
    dims_counter = defaultdict(int)
    for r in saved_results:
        by_type[r["task"]["data_type"]].append(r)
        by_periode[r["task"]["periode"]] += 1
        size_per_type[r["task"]["data_type"]] += r.get("bytes", 0)
        dims_counter[f"{r.get('width')}x{r.get('height')}"] += 1

    print(f"Tanggal         : {target_date}")
    print(f"Periode filter  : P{p_start:02d}-P{p_end:02d}")
    print(f"Total URI       : {total_to_fetch}")
    print(f"Berhasil        : {len(saved_results)} (duplikat skip: {skipped_dup})")
    print(f"Gagal           : {len(failed)}")

    for t in types:
        cnt = len(by_type.get(t, []))
        sz = size_per_type.get(t, 0)
        print(f"  - {t}: {cnt} foto, {sz/1024:.1f} KB total")

    print(f"\nPer periode:")
    for per in sorted(by_periode.keys()):
        print(f"  P{per:02d}: {by_periode[per]} foto")

    if dims_counter:
        print(f"\nDimensi:")
        for dim, cnt in sorted(dims_counter.items(), key=lambda x: -x[1])[:10]:
            print(f"  {dim}: {cnt}")

    # Save summary.json per tanggal
    summary = {
        "date": target_date,
        "periode_filter": sorted(list(periode_filter)),
        "types": types,
        "total_uri": total_to_fetch,
        "saved": len(saved_results),
        "skipped_dup": skipped_dup,
        "failed": len(failed),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "by_periode": dict(by_periode),
        "size_per_type_bytes": dict(size_per_type),
        "size_per_type_kb": {k: round(v/1024,1) for k,v in size_per_type.items()},
        "dims": dict(dims_counter),
        "output_base": date_dir_base,
        "failed_detail": [{"uri": f["task"]["uri"], "error": f.get("error"), "periode": f["task"]["periode"], "nama": f["task"]["item_nama"]} for f in failed[:20]],
        "note": "Alamat asli disimpan di json sidecar, tapi untuk input nanti tetap pakai 13 alamat GI Manggarai"
    }
    summary_path = os.path.join(date_dir_base, "summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nSummary disimpan: {summary_path}")

    # Update global index.json
    global_index_path = os.path.join(out_base, "index.json")
    global_entry = {
        "date": target_date,
        "periode_filter": summary["periode_filter"],
        "saved": summary["saved"],
        "by_type": summary["by_type"],
        "output": date_dir_base,
        "timestamp": datetime.now().isoformat()
    }
    try:
        if os.path.exists(global_index_path):
            with open(global_index_path, 'r') as f:
                idx = json.load(f)
        else:
            idx = []
        # replace if same date exists
        idx = [e for e in idx if e.get("date") != target_date]
        idx.append(global_entry)
        idx = sorted(idx, key=lambda x: x["date"], reverse=True)
        with open(global_index_path, 'w') as f:
            json.dump(idx, f, indent=2)
        print(f"Global index update: {global_index_path}")
    except Exception as e:
        print(f"Gagal update global index: {e}")

    print("\nContoh file (5 pertama):")
    for r in saved_results[:5]:
        print(f"  {r['saved_path']} ({r.get('bytes')}B {r.get('width')}x{r.get('height')})")

    print(f"\nCek manual folder:")
    print(f"  ls -R {date_dir_base}")
    print(f"  open {date_dir_base}/beban-penyulang/  # macOS")
    print(f"  atau: xdg-open {date_dir_base}/beban-penyulang/  # linux")

    print("\nDone.")


if __name__ == "__main__":
    main()
