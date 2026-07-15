#!/usr/bin/env python3
"""Tests for superi_humanizer anti-robot layer.
Updated for durasi unit = menit (server stores minutes, 0.03-0.12 menit = 2-7 detik).
Filename pattern = fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg (manual).
"""

import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import superi_humanizer as hu

FOTO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
FILENAME_RE = re.compile(r"^.+\.jpg$", re.IGNORECASE)
MANUAL_FILENAME_RE = re.compile(r"^foto(BebanPenyulang|BebanTrafo|HV|MV)_\d{4}-\d{2}-\d{2}_[0-9a-f]{12,16}\.jpg$")
WIB = timezone(timedelta(hours=7))


def parse_wib(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).astimezone(WIB)


def test_rand_durasi_never_forbidden():
    vals = [hu.rand_durasi() for _ in range(500)]
    assert all(v != 0.0 for v in vals)
    # In minutes: 2-7 detik = 0.0333 - 0.1167 menit
    assert all(0.02 <= v <= 0.20 for v in vals), f"durasi out of minutes range: min={min(vals)} max={max(vals)}"
    # In seconds: 2-7 detik
    sec_vals = [v * 60.0 for v in vals]
    assert all(1.5 <= s <= 8.5 for s in sec_vals), f"durasi detik out of range: {min(sec_vals)}-{max(sec_vals)}"


def test_rand_durasi_converts_to_2_7_seconds():
    for _ in range(200):
        v = hu.rand_durasi()
        sec = v * 60.0
        assert 2.0 <= sec <= 7.5, f"sec {sec} from menit {v}"


def test_rand_durasi_tegangan_8_40_seconds():
    vals = [hu.rand_durasi_tegangan() for _ in range(200)]
    for v in vals:
        sec = v * 60.0
        assert 7.0 <= sec <= 65.0, f"tegangan sec {sec} out of 8-40 expected, menit {v}"


def test_rand_durasi_for_type():
    assert 0.02 <= hu.rand_durasi_for_type("beban-penyulang") <= 0.20
    assert 0.02 <= hu.rand_durasi_for_type("beban-trafo") <= 0.20
    teg = hu.rand_durasi_for_type("tegangan-trafo")
    # tegangan lebih lama
    assert 0.10 <= teg <= 1.1


def test_rand_foto_datetime_not_midnight_zero():
    for per in [0, 8, 18, 23]:
        for _ in range(30):
            ts = hu.rand_foto_datetime("2026-06-27", per)
            assert FOTO_RE.match(ts), f"bad format {ts}"
            assert not ts.endswith("00:00.000Z"), f"robotic exact hour {ts}"
            dt = parse_wib(ts)
            assert dt.hour == per
            assert 0 <= dt.minute <= 59
            assert dt.second >= 1


def test_rand_foto_datetime_with_durasi_correlated():
    """Hari ini, foto.date = now - (durasi + buffer), max 90 detik lalu."""
    from datetime import timezone as tz
    today_str = datetime.now(WIB).strftime("%Y-%m-%d")
    for _ in range(30):
        dur_min = hu.rand_durasi()
        ts = hu.rand_foto_datetime(today_str, datetime.now(WIB).hour, dur_min)
        dt = parse_wib(ts)
        now = datetime.now(WIB)
        diff = (now - dt).total_seconds()
        # harus dekat: durasi*60 + buffer 0.5-5 detik, max 90 detik
        assert 0.5 <= diff <= 92, f"diff {diff}s too large/small dur_min={dur_min} ts={ts}"


def test_rand_foto_pair_delta_12_85():
    for _ in range(100):
        t1, t2 = hu.rand_foto_pair("2026-06-27", 18)
        d1 = parse_wib(t1)
        d2 = parse_wib(t2)
        delta = (d2 - d1).total_seconds()
        assert 10 <= delta <= 90, f"delta {delta} t1={t1} t2={t2}"
        assert d1.hour == d2.hour == 18


def test_rand_foto_pair_with_durasi():
    today_str = datetime.now(WIB).strftime("%Y-%m-%d")
    for _ in range(50):
        dur = hu.rand_durasi_tegangan()
        t1, t2 = hu.rand_foto_pair(today_str, 16, dur)
        d1 = parse_wib(t1)
        d2 = parse_wib(t2)
        delta = (d2 - d1).total_seconds()
        assert 10 <= delta <= 60, f"delta {delta} for tegangan"


def test_rand_boundary_unique():
    b1 = {hu.rand_boundary() for _ in range(50)}
    assert len(b1) > 40
    assert all(b.startswith("----FormBoundary") for b in b1)


def test_rand_filename_manual_pattern():
    ts = "2026-07-15T09:28:47.879Z"
    # beban-penyulang
    for _ in range(20):
        fn = hu.rand_filename(ts, data_type="beban-penyulang")
        assert MANUAL_FILENAME_RE.match(fn), f"not manual pattern {fn}"
        assert fn.startswith("fotoBebanPenyulang_")
    # beban-trafo
    for _ in range(10):
        fn = hu.rand_filename(ts, data_type="beban-trafo")
        assert fn.startswith("fotoBebanTrafo_")
        assert MANUAL_FILENAME_RE.match(fn)
    # tegangan
    for _ in range(10):
        fn_hv = hu.rand_filename(ts, data_type="tegangan-trafo", subtype="HV")
        fn_mv = hu.rand_filename(ts, data_type="tegangan-trafo", subtype="MV")
        assert fn_hv.startswith("fotoHV_")
        assert fn_mv.startswith("fotoMV_")
        assert MANUAL_FILENAME_RE.match(fn_hv)
        assert MANUAL_FILENAME_RE.match(fn_mv)


def test_rand_filename_correlates_with_datetime():
    ts = "2026-06-27T18:32:15.456Z"
    names = [hu.rand_filename(ts, idx=i, data_type="beban-penyulang") for i in range(20)]
    for n in names:
        assert FILENAME_RE.match(n), n
        assert "foto.jpg" != n.lower()
        assert "hv.jpg" != n.lower()
        assert "mv.jpg" != n.lower()
        assert "IMG_" not in n, f"still IMG pattern {n} not allowed, must fotoBeban*"
        assert "GI MANGGARAI" not in n
    assert len(set(names)) >= 5


def test_rand_filename_no_static_foto_jpg():
    ts = hu.rand_foto_datetime("2026-06-27", 10)
    for _ in range(100):
        fn = hu.rand_filename(ts)
        assert fn.lower() not in {"foto.jpg", "hv.jpg", "mv.jpg", "foto1.jpg", "foto2.jpg"}
        assert not fn.lower().startswith("img_")


def test_rand_location_realistic():
    for _ in range(50):
        addr, lat, lon = hu.rand_location()
        assert isinstance(addr, str) and len(addr) > 10
        assert "GI MANGGARAI" != addr, f"address still static GI MANGGARAI: {addr}"
        # lat/lon sekitar GI Manggarai
        assert -6.22 <= lat <= -6.20, f"lat out of range {lat}"
        assert 106.84 <= lon <= 106.86, f"lon out of range {lon}"
        # address harus salah satu dari 13 alamat real atau Lat/Long format
        assert ("Manggarai" in addr or "Lat=" in addr), f"unexpected addr {addr}"


def test_rand_foto_dict():
    fd = hu.rand_foto_dict(data_type="beban-penyulang", date_str="2026-07-15", periode=16, durasi_min=0.07)
    assert FOTO_RE.match(fd["date"])
    assert fd["address"] != "GI MANGGARAI"
    assert -6.22 <= fd["latitude"] <= -6.20
    assert 106.84 <= fd["longitude"] <= 106.86


def test_rand_foto_pair_dicts():
    hv, mv = hu.rand_foto_pair_dicts("2026-07-15", 16, 0.3)
    assert hv["address"] != "GI MANGGARAI"
    assert mv["address"] != "GI MANGGARAI"
    assert FOTO_RE.match(hv["date"])
    assert FOTO_RE.match(mv["date"])
    # lokasi MV dekat HV (within 10m ~0.00009 degree)
    assert abs(hv["latitude"] - mv["latitude"]) < 0.0002
    assert abs(hv["longitude"] - mv["longitude"]) < 0.0002


def test_shuffled_changes_order_sometimes():
    seq = list(range(20))
    diff_seen = False
    for _ in range(30):
        sh = hu.shuffled(seq)
        assert sorted(sh) == seq
        if sh != seq:
            diff_seen = True
            break
    assert diff_seen, "shuffled never changed order"


def test_jittered_varies():
    vals = {round(hu.jittered(10.0), 3) for _ in range(50)}
    assert len(vals) > 10


def test_user_agent_not_python():
    for _ in range(20):
        ua = hu.rand_user_agent()
        assert "python" not in ua.lower()
        assert "urllib" not in ua.lower()
        assert "okhttp" in ua.lower() or "Dalvik" in ua


def test_no_00_000Z_in_batch():
    seen_exact = 0
    for _ in range(200):
        ts = hu.rand_foto_datetime("2026-06-27", 9)
        if ts.endswith("00:00.000Z"):
            seen_exact += 1
    assert seen_exact == 0


def test_jpeg_bytes_varying_and_realistic_size():
    import hashlib
    hashes = set()
    sizes = []
    for _ in range(20):
        j = hu.rand_jpeg_bytes()
        assert len(j) > 1000, f"too small like dummy 172b: {len(j)}"
        assert j[:2] == b"\xff\xd8", "not JPEG"
        assert j[-2:] == b"\xff\xd9" or b"\xff\xd9" in j[-10:], "no JPEG footer"
        hashes.add(hashlib.sha256(j).hexdigest())
        sizes.append(len(j))
    assert len(hashes) >= 15, f"hashes not varying: {len(hashes)}"
    assert max(sizes) - min(sizes) > 500, "size not varying"
    assert max(sizes) < 300_000, "too large"


def test_jpeg_pair_different():
    import hashlib
    for _ in range(10):
        j1, j2 = hu.rand_jpeg_pair()
        assert len(j1) > 1000 and len(j2) > 1000
        assert hashlib.sha256(j1).hexdigest() != hashlib.sha256(j2).hexdigest()


def test_jpeg_pool_optional():
    import os
    pool_dir = os.path.join(ROOT, "photo", "pool")
    if os.path.isdir(pool_dir):
        j = hu.rand_jpeg_bytes()
        assert len(j) > 1000
    else:
        j = hu.rand_jpeg_bytes()
        assert len(j) > 0


def test_no_dummy_172_bytes():
    for _ in range(20):
        j = hu.rand_jpeg_bytes()
        assert len(j) != 172, "still returning old dummy size"
