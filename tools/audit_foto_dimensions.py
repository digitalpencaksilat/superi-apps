#!/usr/bin/env python3
"""
Audit dimensi foto SUPER-I APP dari server
- Login via .superi_config.json
- Fetch semua beban-penyulang, beban-trafo, tegangan-trafo untuk range tanggal
- Download via /api/media/images/...
- Analisis dimensi, size, progressive, COM segment, EXIF
- Output CSV + summary

Usage:
  python3 tools/audit_foto_dimensions.py --date 2026-07-15 --periode 15
  python3 tools/audit_foto_dimensions.py --range 7 --all-periode
  python3 tools/audit_foto_dimensions.py --range 30 --sample 2
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(SCRIPT_DIR, ".superi_config.json")

BASE_URL = "https://super-i-app.plnes.co.id"
API_BASE = f"{BASE_URL}/api"

try:
    from PIL import Image
except ImportError:
    print("Pillow required: pip install Pillow")
    sys.exit(1)

import urllib.request
import urllib.error


def load_token():
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    nip = cfg["nip"]
    pwd = cfg["password"]
    req = urllib.request.Request(
        f"{API_BASE}/auth/login-mobile",
        data=json.dumps({"nip": nip, "password": pwd}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    token = data["data"]["access_token"]
    user = data["data"]["user"]
    print(f"Login OK: {user.get('namaLengkap')} ({nip})")
    return token, cfg.get("gi_id", "222")


def api_get(token, path, params=None):
    url = f"{API_BASE}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def fetch_image_bytes(token, uri):
    """Fetch via /api + uri, return bytes"""
    url = BASE_URL + "/api" + uri
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            b = resp.read()
            ct = resp.headers.get("Content-Type", "")
            return b, ct, None
    except Exception as e:
        return None, None, str(e)


def analyze_jpeg(b):
    """Return dict with dimension info or None"""
    if not b:
        return None
    # Check header
    if not b.startswith(b"\xff\xd8"):
        return {
            "valid_jpeg": False,
            "width": 0,
            "height": 0,
            "mode": "invalid",
            "format": "not_jpeg",
            "bytes": len(b),
            "is_progressive": False,
            "has_com": False,
            "exif_count": 0,
            "is_dummy_172": len(b) == 172,
            "sha_short": hashlib.sha256(b).hexdigest()[:12],
            "head_hex": b[:20].hex(),
        }
    try:
        im = Image.open(io.BytesIO(b))
        w, h = im.size
        # progressive?
        is_progressive = False
        has_com = False
        # Check info and raw markers
        # progressive JPEG has info 'progression' or 'progressive'
        if im.info.get("progression") or im.info.get("progressive"):
            is_progressive = True
        # Also scan for SOF2 marker (0xFFC2) = progressive
        # SOF0 = 0xFFC0 baseline
        if b"\xff\xc2" in b:
            is_progressive = True
        # COM segment FF FE
        if b"\xff\xfe" in b:
            has_com = True
        # EXIF
        try:
            exif = im.getexif()
            exif_count = len(exif)
        except:
            exif_count = 0
        return {
            "valid_jpeg": True,
            "width": w,
            "height": h,
            "mode": im.mode,
            "format": im.format,
            "bytes": len(b),
            "is_progressive": is_progressive,
            "has_com": has_com,
            "exif_count": exif_count,
            "is_dummy_172": len(b) == 172,
            "sha_short": hashlib.sha256(b).hexdigest()[:12],
            "head_hex": "",
            "jfif_info": str(im.info.get("jfif", "")),
        }
    except Exception as e:
        return {
            "valid_jpeg": False,
            "width": 0,
            "height": 0,
            "mode": "parse_fail",
            "format": "fail",
            "bytes": len(b),
            "is_progressive": False,
            "has_com": b"\xff\xfe" in b if b else False,
            "exif_count": 0,
            "is_dummy_172": len(b) == 172,
            "sha_short": hashlib.sha256(b).hexdigest()[:12],
            "head_hex": b[:20].hex() if b else "",
            "error": str(e)[:200],
        }


def audit_date(token, gi_id, date_str, sample_per_type=5, all_periode=False, target_periode=15):
    """Fetch one date, return list of entries"""
    results = []
    endpoints = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    for data_type, path in endpoints.items():
        try:
            data = api_get(token, path, {"garduIndukId": gi_id, "date": date_str})
            items = data.get("data", {}).get("items", [])
        except Exception as e:
            print(f"  [{date_str}] {data_type} list FAIL: {e}")
            continue

        # Collect foto URIs
        foto_list = []  # (nama, periode, uri, durasi, address, foto_date, extra)
        for it in items:
            nama = it.get("nama", "?")
            if data_type == "tegangan-trafo":
                for teg in it.get("tegangan", []):
                    per = teg.get("periode")
                    if not all_periode and per != target_periode:
                        continue
                    hv = teg.get("fotoHV", {})
                    mv = teg.get("fotoMV", {})
                    for sub, fobj in [("HV", hv), ("MV", mv)]:
                        uri = fobj.get("uri")
                        if not uri:
                            continue
                        foto_list.append(
                            {
                                "item_nama": nama,
                                "data_type": data_type,
                                "subtype": sub,
                                "periode": per,
                                "uri": uri,
                                "durasi": teg.get("durasi"),
                                "address": fobj.get("address", ""),
                                "foto_date": fobj.get("date", ""),
                                "mv": teg.get("mv"),
                                "hv": teg.get("hv"),
                            }
                        )
            else:
                for beb in it.get("beban", []):
                    per = beb.get("periode")
                    if not all_periode and per != target_periode:
                        continue
                    foto = beb.get("foto", {})
                    uri = foto.get("uri")
                    if not uri:
                        continue
                    foto_list.append(
                        {
                            "item_nama": nama,
                            "data_type": data_type,
                            "subtype": "",
                            "periode": per,
                            "uri": uri,
                            "durasi": beb.get("durasi"),
                            "address": foto.get("address", ""),
                            "foto_date": foto.get("date", ""),
                            "beban": beb.get("beban"),
                        }
                    )
        # Sample
        if sample_per_type and len(foto_list) > sample_per_type and not all_periode:
            # Take first N per periode target
            foto_list = foto_list[:sample_per_type]
        elif not all_periode:
            foto_list = foto_list[:sample_per_type]

        if all_periode:
            # Keep all periode but limit per date to avoid too many requests
            # sample 2 per periode
            per_groups = defaultdict(list)
            for f in foto_list:
                per_groups[f["periode"]].append(f)
            sampled = []
            for per in sorted(per_groups.keys()):
                sampled.extend(per_groups[per][:2])
            foto_list = sampled

        # Fetch images parallel
        def fetch_one(f):
            b, ct, err = fetch_image_bytes(token, f["uri"])
            info = analyze_jpeg(b) if b else None
            row = {
                "date": date_str,
                "data_type": f["data_type"],
                "item_nama": f["item_nama"],
                "subtype": f["subtype"],
                "periode": f["periode"],
                "uri": f["uri"],
                "durasi": f["durasi"],
                "foto_date": f["foto_date"],
                "address_short": f["address"][:60],
            }
            if info:
                row.update(info)
            else:
                row.update(
                    {
                        "valid_jpeg": False,
                        "width": 0,
                        "height": 0,
                        "bytes": 0,
                        "is_progressive": False,
                        "has_com": False,
                    }
                )
                row["error"] = err or "fetch fail"
            return row

        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(fetch_one, f) for f in foto_list]
            for fut in as_completed(futs):
                try:
                    r = fut.result()
                    results.append(r)
                except Exception as e:
                    print(f"    fetch thread FAIL {e}")

        print(f"  [{date_str}] {data_type}: fetched {len(foto_list)} samples (target per={target_periode if not all_periode else 'ALL'}) -> {len([x for x in results if x['date']==date_str and x['data_type']==data_type])} OK")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="single date YYYY-MM-DD")
    parser.add_argument("--periode", type=int, default=15, help="target periode 0-23")
    parser.add_argument("--range", type=int, default=7, dest="range_days", help="how many days back from today")
    parser.add_argument("--all-periode", action="store_true", help="audit all 24 periode per date")
    parser.add_argument("--sample", type=int, default=5, help="samples per data_type per date")
    parser.add_argument("--gi", default=None, help="GI ID")
    parser.add_argument("--out", default=None, help="output CSV path")
    args = parser.parse_args()

    token, default_gi = load_token()
    gi_id = args.gi or default_gi
    print(f"GI ID: {gi_id}")

    # Determine dates
    if args.date:
        dates = [args.date]
    else:
        today = datetime.now().date()
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(args.range_days)]
        # Also add some old dates for real app detection
        # We'll add specific historic dates if range >=7
        if args.range_days >= 7:
            extra_old = ["2026-06-19", "2026-06-18", "2026-06-10", "2026-05-20", "2026-03-01", "2026-02-15", "2026-01-20"]
            # Only add if not already in list and within reasonable range (keep order newest first)
            for d in extra_old:
                if d not in dates:
                    dates.append(d)

    print(f"Auditing {len(dates)} dates: {dates[:5]} ... {dates[-3:] if len(dates)>5 else ''}")
    print(f"Target periode: {args.periode if not args.all_periode else 'ALL (0-23)'}")
    print(f"Sample per type: {args.sample}")

    all_results = []
    for date_str in dates:
        print(f"\n=== DATE {date_str} ===")
        try:
            res = audit_date(token, gi_id, date_str, sample_per_type=args.sample, all_periode=args.all_periode, target_periode=args.periode)
            all_results.extend(res)
        except Exception as e:
            print(f"  FAIL auditing {date_str}: {e}")
        time.sleep(0.3)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    if not all_results:
        print("No results!")
        return

    # group by valid
    valid = [r for r in all_results if r.get("valid_jpeg")]
    invalid = [r for r in all_results if not r.get("valid_jpeg")]
    dummy_172 = [r for r in all_results if r.get("is_dummy_172")]
    progressive = [r for r in all_results if r.get("is_progressive")]
    has_com = [r for r in all_results if r.get("has_com")]

    print(f"Total fetched: {len(all_results)}")
    print(f"Valid JPEG: {len(valid)} | Invalid/parse fail: {len(invalid)}")
    print(f"Dummy 172 bytes (old bypass): {len(dummy_172)}")
    print(f"Progressive JPEG: {len(progressive)}")
    print(f"Has COM segment FF FE: {len(has_com)}")

    if valid:
        widths = [r["width"] for r in valid]
        heights = [r["height"] for r in valid]
        byte_sizes = [r["bytes"] for r in valid]
        print(f"\nDimensions:")
        print(f"  Width:  min={min(widths)} max={max(widths)} avg={sum(widths)/len(widths):.0f} | unique {sorted(set(widths))}")
        print(f"  Height: min={min(heights)} max={max(heights)} avg={sum(heights)/len(heights):.0f} | unique {sorted(set(heights))}")
        print(f"  Aspect: {Counter([f'{w}x{h}' for w,h in zip(widths,heights)]).most_common(10)}")
        print(f"  Bytes:  min={min(byte_sizes)} max={max(byte_sizes)} avg={sum(byte_sizes)/len(byte_sizes):.0f}")
        # Size distribution
        size_buckets = Counter()
        for sz in byte_sizes:
            if sz < 1000:
                size_buckets["<1KB (dummy)"] += 1
            elif sz < 10000:
                size_buckets["1-10KB"] += 1
            elif sz < 30000:
                size_buckets["10-30KB"] += 1
            elif sz < 60000:
                size_buckets["30-60KB"] += 1
            elif sz < 100000:
                size_buckets["60-100KB"] += 1
            else:
                size_buckets[">100KB"] += 1
        print(f"  Size distribution: {dict(size_buckets)}")

    # Per date breakdown
    print(f"\nPer-date breakdown (W x H avg):")
    per_date = defaultdict(list)
    for r in all_results:
        per_date[r["date"]].append(r)
    for d in sorted(per_date.keys()):
        rows = per_date[d]
        v = [x for x in rows if x.get("valid_jpeg")]
        if v:
            avg_w = sum(x["width"] for x in v)/len(v)
            avg_h = sum(x["height"] for x in v)/len(v)
            avg_b = sum(x["bytes"] for x in v)/len(v)
            dims = Counter([f"{x['width']}x{x['height']}" for x in v])
            print(f"  {d}: {len(v)}/{len(rows)} valid, avg {avg_w:.0f}x{avg_h:.0f} {avg_b:.0f} bytes | dims {dict(dims)} | prog {sum(1 for x in v if x['is_progressive'])} com {sum(1 for x in v if x['has_com'])}")

    # Per data_type
    print(f"\nPer data_type:")
    per_type = defaultdict(list)
    for r in all_results:
        per_type[r["data_type"]].append(r)
    for typ in per_type:
        rows = per_type[typ]
        v = [x for x in rows if x.get("valid_jpeg")]
        if v:
            avg_w = sum(x["width"] for x in v)/len(v) if v else 0
            avg_h = sum(x["height"] for x in v)/len(v) if v else 0
            avg_b = sum(x["bytes"] for x in v)/len(v) if v else 0
            print(f"  {typ}: {len(v)}/{len(rows)} valid, avg {avg_w:.0f}x{avg_h:.0f} {avg_b:.0f} bytes")

    # Save CSV
    out_path = args.out
    if not out_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(SCRIPT_DIR, f"foto_audit_{ts}.csv")
    fieldnames = ["date","data_type","item_nama","subtype","periode","width","height","bytes","valid_jpeg","is_progressive","has_com","is_dummy_172","exif_count","sha_short","uri","durasi","foto_date","address_short","error","head_hex"]
    with open(out_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            # ensure only fieldnames
            row = {k: r.get(k, "") for k in fieldnames}
            writer.writerow(row)
    print(f"\nCSV saved to: {out_path}")

    # Save JSON summary too
    summary_path = out_path.replace(".csv", "_summary.json")
    summary = {
        "total": len(all_results),
        "valid": len(valid),
        "dummy_172": len(dummy_172),
        "progressive": len(progressive),
        "has_com": len(has_com),
        "dates": dates,
        "per_date_stats": {},
    }
    for d in per_date:
        rows = per_date[d]
        v = [x for x in rows if x.get("valid_jpeg")]
        summary["per_date_stats"][d] = {
            "total": len(rows),
            "valid": len(v),
            "dims": dict(Counter([f"{x['width']}x{x['height']}" for x in v])),
            "avg_bytes": sum(x["bytes"] for x in v)/len(v) if v else 0,
        }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary JSON saved to: {summary_path}")


if __name__ == "__main__":
    main()
