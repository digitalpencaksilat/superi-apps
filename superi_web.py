#!/usr/bin/env python3
"""
SUPER-I APP - Web Dashboard
============================
Flask web app untuk monitoring dan input data SUPER-I APP.
Akses: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import urllib.request
import urllib.error
import json
import os
from datetime import datetime
from functools import wraps
import base64

app = Flask(__name__)
app.secret_key = os.urandom(32)

BASE_URL = "https://super-i-app.plnes.co.id"
API_BASE = f"{BASE_URL}/api"
BOUNDARY = "----FormBoundary7MA4YWxkTrZu0gW"

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
    0x61, 0x61, 0xFF, 0xD9
])

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def login(nip, password):
    """Login ke SUPER-I APP."""
    try:
        req = urllib.request.Request(
            f"{API_BASE}/auth/login-mobile",
            data=json.dumps({"nip": nip, "password": password}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("success"):
            return data["data"]["access_token"], data["data"]["user"]
        return None, None
    except Exception as e:
        print(f"Login error: {e}")
        return None, None

def api_get(token, path, params=None):
    """GET request ke SUPER-I API."""
    try:
        url = f"{API_BASE}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def _teg_mv_decimals(name: str) -> int:
    """Aturan pembulatan MV tegangan per trafo (parity dengan superi_app.py).
    
    - TRAFO PS 1 / TRAFO PS 2 → 0 desimal (bulat: 385, 390)
    - TRAFO 1                → 1 desimal (20.3, 20.4)
    - TRAFO 2 / 3 / lainnya  → 2 desimal (20.43)
    """
    n = (name or "").upper()
    if "PS" in n:
        return 0
    if n == "TRAFO 1":
        return 1
    return 2


def _round_mv(name: str, mv_avg: float):
    """Bulatkan MV sesuai aturan trafo. Return int kalau 0 desimal, float kalau lain."""
    decimals = _teg_mv_decimals(name)
    rounded = round(mv_avg, decimals)
    if decimals == 0:
        return int(rounded)
    return rounded


def learn_pattern(token, gi_id, data_type, item_id, days_back=7):
    """
    Belajar pola beban per periode dari data historis.
    Return dict: {periode: {avg, min, max, samples}}
    """
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    
    today = datetime.now()
    pattern = defaultdict(lambda: {"values": [], "mv_values": [], "hv_values": []})
    item_name = ""
    
    for offset in range(1, days_back + 1):
        date_str = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        result = api_get(token, paths[data_type], {"garduIndukId": gi_id, "date": date_str})
        items = result.get("data", {}).get("items", [])
        
        for it in items:
            if it["id"] != item_id:
                continue
            if not item_name:
                item_name = it.get("nama", "")
            if data_type == "tegangan-trafo":
                for e in it.get("tegangan", []):
                    pattern[e["periode"]]["mv_values"].append(e["mv"])
                    pattern[e["periode"]]["hv_values"].append(e["hv"])
            else:
                for e in it.get("beban", []):
                    pattern[e["periode"]]["values"].append(e["beban"])
    
    # Hitung statistik per periode
    result = {}
    for periode, data in pattern.items():
        if data_type == "tegangan-trafo":
            mvs = data["mv_values"]
            hvs = data["hv_values"]
            if mvs:
                mv_avg_raw = sum(mvs) / len(mvs)
                hv_avg_raw = sum(hvs) / len(hvs)
                # Aturan pembulatan
                mv_rounded = _round_mv(item_name, mv_avg_raw)
                # HV: untuk PS pakai 2 desimal (sisi 20kV), lainnya integer (~150kV)
                if "PS" in (item_name or "").upper():
                    hv_rounded = round(hv_avg_raw, 2)
                else:
                    hv_rounded = int(round(hv_avg_raw))
                result[periode] = {
                    "mv_avg": mv_rounded,
                    "mv_min": min(mvs), "mv_max": max(mvs),
                    "hv_avg": hv_rounded,
                    "hv_min": min(hvs), "hv_max": max(hvs),
                    "samples": len(mvs)
                }
        else:
            vals = data["values"]
            if vals:
                # Round ke kelipatan 5 (sesuai pola data asli yg 35, 40, 90, dll)
                avg = sum(vals)/len(vals)
                rounded = round(avg / 5) * 5
                result[periode] = {
                    "avg": rounded,
                    "raw_avg": round(avg, 1),
                    "min": min(vals), "max": max(vals),
                    "samples": len(vals)
                }
    return result

def api_post_multipart(token, path, data_dict, file_bytes, file_field, num_photos):
    """POST multipart request."""
    try:
        url = f"{API_BASE}{path}"
        inner = json.dumps(data_dict)
        body_parts = [f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="data"\r\n\r\n{inner}\r\n'.encode()]
        for i in range(num_photos):
            name = f"foto{i+1}.jpg" if num_photos > 1 else "foto.jpg"
            body_parts.append(f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{name}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
            body_parts.append(file_bytes if isinstance(file_bytes, bytes) else file_bytes)
            body_parts.append(b'\r\n')
        body_parts.append(f'--{BOUNDARY}--\r\n'.encode())
        body = b''.join(body_parts)
        
        req = urllib.request.Request(url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}", "Authorization": f"Bearer {token}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 500, {"error": str(e)}

def api_delete(token, path):
    """DELETE request."""
    try:
        url = f"{API_BASE}{path}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="DELETE")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def login_required(f):
    """Decorator untuk require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "token" not in session or "user" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def index():
    """Redirect ke dashboard."""
    if "token" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Halaman login."""
    if request.method == "POST":
        nip = request.form.get("nip", "").strip()
        password = request.form.get("password", "").strip()
        
        if not nip or not password:
            return render_template("login.html", error="NIP dan password tidak boleh kosong")
        
        token, user = login(nip, password)
        if token and user:
            session["token"] = token
            session["user"] = user
            session["nip"] = nip
            session["password"] = password
            return redirect(url_for("dashboard"))
        
        return render_template("login.html", error="Login gagal. Cek NIP/password.")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Logout."""
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard utama."""
    token = session["token"]
    user = session["user"]
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    # Fetch data beban penyulang
    penyulang_data = api_get(token, "/gama/opgi-20kv/operator-gi/beban-penyulang", 
        {"garduIndukId": 222, "date": date_str})
    
    trafo_data = api_get(token, "/gama/opgi-20kv/operator-gi/beban-trafo",
        {"garduIndukId": 222, "date": date_str})
    
    tegangan_data = api_get(token, "/gama/opgi-20kv/operator-gi/tegangan-trafo",
        {"garduIndukId": 222, "date": date_str})
    
    return render_template("dashboard.html", 
        user=user,
        date_str=date_str,
        penyulang_data=penyulang_data.get("data", {}).get("items", []),
        trafo_data=trafo_data.get("data", {}).get("items", []),
        tegangan_data=tegangan_data.get("data", {}).get("items", []))

@app.route("/api/data/input", methods=["POST"])
@login_required
def api_input():
    """API untuk input data."""
    token = session["token"]
    data = request.get_json()
    
    data_type = data.get("type")  # beban-penyulang, beban-trafo, tegangan-trafo
    item_id = data.get("item_id")
    periode = data.get("periode")
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    if data_type == "tegangan-trafo":
        mv = data.get("mv")
        hv = data.get("hv")
        endpoint = "/gama/opgi-20kv/operator-gi/tegangan-trafo/input"
        file_field = "files"
        num_photos = 2
        id_field = "trafoId"
        value_field = "mv"
    elif data_type == "beban-trafo":
        value = data.get("value")
        endpoint = "/gama/opgi-20kv/operator-gi/beban-trafo/input"
        file_field = "file"
        num_photos = 1
        id_field = "trafoId"
        value_field = "beban"
    else:  # beban-penyulang
        value = data.get("value")
        endpoint = "/gama/opgi-20kv/operator-gi/beban-penyulang/input"
        file_field = "file"
        num_photos = 1
        id_field = "penyulangId"
        value_field = "beban"
    
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    body_data = {
        id_field: item_id,
        "timezone": "Asia/Jakarta",
        "periode": periode,
        "tanggal": dt.day,
        "bulan": dt.month - 1,
        "tahun": dt.year,
        "durasi": 0.1,
        value_field: mv if data_type == "tegangan-trafo" else value,
    }
    
    if data_type == "tegangan-trafo":
        body_data["hv"] = hv
        body_data["fotoHV"] = {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
        body_data["fotoMV"] = {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
    else:
        body_data["foto"] = {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
    
    status, result = api_post_multipart(token, endpoint, body_data, DUMMY_JPEG, file_field, num_photos)
    
    if result.get("success"):
        return jsonify({"success": True, "id": result["data"].get("id"), "message": "Data berhasil disimpan"})
    
    msg = result.get("message", "Error tidak diketahui")
    if isinstance(msg, list):
        msg = ", ".join(msg)
    return jsonify({"success": False, "message": msg}), 400

@app.route("/api/data/delete", methods=["POST"])
@login_required
def api_delete_entry():
    """API untuk delete data."""
    token = session["token"]
    data = request.get_json()
    data_type = data.get("type")
    entry_id = data.get("entry_id")
    
    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    
    result = api_delete(token, f"{paths[data_type]}/{entry_id}")
    
    if result.get("success"):
        return jsonify({"success": True, "message": "Data berhasil dihapus"})
    
    return jsonify({"success": False, "message": result.get("message", "Error")}), 400

@app.route("/api/data/refresh", methods=["GET"])
@login_required
def api_refresh():
    """API untuk refresh data (AJAX)."""
    token = session["token"]
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    data_type = request.args.get("type")  # penyulang, trafo, tegangan
    
    paths = {
        "penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    
    result = api_get(token, paths[data_type], {"garduIndukId": 222, "date": date_str})
    return jsonify(result.get("data", {}).get("items", []))

@app.route("/api/data/pattern", methods=["GET"])
@login_required
def api_pattern():
    """API untuk mendapatkan pola beban dari data historis."""
    token = session["token"]
    data_type = request.args.get("type")  # beban-penyulang, beban-trafo, tegangan-trafo
    item_id = request.args.get("item_id", type=int)
    days = request.args.get("days", 7, type=int)
    
    pattern = learn_pattern(token, 222, data_type, item_id, days)
    return jsonify({"success": True, "pattern": pattern})

@app.route("/api/data/batch-input", methods=["POST"])
@login_required
def api_batch_input():
    """API untuk batch input — bisa per-item (multiple periods) atau per-periode (multiple items)."""
    token = session["token"]
    data = request.get_json()
    
    data_type = data.get("type")
    mode = data.get("mode", "per-item")  # "per-item" atau "per-periode"
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    results = []
    
    if mode == "per-periode":
        # Batch per periode: 1 jam, banyak item sekaligus
        items = data.get("items")  # list of {item_id, value, mv, hv}
        periode = data.get("periode")
        
        if not items or not isinstance(items, list):
            return jsonify({"success": False, "message": "Items harus list"}), 400
        
        for it in items:
            item_id = it.get("item_id")
            
            if data_type == "tegangan-trafo":
                endpoint = "/gama/opgi-20kv/operator-gi/tegangan-trafo/input"
                file_field = "files"
                num_photos = 2
                id_field = "trafoId"
            elif data_type == "beban-trafo":
                endpoint = "/gama/opgi-20kv/operator-gi/beban-trafo/input"
                file_field = "file"
                num_photos = 1
                id_field = "trafoId"
            else:
                endpoint = "/gama/opgi-20kv/operator-gi/beban-penyulang/input"
                file_field = "file"
                num_photos = 1
                id_field = "penyulangId"
            
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            body_data = {
                id_field: item_id,
                "timezone": "Asia/Jakarta",
                "periode": periode,
                "tanggal": dt.day,
                "bulan": dt.month - 1,
                "tahun": dt.year,
                "durasi": 0.1,
            }
            
            if data_type == "tegangan-trafo":
                body_data["mv"] = it.get("mv")
                body_data["hv"] = it.get("hv")
                body_data["fotoHV"] = {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
                body_data["fotoMV"] = {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
            else:
                body_data["beban"] = it.get("value")
                body_data["foto"] = {"date": f"{date_str}T{periode:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
            
            status, result = api_post_multipart(token, endpoint, body_data, DUMMY_JPEG, file_field, num_photos)
            if result.get("success"):
                results.append({"item_id": item_id, "success": True, "id": result["data"].get("id")})
            else:
                results.append({"item_id": item_id, "success": False, "message": result.get("message")})
    
    else:
        # Batch per item: 1 item, banyak periode sekaligus
        item_id = data.get("item_id")
        periods = data.get("periods")  # list of {periode, value, mv, hv}
        
        if not periods or not isinstance(periods, list):
            return jsonify({"success": False, "message": "Periods harus list"}), 400
        
        for p in periods:
            periodo = p.get("periode")
            
            if data_type == "tegangan-trafo":
                endpoint = "/gama/opgi-20kv/operator-gi/tegangan-trafo/input"
                file_field = "files"
                num_photos = 2
                id_field = "trafoId"
            elif data_type == "beban-trafo":
                endpoint = "/gama/opgi-20kv/operator-gi/beban-trafo/input"
                file_field = "file"
                num_photos = 1
                id_field = "trafoId"
            else:
                endpoint = "/gama/opgi-20kv/operator-gi/beban-penyulang/input"
                file_field = "file"
                num_photos = 1
                id_field = "penyulangId"
            
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            body_data = {
                id_field: item_id,
                "timezone": "Asia/Jakarta",
                "periode": periodo,
                "tanggal": dt.day,
                "bulan": dt.month - 1,
                "tahun": dt.year,
                "durasi": 0.1,
            }
            
            if data_type == "tegangan-trafo":
                body_data["mv"] = p.get("mv")
                body_data["hv"] = p.get("hv")
                body_data["fotoHV"] = {"date": f"{date_str}T{periodo:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
                body_data["fotoMV"] = {"date": f"{date_str}T{periodo:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
            else:
                body_data["beban"] = p.get("value")
                body_data["foto"] = {"date": f"{date_str}T{periodo:02d}:00:00.000Z", "address": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}
            
            status, result = api_post_multipart(token, endpoint, body_data, DUMMY_JPEG, file_field, num_photos)
            if result.get("success"):
                results.append({"periode": periodo, "success": True, "id": result["data"].get("id")})
            else:
                results.append({"periode": periodo, "success": False, "message": result.get("message")})
    
    return jsonify({"success": True, "results": results})

@app.route("/api/data/smart-suggest", methods=["GET"])
@login_required
def api_smart_suggest():
    """
    Smart suggest value berdasarkan:
    1. Rata-rata 7 hari periode sama
    2. Weekday vs Weekend pattern
    3. Trend dari jam sebelumnya hari ini
    
    Formula: 40% base + 40% weekday/weekend + 20% trend
    """
    token = session["token"]
    data_type = request.args.get("type")  # beban-penyulang, beban-trafo
    item_id = request.args.get("item_id", type=int)
    periode = request.args.get("periode", type=int)
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    prev_periode_val = request.args.get("prev_val", type=float, default=None)  # nilai P sebelumnya hari ini
    
    from collections import defaultdict
    from datetime import timedelta
    
    path = "/gama/opgi-20kv/operator-gi/beban-penyulang" if data_type == "beban-penyulang" else \
           "/gama/opgi-20kv/operator-gi/beban-trafo"
    
    today = datetime.strptime(date_str, "%Y-%m-%d")
    is_weekend = today.weekday() >= 5
    
    # Kumpulkan data 14 hari untuk pattern yang robust
    base_vals = []  # rata-rata 7 hari periode sama
    weekday_vals = []  # rata-rata weekday periode sama
    weekend_vals = []  # rata-rata weekend periode sama
    
    for offset in range(1, 15):
        d = today - timedelta(days=offset)
        date_key = d.strftime("%Y-%m-%d")
        d_is_weekend = d.weekday() >= 5
        
        result = api_get(token, path, {"garduIndukId": 222, "date": date_key})
        items = result.get("data", {}).get("items", [])
        
        for it in items:
            if it["id"] != item_id or it.get("statusCB") == "OFF":
                continue
            
            for e in it.get("beban", []):
                if e["periode"] == periode:
                    val = e["beban"]
                    if offset <= 7:
                        base_vals.append(val)
                    
                    if d_is_weekend:
                        weekend_vals.append(val)
                    else:
                        weekday_vals.append(val)
    
    # Hitung rata-rata per faktor
    base_avg = sum(base_vals) / len(base_vals) if base_vals else 0
    
    if is_weekend:
        pattern_avg = sum(weekend_vals) / len(weekend_vals) if weekend_vals else base_avg
    else:
        pattern_avg = sum(weekday_vals) / len(weekday_vals) if weekday_vals else base_avg
    
    # Faktor trend (kalau ada nilai jam sebelumnya hari ini)
    trend_factor = 1.0
    # Hitung rata-rata P-1 7 hari (parallel)
    prev_vals = []
    if prev_periode_val is not None and prev_periode_val > 0:
        from concurrent.futures import ThreadPoolExecutor
        
        def fetch_prev_day(offset):
            d = today - timedelta(days=offset)
            return api_get(token, path, {"garduIndukId": 222, "date": d.strftime("%Y-%m-%d")})
        
        with ThreadPoolExecutor(max_workers=7) as executor:
            results = list(executor.map(fetch_prev_day, range(1, 8)))
        
        for result in results:
            items = result.get("data", {}).get("items", [])
            for it in items:
                if it["id"] == item_id:
                    for e in it.get("beban", []):
                        if e["periode"] == periode - 1:
                            prev_vals.append(e["beban"])
        
        if prev_vals:
            prev_avg = sum(prev_vals) / len(prev_vals)
            if prev_avg > 0:
                trend_factor = prev_periode_val / prev_avg  # berapa kali naik dibanding biasanya
    
    # Formula: 40% base + 40% pattern + 20% trend
    smart_value = (0.4 * base_avg) + (0.4 * pattern_avg) + (0.2 * pattern_avg * trend_factor)
    
    # Round ke kelipatan 5
    suggested = round(smart_value / 5) * 5
    
    # Clamp ke range historis (min-max)
    all_historical = base_vals + weekday_vals + weekend_vals
    if all_historical:
        min_val = min(all_historical)
        max_val = max(all_historical)
        suggested = max(min_val, min(max_val, suggested))
    
    return jsonify({
        "success": True,
        "suggested": suggested,
        "breakdown": {
            "base_avg": round(base_avg, 1),
            "pattern_avg": round(pattern_avg, 1),
            "trend_factor": round(trend_factor, 2),
            "is_weekend": is_weekend,
            "samples": len(base_vals)
        }
    })

@app.route("/api/data/batch-pattern", methods=["GET"])
@login_required
def api_batch_pattern():
    """API untuk get pola semua item di satu periode (smart: weekday/weekend aware)."""
    token = session["token"]
    data_type = request.args.get("type")
    periode = request.args.get("periode", type=int)
    days = request.args.get("days", 14, type=int)  # ambil 14 hari untuk akurasi
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    from collections import defaultdict
    from datetime import timedelta
    
    paths = {
        "beban-penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
        "beban-trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
        "tegangan-trafo": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
    }
    
    today = datetime.strptime(date_str, "%Y-%m-%d")
    is_target_weekend = today.weekday() >= 5
    
    # Fetch parallel untuk semua tanggal (drastis lebih cepat dari sequential)
    from concurrent.futures import ThreadPoolExecutor
    
    def fetch_day(offset):
        d = today - timedelta(days=offset)
        return offset, d, d.weekday() >= 5, api_get(token, paths[data_type], 
            {"garduIndukId": 222, "date": d.strftime("%Y-%m-%d")})
    
    # Kumpulkan: semua, weekday, weekend (separate)
    item_patterns = defaultdict(lambda: {
        "all_values": [], "weekday_values": [], "weekend_values": [],
        "mv_values": [], "hv_values": [],
        "mv_weekday": [], "mv_weekend": [],
        "hv_weekday": [], "hv_weekend": [],
    })
    item_names = {}  # id → nama trafo (untuk aturan pembulatan MV)
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        results_list = list(executor.map(fetch_day, range(1, days + 1)))
    
    for offset, d, d_is_weekend, result in results_list:
        items = result.get("data", {}).get("items", [])
        for it in items:
            # Simpan nama untuk aturan pembulatan MV
            item_names[it["id"]] = it.get("nama", "")
            if data_type == "tegangan-trafo":
                for e in it.get("tegangan", []):
                    if e["periode"] == periode:
                        item_patterns[it["id"]]["mv_values"].append(e["mv"])
                        item_patterns[it["id"]]["hv_values"].append(e["hv"])
                        if d_is_weekend:
                            item_patterns[it["id"]]["mv_weekend"].append(e["mv"])
                            item_patterns[it["id"]]["hv_weekend"].append(e["hv"])
                        else:
                            item_patterns[it["id"]]["mv_weekday"].append(e["mv"])
                            item_patterns[it["id"]]["hv_weekday"].append(e["hv"])
            else:
                if it.get("statusCB") == "OFF":
                    continue
                for e in it.get("beban", []):
                    if e["periode"] == periode:
                        v = e["beban"]
                        item_patterns[it["id"]]["all_values"].append(v)
                        if d_is_weekend:
                            item_patterns[it["id"]]["weekend_values"].append(v)
                        else:
                            item_patterns[it["id"]]["weekday_values"].append(v)
    
    # Hitung smart suggest per item
    patterns = {}
    for item_id, data in item_patterns.items():
        if data_type == "tegangan-trafo":
            mvs = data["mv_values"]
            if mvs:
                nama = item_names.get(item_id, "")
                mv_avg_raw = sum(mvs) / len(mvs)
                hv_avg_raw = sum(data["hv_values"]) / len(data["hv_values"])
                # Aturan pembulatan MV per trafo
                mv_rounded = _round_mv(nama, mv_avg_raw)
                # HV: PS pakai 2 desimal (sisi 20kV), lainnya integer
                if "PS" in nama.upper():
                    hv_rounded = round(hv_avg_raw, 2)
                else:
                    hv_rounded = int(round(hv_avg_raw))
                patterns[str(item_id)] = {
                    "mv_avg": mv_rounded,
                    "hv_avg": hv_rounded,
                    "samples": len(mvs)
                }
        else:
            all_vals = data["all_values"]
            if not all_vals:
                continue
            
            # Pakai weekday atau weekend pattern sesuai target hari
            if is_target_weekend:
                pattern_vals = data["weekend_values"] if data["weekend_values"] else all_vals
                pattern_label = "weekend"
            else:
                pattern_vals = data["weekday_values"] if data["weekday_values"] else all_vals
                pattern_label = "weekday"
            
            base_avg = sum(all_vals) / len(all_vals)
            pattern_avg = sum(pattern_vals) / len(pattern_vals)
            
            # Smart formula: 50% pattern (weekday/weekend) + 50% base
            smart_avg = 0.5 * pattern_avg + 0.5 * base_avg
            
            # Round ke kelipatan 5
            suggested = round(smart_avg / 5) * 5
            
            # Clamp ke range historis pattern
            if pattern_vals:
                p_min, p_max = min(pattern_vals), max(pattern_vals)
                suggested = max(p_min, min(p_max, suggested))
            
            patterns[str(item_id)] = {
                "avg": suggested,
                "raw_avg": round(smart_avg, 1),
                "base_avg": round(base_avg, 1),
                "pattern_avg": round(pattern_avg, 1),
                "pattern_type": pattern_label,
                "min": min(all_vals),
                "max": max(all_vals),
                "samples": len(all_vals),
                "pattern_samples": len(pattern_vals),
            }
    
    return jsonify({"success": True, "patterns": patterns, "is_target_weekend": is_target_weekend})

# Aturan khusus tegangan GI MANGGARAI:
# - TRAFO PS 1 (22244): HV = MV dari TRAFO 1 (22241), MV = genap bulat
# - TRAFO PS 2 (22245): HV = MV dari TRAFO 3 (22243), MV = genap bulat
PS_RULES = {
    22244: {"hv_source": 22241, "name": "TRAFO PS 1"},  # HV dari MV TRAFO 1
    22245: {"hv_source": 22243, "name": "TRAFO PS 2"},  # HV dari MV TRAFO 3
}

@app.route("/api/data/batch-pattern-tegangan", methods=["GET"])
@login_required
def api_batch_pattern_tegangan():
    """
    API khusus tegangan: pola + aturan PS1/PS2.
    HV PS1 = MV TRAFO 1, HV PS2 = MV TRAFO 3, MV PS genap bulat.
    """
    token = session["token"]
    periode = request.args.get("periode", type=int)
    days = request.args.get("days", 7, type=int)
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    from collections import defaultdict
    from datetime import timedelta
    
    path = "/gama/opgi-20kv/operator-gi/tegangan-trafo"
    today = datetime.strptime(date_str, "%Y-%m-%d")
    item_patterns = defaultdict(lambda: {"mv_values": [], "hv_values": []})
    item_names = {}  # id → nama trafo (untuk aturan pembulatan MV)
    
    from concurrent.futures import ThreadPoolExecutor
    
    def fetch_day_teg(offset):
        d = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        return api_get(token, path, {"garduIndukId": 222, "date": d})
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        results_list = list(executor.map(fetch_day_teg, range(1, days + 1)))
    
    for result in results_list:
        items = result.get("data", {}).get("items", [])
        for it in items:
            item_names[it["id"]] = it.get("nama", "")
            for e in it.get("tegangan", []):
                if e["periode"] == periode:
                    item_patterns[it["id"]]["mv_values"].append(e["mv"])
                    item_patterns[it["id"]]["hv_values"].append(e["hv"])
    
    patterns = {}
    for item_id, data in item_patterns.items():
        if data["mv_values"]:
            nama = item_names.get(item_id, "")
            mv_avg = sum(data["mv_values"]) / len(data["mv_values"])
            hv_avg = sum(data["hv_values"]) / len(data["hv_values"])
            
            if item_id in PS_RULES:
                # PS trafo: MV pembulatan ke integer (parity dengan CLI), HV dari MV trafo sumber
                mv_rounded = _round_mv(nama, mv_avg)  # PS → 0 desimal (int)
                source_id = PS_RULES[item_id]["hv_source"]
                source_data = item_patterns.get(source_id, {"mv_values": []})
                if source_data["mv_values"]:
                    # HV PS = rata-rata MV trafo sumber, dibulatkan sesuai aturan trafo sumber
                    source_name = item_names.get(source_id, "")
                    hv_from_source = _round_mv(source_name, sum(source_data["mv_values"]) / len(source_data["mv_values"]))
                else:
                    hv_from_source = round(hv_avg, 2)
                
                patterns[str(item_id)] = {
                    "mv_avg": mv_rounded,
                    "hv_avg": hv_from_source,
                    "samples": len(data["mv_values"]),
                    "is_ps": True,
                    "hv_source_name": "TRAFO 1" if source_id == 22241 else "TRAFO 3",
                    "note": f"HV=MV {patterns.get(str(source_id), {}).get('note', 'TRAFO sumber')}, MV bulat"
                }
            else:
                # TRAFO 1/2/3: aturan pembulatan per nama
                mv_rounded = _round_mv(nama, mv_avg)
                patterns[str(item_id)] = {
                    "mv_avg": mv_rounded,
                    "hv_avg": int(round(hv_avg)),
                    "samples": len(data["mv_values"]),
                    "is_ps": False
                }
    
    # Update note PS setelah semua trafo diproses
    for item_id_str, pdata in patterns.items():
        item_id = int(item_id_str)
        if item_id in PS_RULES:
            source_id = PS_RULES[item_id]["hv_source"]
            source_name = "TRAFO 1" if source_id == 22241 else "TRAFO 3"
            source_mv = patterns.get(str(source_id), {}).get("mv_avg", "?")
            pdata["note"] = f"HV={source_mv}kV (dari MV {source_name}), MV genap bulat"
    
    return jsonify({"success": True, "patterns": patterns})

@app.route("/api/data/sync-portal", methods=["POST"])
@login_required
def api_sync_portal():
    """API endpoint: sync data ke Portal PLN APD Jakarta setelah batch fill."""
    data = request.get_json()
    data_type = data.get("type")  # beban-penyulang, beban-trafo, tegangan-trafo
    periodes = data.get("periodes", [])  # list of int
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    # Map type
    sync_type_map = {
        "beban-penyulang": "penyulang",
        "beban-trafo": "trafo",
        "tegangan-trafo": "tegangan",
    }
    sync_type = sync_type_map.get(data_type)
    if not sync_type or not periodes:
        return jsonify({"success": False, "message": "Missing type or periodes"})
    
    try:
        import superi_sync
        if not superi_sync.PORTAL_USER or not superi_sync.PORTAL_PASS:
            return jsonify({"success": False, "message": "Portal PLN credentials belum diset di .superi_config.json"})
        
        results = []
        for p in sorted(periodes):
            ok = superi_sync.do_sync(sync_type, p, p, date_str, dry_run=False)
            results.append({"periode": p, "success": ok})
        
        all_ok = all(r["success"] for r in results)
        return jsonify({"success": all_ok, "results": results, "message": f"Sync {len(periodes)} periode {'berhasil' if all_ok else 'sebagian gagal'}"})
    except ImportError:
        return jsonify({"success": False, "message": "Module superi_sync tidak tersedia"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == "__main__":
    import subprocess
    # Auto-kill port 8888 jika bentrok
    try:
        result = subprocess.run(["lsof", "-ti", ":8888"], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                subprocess.run(["kill", "-9", pid], capture_output=True)
            import time
            time.sleep(1)
            print("  ⚠ Port 8888 bentrok — proses lama dihentikan.")
    except Exception:
        pass
    app.run(debug=False, host="127.0.0.1", port=8888)
