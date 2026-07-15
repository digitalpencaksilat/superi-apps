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

_JPEG_CACHE = {}
_WIB = timezone(timedelta(hours=7))
_UTC = timezone.utc

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
# JPEG HANDLING - ANTI BYPASS: 720x720 SQUARE MIRIP APP ASLI
# Audit server: stored 720x720 (95%) / 720x960 (5%), baseline JPEG,
# no progressive, no COM, no EXIF, 14-51KB avg 27KB.
# Pool: ambil dari photo/pool/ -> crop center square 720x720
# ============================================================

# Target dimensi final (sesuai foto asli dari aplikasi)
# Server menyimpan 720x720 dominan, jadi kita upload juga 720x720 agar tidak terdeteksi
# sebagai bypass via log dimensi original.
_TARGET_DIMS = [
    # (W, H, weight) — 85% square 720x720, 15% variasi realistic
    (720, 720, 60),   # dominan, match server stored
    (720, 960, 8),    # portrait 3:4 — 5% terjadi di server (outlier asli)
    (960, 720, 4),    # landscape
    (1080, 1080, 12), # square HD — kamera HP crop
    (1080, 1440, 6),  # portrait 3:4 HD
    (1440, 1080, 4),  # landscape 4:3
    (1440, 1440, 6),  # square bigger
]

def _pick_target_dim():
    """Pick (W,H) weighted sesuai audit server — dominan 720x720."""
    choices = []
    for w, h, wt in _TARGET_DIMS:
        choices.extend([(w, h)] * wt)
    return random.choice(choices)

def _get_target_dim_720():
    """Default return 720x720 — untuk pool crop agar seragam dengan app asli."""
    # 85% chance 720x720, 15% chance 720x960 (sesuai outlier server)
    if random.random() < 0.85:
        return (720, 720)
    else:
        return (720, 960) if random.random() < 0.7 else (1080, 1080)


def _get_photo_pool():
    """Pool of real operator sample photos in photo/pool/ - supports jpg/jpeg/png."""
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


def _reencode_pool_image(path: str, target_w: int = None, target_h: int = None):
    """
    Re-encode pool image ke 720x720 square mirip app asli.
    
    Proses:
    1. Open + convert RGB
    2. Crop center square (anti bypass: dimensi jadi square 720x720 seperti app)
    3. Resize ke target_w x target_h (default 720x720, weighted sesuai audit)
    4. Variasi pixel halus (1-3 pixel tweak) — anti hash duplicate
    5. Save baseline JPEG (progressive=False, no EXIF, no COM)
    
    Returns: JPEG bytes atau None
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

        # === ANTI BYPASS: CROP SQUARE + RESIZE KE 720x720 ===
        if target_w is None or target_h is None:
            target_w, target_h = _get_target_dim_720()

        # Jika target square 720x720, crop center square dulu biar tidak stretch
        if target_w == target_h:
            # Crop center square dari original (misal 1200x1600 -> 1200x1200)
            im = _crop_center_square(im)

        # Resize ke target (720x720)
        if im.size != (target_w, target_h):
            im = im.resize((target_w, target_h), Image.LANCZOS)

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

        # Jika terlalu besar (>80KB) untuk 720x720, turunkan quality sedikit
        if len(data) > 80000 and target_w <= 720:
            out = io.BytesIO()
            im.save(out, format='JPEG', quality=max(78, q - 12), optimize=True, exif=b'', progressive=False)
            data = out.getvalue()

        return data

    except Exception as e:
        # Fallback: coba baca raw dan re-encode minimal
        try:
            from PIL import Image
            with open(path, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\x89PNG'):
                im = Image.open(io.BytesIO(raw))
                if im.mode != 'RGB':
                    im = im.convert('RGB')
                # Crop square + resize 720x720
                im = _crop_center_square(im)
                tw, th = _get_target_dim_720()
                if im.size != (tw, th):
                    im = im.resize((tw, th), Image.LANCZOS)
                out = io.BytesIO()
                im.save(out, format='JPEG', quality=random.randint(82, 92), optimize=True, exif=b'', progressive=False)
                return out.getvalue()
            # Jika JPEG tapi gagal diproses, coba tetap crop-resize paksa
            if raw.startswith(b'\xff\xd8'):
                im = Image.open(io.BytesIO(raw))
                if im.mode != 'RGB':
                    im = im.convert('RGB')
                im = _crop_center_square(im)
                tw, th = _get_target_dim_720()
                im = im.resize((tw, th), Image.LANCZOS)
                out = io.BytesIO()
                im.save(out, format='JPEG', quality=random.randint(82, 92), optimize=True, exif=b'', progressive=False)
                return out.getvalue()
        except Exception:
            pass
        return None


def _rand_jpeg_via_pil(width=None, height=None, quality=None):
    """
    Fallback generate synthetic meter foto jika pool kosong.
    Sekarang generate 720x720 square baseline (match server).
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    # Default 720x720 square — anti bypass detection
    if width is None or height is None:
        tw, th = _get_target_dim_720()
        width, height = tw, th
    if quality is None:
        quality = random.randint(82, 93)

    # Jika masih ada request dimensions lama (misal 800x600), override ke square
    # kecuali sudah square realistic
    if width != height:
        # Force square 720x720 untuk konsistensi dengan app asli
        if random.random() < 0.85:
            width = height = 720
        else:
            # Portrait 720x960 — sesuai outlier real di server
            width, height = 720, 960

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


def rand_jpeg_bytes(target_w: int = None, target_h: int = None):
    """
    Return valid JPEG bytes 720x720 square mirip app asli.
    
    - Ambil dari pool (photo/pool/) -> crop center square -> resize 720x720
    - Fallback synthetic 720x720 jika pool kosong
    - Baseline JPEG, no progressive, no COM, no EXIF
    - Size 15-60KB (match audit server 14-51KB avg 27KB)
    
    Args:
        target_w, target_h: opsional target dimensi (default 720x720)
    
    Returns:
        bytes JPEG valid
    """
    if target_w is None or target_h is None:
        target_w, target_h = _get_target_dim_720()

    pool = _get_photo_pool()
    if pool:
        # Coba 5 kali dari pool
        for _ in range(5):
            p = random.choice(pool)
            enc = _reencode_pool_image(p, target_w, target_h)
            if enc and enc.startswith(b"\xff\xd8") and len(enc) >= 8000:
                # Validasi dimensi
                try:
                    from PIL import Image
                    im = Image.open(io.BytesIO(enc))
                    w, h = im.size
                    # Harus 720x720 atau 720x960 atau 1080x1080 (dalam range TARGET_DIMS)
                    if (w, h) in [(720, 720), (720, 960), (960, 720), (1080, 1080), (1080, 1440), (1440, 1080), (1440, 1440)]:
                        if 10000 <= len(enc) <= 100000:
                            return enc
                    # Tetap return jika valid JPEG meski dimensi tidak exact (fallback toleran)
                    if len(enc) >= 10000:
                        return enc
                except:
                    # Jika PIL gagal cek, tetap return jika size ok
                    if len(enc) >= 8000:
                        return enc

        # Fallback: baca raw dan crop paksa ke 720x720
        try:
            from PIL import Image
            raw_path = random.choice(pool)
            with open(raw_path, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\xff\xd8') and len(raw) >= 5000:
                im = Image.open(io.BytesIO(raw))
                if im.mode != 'RGB':
                    im = im.convert('RGB')
                im = _crop_center_square(im)
                im = im.resize((target_w, target_h), Image.LANCZOS)
                out = io.BytesIO()
                im.save(out, format='JPEG', quality=random.randint(82, 93), optimize=True, exif=b'', progressive=False)
                data = out.getvalue()
                if len(data) >= 10000:
                    return data
        except Exception:
            pass

    # Fallback synthetic 720x720
    for _ in range(5):
        gen = _rand_jpeg_via_pil(target_w, target_h)
        if gen and gen.startswith(b"\xff\xd8") and len(gen) >= 8000:
            return gen

    # Last fallback: minimal 720x720 valid JPEG (1x1 dummy di-expand ke 720x720 gray)
    # Ini seharusnya tidak terjadi jika pool ada, tapi safety
    try:
        from PIL import Image
        img = Image.new('RGB', (target_w, target_h), (random.randint(30, 60), random.randint(30, 60), random.randint(35, 65)))
        out = io.BytesIO()
        img.save(out, format='JPEG', quality=85, optimize=True, exif=b'', progressive=False)
        return out.getvalue()
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


def rand_jpeg_pair(target_w: int = None, target_h: int = None):
    """Two different valid JPEGs 720x720 untuk tegangan (HV + MV)."""
    if target_w is None or target_h is None:
        target_w, target_h = _get_target_dim_720()

    for _ in range(10):
        j1 = rand_jpeg_bytes(target_w, target_h)
        j2 = rand_jpeg_bytes(target_w, target_h)
        if j1 != j2 and hashlib.sha256(j1).hexdigest() != hashlib.sha256(j2).hexdigest():
            return j1, j2
    # fallback pair dengan variasi dimensi ringan jika tetap sama
    return rand_jpeg_bytes(target_w, target_h), rand_jpeg_bytes(target_w, target_h)


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
# FOTO DATETIME - KORELASI DENGAN DURASI
# ============================================================

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


def rand_foto_datetime(date_str: str, periode: int, durasi_min: float = None) -> str:
    """Foto datetime realistis, korelasi dengan durasi jika disediakan.

    - Jika date_str == hari ini DAN durasi_min ada:
        foto.date = now - (durasi*60 detik + buffer 0.5-2.5 detik)
        -> konsisten: durasi 4 detik berarti foto diambil 4 detik lalu
    - Jika date_str == hari ini tanpa durasi:
        foto = now - random(2, 12) detik (cepat)
    - Jika date_str historis:
        random menit/detik dalam jam periode
    Format: YYYY-MM-DDTHH:MM:SS.mmmZ
    """
    safe_periode = max(0, min(23, int(periode)))
    now = datetime.now(_WIB)
    today_str = now.strftime("%Y-%m-%d")

    # Hitung durasi detik untuk korelasi
    durasi_sec = None
    if durasi_min is not None:
        try:
            durasi_sec = float(durasi_min) * 60.0
        except:
            durasi_sec = None

    if date_str == today_str:
        if durasi_sec is not None and durasi_sec > 0:
            # Korelasi: foto diambil durasi + buffer lalu
            buffer = random.uniform(0.5, 2.8)
            total_offset = durasi_sec + buffer
            # Clamp: jangan lebih dari 90 detik lalu untuk hari ini
            total_offset = min(total_offset, 85.0)
            capture = now - timedelta(seconds=total_offset, milliseconds=random.randint(50, 900))
        else:
            # Fallback minimal: 2-12 detik lalu untuk P>=now, atau random dalam jam untuk P<now
            if safe_periode >= now.hour:
                capture = now - timedelta(seconds=random.uniform(2.0, 12.0), milliseconds=random.randint(50, 900))
            else:
                capture = _local_period_datetime(date_str, safe_periode)
    else:
        capture = _local_period_datetime(date_str, safe_periode)

    return _format_utc(capture)


def rand_foto_pair(date_str: str, periode: int, durasi_min: float = None):
    """Dua timestamp HV/MV, korelasi dengan durasi.

    - Jika durasi ada: first = now - durasi - buffer, second = first + 12-40 detik (HV->MV)
    - Selisih HV-MV 12-40 detik realistis (manual)
    - Keduanya dekat now untuk hari ini (max 45 detik lalu)
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

    if date_str == today_str:
        if durasi_sec is not None and durasi_sec > 0:
            buffer = random.uniform(0.8, 3.0)
            total_offset = durasi_sec + buffer
            total_offset = min(total_offset, 90.0)
            first = now - timedelta(seconds=total_offset, milliseconds=random.randint(50, 900))
        else:
            # fallback: 8-20 detik lalu
            first = now - timedelta(seconds=random.uniform(8.0, 22.0), milliseconds=random.randint(50, 900))

        # Jika periode sudah lewat (safe_periode < now.hour), pakai jam tersebut tapi tetap dekat
        if safe_periode < now.hour:
            # 70% chance pakai jam historis, 30% pakai now-based (biar variasi)
            if random.random() < 0.7:
                first = _local_period_datetime(date_str, safe_periode)

        delta = random.randint(12, 42)
        second = first + timedelta(seconds=delta, milliseconds=random.randint(80, 850))
        if second >= now:
            second = now - timedelta(seconds=random.uniform(2.0, 8.0))
            first = second - timedelta(seconds=delta)
    else:
        first = _local_period_datetime(date_str, safe_periode)
        delta = random.randint(12, 55)
        second = first + timedelta(seconds=delta, milliseconds=random.randint(80, 850))

    return _format_utc(first), _format_utc(second)


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
