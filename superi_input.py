#!/usr/bin/env python3
"""
SUPER-I APP - Data Input Script (PRODUCTION READY)
==================================================
Script untuk input data Beban Penyulang, Beban Trafo, dan Tegangan Trafo
ke SUPER-I APP tanpa menggunakan aplikasi mobile.

TERBUKTI BERHASIL dengan akun aktif (sudah absen masuk).

USAGE:
  # Input Beban Penyulang
  python3 superi_input.py --nip <NIP> --pass <PASSWORD> \
    --type beban-penyulang --gi 222 --id 2660 --periode 0 --value 150

  # Input Beban Trafo  
  python3 superi_input.py --nip <NIP> --pass <PASSWORD> \
    --type beban-trafo --gi 222 --id 22241 --periode 0 --value 400

  # Lihat data
  python3 superi_input.py --nip <NIP> --pass <PASSWORD> \
    --list-penyulang --gi 222

  # Hapus entry
  python3 superi_input.py --nip <NIP> --pass <PASSWORD> \
    --type beban-penyulang --delete 2848443

REQUIREMENTS: Python 3.8+ (stdlib only)
"""

import urllib.request
import urllib.error
import json
import argparse
import sys
import os
from datetime import datetime
from typing import Optional, Dict, List, Any

# ============================================================
# CONFIG
# ============================================================
BASE_URL = "https://super-i-app.plnes.co.id"
API_BASE = f"{BASE_URL}/api"
AUTH_URL = f"{API_BASE}/auth/login-mobile"
BOUNDARY = "----FormBoundary7MA4YWxkTrZu0gW"

try:
    import superi_humanizer as hu
except Exception:
    hu = None


def _h_durasi():
    return hu.rand_durasi() if hu else 0.1


def _h_foto_date(date_str, periode):
    if hu:
        return hu.rand_foto_datetime(date_str, periode)
    return f"{date_str}T{periode:02d}:00:00.000Z"


def _h_foto_pair(date_str, periode):
    if hu:
        return hu.rand_foto_pair(date_str, periode)
    ts = f"{date_str}T{periode:02d}:00:00.000Z"
    return ts, ts


def _h_boundary():
    return hu.rand_boundary() if hu else BOUNDARY


def _h_filename(foto_ts, idx=0):
    return hu.rand_filename(foto_ts, idx=idx) if hu else f"foto{idx + 1}.jpg"


def _h_user_agent():
    return hu.rand_user_agent() if hu else "okhttp/4.12.0"


def _get_jpeg_bytes(single=True):
    if hu:
        if single:
            return hu.rand_jpeg_bytes()
        else:
            a, b = hu.rand_jpeg_pair()
            return a, b
    return DUMMY_JPEG if single else (DUMMY_JPEG, DUMMY_JPEG)


# 1x1 pixel JPEG minimal (fallback legacy, real now from hu.rand_jpeg_bytes)
DUMMY_JPEG = bytes([
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
    0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A,
    0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03, 0x03, 0x02,
    0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D, 0x01, 0x02,
    0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13, 0x51,
    0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08, 0x23, 0x42,
    0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72, 0x82, 0x09,
    0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A,
    0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47,
    0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x63,
    0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75, 0x76, 0x77,
    0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x92,
    0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5,
    0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8,
    0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xD2,
    0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2, 0xE3, 0xE4,
    0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6,
    0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00,
    0x3F, 0x00, 0x7B, 0x94, 0x11, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xD9
])

ENDPOINTS = {
    "beban-penyulang": {
        "input": "/gama/opgi-20kv/operator-gi/beban-penyulang/input",
        "list": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "delete": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "id_field": "penyulangId",
        "value_field": "beban",
        "label": "Beban Penyulang",
    },
    "beban-trafo": {
        "input": "/gama/opgi-20kv/operator-gi/beban-trafo/input",
        "list": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "delete": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "id_field": "trafoId",
        "value_field": "beban",
        "label": "Beban Trafo",
    },
    "tegangan-trafo": {
        "input": "/gama/opgi-20kv/operator-gi/tegangan-trafo/input",
        "list": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
        "delete": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
        "id_field": "trafoId",
        "value_field": "mv",
        "value_field_2": "hv",
        "label": "Tegangan Trafo",
        "file_field": "files",  # plural - butuh 2 foto!
    },
}

# ============================================================
# HELPERS
# ============================================================

def login(nip: str, password: str) -> str:
    """Login dan return access_token."""
    req = urllib.request.Request(AUTH_URL,
        data=json.dumps({"nip": nip, "password": password}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    if not data.get("success"):
        raise Exception(f"Login gagal: {data.get('message')}")
    return data["data"]["access_token"]


def api_request(method, path, token, body=None, params=None):
    """HTTP request ke API."""
    url = f"{API_BASE}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        if isinstance(body, bytes):
            data = body
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def build_multipart(data_dict: dict, file_bytes: bytes = None) -> bytes:
    bd = _h_boundary()
    data_json = json.dumps(data_dict)
    foto_ts = data_dict.get("foto", {}).get("date") or data_dict.get("fotoHV", {}).get("date")
    fname = _h_filename(foto_ts, idx=0)
    parts = [
        f'--{bd}\r\nContent-Disposition: form-data; name="data"\r\n\r\n{data_json}\r\n'.encode(),
    ]
    if file_bytes:
        parts.append(
            f'--{bd}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
        )
        parts.append(file_bytes)
        parts.append(f'\r\n--{bd}--\r\n'.encode())
    else:
        parts.append(f'--{bd}--\r\n'.encode())
    return b''.join(parts)


# ============================================================
# API OPERATIONS
# ============================================================

def submit_beban(token: str, data_type: str, gi_id: int, item_id: int,
                 periode: int, value: float, date_str: str = None,
                 tz: str = "Asia/Jakarta", file_bytes: bytes = None,
                 value_2: float = None) -> bool:
    """Submit data. Return True jika berhasil."""
    ep = ENDPOINTS[data_type]
    
    if date_str is None:
        dt = datetime.now()
    else:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    
    if file_bytes is None:
        file_bytes = DUMMY_JPEG
    
    date_str_full = f"{dt.year}-{dt.month:02d}-{dt.day:02d}"
    ts_beban = _h_foto_date(date_str_full, periode)
    ts1, ts2 = _h_foto_pair(date_str_full, periode)

    data_dict = {
        ep["id_field"]: item_id,
        "timezone": tz,
        "periode": periode,
        "tanggal": dt.day,
        "bulan": dt.month - 1,
        "tahun": dt.year,
        "durasi": _h_durasi(),
        ep["value_field"]: value,
        "foto": {
            "date": ts_beban,
            "address": "GI MANGGARAI",
            "latitude": -6.213,
            "longitude": 106.846,
        }
    }

    if data_type == "tegangan-trafo":
        data_dict["hv"] = value_2 or 150
        del data_dict["foto"]
        data_dict["fotoHV"] = {
            "date": ts1,
            "address": "GI MANGGARAI",
            "latitude": -6.213,
            "longitude": 106.846,
        }
        data_dict["fotoMV"] = {
            "date": ts2,
            "address": "GI MANGGARAI",
            "latitude": -6.213,
            "longitude": 106.846,
        }

    file_field = ep.get("file_field", "file")
    inner = json.dumps(data_dict)
    bd = _h_boundary()

    if hu:
        if data_type == "tegangan-trafo":
            jb1, jb2 = hu.rand_jpeg_pair()
            jpeg_pool = [jb1, jb2]
        else:
            jpeg_pool = [hu.rand_jpeg_bytes()]
    else:
        jpeg_pool = [file_bytes]

    body_parts = [
        f'--{bd}\r\nContent-Disposition: form-data; name="data"\r\n\r\n{inner}\r\n'.encode(),
    ]
    if data_type == "tegangan-trafo":
        fn1 = _h_filename(ts1, idx=0)
        fn2 = _h_filename(ts2, idx=1)
        body_parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{fn1}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
        body_parts.append(jpeg_pool[0])
        body_parts.append(f'\r\n--{bd}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{fn2}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
        body_parts.append(jpeg_pool[1])
        body_parts.append(f'\r\n--{bd}--\r\n'.encode())
    else:
        fn = _h_filename(ts_beban, idx=0)
        body_parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{fn}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
        body_parts.append(jpeg_pool[0])
        body_parts.append(f'\r\n--{bd}--\r\n'.encode())

    body = b''.join(body_parts)

    req = urllib.request.Request(f"{API_BASE}{ep['input']}", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={bd}", "Authorization": f"Bearer {token}",
                 "Accept": "application/json", "User-Agent": _h_user_agent()},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            status = resp.status
    except urllib.error.HTTPError as e:
        result = json.loads(e.read())
        status = e.code
    
    msg = result.get("message", "")
    success = result.get("success", False)
    
    if success:
        data = result.get("data", {})
        nama = data.get("penyulang", data.get("trafo", {})).get("nama", "?")
        if data_type == "tegangan-trafo":
            print(f"  ✓ BERHASIL! ID: {data.get('id')} | {nama} | P{periode} | HV={data.get('hv')}kV MV={data.get('mv')}kV")
        else:
            print(f"  ✓ BERHASIL! ID: {data.get('id')} | {nama} | Periode {periode} | {value}A")
        return True
    elif "sudah terinput" in msg.lower():
        print(f"  ⚠ Data periode {periode} sudah ada (duplicate)")
        return False
    elif "belum melakukan absen" in msg.lower():
        print(f"  ✗ GAGAL: Belum absen masuk!")
        return False
    elif "dimulai pada jam" in msg.lower():
        print(f"  ⚠ {msg}")
        return False
    else:
        print(f"  ✗ [{status}] {msg}")
        return False


def list_data(token: str, data_type: str, gi_id: int, date_str: str = None):
    """Tampilkan daftar penyulang/trafo dan ringkasan data."""
    ep = ENDPOINTS[data_type]
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    status, data = api_request("GET", ep["list"], token,
                               params={"garduIndukId": gi_id, "date": date_str})
    if status != 200:
        print(f"Error: {data.get('message', 'Unknown')}")
        return
    
    items = data["data"].get("items", [])
    total = data["data"].get("totalItems", len(items))
    print(f"\n{'='*60}")
    print(f"  {ep['label']} - GI:{gi_id} - {date_str} ({total} items)")
    print(f"{'='*60}")
    
    for item in items:
        nama = item.get("nama", "?")
        item_id = item.get("id", "?")
        gi = item.get("garduInduk", {}).get("nama", "?")
        data_entries = item.get("beban", [])
        
        if data_type == "beban-penyulang":
            i_max = item.get("iMax", "?")
            trafo = item.get("trafo", {}).get("nama", "")
            status_cb = item.get("statusCB", "")
            print(f"\n  [{item_id}] {nama} (iMax={i_max}A, CB={status_cb}, Trafo={trafo})")
        else:
            i_max = item.get("iMax", "?")
            print(f"\n  [{item_id}] {nama} (iMax={i_max}A)")
        
        if data_entries:
            values = [b["beban"] for b in data_entries]
            periods = sorted([b["periode"] for b in data_entries])
            empty = [p for p in range(24) if p not in periods]
            print(f"      Range: {min(values)}-{max(values)}A | Terisi: {len(periods)}/24")
            print(f"      Kosong: {empty[:8]}{'...' if len(empty) > 8 else ''}")


def delete_entry(token: str, data_type: str, entry_id: int):
    """Hapus entry data."""
    ep = ENDPOINTS[data_type]
    status, data = api_request("DELETE", f"{ep['delete']}/{entry_id}", token)
    if status == 200:
        print(f"  ✓ Entry {entry_id} berhasil dihapus!")
    else:
        print(f"  ✗ Gagal: {data.get('message', 'Unknown')}")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="SUPER-I APP Data Input Tool")
    parser.add_argument("--nip", default=os.environ.get("SUPERI_NIP", ""), help="NIP")
    parser.add_argument("--pass", default=os.environ.get("SUPERI_PASS", ""), dest="password", help="Password (atau set env SUPERI_PASS)")
    parser.add_argument("--type", choices=["beban-penyulang", "beban-trafo", "tegangan-trafo"], help="Tipe data")
    parser.add_argument("--gi", type=int, default=222, help="Gardu Induk ID")
    parser.add_argument("--id", type=int, dest="item_id", help="ID penyulang/trafo")
    parser.add_argument("--periode", type=int, choices=range(0, 24), help="Periode (0-23)")
    parser.add_argument("--value", type=float, help="Nilai beban (Ampere) / MV (kV)")
    parser.add_argument("--hv", type=float, help="Nilai HV (kV) - khusus tegangan-trafo")
    parser.add_argument("--date", default=None, help="Tanggal YYYY-MM-DD (default: hari ini)")
    parser.add_argument("--list-penyulang", action="store_true", help="Tampilkan daftar penyulang")
    parser.add_argument("--list-trafo", action="store_true", help="Tampilkan daftar trafo")
    parser.add_argument("--delete", type=int, dest="delete_id", help="Hapus entry")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  SUPER-I APP Data Input Tool")
    print("=" * 60)
    
    token = login(args.nip, args.password)
    print(f"  ✓ Login berhasil")
    
    if args.list_penyulang:
        list_data(token, "beban-penyulang", args.gi, args.date)
        return
    if args.list_trafo:
        list_data(token, "beban-trafo", args.gi, args.date)
        return
    if args.delete_id:
        if not args.type:
            print("  ✗ Harap tentukan --type")
            return
        delete_entry(token, args.type, args.delete_id)
        return
    if args.type:
        if not args.item_id or args.periode is None or args.value is None:
            print("  ✗ Harap tentukan --id, --periode, --value")
            return
        submit_beban(token, args.type, args.gi, args.item_id,
                     args.periode, args.value, args.date,
                     value_2=args.hv)
        return
    
    parser.print_help()

if __name__ == "__main__":
    main()
