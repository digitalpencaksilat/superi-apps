#!/usr/bin/env python3
"""
SUPER-I Humanizer — anti-robot behaviour layer (stdlib only).

Menyamarkan perilaku input agar mirip aplikasi mobile asli:
- durasi random (ganti hardcoded 0.1 / 0.001)
- foto.datetime random menit/detik/ms dalam jam periode (bukan 00:00.000Z)
- filename mirip kamera HP Android / Expo ImagePicker (korelasi dengan foto datetime)
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

_FORBIDDEN_DURASI = {0.1, 0.001, 0.0}

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PHOTO_POOL_DIR = os.path.join(_SCRIPT_DIR, "photo", "pool")

_JPEG_CACHE = {}
_WIB = timezone(timedelta(hours=7))
_UTC = timezone.utc


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
    """Insert COM segment after SOI safely to vary file without corrupting (valid JPEG)."""
    if not jpeg_data.startswith(b"\xff\xd8"):
        return jpeg_data
    comment = os.urandom(comment_len)
    seg_len = 2 + len(comment)
    com = b"\xff\xfe" + seg_len.to_bytes(2, "big") + comment
    return jpeg_data[:2] + com + jpeg_data[2:]


def _reencode_pool_image(path: str):
    """Re-encode pool image (JPG/PNG) to JPEG varying but always valid."""
    try:
        from PIL import Image
        im = Image.open(path)
        if im.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', im.size, (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255)))
            if im.mode == 'P':
                im = im.convert('RGBA')
            bg.paste(im, mask=im.split()[-1] if im.mode == 'RGBA' else None)
            im = bg
        elif im.mode != 'RGB':
            im = im.convert('RGB')

        w, h = im.size
        if w > 1920 or h > 1920:
            scale = 1920 / max(w, h)
            nw = int(w * scale)
            nh = int(h * scale)
            im = im.resize((nw, nh), Image.LANCZOS)
            w, h = nw, nh
        else:
            if random.random() < 0.4:
                nw = max(10, w + random.randint(-3, 3))
                nh = max(10, h + random.randint(-3, 3))
                if nw != w or nh != h:
                    im = im.resize((nw, nh), Image.LANCZOS)

        if random.random() < 0.7:
            px = im.load()
            for _ in range(random.randint(1, 3)):
                rx = random.randint(0, max(0, w - 1))
                ry = random.randint(0, max(0, h - 1))
                try:
                    r, g, b = px[rx, ry]
                    px[rx, ry] = (min(255, r + random.randint(1, 8)), max(0, g + random.randint(-2, 3)), max(0, b + random.randint(-2, 3)))
                except Exception:
                    pass

        out = io.BytesIO()
        q = random.randint(82, 93)
        im.save(out, format='JPEG', quality=q, optimize=True, exif=b'')
        data = out.getvalue()
        return _add_com_segment(data, random.randint(8, 40)) if random.random() < 0.5 else data
    except Exception as e:
        try:
            with open(path, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\xff\xd8'):
                return _add_com_segment(raw, random.randint(10, 60))
            if raw.startswith(b'\x89PNG'):
                from PIL import Image
                im = Image.open(io.BytesIO(raw))
                if im.mode != 'RGB':
                    im = im.convert('RGB')
                out = io.BytesIO()
                im.save(out, format='JPEG', quality=random.randint(82, 92))
                return out.getvalue()
        except Exception:
            pass
        return None


def _rand_jpeg_via_pil(width=None, height=None, quality=None):
    """Generate realistic meter panel JPEG with PIL - always valid."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    if width is None:
        width = random.choice([800, 1024, 1280, 1280, 1440])
    if height is None:
        height = random.choice([600, 768, 720, 960, 900])
    if quality is None:
        quality = random.randint(80, 92)

    base_gray = random.randint(45, 85)
    img = Image.new("RGB", (width, height), (base_gray, base_gray, base_gray + 8))
    draw = ImageDraw.Draw(img)

    for _ in range(random.randint(180, 450)):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        r = random.randint(1, 2)
        n = random.randint(-12, 18)
        c = max(0, min(255, base_gray + n))
        draw.ellipse([x, y, x + r, y + r], fill=(c, c, c))

    panel_w = random.randint(width // 2, width - 30)
    panel_h = random.randint(height // 3, height - 60)
    panel_x = random.randint(10, max(10, width - panel_w - 10))
    panel_y = random.randint(10, max(10, height - panel_h - 10))

    pc = (random.randint(185, 225), random.randint(185, 225), random.randint(175, 215))
    draw.rectangle([panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
                   fill=pc, outline=(70, 70, 70), width=2)

    disp_h = max(28, panel_h // 5)
    draw.rectangle([panel_x + 8, panel_y + 8, panel_x + panel_w - 8, panel_y + 8 + disp_h],
                   fill=(12, 18, 12), outline=(45, 45, 45))

    fake_val = random.randint(0, 500)
    unit = random.choice(["A", "A", "kV"])
    try:
        draw.text((panel_x + 14, panel_y + 12), f"{fake_val} {unit}", fill=(90, 255, 110))
    except Exception:
        pass

    for _ in range(random.randint(6, 16)):
        bx = random.randint(panel_x + 10, panel_x + panel_w - 40)
        by = random.randint(panel_y + disp_h + 20, panel_y + panel_h - 15)
        bw = random.randint(18, 50)
        bh = random.randint(10, 18)
        bc = (random.randint(40, 110), random.randint(40, 110), random.randint(40, 110))
        draw.rectangle([bx, by, bx + bw, by + bh], fill=bc, outline=(0, 0, 0))

    gx = random.randint(0, width // 3)
    gy = random.randint(0, height // 3)
    gw = random.randint(60, 180)
    gh = random.randint(30, 90)
    draw.ellipse([gx, gy, gx + gw, gy + gh], fill=(255, 255, 255))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def rand_jpeg_bytes():
    """Return valid JPEG bytes varying each call, server-readable.

    Priority:
    1. photo/pool/*.jpg exists -> re-encode via PIL to vary hash but keep valid.
    2. Generate synthetic via PIL (valid JPEG).
    3. Fallback minimal valid JPEG with COM segment varying (valid).

    All results start with FF D8 and end with FF D9, PIL can open.
    """
    pool = _get_photo_pool()
    if pool:
        for _ in range(3):
            p = random.choice(pool)
            enc = _reencode_pool_image(p)
            if enc and enc.startswith(b"\xff\xd8") and len(enc) > 800:
                return enc
        try:
            with open(random.choice(pool), "rb") as f:
                return f.read()
        except Exception:
            pass

    for _ in range(3):
        gen = _rand_jpeg_via_pil()
        if gen and gen.startswith(b"\xff\xd8") and len(gen) > 800:
            return gen

    base = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
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
    return _add_com_segment(base, random.randint(12, 80))


def rand_jpeg_pair():
    """Two different valid JPEGs for tegangan."""
    for _ in range(10):
        j1 = rand_jpeg_bytes()
        j2 = rand_jpeg_bytes()
        if j1 != j2 and hashlib.sha256(j1).hexdigest() != hashlib.sha256(j2).hexdigest():
            return j1, j2
    return rand_jpeg_bytes(), rand_jpeg_bytes()


def rand_durasi() -> float:
    """Durasi random 2.00-7.00 detik, 2 angka belakang koma (mis 2.81, 5.67)."""
    while True:
        v = round(random.uniform(2.0, 7.0), 2)
        if len(str(v).split(".")[-1]) == 1:
            v = round(v + 0.01, 2)
        if v not in _FORBIDDEN_DURASI and 2.0 <= v <= 7.0:
            return v


def rand_durasi_fast() -> float:
    """Variant burst tetap 2-5 detik biar tetap masuk akal."""
    while True:
        v = round(random.uniform(2.0, 5.0), 2)
        if v not in _FORBIDDEN_DURASI:
            return v


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


def rand_foto_datetime(date_str: str, periode: int) -> str:
    """Foto datetime realistis sesuai waktu sekarang (WIB).

    - Jika date_str == hari ini: pakai jam periode tapi menit/detik dekat waktu sekarang (now - 20..180 detik), anti future.
    - Jika date_str historis: random menit/detik dalam jam periode (lama).
    Format: YYYY-MM-DDTHH:MM:SS.mmmZ
    """
    safe_periode = max(0, min(23, int(periode)))
    now = datetime.now(_WIB)
    today_str = now.strftime("%Y-%m-%d")

    if date_str == today_str:
        if safe_periode >= now.hour:
            capture = now - timedelta(seconds=random.randint(20, 180))
        else:
            capture = _local_period_datetime(date_str, safe_periode)
    else:
        capture = _local_period_datetime(date_str, safe_periode)
    return _format_utc(capture)


def rand_foto_pair(date_str: str, periode: int):
    """Dua timestamp HV/MV, selisih 12-45 detik, keduanya dekat waktu sekarang kalau hari ini."""
    safe_periode = max(0, min(23, int(periode)))
    now = datetime.now(_WIB)
    today_str = now.strftime("%Y-%m-%d")

    if date_str == today_str:
        if safe_periode >= now.hour:
            first = now - timedelta(seconds=random.randint(60, 220))
        else:
            first = _local_period_datetime(date_str, safe_periode)
        delta = random.randint(12, 45)
        second = first + timedelta(seconds=delta)
        if second >= now:
            second = now - timedelta(seconds=random.randint(5, 15))
            first = second - timedelta(seconds=delta)
    else:
        first = _local_period_datetime(date_str, safe_periode)
        delta = random.randint(12, 85)
        second = first + timedelta(seconds=delta)
    return _format_utc(first), _format_utc(second)


def rand_boundary() -> str:
    """Boundary multipart random 16 char alnum (mirip browser/mobile)."""
    rand = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    return f"{_BASE_BOUNDARY_PREFIX}{rand}"


def rand_filename(foto_datetime: str = None, idx: int = 0) -> str:
    """Filename mirip kamera Android / Expo ImagePicker, korelasi dengan foto_datetime bila ada.

    Pola:
      50%: IMG_YYYYMMDD_HHMMSS.jpg
      20%: IMG_YYYYMMDD_HHMMSS_mmm.jpg
      15%: DCIM_<rand>.jpg / <8hex>.jpg (Expo style)
      15%: foto_HHMMSS.jpg (legacy minor)
    """
    if foto_datetime:
        try:
            dt = datetime.strptime(foto_datetime, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=_UTC).astimezone(_WIB)
            date_part = dt.strftime("%Y%m%d")
            time_part = dt.strftime("%H%M%S")
            ms_part = dt.strftime("%f")[:3]
        except ValueError:
            try:
                dt = datetime.strptime(foto_datetime, "%Y-%m-%dT%H:%M:%S.%f")
                date_part = dt.strftime("%Y%m%d")
                time_part = dt.strftime("%H%M%S")
                ms_part = dt.strftime("%f")[:3]
            except Exception:
                now = datetime.now()
                date_part = now.strftime("%Y%m%d")
                time_part = now.strftime("%H%M%S")
                ms_part = f"{random.randint(0,999):03d}"
    else:
        now = datetime.now()
        date_part = now.strftime("%Y%m%d")
        time_part = now.strftime("%H%M%S")
        ms_part = f"{random.randint(0,999):03d}"

    r = random.random()
    if r < 0.5:
        if idx > 0:
            suf = f"_{idx}" if random.random() < 0.5 else f"_{int(time_part) % 1000:03d}"
            return f"IMG_{date_part}_{time_part}{suf}.jpg"
        return f"IMG_{date_part}_{time_part}.jpg"
    elif r < 0.7:
        return f"IMG_{date_part}_{time_part}_{ms_part}.jpg"
    elif r < 0.85:
        if random.random() < 0.5:
            return f"{uuid.uuid4().hex[:8]}.jpg"
        return f"{uuid.uuid4().hex[:12]}.jpg"
    else:
        return f"foto_{time_part}.jpg"


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
