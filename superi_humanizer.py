#!/usr/bin/env python3
"""
SUPER-I Humanizer — anti-robot behaviour layer (stdlib only).

Menyamarkan perilaku input agar mirip aplikasi mobile asli:
- durasi random dalam MENIT (unit server), mewakili 2-7 detik untuk beban, 8-40 detik untuk tegangan
  (manual avg: beban 0.105 menit=6.35s, tegangan 0.305 menit=18.3s)
- foto.datetime random menit/detik/ms dalam jam periode (bukan 00:00.000Z), korelasi dengan durasi
- filename mirip app asli: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg, fotoBebanTrafo_, fotoHV_, fotoMV_
- foto.address + lat/lon realistis (13 alamat GI MANGGARAI area + jitter 5-15m), bukan "GI MANGGARAI" statis
- boundary multipart random
- sleep seperti manusia + shuffle urutan

Tidak mengubah nilai beban/tegangan (hanya metadata & timing).
"""

import io
import os
import random
import string
import time
import uuid
import hashlib
from datetime import datetime, timedelta, timezone

_BASE_BOUNDARY_PREFIX = "----FormBoundary"
_OKHTTP_UA = "okhttp/4.12.0"
_DALVIK_UA = "Dalvik/2.1.0 (Linux; U; Android 13; SM-A546B Build/TP1A.220624.014)"
_USER_AGENTS = [
    _OKHTTP_UA,
    "okhttp/4.11.0",
    "okhttp/4.10.0",
    _DALVIK_UA,
]

# Durasi server disimpan dalam MENIT (bukan detik).
# Manual: beban 0.057-2.1 menit, avg 0.105 menit = 6.35 detik.
#         tegangan 0.14-1.02 menit, avg 0.305 menit = 18.3 detik.
# Forbidden kalau 0.0 (jangan pernah kirim nol)
_FORBIDDEN_DURASI = {0.0}

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PHOTO_POOL_DIR = os.path.join(_SCRIPT_DIR, "photo", "pool")
_MANUAL_POOL_BASE = os.path.join(_SCRIPT_DIR, "photo", "manual")
_NAMA_MAPPING_PATH = os.path.join(_MANUAL_POOL_BASE, "NAMA_MAPPING.json")

_JPEG_CACHE = {}
_MANUAL_CACHE = {}  # path -> (mtime, file_list)
_MAPPING_CACHE = None
_MAPPING_MTIME = 0
_LAST_META = {}  # last used: src_path, variant, bytes, source_mode, folder

_WIB = timezone(timedelta(hours=7))
_UTC = timezone.utc

# === VALIDASI & CONFIG ===
_VALID_PHOTO_SOURCES = {"pool", "manual"}
_DEFAULT_PHOTO_SOURCE = "pool"

# Variant weights: asli 40%, blur ringan 20%, blur berat 10%, kabur glare 15%, noisy gelap 15%
_VARIANT_CHOICES = ["asli", "blur_ringan", "blur_berat", "kabur_glare", "noisy_gelap"]
_VARIANT_WEIGHTS = [40, 20, 10, 15, 15]

# ============================================================
# REAL LOCATIONS - dari API manual (13 alamat unik di sekitar GI MANGGARAI)
# Lat/Lon jitter akan ditambahkan ±5-15m agar tidak statis
# ============================================================
_REAL_LOCATIONS = [
    # alamat lengkap, lat, lon
    ("Jl. Swadaya 1 No.36, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213095, 106.846073),
    ("Gis 150 Kv Manggarai, Jl. Swadaya 1 No.21, RT.12/RW.10, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213208, 106.845899),
    ("Jl. Swadaya 1 No.38, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213110, 106.846055),
    ("Jl. Swadaya 1 No.6A, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213235, 106.845678),
    ("Jl. Swadaya IV No.20, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213078, 106.845978),
    ("Jln. Poltangan raya Jl. Swadaya 1 No.36, RT.7/RW.10, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213090, 106.845980),
    ("Jl. Dr. Saharjo No.57, RT.16/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12860, Indonesia", -6.213200, 106.846000),
    ("Jl. Dr. Saharjo No.69 3, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213150, 106.846020),
    ("QRPW+V8P, Jl. Swadaya 1, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213120, 106.846010),
    ("Jl. Swadaya 1 No.69, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213140, 106.845950),
    ("Jl. Swadaya 1 No.36, RT.3/RW.8, Manggarai, Kec. Tebet, Kota Jakarta Selatan, Daerah Khusus Ibukota Jakarta 12850, Indonesia", -6.213098, 106.846077),  # duplicate sengaja untuk weight
    # Variasi koordinat "Lat=-6.213..., Long=..." kadang muncul di manual (tanpa alamat jalan)
    # Representasikan sebagai alamat jalan terdekat dengan koordinat tersebut
]

# Alamat fallback "Lat=..., Long=..." style (5% chance) - beberapa entry manual pakai format ini
_LAT_LONG_ADDRESSES = [
    "Lat=-6.2130958, Long=106.8460737",
    "Lat=-6.2130893, Long=106.8460603",
    "Lat=-6.2130784, Long=106.8459783",
    "Lat=-6.2130717, Long=106.8459829",
    "Lat=-6.2135789, Long=106.8449406",
]

# ============================================================
# JPEG HANDLING - STRICT 720x720 SQUARE UNTUK SEMUA TIPE (ANTI BYPASS)
# Audit server: stored 720x720 (95%) / 720x960 (5%), baseline JPEG,
# no progressive, no COM, no EXIF, 14-51KB avg 27KB.
# Requirement: SEMUA tipe (beban-penyulang, beban-trafo, tegangan-trafo) wajib 720x720.
# Pool: ambil dari photo/pool/ -> crop center square 720x720
# ============================================================

# Target dimensi final — STRICT 720x720 untuk semua tipe
# Sebelumnya weighted 85% 720x720 + 15% outlier (720x960/1080x1080) untuk meniru real app.
# Sekarang strict 720x720 100% sesuai requirement user (semua tipe).
_TARGET_DIMS = [
    # (W, H, weight) — strict 720x720 100%
    (720, 720, 100),  # strict, match server stored 95%
]


def _pick_target_dim():
    """Pick (W,H) — strict 720x720 untuk semua tipe."""
    # Deprecated weighted pick, sekarang strict 720x720
    return (720, 720)


def _get_target_dim_720():
    """Default return 720x720 — strict untuk semua tipe (beban penyulang, trafo, tegangan)."""
    # STRICT 720x720 100% — tidak ada lagi outlier 720x960/1080x1080
    return (720, 720)
def sanitize_folder_name(name: str) -> str:
    """Samakan dengan fetch_foto_server.py: uppercase alnum -> _, max 40."""
    import re
    if not name:
        return "UNKNOWN"
    s = re.sub(r'[^A-Za-z0-9]+', '_', name.strip()).upper()
    s = s.strip('_')
    return s[:40] or "UNKNOWN"


def _scan_jpg(dir_path: str):
    """Scan jpg/jpeg/png di folder, skip .gitkeep, instruction txt, handle spasi WhatsApp name."""
    if not dir_path or not os.path.isdir(dir_path):
        return []
    # cache check by mtime
    try:
        mtime = os.path.getmtime(dir_path)
    except:
        mtime = 0
    cache_key = dir_path
    if cache_key in _MANUAL_CACHE:
        cached_mtime, cached_list = _MANUAL_CACHE[cache_key]
        if cached_mtime == mtime:
            return cached_list

    files = []
    try:
        for fn in os.listdir(dir_path):
            low = fn.lower()
            if fn.startswith('.'):
                continue
            if fn in ('.gitkeep',):
                continue
            if fn.upper().startswith('TARUH_FOTO') or fn.upper().startswith('README'):
                continue
            if fn.lower().endswith(('.txt', '.md', '.json')):
                continue
            if low.endswith(('.jpg', '.jpeg', '.png', '.png.png', '.jpg.jpg')) or ('.' not in fn):
                full = os.path.join(dir_path, fn)
                if os.path.isfile(full):
                    try:
                        sz = os.path.getsize(full)
                        if sz > 5000:
                            # check extension after all
                            if low.endswith(('.jpg', '.jpeg', '.png')) or '.' not in fn:
                                files.append(full)
                    except:
                        pass
    except:
        pass

    # Dedup
    files = list(dict.fromkeys(files))
    _MANUAL_CACHE[cache_key] = (mtime, files)
    return files


def _load_mapping():
    """Load NAMA_MAPPING.json cache."""
    global _MAPPING_CACHE, _MAPPING_MTIME
    if not os.path.isfile(_NAMA_MAPPING_PATH):
        return {}
    try:
        mtime = os.path.getmtime(_NAMA_MAPPING_PATH)
        if _MAPPING_CACHE is not None and _MAPPING_MTIME == mtime:
            return _MAPPING_CACHE
        import json
        with open(_NAMA_MAPPING_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _MAPPING_CACHE = data
        _MAPPING_MTIME = mtime
        return data
    except Exception:
        return _MAPPING_CACHE if _MAPPING_CACHE is not None else {}


def _load_photo_source_from_config():
    """Baca photo_source dari .superi_config.json tanpa import circular."""
    # Env override
    env_val = os.environ.get("SUPERI_PHOTO_SOURCE", "").strip().lower()
    if env_val in _VALID_PHOTO_SOURCES:
        return env_val
    # Try project config
    cfg_paths = [
        os.path.join(_SCRIPT_DIR, ".superi_config.json"),
        os.path.join(_SCRIPT_DIR, ".superi_config.json.bak"),
        os.path.expanduser("~/.superi_config.json"),
    ]
    for cp in cfg_paths:
        if os.path.isfile(cp):
            try:
                import json
                with open(cp, 'r') as f:
                    cfg = json.load(f)
                v = str(cfg.get("photo_source", "")).lower().strip()
                if v in _VALID_PHOTO_SOURCES:
                    return v
            except:
                continue
    return _DEFAULT_PHOTO_SOURCE


def _get_photo_pool_per_item(item_name=None, data_type=None, subtype=None, photo_source=None):
    """
    Resolver per-item untuk manual vs pool.

    Priority:
      Layer1: photo/manual/{data_type}/{SANITIZED}/ atau {data_type}/{SANITIZED}/{hv|mv}/ untuk tegangan
      Layer2: photo/manual/{data_type}/_generic/ (optional)
      Layer3: photo/pool/ (generic)
      Layer4: [] -> synthetic fallback

    Returns: (file_list, source_mode, folder_label, full_dir_path)
    """
    src = (photo_source or _load_photo_source_from_config() or _DEFAULT_PHOTO_SOURCE).lower().strip()
    if src not in _VALID_PHOTO_SOURCES:
        src = _DEFAULT_PHOTO_SOURCE

    if src == "manual" and item_name and data_type:
        sanitized = sanitize_folder_name(item_name)

        # Tegangan: hv/mv terpisah per trafo
        if data_type == "tegangan-trafo" and subtype:
            sub = subtype.lower()  # hv or mv
            # photo/manual/tegangan-trafo/TRAFO_1/hv/
            target = os.path.join(_MANUAL_POOL_BASE, data_type, sanitized, sub)
            files = _scan_jpg(target)
            if files:
                return files, "manual", f"{sanitized}/{sub}", target
            # Fallback: jika hv/mv folder kosong tapi ada foto di folder trafo langsung (tanpa sub)
            target_parent = os.path.join(_MANUAL_POOL_BASE, data_type, sanitized)
            files_parent = _scan_jpg(target_parent)
            if files_parent:
                # Filter by filename contains hv/mv if available
                filtered = [f for f in files_parent if sub in os.path.basename(f).lower()]
                if filtered:
                    return filtered, "manual", f"{sanitized}/(filtered {sub})", target_parent
                # If no filtered, use all parent files for both hv/mv (still per-item)
                return files_parent, "manual", f"{sanitized}/(shared)", target_parent
        else:
            # beban-penyulang / beban-trafo per-item folder
            target = os.path.join(_MANUAL_POOL_BASE, data_type, sanitized)
            files = _scan_jpg(target)
            if files:
                return files, "manual", sanitized, target

        # Fallback generic manual per tipe: photo/manual/{type}/_generic/ or flat files in type
        generic_dir = os.path.join(_MANUAL_POOL_BASE, data_type, "_generic")
        files_generic = _scan_jpg(generic_dir)
        if files_generic:
            return files_generic, "manual-generic", f"{data_type}/_generic", generic_dir

        # Also check flat files directly in data_type folder (without subfolder)
        type_dir = os.path.join(_MANUAL_POOL_BASE, data_type)
        if os.path.isdir(type_dir):
            # Only flat files, not subdirs
            flat_files = []
            try:
                for fn in os.listdir(type_dir):
                    full = os.path.join(type_dir, fn)
                    if os.path.isfile(full) and fn.lower().endswith(('.jpg', '.jpeg', '.png')):
                        if os.path.getsize(full) > 5000:
                            flat_files.append(full)
            except:
                pass
            if flat_files:
                return flat_files, "manual-generic", f"{data_type}/(flat)", type_dir

    # Layer3: pool generic (used for both pool mode and manual fallback)
    pool_files = _scan_jpg(_PHOTO_POOL_DIR)
    # Also try flat _get_photo_pool legacy fallback if scan empty
    if not pool_files:
        # legacy method: scan pool dir again with looser filter
        try:
            for fn in os.listdir(_PHOTO_POOL_DIR):
                full = os.path.join(_PHOTO_POOL_DIR, fn)
                if os.path.isfile(full) and os.path.getsize(full) > 10000:
                    if fn.lower().endswith(('.jpg', '.jpeg', '.png')):
                        pool_files.append(full)
        except:
            pass

    if pool_files:
        return pool_files, "pool", "_pool", _PHOTO_POOL_DIR

    return [], "synthetic", "none", None


def _apply_variant_transform(img, mode="auto"):
    """
    Varian blur/kabur/asli + noisy gelap (untuk jam 00-06).
    Returns (img, variant_name)
    """
    try:
        from PIL import ImageDraw, ImageEnhance, ImageFilter
    except ImportError:
        return img, "asli"

    if mode == "auto" or mode is None:
        mode = random.choices(_VARIANT_CHOICES, weights=_VARIANT_WEIGHTS)[0]

    if mode == "asli":
        return img, "asli"
    elif mode == "blur_ringan":
        try:
            r = random.uniform(0.4, 0.9)
            img = img.filter(ImageFilter.GaussianBlur(radius=r))
            img = ImageEnhance.Brightness(img).enhance(random.uniform(0.92, 1.06))
            img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.05))
        except Exception:
            pass
        return img, "blur_ringan"
    elif mode == "blur_berat":
        try:
            r = random.uniform(1.0, 2.2)
            img = img.filter(ImageFilter.GaussianBlur(radius=r))
            img = ImageEnhance.Brightness(img).enhance(random.uniform(0.85, 0.95))
            img = ImageEnhance.Contrast(img).enhance(random.uniform(0.90, 1.00))
        except Exception:
            pass
        return img, "blur_berat"
    elif mode == "kabur_glare":
        try:
            w, h = img.size
            draw = ImageDraw.Draw(img)
            gx = random.randint(0, max(0, w // 3))
            gy = random.randint(0, max(0, h // 3))
            gw = random.randint(80, 240)
            gh = random.randint(30, 110)
            # glare ellipse putih kekuningan
            draw.ellipse([gx, gy, gx+gw, gy+gh], fill=(255, 255, 240))
            img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
            img = ImageEnhance.Brightness(img).enhance(random.uniform(0.95, 1.08))
        except Exception:
            pass
        return img, "kabur_glare"
    elif mode == "noisy_gelap":
        try:
            w, h = img.size
            draw = ImageDraw.Draw(img)
            # grain 8k-12k (reduce from 15k-20k to keep size 20-80KB)
            for _ in range(random.randint(8000, 12000)):
                x = random.randint(0, w-1)
                y = random.randint(0, h-1)
                try:
                    r, g, b = img.getpixel((x, y))
                    nv = random.randint(-25, 30)
                    # dark grain
                    if random.random() < 0.12:
                        nv2 = random.randint(30, 90)
                        draw.point((x, y), fill=(
                            max(0, min(255, r + nv2)),
                            max(0, min(255, g + nv2)),
                            max(0, min(255, b + nv2)),
                        ))
                    else:
                        draw.point((x, y), fill=(
                            max(0, min(255, r + nv)),
                            max(0, min(255, g + nv)),
                            max(0, min(255, b + nv)),
                        ))
                except:
                    pass
            img = ImageEnhance.Brightness(img).enhance(random.uniform(0.70, 0.90))
            img = ImageEnhance.Contrast(img).enhance(random.uniform(0.85, 1.00))
        except Exception:
            pass
        return img, "noisy_gelap"
    else:
        return img, "asli"


def get_last_meta():
    """Return last used meta: src_path, variant, bytes, source_mode, folder"""
    return dict(_LAST_META)


def get_manual_count(item_name, data_type, subtype=None):
    """Count foto per item untuk UI CLI."""
    if not item_name or not data_type:
        return 0
    sanitized = sanitize_folder_name(item_name)
    if data_type == "tegangan-trafo" and subtype:
        target = os.path.join(_MANUAL_POOL_BASE, data_type, sanitized, subtype.lower())
        files = _scan_jpg(target)
        if not files:
            # fallback parent
            parent = os.path.join(_MANUAL_POOL_BASE, data_type, sanitized)
            files = _scan_jpg(parent)
        return len(files)
    else:
        target = os.path.join(_MANUAL_POOL_BASE, data_type, sanitized)
        return len(_scan_jpg(target))


def get_pool_stats():
    """Return stats untuk CLI settings."""
    stats = {
        "pool": len(_scan_jpg(_PHOTO_POOL_DIR)),
        "manual": {
            "beban-penyulang": {"count": 0, "folders": 0, "files": 0},
            "beban-trafo": {"count": 0, "folders": 0, "files": 0},
            "tegangan-trafo": {"count": 0, "folders": 0, "files": 0, "hv": 0, "mv": 0, "total": 0},
        },
        "total_manual": 0,
    }
    # beban-penyulang
    bp_base = os.path.join(_MANUAL_POOL_BASE, "beban-penyulang")
    if os.path.isdir(bp_base):
        for d in os.listdir(bp_base):
            full = os.path.join(bp_base, d)
            if os.path.isdir(full):
                cnt = len(_scan_jpg(full))
                if cnt > 0:
                    stats["manual"]["beban-penyulang"]["folders"] += 1
                    stats["manual"]["beban-penyulang"]["files"] += cnt
        stats["manual"]["beban-penyulang"]["count"] = stats["manual"]["beban-penyulang"]["folders"]

    bt_base = os.path.join(_MANUAL_POOL_BASE, "beban-trafo")
    if os.path.isdir(bt_base):
        for d in os.listdir(bt_base):
            full = os.path.join(bt_base, d)
            if os.path.isdir(full):
                cnt = len(_scan_jpg(full))
                if cnt > 0:
                    stats["manual"]["beban-trafo"]["folders"] += 1
                    stats["manual"]["beban-trafo"]["files"] += cnt
        stats["manual"]["beban-trafo"]["count"] = stats["manual"]["beban-trafo"]["folders"]

    tt_base = os.path.join(_MANUAL_POOL_BASE, "tegangan-trafo")
    if os.path.isdir(tt_base):
        hv_total = 0
        mv_total = 0
        folders = 0
        for trafo in os.listdir(tt_base):
            trafo_path = os.path.join(tt_base, trafo)
            if not os.path.isdir(trafo_path):
                continue
            hv_path = os.path.join(trafo_path, "hv")
            mv_path = os.path.join(trafo_path, "mv")
            cnt_hv = len(_scan_jpg(hv_path)) if os.path.isdir(hv_path) else 0
            cnt_mv = len(_scan_jpg(mv_path)) if os.path.isdir(mv_path) else 0
            if cnt_hv > 0 or cnt_mv > 0:
                folders += 1
            hv_total += cnt_hv
            mv_total += cnt_mv
        stats["manual"]["tegangan-trafo"]["folders"] = folders
        stats["manual"]["tegangan-trafo"]["hv"] = hv_total
        stats["manual"]["tegangan-trafo"]["mv"] = mv_total
        stats["manual"]["tegangan-trafo"]["total"] = hv_total + mv_total

    stats["total_manual"] = (
        stats["manual"]["beban-penyulang"]["files"] +
        stats["manual"]["beban-trafo"]["files"] +
        stats["manual"]["tegangan-trafo"]["total"]
    )
    return stats


def _get_photo_pool():
    """Pool of real operator sample photos in photo/pool/ - supports jpg/jpeg/png.
    Legacy wrapper, now calls _scan_jpg.
    """
    if not os.path.isdir(_PHOTO_POOL_DIR):
        return []
    files = []
    for fn in os.listdir(_PHOTO_POOL_DIR):
        low = fn.lower()
        if low.endswith(('.jpg', '.jpeg', '.png', '.png.png', '.jpg.jpg')) or ('.' not in fn and os.path.isfile(os.path.join(_PHOTO_POOL_DIR, fn))):
            full = os.path.join(_PHOTO_POOL_DIR, fn)
            if os.path.isfile(full) and os.path.getsize(full) > 5000:
                if low.endswith(('.png', '.jpg', '.jpeg')) or not low.endswith('.md'):
                    if not fn.startswith('.') and fn != 'README.md' and fn != '.gitkeep':
                        if os.path.getsize(full) > 10000:
                            files.append(full)
    cleaned = []
    for f in files:
        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
            cleaned.append(f)
    if not cleaned:
        for fn in os.listdir(_PHOTO_POOL_DIR):
            full = os.path.join(_PHOTO_POOL_DIR, fn)
            if os.path.isfile(full) and os.path.getsize(full) > 5000:
                if not fn.startswith('.') and 'readme' not in fn.lower() and 'gitkeep' not in fn.lower():
                    cleaned.append(full)
    return list(dict.fromkeys(cleaned))


def _add_com_segment(jpeg_data: bytes, comment_len: int = 32) -> bytes:
    """
    Insert COM segment — DEPRECATED untuk anti-deteksi.
    COM FF FE tidak ada di foto kamera HP asli, jadi kita NONAKTIFKAN.
    Fungsi ini dipertahankan untuk backward-compat tapi tidak dipakai lagi
    kecuali explicitly dipanggil.
    """
    if not jpeg_data.startswith(b"\xff\xd8"):
        return jpeg_data
    comment = os.urandom(comment_len)
    seg_len = 2 + len(comment)
    com = b"\xff\xfe" + seg_len.to_bytes(2, "big") + comment
    return jpeg_data[:2] + com + jpeg_data[2:]


def _crop_center_square(im):
    """Crop center square dari image (misal 1200x1600 -> 1200x1200) lalu resize ke target."""
    from PIL import Image
    w, h = im.size
    # Ambil sisi terkecil sebagai square
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    right = left + side
    bottom = top + side
    # Sedikit randomize crop position (±5% dari center) biar tidak exact
    offset_x = random.randint(-side // 20, side // 20)
    offset_y = random.randint(-side // 20, side // 20)
    left = max(0, min(w - side, left + offset_x))
    top = max(0, min(h - side, top + offset_y))
    right = left + side
    bottom = top + side
    return im.crop((left, top, right, bottom))


def _reencode_pool_image(path: str, target_w: int = None, target_h: int = None, variant_mode: str = "auto"):
    """
    Re-encode pool image ke 720x720 square mirip app asli.

    Proses:
    1. Open + convert RGB
    2. Crop center square (anti bypass: dimensi jadi square 720x720 seperti app)
    3. Resize ke target_w x target_h (default 720x720, weighted sesuai audit)
    4. VARIAN: asli / blur_ringan / blur_berat / kabur_glare / noisy_gelap (random 40/20/10/15/15)
    5. Variasi pixel halus (1-3 pixel tweak) — anti hash duplicate
    6. Save baseline JPEG (progressive=False, no EXIF, no COM)

    Args:
        path: path foto source
        target_w, target_h: target dimensi
        variant_mode: "auto" (random) atau "asli"/"blur_ringan"/"blur_berat"/"kabur_glare"/"noisy_gelap"

    Returns: JPEG bytes atau None. _LAST_META di-update dengan variant + src_path
    """
    try:
        from PIL import Image
        im = Image.open(path)
        # Ensure RGB
        if im.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', im.size, (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255)))
            if im.mode == 'P':
                im = im.convert('RGBA')
            bg.paste(im, mask=im.split()[-1] if im.mode == 'RGBA' else None)
            im = bg
        elif im.mode != 'RGB':
            im = im.convert('RGB')

        # === STRICT 720x720: SELALU CROP SQUARE + RESIZE KE 720x720 ===
        # Requirement: semua tipe wajib 720x720, tidak ada lagi outlier 720x960
        target_w, target_h = 720, 720

        # Selalu crop center square dulu biar tidak stretch (1200x1600 -> 1200x1200)
        im = _crop_center_square(im)

        # Resize ke 720x720 strict (LANCZOS high quality)
        if im.size != (720, 720):
            im = im.resize((720, 720), Image.LANCZOS)

        # === VARIAN blur/kabur/asli/noisy (request user) ===
        variant_used = "asli"
        try:
            im, variant_used = _apply_variant_transform(im, mode=variant_mode)
        except Exception:
            variant_used = variant_mode if variant_mode != "auto" else "asli"

        w, h = im.size

        # Variasi halus 1-5 pixel biar hash beda tiap upload (anti duplicate detection)
        # Tapi jangan ubah ukuran — tetap 720x720
        if random.random() < 0.8:
            px = im.load()
            for _ in range(random.randint(2, 6)):
                rx = random.randint(0, max(0, w - 1))
                ry = random.randint(0, max(0, h - 1))
                try:
                    r, g, b = px[rx, ry]
                    # tweak halus ±2-7 biar foto tampak natural tapi hash beda
                    px[rx, ry] = (
                        max(0, min(255, r + random.randint(-3, 5))),
                        max(0, min(255, g + random.randint(-2, 4))),
                        max(0, min(255, b + random.randint(-2, 4))),
                    )
                except Exception:
                    pass

        # Save baseline JPEG — anti deteksi bypass:
        # - progressive=False (kamera HP baseline, bukan progressive)
        # - exif=b'' (kamera HP asli strip EXIF oleh app sebelum upload)
        # - quality 82-93 (match real app, size 20-60KB untuk 720x720)
        # - optimize=True
        # - NO COM segment (FF FE tidak ada di kamera HP)
        out = io.BytesIO()
        q = random.randint(82, 93)
        im.save(
            out,
            format='JPEG',
            quality=q,
            optimize=True,
            exif=b'',
            progressive=False,
        )
        data = out.getvalue()

        # === Validasi size agar tidak terdeteksi bypass (pool gelap = size kecil) ===
        # Target 20-60KB untuk 720x720 (audit server 14-51KB avg 27KB)
        # Pool asli 1.jpeg mean=2 (hampir hitam) -> crop jadi 4.8KB, terlalu kecil -> flag bypass
        # Solusi: jika size <15KB, tambahkan noise texture dan re-encode higher quality
        if len(data) < 15000:
            # Cek apakah image terlalu flat (low entropy)
            try:
                # Tambah noise halus + overlay panel meter biar detail naik
                from PIL import ImageDraw
                draw = ImageDraw.Draw(im)
                # Tambah grain noise biar size naik
                for _ in range(random.randint(8000, 15000)):
                    x = random.randint(0, w - 1)
                    y = random.randint(0, h - 1)
                    nv = random.randint(-20, 25)
                    try:
                        r, g, b = im.getpixel((x, y))
                        draw.point((x, y), fill=(
                            max(0, min(255, r + nv + random.randint(-5, 8))),
                            max(0, min(255, g + nv)),
                            max(0, min(255, b + nv)),
                        ))
                    except:
                        pass
                out = io.BytesIO()
                im.save(out, format='JPEG', quality=min(95, q + 10), optimize=True, exif=b'', progressive=False)
                new_data = out.getvalue()
                # Pakai yang lebih besar jika masih dalam batas wajar
                if len(new_data) > len(data) and len(new_data) < 90000:
                    data = new_data
            except Exception:
                pass

        # Final guard: jika masih <12KB (pool corrupt), fallback ke synthetic meter 720x720
        if len(data) < 12000:
            # Synthetic fallback — tetap 720x720 realistic
            synth = _rand_jpeg_via_pil(target_w, target_h, quality=random.randint(85, 92))
            if synth and len(synth) >= 12000:
                return synth
            # Jika synthetic juga kecil, force high quality
            out = io.BytesIO()
            im.save(out, format='JPEG', quality=96, optimize=True, exif=b'', progressive=False)
            data = out.getvalue()

        # Batasi ukuran: loop quality turun sampai <70KB untuk tegangan (2 file total <140KB)
        # dan <80KB untuk beban. Audit server: 14-51KB avg 27KB, jadi target 20-60KB ideal.
        # STRICT 720x720: tetap 720x720, tidak boleh fallback ke 640x640
        if len(data) > 70000:
            # Loop turunkan quality sampai <70KB atau quality 50 (lebih agresif, tetap 720x720)
            for q_try in range(max(50, q - 12), 49, -3):
                out = io.BytesIO()
                im.save(out, format='JPEG', quality=q_try, optimize=True, exif=b'', progressive=False)
                nd = out.getvalue()
                if len(nd) <= 70000 or q_try <= 50:
                    data = nd
                    break
                if len(nd) < len(data):
                    data = nd

        # Jika masih >75KB setelah quality 50, coba tambah blur ringan untuk turunkan size
        # (tetap 720x720, tidak boleh resize ke 640x640)
        if len(data) > 75000:
            try:
                from PIL import ImageFilter
                im_blur = im.filter(ImageFilter.GaussianBlur(radius=0.6))
                out = io.BytesIO()
                im_blur.save(out, format='JPEG', quality=65, optimize=True, exif=b'', progressive=False)
                nd = out.getvalue()
                if 12000 <= len(nd) <= 75000 and len(nd) < len(data):
                    data = nd
            except Exception:
                # Last resort: tetap 720x720 quality 50
                try:
                    out = io.BytesIO()
                    im.save(out, format='JPEG', quality=50, optimize=True, exif=b'', progressive=False)
                    nd = out.getvalue()
                    if 12000 <= len(nd) <= 80000:
                        data = nd
                except Exception:
                    pass

        # Simpan meta terakhir untuk logging CLI (src_path, variant, size)
        try:
            _LAST_META["src_path"] = path
            _LAST_META["src_basename"] = os.path.basename(path)
            _LAST_META["variant"] = variant_used
            _LAST_META["bytes"] = len(data)
        except:
            pass

        return data

    except Exception as e:
        # Fallback: coba baca raw dan re-encode minimal — STRICT 720x720
        try:
            from PIL import Image
            with open(path, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\x89PNG'):
                im = Image.open(io.BytesIO(raw))
                if im.mode != 'RGB':
                    im = im.convert('RGB')
                # Crop square + resize strict 720x720
                im = _crop_center_square(im)
                if im.size != (720, 720):
                    im = im.resize((720, 720), Image.LANCZOS)
                out = io.BytesIO()
                im.save(out, format='JPEG', quality=random.randint(82, 92), optimize=True, exif=b'', progressive=False)
                return out.getvalue()
            # Jika JPEG tapi gagal diproses, coba tetap crop-resize paksa 720x720
            if raw.startswith(b'\xff\xd8'):
                im = Image.open(io.BytesIO(raw))
                if im.mode != 'RGB':
                    im = im.convert('RGB')
                im = _crop_center_square(im)
                im = im.resize((720, 720), Image.LANCZOS)
                out = io.BytesIO()
                im.save(out, format='JPEG', quality=random.randint(82, 92), optimize=True, exif=b'', progressive=False)
                return out.getvalue()
        except Exception:
            pass
        return None


def _rand_jpeg_via_pil(width=None, height=None, quality=None):
    """
    Fallback generate synthetic meter foto jika pool kosong.
    STRICT 720x720 square untuk semua tipe.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    # STRICT 720x720 untuk semua tipe — tidak ada lagi outlier
    width, height = 720, 720

    if quality is None:
        quality = random.randint(82, 93)

    # Buat background mirip foto meter real (bukan gray noise flat)
    # Base: panel gelap dengan sedikit texture
    base_dark = random.randint(20, 45)
    img = Image.new("RGB", (width, height), (base_dark, base_dark + 5, base_dark + 8))
    draw = ImageDraw.Draw(img)

    # Noise texture halus (seperti sensor kamera HP)
    for _ in range(random.randint(3000, 6000)):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        n = random.randint(-15, 20)
        c = max(0, min(255, base_dark + n))
        draw.point((x, y), fill=(c, c, c + random.randint(0, 5)))

    # Panel meter area (center, 70-85% dari sisi)
    margin = width // 12
    panel_w = random.randint(int(width * 0.7), width - margin * 2)
    panel_h = random.randint(int(height * 0.35), int(height * 0.6))
    panel_x = random.randint(margin, max(margin, width - panel_w - margin))
    panel_y = random.randint(margin + height // 10, max(margin, height - panel_h - margin))

    # Panel color metallic light
    pc_r = random.randint(185, 225)
    pc_g = random.randint(185, 225)
    pc_b = random.randint(175, 215)
    draw.rectangle([panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
                   fill=(pc_r, pc_g, pc_b), outline=(60, 60, 60), width=2)

    # Display hitam (LCD meter)
    disp_h = max(35, panel_h // 4)
    draw.rectangle([panel_x + 10, panel_y + 10, panel_x + panel_w - 10, panel_y + 10 + disp_h],
                   fill=(8, 18, 8), outline=(35, 35, 35), width=1)

    # Nilai meter fake
    fake_val = random.randint(0, 500)
    unit = random.choice(["A", "A", "A", "kV"])
    try:
        draw.text((panel_x + 18, panel_y + 16), f"{fake_val} {unit}", fill=(70, 255, 90))
    except Exception:
        pass

    # Tombol indikator
    for _ in range(random.randint(3, 6)):
        bx = random.randint(panel_x + 15, panel_x + panel_w - 50)
        by = random.randint(panel_y + disp_h + 25, panel_y + panel_h - 20)
        bw = random.randint(20, 45)
        bh = random.randint(12, 20)
        bc = (random.randint(40, 110), random.randint(40, 110), random.randint(40, 110))
        draw.rectangle([bx, by, bx + bw, by + bh], fill=bc, outline=(0, 0, 0))

    # Glare / pantulan cahaya (realistic untuk foto meter)
    if random.random() < 0.4:
        gx = random.randint(0, width // 4)
        gy = random.randint(0, height // 4)
        gw = random.randint(50, 150)
        gh = random.randint(20, 80)
        draw.ellipse([gx, gy, gx + gw, gy + gh], fill=(255, 255, 255))

    out = io.BytesIO()
    # Baseline JPEG, no progressive, no EXIF, quality 82-93 => 20-60KB for 720x720
    img.save(out, format="JPEG", quality=quality, optimize=True, exif=b'', progressive=False)
    return out.getvalue()


def rand_jpeg_bytes(target_w: int = None, target_h: int = None, item_name: str = None, data_type: str = None, subtype: str = None, photo_source: str = None, variant_mode: str = None):
    """
    Return valid JPEG bytes 720x720 square mirip app asli.

    - Jika photo_source=manual + item_name ada -> ambil dari photo/manual/{data_type}/{ITEM}/ (per-item sesuai)
      + hv/mv terpisah untuk tegangan (photo/manual/tegangan-trafo/TRAFO_1/hv/ & mv/)
      + random pick + varian blur/kabur/asli/noisy_gelap (40/20/10/15/15)
    - Jika photo_source=pool (default) -> ambil dari photo/pool/ 1 foto untuk semua
    - Fallback synthetic 720x720 jika pool kosong
    - Baseline JPEG, no progressive, no COM, no EXIF
    - Size 15-60KB (match audit server 14-51KB avg 27KB)
    - Nama file upload TETAP pakai humanizer: fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg (bukan basename manual)

    Args:
        target_w, target_h: opsional target dimensi (default 720x720)
        item_name: nama penyulang/trafo untuk per-item pool
        data_type: beban-penyulang / beban-trafo / tegangan-trafo
        subtype: untuk tegangan: HV atau MV
        photo_source: "pool" (1 foto semua) atau "manual" (per-item sesuai)
        variant_mode: "auto" atau "asli"/"blur_ringan"/"blur_berat"/"kabur_glare"/"noisy_gelap"

    Returns:
        bytes JPEG valid
    """
    # STRICT 720x720 untuk semua tipe
    target_w, target_h = 720, 720

    # Resolver per-item pool (manual vs pool) — content only, filename tetap humanizer
    pool_files, src_mode, folder_label, full_dir = _get_photo_pool_per_item(
        item_name=item_name, data_type=data_type, subtype=subtype, photo_source=photo_source
    )

    # Update last meta untuk tracking
    _LAST_META["source_mode"] = src_mode
    _LAST_META["folder_label"] = folder_label
    _LAST_META["full_dir"] = full_dir or ""
    _LAST_META["item_name"] = item_name or ""
    _LAST_META["data_type"] = data_type or ""

    if pool_files:
        # Coba 5 kali dari pool (random pick per input) — strict 720x720
        for _ in range(5):
            p = random.choice(pool_files)
            # variant_mode: auto = random 40% asli, 20% blur_ringan, 10% blur_berat, 15% kabur_glare, 15% noisy_gelap
            enc = _reencode_pool_image(p, 720, 720, variant_mode=variant_mode or "auto")
            if enc and enc.startswith(b"\xff\xd8") and len(enc) >= 8000:
                # Validasi dimensi strict 720x720
                try:
                    from PIL import Image
                    im = Image.open(io.BytesIO(enc))
                    w, h = im.size
                    # STRICT: harus 720x720
                    if (w, h) == (720, 720):
                        if 10000 <= len(enc) <= 100000:
                            return enc
                    # Jika bukan 720x720, coba re-encode lagi (jangan return yang non-720)
                except:
                    # Jika PIL gagal cek, tetap return jika size ok (akan di-validasi lagi downstream)
                    if len(enc) >= 8000:
                        # Cek lagi dimensi, kalau gagal PIL tapi bytes valid, tetap coba return
                        # tapi next iteration akan coba lagi yang strict
                        try:
                            from PIL import Image
                            im = Image.open(io.BytesIO(enc))
                            if im.size == (720, 720):
                                return enc
                        except:
                            if len(enc) >= 10000:
                                return enc

        # Fallback: baca raw dan crop paksa ke 720x720 strict
        try:
            from PIL import Image
            raw_path = random.choice(pool_files)
            with open(raw_path, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\xff\xd8') and len(raw) >= 5000:
                im = Image.open(io.BytesIO(raw))
                if im.mode != 'RGB':
                    im = im.convert('RGB')
                im = _crop_center_square(im)
                im = im.resize((720, 720), Image.LANCZOS)
                # variant untuk fallback raw juga
                try:
                    im, _ = _apply_variant_transform(im, mode=variant_mode or "auto")
                except:
                    pass
                out = io.BytesIO()
                im.save(out, format='JPEG', quality=random.randint(82, 93), optimize=True, exif=b'', progressive=False)
                data = out.getvalue()
                if len(data) >= 10000:
                    # update meta
                    _LAST_META["src_path"] = raw_path
                    _LAST_META["src_basename"] = os.path.basename(raw_path)
                    _LAST_META["bytes"] = len(data)
                    return data
        except Exception:
            pass

    # Fallback synthetic strict 720x720
    for _ in range(5):
        gen = _rand_jpeg_via_pil(720, 720)
        if gen and gen.startswith(b"\xff\xd8") and len(gen) >= 8000:
            _LAST_META["source_mode"] = "synthetic"
            _LAST_META["variant"] = "synthetic"
            _LAST_META["bytes"] = len(gen)
            return gen

    # Last fallback: minimal 720x720 valid JPEG (gray) — strict 720x720
    try:
        from PIL import Image
        img = Image.new('RGB', (720, 720), (random.randint(30, 60), random.randint(30, 60), random.randint(35, 65)))
        out = io.BytesIO()
        img.save(out, format='JPEG', quality=85, optimize=True, exif=b'', progressive=False)
        data = out.getvalue()
        _LAST_META["source_mode"] = "gray-fallback"
        _LAST_META["bytes"] = len(data)
        return data
    except:
        pass

    # Ultimate fallback: old 1x1 + expand via COM (legacy, tapi tetap valid JPEG)
    # Dengan catatan ini akan terdeteksi sebagai bypass jika masih dipakai — jadi log warning
    base = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x02, 0xD0,
        0x02, 0xD0, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0x7B, 0x94, 0x11, 0x00, 0x00, 0x00, 0x00, 0x00,
        0xFF, 0xD9
    ])
    return base


def rand_jpeg_pair(target_w: int = None, target_h: int = None, item_name: str = None, data_type: str = None, photo_source: str = None, variant_mode: str = None):
    """Two different valid JPEGs 720x720 untuk tegangan (HV + MV) - mirip aplikasi asli.

    APK GAMA asli: fotoHV.jpg & fotoMV.jpg, 2 file field 'files', baseline 720x720, no EXIF.
    Project kita tetap pakai penamaan: fotoHV_YYYY-MM-DD_<hex>.jpg / fotoMV_... (humanizer)
    Content: dari photo/manual/tegangan-trafo/TRAFO_1/hv/, mv/ terpisah, varian blur/kabur/asli.

    Perbaikan agar tidak dianggap robot & foto terbaca server:
    - HV dan MV harus distinct (hash beda, size beda minimal 1KB)
    - Jika manual, HV dari hv/ folder, MV dari mv/ folder (terpisah)
    - Jika pool, 1 file untuk semua tapi tetap distinct via variant
    - Pastikan baseline, no progressive, no COM, no EXIF (audit server)
    """
    # STRICT 720x720 untuk semua tipe (beban penyulang, beban trafo, tegangan HV+MV)
    target_w, target_h = 720, 720

    for attempt in range(15):
        # Untuk tegangan, paksa variant berbeda agar tidak dianggap duplicate oleh server
        # APK asli: HV dan MV adalah 2 foto berbeda (beda waktu 12-42 detik, lokasi 2-5m)
        # Kita: HV pakai variant random, MV pakai variant berbeda
        v1 = None
        v2 = None
        if attempt % 2 == 0:
            # Coba variant berbeda
            variants = ["asli", "blur_ringan", "blur_berat", "kabur_glare", "noisy_gelap"]
            v1 = random.choice(variants)
            v2 = random.choice([x for x in variants if x != v1])

        j1 = rand_jpeg_bytes(target_w, target_h, item_name=item_name, data_type=data_type or "tegangan-trafo", subtype="HV", photo_source=photo_source, variant_mode=v1 or variant_mode)
        j2 = rand_jpeg_bytes(target_w, target_h, item_name=item_name, data_type=data_type or "tegangan-trafo", subtype="MV", photo_source=photo_source, variant_mode=v2 or variant_mode)

        # Validasi: harus JPEG valid, size 15-70KB, hash beda
        if not j1 or not j2:
            continue
        if len(j1) < 12000 or len(j2) < 12000:
            continue
        if len(j1) > 75000 or len(j2) > 75000:
            # Jika masih >75KB, coba lagi (loop quality di _reencode sudah handle, tapi double-check)
            continue
        if j1 == j2:
            continue
        if hashlib.sha256(j1).hexdigest() == hashlib.sha256(j2).hexdigest():
            continue
        # Pastikan size beda minimal 500 byte (tidak identik)
        if abs(len(j1) - len(j2)) < 500 and attempt < 10:
            # Coba lagi biar size beda (lebih natural seperti 2 foto berbeda)
            continue
        return j1, j2

    # fallback: paksa distinct dengan resize quality berbeda
    j1 = rand_jpeg_bytes(target_w, target_h, item_name=item_name, data_type=data_type, subtype="HV", photo_source=photo_source, variant_mode="asli")
    j2 = rand_jpeg_bytes(target_w, target_h, item_name=item_name, data_type=data_type, subtype="MV", photo_source=photo_source, variant_mode="blur_ringan")
    return j1, j2


# ============================================================
# DURASI - UNIT SERVER ADALAH MENIT (bukan detik)
# Manual: beban avg 0.105 menit = 6.35 detik (2-7 detik realistic)
#         tegangan avg 0.305 menit = 18.3 detik (8-40 detik)
# ============================================================

def _sec_to_min(sec: float) -> float:
    """Konversi detik ke menit (unit server)."""
    return round(sec / 60.0, 8)


def rand_durasi() -> float:
    """
    Durasi beban penyulang/trafo: 2.00-7.00 detik, dikembalikan dalam MENIT.
    Contoh: 3.91 detik -> 0.06516666 menit -> server akan display 3.91 detik
    Manual: min 0.057, max 2.14, avg 0.105 menit = 6.35 detik
    """
    # Weighted: lebih sering di 3-6 detik, jarang di edge
    if random.random() < 0.7:
        sec = random.uniform(2.5, 6.5)
    else:
        sec = random.uniform(2.0, 7.0)
    sec = round(sec, 2)
    # Pastikan 2 decimal places (mis 2.81, 5.67)
    if len(str(sec).split(".")[-1]) == 1:
        sec = round(sec + 0.01, 2)
    menit = _sec_to_min(sec)
    if menit in _FORBIDDEN_DURASI or menit == 0.0:
        return rand_durasi()
    return menit


def rand_durasi_trafo() -> float:
    """Durasi beban trafo: mirip beban penyulang (2-7 detik) -> menit."""
    return rand_durasi()


def rand_durasi_tegangan() -> float:
    """
    Durasi tegangan trafo: butuh 2 foto (HV+MV), jadi lebih lama: 8-35 detik -> menit.
    Manual tegangan: min 0.146 (8.8s), max 1.02 (61s), avg 0.305 (18.3s)
    """
    if random.random() < 0.6:
        sec = random.uniform(10.0, 25.0)  # common 10-25s
    else:
        sec = random.uniform(8.0, 38.0)
    sec = round(sec, 2)
    menit = _sec_to_min(sec)
    if menit == 0.0:
        return rand_durasi_tegangan()
    return menit


def rand_durasi_fast() -> float:
    """Variant cepat untuk burst: 2-5 detik -> menit."""
    sec = round(random.uniform(2.0, 5.0), 2)
    return _sec_to_min(sec)


def rand_durasi_for_type(data_type: str) -> float:
    """Helper: pilih durasi sesuai tipe data."""
    if "tegangan" in data_type:
        return rand_durasi_tegangan()
    return rand_durasi()


# ============================================================
# LOKASI REALISTIS
# ============================================================

def _jitter_coord(base: float, meters: int = 10) -> float:
    """Jitter koordinat ±meters (1 degree ~111km)."""
    # 0.00001 degree ~ 1.11m
    jitter_deg = (meters / 111000.0) * random.uniform(-1, 1)
    return round(base + jitter_deg, 7)


def rand_location():
    """
    Return (address, latitude, longitude) realistis seperti manual.
    5% chance alamat format Lat=..., Long=...
    Lat/lon jitter ±5-15m.
    """
    # 5% chance pakai format Lat/Long mentah
    if random.random() < 0.05:
        base = random.choice(_REAL_LOCATIONS)
        lat = _jitter_coord(base[1], meters=random.randint(5, 15))
        lon = _jitter_coord(base[2], meters=random.randint(5, 15))
        addr = f"Lat={lat:.7f}, Long={lon:.7f}"
        return addr, lat, lon

    addr, base_lat, base_lon = random.choice(_REAL_LOCATIONS)
    lat = _jitter_coord(base_lat, meters=random.randint(5, 15))
    lon = _jitter_coord(base_lon, meters=random.randint(5, 15))

    # Kadang alamat sedikit variasi: nomor jalan ±1, RT/RW ±1
    if random.random() < 0.15:
        # variasi nomor
        import re
        # contoh: No.36 -> No.37
        def repl_no(m):
            try:
                num = int(m.group(1))
                return f"No.{num + random.choice([-1, 0, 1])}"
            except:
                return m.group(0)
        addr_varied = re.sub(r"No\.(\d+)", repl_no, addr)
        # kalau berubah, pakai yang variasi
        if addr_varied != addr and random.random() < 0.5:
            addr = addr_varied

    return addr, lat, lon


def rand_foto_dict(
    data_type: str = "beban-penyulang",
    date_str: str = None,
    periode: int = None,
    durasi_min: float = None,
    subtype: str = None,
):
    """
    Return dict foto lengkap: {date, address, latitude, longitude}
    - date: ISO8601 UTC, korelasi dengan durasi (now - durasi - buffer)
    - address/lat/lon: realistis
    Kwargs order: data_type, date_str, periode, durasi_min, subtype (backward compat positional handled)
    """
    # Backward-compat: if second positional was actually date_str (when called as old signature)
    # Detect if subtype looks like a date string YYYY-MM-DD
    if subtype is None and date_str is not None and isinstance(date_str, str) and len(date_str) == 10 and date_str[4] == "-":
        # called with (data_type, date_str, periode, durasi) misuse? Actually our old had (data_type, subtype, date_str, periode, durasi)
        # If subtype is None and date_str is date, fine.
        pass

    if date_str is None or periode is None:
        # fallback to today
        date_str = date_str or datetime.now(_WIB).strftime("%Y-%m-%d")
        periode = periode if periode is not None else 12

    foto_date = rand_foto_datetime(date_str, periode, durasi_min)
    addr, lat, lon = rand_location()
    return {"date": foto_date, "address": addr, "latitude": lat, "longitude": lon}


def rand_foto_dict_compat(*args, **kwargs):
    """Legacy wrapper to handle old positional order."""
    # old order: data_type, subtype, date_str, periode, durasi
    # new order: data_type, date_str, periode, durasi, subtype
    # We try to detect.
    return rand_foto_dict(**kwargs)


# ============================================================
# FOTO DATETIME - KORELASI DENGAN DURASI + ANTI-ROBOT SPACING 10-20 DETIK
# ============================================================

# Tracker untuk menghindari timestamp duplikat dalam 1 batch periode yang sama.
# Struktur: {(date_str, periode): [datetime_wib, ...]} urutan insert, oldest = min()
_FOTO_TIMELINE: dict = {}


def reset_foto_sequence(date_str: str = None, periode: int = None):
    """Reset tracker foto sequence. Dipanggil di awal batch per-periode.

    - reset_foto_sequence() -> clear semua
    - reset_foto_sequence("2026-07-15", 17) -> clear periode 17 saja
    """
    if date_str is None and periode is None:
        _FOTO_TIMELINE.clear()
    else:
        if periode is None:
            # clear semua periode di tanggal tersebut
            keys = [k for k in _FOTO_TIMELINE.keys() if k[0] == date_str]
            for k in keys:
                _FOTO_TIMELINE.pop(k, None)
        else:
            _FOTO_TIMELINE.pop((date_str, int(periode)), None)


# Backward-compat alias yang dipakai beberapa modul mungkin import reset_sequence
def reset_sequence(date_str: str = None, periode: int = None):
    return reset_foto_sequence(date_str, periode)


def _rand_minute_second_ms():
    mm = random.randint(2, 54)
    ss = random.randint(3, 58)
    ms = random.randint(80, 970)
    return mm, ss, ms


def _format_utc(local_dt: datetime) -> str:
    return local_dt.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{local_dt.microsecond // 1000:03d}Z"


def _local_period_datetime(date_str: str, periode: int) -> datetime:
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    mm, ss, ms = _rand_minute_second_ms()
    return datetime(date.year, date.month, date.day, periode, mm, ss, ms * 1000, tzinfo=_WIB)


def _hour_window(date_str: str, periode: int):
    """Return (hour_start, hour_end) WIB datetime untuk jam tersebut."""
    safe = max(0, min(23, int(periode)))
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    start = datetime(d.year, d.month, d.day, safe, 0, 2, random.randint(80, 970) * 1000, tzinfo=_WIB)
    end = datetime(d.year, d.month, d.day, safe, 59, 59, random.randint(80, 970) * 1000, tzinfo=_WIB)
    return start, end


def _find_free_slot(hard_start: datetime, hard_end: datetime, existing: list, min_gap: float = 10.0, max_attempts: int = 80):
    """Cari slot random di [hard_start, hard_end] yang min_gap dari semua existing."""
    span = (hard_end - hard_start).total_seconds()
    if span <= 10:
        return None
    for _ in range(max_attempts):
        sec = random.uniform(5.0, max(5.0, span - 5.0))
        cand = hard_start + timedelta(seconds=sec, milliseconds=random.randint(0, 900))
        if all(abs((cand - e).total_seconds()) >= min_gap for e in existing):
            return cand
    return None


def _next_spaced_datetime(date_str: str, periode: int, durasi_sec: float = None, is_current_hour: bool = False):
    """Core generator: timestamp berikutnya dengan jeda 10-20 detik dari timestamp terakhir.

    - Untuk periode == now.hour (is_current_hour True): generate mundur dari now, gap 10-20s
      contoh: now-4s, now-4-15s, now-4-15-13s dst -> span 6 menit untuk 25 item
    - Untuk periode historis: tetap sebar dalam jam 00-59, gap 10-20s minimal
    """
    safe_periode = max(0, min(23, int(periode)))
    now = datetime.now(_WIB)
    key = (date_str, safe_periode)

    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    h_start, h_end = _hour_window(date_str, safe_periode)
    if is_current_hour:
        hard_start = h_start
        hard_end = now
        # Pada beberapa menit pertama setelah pergantian jam, 25 foto tidak
        # mungkin muat dengan gap aman. Izinkan timeline mundur sedikit ke jam
        # sebelumnya daripada memampatkan timestamp menjadi 2-6 detik.
        reserved_gap = 10.5
        min_batch_span = 24 * reserved_gap + 60
        if (hard_end - hard_start).total_seconds() < min_batch_span:
            hard_start = hard_end - timedelta(seconds=min_batch_span)
    else:
        hard_start = h_start
        hard_end = h_end

    existing = _FOTO_TIMELINE.get(key, [])
    # hard_start minimal 2 detik setelah 00:00 agar tidak 00:00.000
    if hard_start.second < 2:
        hard_start = hard_start + timedelta(seconds=random.randint(2, 8))

    if not existing:
        if is_current_hour:
            buf = random.uniform(0.5, 2.8)
            base_offset = (durasi_sec or random.uniform(2.5, 6.0)) + buf
            # Tambahkan jitter ekstra 0-35s agar antar-proses (CLI terpisah) tidak tabrakan di detik yang sama
            extra = random.uniform(0, 35.0)
            total_offset = base_offset + extra
            # Pastikan tidak lebih dari available window, minimal 90s max untuk first
            max_allowed = (hard_end - hard_start).total_seconds() - 5
            total_offset = min(total_offset, max(25.0, max_allowed * 0.15))  # first item 5-35% dari available atau min 25s
            # Random lagi untuk first agar tidak selalu di ujung
            total_offset = random.uniform(min(5.0, total_offset), total_offset)
            total_offset = max(2.0, total_offset)
            # Sisakan ruang untuk batch penyulang umum (25 foto) dengan gap aman.
            available = (hard_end - hard_start).total_seconds()
            reserved_gap = 10.5
            if available >= 24 * reserved_gap + 4:
                total_offset = min(total_offset, available - 24 * reserved_gap - 2)
            cand = hard_end - timedelta(seconds=total_offset, milliseconds=random.randint(50, 900))
            if cand < hard_start:
                cand = hard_start + timedelta(seconds=random.uniform(10, 120), milliseconds=random.randint(50, 900))
        else:
            cand = _local_period_datetime(date_str, safe_periode)
        # simpan
        _FOTO_TIMELINE.setdefault(key, []).append(cand)
        return cand

    oldest = min(existing)  # timestamp paling lama (paling kecil) -> next harus lebih lama lagi (mundur)
    if is_current_hour and len(existing) < 25:
        available = (oldest - hard_start).total_seconds()
        reserved_gap = 10.5
        remaining_after = 24 - len(existing)
        max_gap = available - remaining_after * reserved_gap
        if max_gap >= reserved_gap:
            low_gap = reserved_gap
            gap = random.uniform(low_gap, min(20.9, max_gap))
            cand = oldest - timedelta(seconds=gap)
            _FOTO_TIMELINE[key].append(cand)
            return cand

    # Untuk current hour, kita mundur terus dari oldest
    attempts = 0
    while attempts < 60:
        gap = random.uniform(10.0, 20.0) + random.uniform(0.0, 0.9)  # 10-20.9 detik sesuai request
        # Kalau sudah banyak item dan window sempit, compress gap sedikit
        if is_current_hour:
            available = (oldest - hard_start).total_seconds()
            if available < 15:
                # window hampir habis, coba cari slot kosong di tengah
                free = _find_free_slot(hard_start, hard_end, existing, min_gap=8.0)
                if free:
                    _FOTO_TIMELINE[key].append(free)
                    return free
                # compress gap ke 5-9 detik sebagai last resort
                gap = random.uniform(5.0, 9.5)

        cand = oldest - timedelta(seconds=gap, milliseconds=random.randint(50, 900))

        if cand < hard_start:
            # overflow sebelum jam mulai -> cari slot kosong di antara existing
            free = _find_free_slot(hard_start, hard_end, existing, min_gap=8.0)
            if free:
                _FOTO_TIMELINE[key].append(free)
                return free
            # jika tidak ada slot kosong, compress dan letakkan di awal jam + jitter
            cand = hard_start + timedelta(seconds=random.uniform(2, 60), milliseconds=random.randint(50, 900))
            # pastikan tidak tabrakan same-second
            if all(abs((cand - e).total_seconds()) >= 3 for e in existing):
                _FOTO_TIMELINE[key].append(cand)
                return cand
            attempts += 1
            continue

        # cek gap minimal 8s dari semua (ideal 10s, tapi 8s minimum anti same-second UI)
        min_gap_needed = 8.0 if len(existing) > 25 else 10.0
        if all(abs((cand - e).total_seconds()) >= min_gap_needed for e in existing):
            _FOTO_TIMELINE[key].append(cand)
            return cand

        # kalau historis, coba random slot
        if not is_current_hour:
            cand = _local_period_datetime(date_str, safe_periode)
            if all(abs((cand - e).total_seconds()) >= min_gap_needed for e in existing):
                _FOTO_TIMELINE[key].append(cand)
                return cand

        attempts += 1

    # fallback last resort: paksa mundur dengan gap kecil tapi pastikan detik tidak sama persis
    cand = oldest - timedelta(seconds=random.uniform(6, 12), milliseconds=random.randint(50, 900))
    if cand < hard_start:
        cand = hard_start + timedelta(seconds=random.uniform(1, 20))
    # anti same-second: loop sampai detik beda
    tries = 0
    while any(abs((cand - e).total_seconds()) < 2 for e in existing) and tries < 20:
        cand -= timedelta(seconds=random.uniform(1, 3))
        if cand < hard_start:
            cand = hard_start + timedelta(seconds=random.uniform(5, 90))
        tries += 1
    _FOTO_TIMELINE[key].append(cand)
    return cand


def rand_foto_datetime(date_str: str, periode: int, durasi_min: float = None) -> str:
    """Foto datetime realistis + anti-robot spacing 10-20 detik.

    - Jika date_str == hari ini:
        * periode == jam sekarang: timestamp mundur dari now dengan gap 10-20s
          (foto1 = now-4s, foto2 = foto1-15s, dst) -> tidak lagi cluster 6 detik
        * periode < jam sekarang: random dalam jam + gap 10-20s antar item
    - Jika date_str historis: random menit/detik dalam jam periode + gap 10-20s
    Format: YYYY-MM-DDTHH:MM:SS.mmmZ
    """
    safe_periode = max(0, min(23, int(periode)))
    now = datetime.now(_WIB)
    today_str = now.strftime("%Y-%m-%d")

    durasi_sec = None
    if durasi_min is not None:
        try:
            durasi_sec = float(durasi_min) * 60.0
        except:
            durasi_sec = None

    is_today = (date_str == today_str)
    is_current_hour = is_today and safe_periode == now.hour
    is_past_hour_today = is_today and safe_periode < now.hour

    # Untuk periode yang sudah lewat hari ini (mis P09 jam 17), tetap anggap bukan current_hour,
    # tapi pakai logic spaced random dalam jam tersebut (lebih realistis operator foto jam 09 pagi)
    # -> _next_spaced akan pakai hour window 09:00-09:59

    # Jika periode malam yang belum lewat (safe_periode > now.hour) tapi hari ini,
    # itu edge (input masa depan jam 20 padahal sekarang jam 17) -> pakai logic current_hour tapi cap ke hour_end
    if is_today and safe_periode > now.hour:
        # masa depan hari ini -> treat sebagai historical random dalam jam tersebut (tidak pakai now)
        is_current_hour = False

    if is_current_hour or is_past_hour_today or not is_today or True:
        # Semua jalur sekarang lewat spaced generator agar 10-20s terjamin
        # (dulu ada branch now-durasi yang bikin cluster)
        capture = _next_spaced_datetime(date_str, safe_periode, durasi_sec, is_current_hour=is_current_hour)
    else:
        # fallback lama (tidak dipakai lagi, tapi keep untuk safety)
        if durasi_sec is not None and durasi_sec > 0:
            buffer = random.uniform(0.5, 2.8)
            total_offset = durasi_sec + buffer
            total_offset = min(total_offset, 85.0)
            capture = now - timedelta(seconds=total_offset, milliseconds=random.randint(50, 900))
        else:
            if safe_periode >= now.hour:
                capture = now - timedelta(seconds=random.uniform(2.0, 12.0), milliseconds=random.randint(50, 900))
            else:
                capture = _local_period_datetime(date_str, safe_periode)

    return _format_utc(capture)


def rand_foto_pair(date_str: str, periode: int, durasi_min: float = None):
    """Dua timestamp HV/MV dengan spacing 10-20 detik antar trafo + 12-42 detik HV-MV.

    Baru:
    - Gap antar input trafo: 10-20 detik (MV_prev -> HV_next = 10-20s)
    - Gap dalam 1 trafo (HV->MV): 12-42 detik (real walk)
    - Total untuk 5 trafo: ~ (15+25)*5 = 200 detik = 3 menit sebaran

    Implementasi mundur dari now (per batch):
    MV = oldest - gap_inter (10-20s)
    HV = MV - gap_pair (12-42s)
    Jadi urutan waktu real: HV older, MV newer (HV diambil dulu, jalan ke MV)
    """
    safe_periode = max(0, min(23, int(periode)))
    now = datetime.now(_WIB)
    today_str = now.strftime("%Y-%m-%d")
    key = (date_str, safe_periode)

    is_today = (date_str == today_str)
    is_current_hour = is_today and safe_periode == now.hour

    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    h_start, h_end = _hour_window(date_str, safe_periode)

    if is_current_hour:
        hard_start = h_start
        hard_end = now
        # Lima pair membutuhkan ruang untuk gap HV-MV dan antar-trafo. Pada
        # awal jam gunakan overlap historis pendek agar spacing tidak rusak.
        if (hard_end - hard_start).total_seconds() < 5 * 45:
            hard_start = hard_end - timedelta(seconds=5 * 45)
    else:
        hard_start = h_start
        hard_end = h_end

    existing = _FOTO_TIMELINE.get(key, [])

    if not existing:
        # First pair: buat dekat now atau random dalam jam
        durasi_sec = None
        if durasi_min is not None:
            try:
                durasi_sec = float(durasi_min) * 60.0
            except:
                durasi_sec = None
        gap_inter = random.uniform(10.0, 20.0)
        gap_pair = random.randint(12, 42)
        if is_current_hour:
            buf = random.uniform(0.8, 3.0)
            total_offset = (durasi_sec or random.uniform(10, 22)) + buf
            mv = hard_end - timedelta(seconds=random.uniform(2.0, 8.0), milliseconds=random.randint(50, 900))
            hv = mv - timedelta(seconds=gap_pair, milliseconds=random.randint(80, 850))
        else:
            # historical: random HV, MV = HV+delta
            hv = _local_period_datetime(date_str, safe_periode)
            mv = hv + timedelta(seconds=gap_pair, milliseconds=random.randint(80, 850))
            # clamp MV still in same hour (< :59)
            if mv.hour != safe_periode or mv > hard_end:
                mv = hv + timedelta(seconds=random.uniform(8, 20))
                if mv.hour != safe_periode:
                    hv = h_start + timedelta(seconds=random.uniform(10, 1800))
                    mv = hv + timedelta(seconds=gap_pair)
        # register
        _FOTO_TIMELINE.setdefault(key, []).extend([hv, mv])
        return _format_utc(hv), _format_utc(mv)

    # ada existing -> pakai logic mundur: MV_next = oldest - gap_inter, HV_next = MV_next - gap_pair
    oldest = min(existing)
    attempts = 0
    while attempts < 60:
        gap_inter = random.uniform(10.0, 20.0) + random.uniform(0, 0.9)
        gap_pair = random.randint(12, 42)

        # compress jika window hampir habis
        available = (oldest - hard_start).total_seconds()
        if available < (gap_inter + gap_pair + 5):
            gap_inter = random.uniform(5.0, 9.5)
            gap_pair = random.randint(8, 20)

        mv = oldest - timedelta(seconds=gap_inter, milliseconds=random.randint(50, 900))
        hv = mv - timedelta(seconds=gap_pair, milliseconds=random.randint(80, 850))

        if hv < hard_start:
            # cari slot kosong
            free_mv = _find_free_slot(hard_start, hard_end, existing, min_gap=10.0)
            if free_mv:
                # HV = free_mv - gap_pair, MV = free_mv
                hv_try = free_mv - timedelta(seconds=gap_pair, milliseconds=random.randint(80, 850))
                if hv_try >= hard_start and all(abs((hv_try - e).total_seconds()) >= 8 for e in existing) and all(abs((free_mv - e).total_seconds()) >= 8 for e in existing):
                    _FOTO_TIMELINE[key].extend([hv_try, free_mv])
                    return _format_utc(hv_try), _format_utc(free_mv)
            attempts += 1
            continue

        # cek gap minimal
        def _ok_gap(ts, ex_list, gap):
            return all(abs((ts - e).total_seconds()) >= gap for e in ex_list)

        if _ok_gap(mv, existing, 8) and _ok_gap(hv, existing, 8):
            # ideal min 10s, tapi 8s ok untuk crowded hour
            if len(existing) < 15:
                if not (_ok_gap(mv, existing, 10) and _ok_gap(hv, existing, 10)):
                    if attempts < 30:
                        attempts += 1
                        continue
            _FOTO_TIMELINE[key].extend([hv, mv])
            return _format_utc(hv), _format_utc(mv)

        attempts += 1

    # fallback: paksa
    mv = oldest - timedelta(seconds=random.uniform(10, 20))
    hv = mv - timedelta(seconds=random.randint(12, 42))
    if hv < hard_start:
        hv = hard_start + timedelta(seconds=random.uniform(5, 30))
        mv = hv + timedelta(seconds=random.randint(12, 25))
    _FOTO_TIMELINE[key].extend([hv, mv])
    return _format_utc(hv), _format_utc(mv)


def rand_foto_pair_dicts(date_str: str, periode: int, durasi_min: float = None):
    """Return (fotoHV dict, fotoMV dict) lengkap dengan lokasi realistis."""
    ts1, ts2 = rand_foto_pair(date_str, periode, durasi_min)
    # HV dan MV lokasi bisa sedikit berbeda (orang jalan 2-5 meter antar foto)
    addr1, lat1, lon1 = rand_location()
    # MV lokasi dekat HV tapi jitter lagi
    if random.random() < 0.7:
        # dekat HV
        lat2 = _jitter_coord(lat1, meters=random.randint(2, 6))
        lon2 = _jitter_coord(lon1, meters=random.randint(2, 6))
        addr2 = addr1  # alamat sama
    else:
        addr2, lat2, lon2 = rand_location()

    fotoHV = {"date": ts1, "address": addr1, "latitude": lat1, "longitude": lon1}
    fotoMV = {"date": ts2, "address": addr2, "latitude": lat2, "longitude": lon2}
    return fotoHV, fotoMV


def rand_boundary() -> str:
    """Boundary multipart random 16 char alnum (mirip browser/mobile)."""
    rand = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    return f"{_BASE_BOUNDARY_PREFIX}{rand}"


def rand_filename(foto_datetime: str = None, idx: int = 0, data_type: str = "beban-penyulang", subtype: str = None) -> str:
    """Filename mirip aplikasi SUPER-I asli.

    Pola asli (dari API manual):
      beban-penyulang: fotoBebanPenyulang_YYYY-MM-DD_<hex16>.jpg  (2255 samples)
      beban-trafo:     fotoBebanTrafo_YYYY-MM-DD_<hex>.jpg
      tegangan:        fotoHV_YYYY-MM-DD_<hex>.jpg, fotoMV_YYYY-MM-DD_<hex>.jpg

    Args:
        foto_datetime: ISO8601 string untuk korelasi tanggal
        idx: index untuk tegangan (0=HV,1=MV)
        data_type: beban-penyulang | beban-trafo | tegangan-trafo
        subtype: untuk tegangan: HV atau MV

    Returns:
        filename string seperti app asli
    """
    # Parse date dari foto_datetime
    if foto_datetime:
        try:
            dt = datetime.strptime(foto_datetime, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=_UTC).astimezone(_WIB)
            date_part = dt.strftime("%Y-%m-%d")
        except ValueError:
            try:
                dt = datetime.strptime(foto_datetime, "%Y-%m-%dT%H:%M:%S.%f")
                date_part = dt.strftime("%Y-%m-%d")
            except Exception:
                date_part = datetime.now().strftime("%Y-%m-%d")
    else:
        date_part = datetime.now().strftime("%Y-%m-%d")

    # 16 hex chars (seperti manual: 707ab3a0bbe0d9a5) atau 12 hex untuk HV/MV
    if "tegangan" in data_type:
        hex_len = random.choice([12, 12, 16])  # HV/MV sering 12 chars
    else:
        hex_len = 16

    hex_part = uuid.uuid4().hex[:hex_len]

    # Tentukan prefix
    if "tegangan" in data_type:
        # subtype HV/MV
        if subtype:
            pref = f"foto{subtype}"
        else:
            pref = "fotoHV" if idx == 0 else "fotoMV"
    elif "beban-trafo" in data_type or data_type == "trafo":
        pref = "fotoBebanTrafo"
    else:
        pref = "fotoBebanPenyulang"

    return f"{pref}_{date_part}_{hex_part}.jpg"


def rand_user_agent() -> str:
    return random.choice(_USER_AGENTS)


def human_sleep(a: float = 0.6, b: float = 2.2, long_chance: float = 0.08):
    """Sleep cepat mirip manusia tap HP (detik saja, bukan menit)."""
    base = random.uniform(a, b)
    if random.random() < long_chance:
        base += random.uniform(2.0, 5.0)
    time.sleep(base)


def jittered(value: float, factor: float = 0.35) -> float:
    lo = value * (1.0 - factor)
    hi = value * (1.0 + factor)
    return max(0.1, random.uniform(lo, hi))


def shuffled(seq):
    arr = list(seq)
    random.shuffle(arr)
    return arr


def rand_initial_jitter(max_seconds: int = 110) -> float:
    """Jitter awal untuk auto mode (anti cron exact menit 05)."""
    sec = random.uniform(2.0, float(max_seconds))
    return sec


def rand_headers(boundary: str = None, token: str = None):
    """Build realistic multipart headers dict."""
    b = boundary or rand_boundary()
    headers = {
        "Content-Type": f"multipart/form-data; boundary={b}",
        "Accept": "application/json",
        "User-Agent": rand_user_agent(),
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers, b
