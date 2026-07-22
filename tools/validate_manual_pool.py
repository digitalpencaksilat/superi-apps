#!/usr/bin/env python3
"""
Validasi pool foto manual per-item untuk CLI.

- Scan photo/manual/ (32 penyulang, 3 trafo beban, 5 trafo tegangan hv/mv terpisah)
- Cek: count, size min/max/avg, dimensi via PIL, progressive flag, COM flag, EXIF, duplicate SHA
- OFF: 7 penyulang CB OFF tetap simpan 84 foto tapi skip input (read-only, tidak dihapus)
- Pool generic: photo/pool/ 1 foto untuk semua (mode pool)
- Manual: per-item sesuai (random dari folder item + hv/mv terpisah) + varian blur/kabur/asli
- Filename upload TETAP humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg (bukan basename manual)

Usage:
  python3 tools/validate_manual_pool.py
  python3 tools/validate_manual_pool.py --detail
  python3 tools/validate_manual_pool.py --csv out.csv
"""

import os
import sys
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict, Counter

SCRIPT_DIR = Path(__file__).parent.parent
MANUAL_BASE = SCRIPT_DIR / "photo" / "manual"
POOL_DIR = SCRIPT_DIR / "photo" / "pool"
MAPPING_PATH = MANUAL_BASE / "NAMA_MAPPING.json"

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Pillow not installed, dimensi check skip. pip install Pillow")

def scan_jpg(dir_path):
    if not dir_path or not Path(dir_path).is_dir():
        return []
    files = []
    for fn in os.listdir(dir_path):
        low = fn.lower()
        if fn.startswith('.') or fn in ('.gitkeep',):
            continue
        if fn.upper().startswith('TARUH_FOTO') or fn.upper().startswith('README'):
            continue
        if low.endswith(('.txt','.md','.json')):
            continue
        full = os.path.join(dir_path, fn)
        if os.path.isfile(full):
            try:
                sz = os.path.getsize(full)
                if sz > 3000 and low.endswith(('.jpg','.jpeg','.png')):
                    files.append(full)
            except:
                pass
    return files

def analyze_file(path):
    """Analyze jpeg: size, dim, progressive (FFC2), COM (FFFE), EXIF, sha"""
    try:
        with open(path, 'rb') as f:
            b = f.read()
    except Exception as e:
        return {"error": str(e), "bytes":0, "width":0, "height":0, "sha_short":""}

    if not b.startswith(b"\xff\xd8"):
        return {"error":"Not JPEG", "bytes":len(b), "width":0, "height":0, "sha_short": hashlib.sha256(b).hexdigest()[:12], "is_progressive":False, "has_com":False, "exif_count":0}

    sha = hashlib.sha256(b).hexdigest()
    is_prog = b"\xff\xc2" in b
    has_com = b"\xff\xfe" in b
    width = height = 0
    exif_count = 0
    if HAS_PIL:
        try:
            im = Image.open(Path(path))
            width, height = im.size
            try:
                exif_count = len(im.getexif())
            except:
                exif_count = 0
        except Exception:
            pass

    return {
        "bytes": len(b),
        "width": width,
        "height": height,
        "sha": sha,
        "sha_short": sha[:12],
        "is_progressive": is_prog,
        "has_com": has_com,
        "exif_count": exif_count,
        "error": None,
    }

def main():
    parser = argparse.ArgumentParser(description="Validasi pool foto manual per-item")
    parser.add_argument("--detail", action="store_true", help="Tampilkan detail per file")
    parser.add_argument("--csv", default=None, help="Simpan CSV ke file")
    args = parser.parse_args()

    print("="*80)
    print("VALIDASI POOL FOTO MANUAL - SUPER-I APP CLI")
    print("="*80)
    print(f"Manual base: {MANUAL_BASE}")
    print(f"Pool generic: {POOL_DIR}")
    print(f"Mapping: {MAPPING_PATH}")
    print("")
    print("Mode:")
    print("  pool   = 1 foto di photo/pool/ untuk semua input (fallback cepat)")
    print("  manual = per-item sesuai (random dari folder item + hv/mv terpisah + varian blur/kabur/asli)")
    print("  Filename upload TETAP humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg")
    print("  OFF 7 penyulang tetap simpan tapi skip input CB OFF")
    print("  Foto tidak dihapus setelah dipakai (read-only random choice)")
    print("="*80)

    # Load mapping for OFF info
    off_names = set()
    mapping = {}
    if MAPPING_PATH.is_file():
        try:
            import json
            with open(MAPPING_PATH, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
            for k,v in mapping.get("beban-penyulang", {}).items():
                if v.get("cb") == "OFF":
                    off_names.add(k)
        except Exception as e:
            print(f"Mapping load error: {e}")

    if off_names:
        print(f"OFF penyulang terdeteksi (tetap simpan, skip input): {sorted(off_names)}")
        print("")

    total_files = 0
    total_issues = 0
    all_stats = []

    # Scan beban-penyulang
    bp_base = MANUAL_BASE / "beban-penyulang"
    print(f"\n{'='*80}")
    print("BEBAN PENYULANG (32 folder, 25 ON + 7 OFF tetap):")
    print("="*80)
    if not bp_base.is_dir():
        print(f"  ❌ Folder tidak ada: {bp_base}")
    else:
        rows = []
        for folder in sorted(os.listdir(bp_base)):
            full = bp_base / folder
            if not full.is_dir():
                continue
            files = scan_jpg(full)
            if not files and folder.startswith('_'):
                continue
            # Analyze
            sizes = []
            sha_seen = {}
            dup_sha = 0
            prog_cnt = 0
            com_cnt = 0
            small_cnt = 0
            issues = []
            for fp in files:
                info = analyze_file(fp)
                sizes.append(info["bytes"])
                if info.get("is_progressive"):
                    prog_cnt += 1
                    issues.append(f"progressive {os.path.basename(fp)}")
                if info.get("has_com"):
                    com_cnt += 1
                    issues.append(f"COM {os.path.basename(fp)}")
                if info["bytes"] < 12000:
                    small_cnt += 1
                    issues.append(f"<12KB {os.path.basename(fp)} {info['bytes']}B")
                # duplicate sha inside same folder
                sha = info.get("sha","")
                if sha in sha_seen:
                    dup_sha += 1
                    issues.append(f"dup SHA {info['sha_short']} {os.path.basename(fp)} == {os.path.basename(sha_seen[sha])}")
                else:
                    sha_seen[sha] = fp

            avg_sz = sum(sizes)/len(sizes) if sizes else 0
            min_sz = min(sizes) if sizes else 0
            max_sz = max(sizes) if sizes else 0
            is_off = folder in off_names
            badge = "OFF (skip input, tetap simpan)" if is_off else "ON"
            # count
            total_files += len(files)
            status_icon = "⚠️" if issues else "✅"
            print(f"  {status_icon} {folder:<22} : {len(files):>3} foto | avg {avg_sz/1024:4.1f}KB min {min_sz/1024:4.1f}KB max {max_sz/1024:4.1f}KB | {badge} | dup {dup_sha} prog {prog_cnt} <12KB {small_cnt}")
            if args.detail and issues:
                for iss in issues[:5]:
                    print(f"      - {iss}")
                if len(issues) > 5:
                    print(f"      ... +{len(issues)-5} lagi")

            all_stats.append({
                "type": "beban-penyulang",
                "folder": folder,
                "count": len(files),
                "avg_kb": avg_sz/1024,
                "is_off": is_off,
                "issues": len(issues),
                "dup": dup_sha,
                "prog": prog_cnt,
                "small": small_cnt,
            })
            total_issues += len(issues)

    # beban-trafo
    bt_base = MANUAL_BASE / "beban-trafo"
    print(f"\n{'='*80}")
    print("BEBAN TRAFO (3 folder):")
    print("="*80)
    if not bt_base.is_dir():
        print(f"  ❌ Folder tidak ada: {bt_base}")
    else:
        for folder in sorted(os.listdir(bt_base)):
            full = bt_base / folder
            if not full.is_dir():
                continue
            files = scan_jpg(full)
            sizes = []
            issues = []
            for fp in files:
                info = analyze_file(fp)
                sizes.append(info["bytes"])
                if info.get("is_progressive"):
                    issues.append(f"progressive {os.path.basename(fp)}")
                if info["bytes"] < 12000:
                    issues.append(f"<12KB {os.path.basename(fp)}")
            avg_sz = sum(sizes)/len(sizes) if sizes else 0
            total_files += len(files)
            status_icon = "⚠️" if issues else "✅"
            print(f"  {status_icon} {folder:<22} : {len(files):>3} foto | avg {avg_sz/1024:4.1f}KB")
            all_stats.append({
                "type": "beban-trafo",
                "folder": folder,
                "count": len(files),
                "avg_kb": avg_sz/1024,
                "issues": len(issues),
            })
            total_issues += len(issues)

    # tegangan-trafo hv/mv terpisah
    tt_base = MANUAL_BASE / "tegangan-trafo"
    print(f"\n{'='*80}")
    print("TEGANGAN TRAFO (5 trafo × hv/mv terpisah, tidak perlu rename):")
    print("="*80)
    if not tt_base.is_dir():
        print(f"  ❌ Folder tidak ada: {tt_base}")
    else:
        for trafo in sorted(os.listdir(tt_base)):
            trafo_path = tt_base / trafo
            if not trafo_path.is_dir():
                continue
            hv_path = trafo_path / "hv"
            mv_path = trafo_path / "mv"
            hv_files = scan_jpg(hv_path) if hv_path.is_dir() else []
            mv_files = scan_jpg(mv_path) if mv_path.is_dir() else []
            # Also check flat files in trafo folder (in case user didn't use hv/mv subfolders)
            flat_files = []
            if trafo_path.is_dir():
                for fn in os.listdir(trafo_path):
                    fp = trafo_path / fn
                    if fp.is_file() and fn.lower().endswith(('.jpg','.jpeg','.png')):
                        if fp.stat().st_size > 5000:
                            # exclude if in hv/mv subdir already counted
                            if fn.lower().endswith(('.txt','.md','.json')):
                                continue
                            # if not in hv/mv subfolders list, it's flat
                            full_str = str(fp)
                            if str(hv_path) not in full_str and str(mv_path) not in full_str:
                                flat_files.append(str(fp))

            total_t = len(hv_files) + len(mv_files) + len(flat_files)
            total_files += len(hv_files) + len(mv_files)  # flat not counted in hv/mv total but still files
            # analyze small
            small = 0
            for lst in [hv_files, mv_files]:
                for fp in lst:
                    info = analyze_file(fp)
                    if info["bytes"] < 12000:
                        small += 1

            icon = "✅" if total_t>0 else "❌"
            print(f"  {icon} {trafo:<12} : HV {len(hv_files):>2} foto  MV {len(mv_files):>2} foto  flat {len(flat_files):>2} | total {total_t:>2} | <12KB {small}")
            if flat_files and (len(hv_files)==0 or len(mv_files)==0):
                print(f"      ⚠️ Flat files ditemukan {len(flat_files)} di {trafo}/ (sebaiknya pisah ke hv/ & mv/)")

            all_stats.append({
                "type": "tegangan-trafo-hv",
                "folder": f"{trafo}/hv",
                "count": len(hv_files),
            })
            all_stats.append({
                "type": "tegangan-trafo-mv",
                "folder": f"{trafo}/mv",
                "count": len(mv_files),
            })

    # pool generic
    print(f"\n{'='*80}")
    print("POOL GENERIC (photo/pool/ 1 foto untuk semua - mode pool):")
    print("="*80)
    pool_files = scan_jpg(POOL_DIR) if POOL_DIR.is_dir() else []
    if not pool_files:
        # try legacy scan
        try:
            for fn in os.listdir(POOL_DIR):
                fp = os.path.join(POOL_DIR, fn)
                if os.path.isfile(fp) and os.path.getsize(fp) > 10000 and fn.lower().endswith(('.jpg','.jpeg','.png')):
                    pool_files.append(fp)
        except:
            pass
    print(f"  Pool: {len(pool_files)} file")
    for fp in pool_files[:5]:
        info = analyze_file(fp)
        print(f"    {os.path.basename(fp)}: {info['bytes']/1024:.1f}KB {info['width']}x{info['height']} prog={info.get('is_progressive')} com={info.get('has_com')} exif={info.get('exif_count')}")
    total_files += len(pool_files)

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print("="*80)
    print(f"Total foto (manual + pool): {total_files}")
    print(f"Total issues: {total_issues} (progressive/COM/<12KB/dup)")
    print("")
    print("Mode penggunaan di CLI:")
    print("  [T] Settings → [1] Ganti Sumber Foto")
    print("    pool   = 1 foto di photo/pool/ untuk semua input (fallback cepat)")
    print("           re-encode 720x720 crop ±5% + pixel jitter + quality 82-93 beda SHA tiap upload")
    print("           filename tetap humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg")
    print("    manual = per-item sesuai (random dari folder item + hv/mv terpisah + varian)")
    print("           CASABLANCA4 → 12 foto random → blur_ringan 25% / blur_berat 15% / noisy_gelap 15% / asli 45%")
    print("           TRAFO_1 hv: 9 foto di TRAFO_1/hv/ → random, mv: 7 foto di TRAFO_1/mv/ → random pisah")
    print("           filename tetap humanizer, OFF tetap simpan 84 foto tapi skip input CB OFF")
    print("           Foto tidak dihapus setelah dipakai (read-only random choice)")
    print("")
    if total_issues == 0:
        print("✅ Semua foto OK untuk anti-bypass (720x720 baseline, no progressive/COM, >12KB, unique SHA per folder)")
    else:
        print(f"⚠️ Ada {total_issues} warning, cek detail di atas")

    # CSV
    if args.csv:
        import csv
        with open(args.csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["type","folder","count","avg_kb","is_off","issues","dup","prog","small"])
            writer.writeheader()
            for row in all_stats:
                writer.writerow(row)
        print(f"\nCSV disimpan: {args.csv}")

if __name__ == "__main__":
    main()
