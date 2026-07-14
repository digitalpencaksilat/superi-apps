#!/usr/bin/env python3
"""Tests for superi_humanizer anti-robot layer."""

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
WIB = timezone(timedelta(hours=7))


def parse_wib(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).astimezone(WIB)


def test_rand_durasi_never_forbidden():
    vals = [hu.rand_durasi() for _ in range(500)]
    assert all(v not in {0.1, 0.001, 0.0} for v in vals)
    assert all(2.0 <= v <= 7.0 for v in vals)
    for v in vals:
        s = str(v)
        assert "." in s and len(s.split(".")[-1]) == 2, f"not 2 decimals {v}: {s}"


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


def test_rand_foto_pair_delta_12_85():
    for _ in range(100):
        t1, t2 = hu.rand_foto_pair("2026-06-27", 18)
        d1 = parse_wib(t1)
        d2 = parse_wib(t2)
        delta = (d2 - d1).total_seconds()
        assert 10 <= delta <= 90, f"delta {delta} t1={t1} t2={t2}"
        assert d1.hour == d2.hour == 18


def test_rand_boundary_unique():
    b1 = {hu.rand_boundary() for _ in range(50)}
    assert len(b1) > 40
    assert all(b.startswith("----FormBoundary") for b in b1)


def test_rand_filename_correlates_with_datetime():
    ts = "2026-06-27T18:32:15.456Z"
    names = [hu.rand_filename(ts, idx=i) for i in range(20)]
    for n in names:
        assert FILENAME_RE.match(n), n
        assert "foto.jpg" != n.lower()
        assert "hv.jpg" != n.lower()
        assert "mv.jpg" != n.lower()
    assert len(set(names)) >= 5


def test_rand_filename_no_static_foto_jpg():
    ts = hu.rand_foto_datetime("2026-06-27", 10)
    for _ in range(100):
        fn = hu.rand_filename(ts)
        assert fn.lower() not in {"foto.jpg", "hv.jpg", "mv.jpg", "foto1.jpg", "foto2.jpg"}


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
    dummies = [b for b in [b"\xff\xd8\xff\xe0\x00\x10JFIF"] if len(b) == 172]
    for _ in range(20):
        j = hu.rand_jpeg_bytes()
        assert len(j) != 172, "still returning old dummy size"
