#!/usr/bin/env python3
"""
Fix Tegangan Trafo Jam 3 (Periode 3) - Foto tidak tersimpan di server

Perbandingan:
- Beban Penyulang P3: foto tersimpan OK (field "file", 1 foto)
- Beban Trafo P3: foto tersimpan OK (field "file", 1 foto)
- Tegangan Trafo P3: foto TIDAK tersimpan (field "files", 2 foto HV+MV) -> BUG

Fix:
- Hanya proses periode 3 (jam 3) saja
- Cek beban penyulang & trafo P3 untuk konfirmasi mereka OK (tapi JANGAN dihapus)
- Untuk tegangan P3 yang foto missing (uri None), hapus record gagal dan re-upload dengan foto valid
- Verifikasi setelah upload foto benar-benar ada uri

Usage:
  python3 tools/fix_tegangan_jam3.py --date 2026-07-17 --dry-run
  python3 tools/fix_tegangan_jam3.py --date 2026-07-17
  python3 tools/fix_tegangan_jam3.py --date 2026-07-17 --trafo TRAFO_1
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import superi_humanizer as hu
except Exception:
    hu = None

CONFIG_FILE = os.path.join(SCRIPT_DIR, ".superi_config.json")
BASE_URL = "https://super-i-app.plnes.co.id"
API_BASE = f"{BASE_URL}/api"
AUTH_URL = f"{API_BASE}/auth/login-mobile"


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def login(nip, password):
    req = urllib.request.Request(
        AUTH_URL,
        data=json.dumps({"nip": nip, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return data["data"]["access_token"], data["data"]["user"]


def api_get(token, path, params=None):
    url = f"{API_BASE}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def api_delete(token, path):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def upload_tegangan(token, trafo_id, trafo_name, periode, date_str, mv, hv, photo_source="manual"):
    """Upload tegangan dengan 2 foto HV/MV, return (success, record_id, has_uri)"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if hu:
        hu.reset_foto_sequence(date_str, periode)
        durasi = hu.rand_durasi_for_type("tegangan-trafo")
        fotoHV, fotoMV = hu.rand_foto_pair_dicts(date_str, periode, durasi)
        jb1 = hu.rand_jpeg_bytes(item_name=trafo_name, data_type="tegangan-trafo", subtype="HV", photo_source=photo_source)
        jb2 = hu.rand_jpeg_bytes(item_name=trafo_name, data_type="tegangan-trafo", subtype="MV", photo_source=photo_source)
        # Ensure distinct
        import hashlib
        tries = 0
        while hashlib.sha256(jb1).hexdigest() == hashlib.sha256(jb2).hexdigest() and tries < 10:
            jb2 = hu.rand_jpeg_bytes(item_name=trafo_name, data_type="tegangan-trafo", subtype="MV", photo_source=photo_source)
            tries += 1
    else:
        import random
        durasi = round(random.uniform(8.0, 35.0) / 60.0, 8)
        fotoHV = {"date": f"{date_str}T{periode:02d}:10:00.000Z", "address": "Jl Test", "latitude": -6.213, "longitude": 106.846}
        fotoMV = {"date": f"{date_str}T{periode:02d}:10:30.000Z", "address": "Jl Test", "latitude": -6.2131, "longitude": 106.8461}
        jb1 = jb2 = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"

    # Ensure size <70KB each (loop quality already in humanizer, but double-check)
    if len(jb1) > 70000 or len(jb2) > 70000:
        print(f"  ⚠ Foto size terlalu besar HV={len(jb1)} MV={len(jb2)}, akan tetap coba")

    data_dict = {
        "trafoId": trafo_id,
        "timezone": "Asia/Jakarta",
        "periode": periode,
        "tanggal": dt.day,
        "bulan": dt.month - 1,
        "tahun": dt.year,
        "durasi": durasi,
        "mv": mv,
        "hv": hv,
        "fotoHV": fotoHV,
        "fotoMV": fotoMV,
    }

    bd = hu.rand_boundary() if hu else "----FormBoundaryTest123"
    inner = json.dumps(data_dict)
    body_parts = [f'--{bd}\r\nContent-Disposition: form-data; name="data"\r\n\r\n{inner}\r\n'.encode()]
    for jb, fobj, subtype in [(jb1, fotoHV, "HV"), (jb2, fotoMV, "MV")]:
        fname = hu.rand_filename(fobj["date"], idx=0 if subtype == "HV" else 1, data_type="tegangan-trafo", subtype=subtype) if hu else f"foto{subtype}_{date_str}.jpg"
        body_parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="files"; filename="{fname}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
        body_parts.append(jb)
        body_parts.append(b'\r\n')
    body_parts.append(f'--{bd}--\r\n'.encode())
    body = b"".join(body_parts)

    req = urllib.request.Request(
        f"{API_BASE}/gama/opgi-20kv/operator-gi/tegangan-trafo/input",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={bd}",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": hu.rand_user_agent() if hu else "okhttp/4.12.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            status = resp.status
    except urllib.error.HTTPError as e:
        try:
            result = json.loads(e.read())
            status = e.code
        except:
            result = {"message": str(e)}
            status = e.code

    if not result.get("success"):
        return False, None, False, result.get("message", "unknown")

    rec_id = result.get("data", {}).get("id")
    # Verify uri
    listed = api_get(token, "/gama/opgi-20kv/operator-gi/tegangan-trafo", {"garduIndukId": "222", "date": date_str})
    found = None
    for item in listed.get("data", {}).get("items", []):
        for teg in item.get("tegangan", []):
            if teg.get("id") == rec_id:
                found = teg
                break
    if not found:
        return False, rec_id, False, "record tidak ditemukan setelah upload"

    hv_uri = (found.get("fotoHV") or {}).get("uri")
    mv_uri = (found.get("fotoMV") or {}).get("uri")
    has_uri = bool(hv_uri and mv_uri)
    return True, rec_id, has_uri, {"hv_uri": hv_uri, "mv_uri": mv_uri}


def main():
    parser = argparse.ArgumentParser(description="Fix Tegangan Trafo Jam 3 (P3) - foto missing")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD, default today")
    parser.add_argument("--periode", type=int, default=3, help="Periode jam, default 3 (jam 3)")
    parser.add_argument("--dry-run", action="store_true", help="Preview saja, tidak upload/delete")
    parser.add_argument("--trafo", default=None, help="Filter nama trafo, mis TRAFO_1")
    parser.add_argument("--gi", default="222", help="GI ID")
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    cfg = load_config()
    print("=" * 70)
    print("FIX TEGANGAN TRAFO JAM 3 - FOTO TIDAK TERSIMPAN")
    print("=" * 70)
    print(f"Tanggal : {date_str}")
    print(f"Periode : {args.periode} (jam {args.periode:02d}:00)")
    print(f"GI ID   : {args.gi}")
    print(f"Dry-run : {args.dry_run}")
    print("=" * 70)

    try:
        token, user = login(cfg["nip"], cfg["password"])
        print(f"✓ Login OK: {user.get('namaLengkap')} ({cfg['nip']})")
    except Exception as e:
        print(f"✗ Login gagal: {e}")
        return

    # 1. Cek beban penyulang P3 (harus OK, jangan dihapus)
    print(f"\n[1] CEK BEBAN PENYULANG P{args.periode:02d} (harusnya OK, JANGAN dihapus)")
    try:
        data_penyulang = api_get(token, "/gama/opgi-20kv/operator-gi/beban-penyulang", {"garduIndukId": args.gi, "date": date_str})
        items = data_penyulang.get("data", {}).get("items", [])
        ok_count = 0
        miss_count = 0
        for it in items:
            for b in it.get("beban", []):
                if b.get("periode") == args.periode:
                    uri = b.get("foto", {}).get("uri")
                    if uri:
                        ok_count += 1
                    else:
                        miss_count += 1
        print(f"  → Beban penyulang P{args.periode:02d}: {ok_count} OK, {miss_count} MISSING (dari {len(items)} penyulang)")
        if ok_count > 0:
            print(f"  ✓ Beban penyulang foto tersimpan - BEDA dengan tegangan yang gagal")
    except Exception as e:
        print(f"  ✗ Gagal cek beban penyulang: {e}")

    # 2. Cek beban trafo P3 (harusnya OK, jangan dihapus)
    print(f"\n[2] CEK BEBAN TRAFO P{args.periode:02d} (harusnya OK, JANGAN dihapus)")
    try:
        data_trafo = api_get(token, "/gama/opgi-20kv/operator-gi/beban-trafo", {"garduIndukId": args.gi, "date": date_str})
        items = data_trafo.get("data", {}).get("items", [])
        ok_count = 0
        miss_count = 0
        for it in items:
            for b in it.get("beban", []):
                if b.get("periode") == args.periode:
                    uri = b.get("foto", {}).get("uri")
                    if uri:
                        ok_count += 1
                    else:
                        miss_count += 1
        print(f"  → Beban trafo P{args.periode:02d}: {ok_count} OK, {miss_count} MISSING (dari {len(items)} trafo)")
        if ok_count > 0:
            print(f"  ✓ Beban trafo foto tersimpan - BEDA dengan tegangan yang gagal")
    except Exception as e:
        print(f"  ✗ Gagal cek beban trafo: {e}")

    # 3. Cek tegangan trafo P3 (yang bermasalah)
    print(f"\n[3] CEK TEGANGAN TRAFO P{args.periode:02d} (yang foto tidak tersimpan)")
    try:
        data_teg = api_get(token, "/gama/opgi-20kv/operator-gi/tegangan-trafo", {"garduIndukId": args.gi, "date": date_str})
        items = data_teg.get("data", {}).get("items", [])
        to_fix = []
        ok_list = []
        for it in items:
            if args.trafo and args.trafo.upper() not in it.get("nama", "").upper():
                continue
            for teg in it.get("tegangan", []):
                if teg.get("periode") == args.periode:
                    hv_uri = (teg.get("fotoHV") or {}).get("uri")
                    mv_uri = (teg.get("fotoMV") or {}).get("uri")
                    if not hv_uri or not mv_uri:
                        to_fix.append({"item": it, "teg": teg})
                        print(f"  ✗ {it['nama']} P{args.periode:02d} ID {teg['id']} MISSING uri HV={bool(hv_uri)} MV={bool(mv_uri)} MV={teg.get('mv')} HV={teg.get('hv')}")
                    else:
                        ok_list.append({"item": it, "teg": teg})
                        print(f"  ✓ {it['nama']} P{args.periode:02d} ID {teg['id']} OK uri HV+MV ada")

        print(f"\n  Ringkasan P{args.periode:02d}: {len(ok_list)} OK, {len(to_fix)} MISSING perlu fix")

        if args.dry_run:
            print("\n  [DRY-RUN] Tidak melakukan delete/upload, hanya cek")
            return

        # 4. Fix yang missing
        if not to_fix:
            print("\n  ✓ Semua tegangan P3 sudah OK, tidak perlu fix")
            return

        print(f"\n[4] FIX {len(to_fix)} record MISSING uri untuk P{args.periode:02d}")
        success = 0
        fail = 0
        for entry in to_fix:
            item = entry["item"]
            teg = entry["teg"]
            trafo_id = item["id"]
            trafo_name = item["nama"]
            mv = teg.get("mv")
            hv = teg.get("hv")
            rec_id = teg.get("id")

            print(f"\n  → Fix {trafo_name} P{args.periode:02d} ID {rec_id} MV={mv} HV={hv}")

            # Delete existing missing record
            try:
                api_delete(token, f"/gama/opgi-20kv/operator-gi/tegangan-trafo/{rec_id}")
                print(f"    ✓ Deleted old record {rec_id} (foto missing)")
            except Exception as e:
                print(f"    ✗ Gagal delete {rec_id}: {e}")
                fail += 1
                continue

            # Try upload up to 3 times
            for attempt in range(1, 4):
                print(f"    Attempt {attempt}/3 upload...", end=" ")
                ok, new_id, has_uri, info = upload_tegangan(token, trafo_id, trafo_name, args.periode, date_str, mv, hv, photo_source=cfg.get("photo_source", "manual"))
                if ok and has_uri:
                    print(f"✓ OK ID {new_id} uri HV+MV ada")
                    success += 1
                    break
                elif ok and not has_uri:
                    print(f"✗ Foto masih MISSING ID {new_id} -> hapus & retry")
                    try:
                        api_delete(token, f"/gama/opgi-20kv/operator-gi/tegangan-trafo/{new_id}")
                    except:
                        pass
                    # Tunggu sebentar
                    import time
                    time.sleep(1.5)
                else:
                    print(f"✗ Gagal upload: {info}")
                    # retry
                    import time
                    time.sleep(1.5)
            else:
                print(f"    ✗ Gagal fix {trafo_name} P{args.periode:02d} setelah 3 attempt")
                fail += 1

        print("\n" + "=" * 70)
        print(f"HASIL FIX JAM {args.periode}: {success} berhasil, {fail} gagal")
        print("=" * 70)

        if fail > 0:
            print("\n  ⚠ Beberapa masih gagal - kemungkinan server storage penuh untuk tegangan")
            print("  Coba lagi nanti, atau hubungi admin server untuk cek folder media/images/tegangan-trafo/")
            print("  Beban penyulang & trafo tetap OK (tidak dihapus) sesuai permintaan")

    except Exception as e:
        print(f"  ✗ Gagal cek tegangan: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
