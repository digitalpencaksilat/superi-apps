# ⚡ SUPER-I APP — Automation Toolkit

<p align="center">
  <img src="https://img.shields.io/badge/SUPER--I%20APP-Automation-blue?style=for-the-badge&logo=lightning&logoColor=white" alt="SUPER-I APP"/>
  <img src="https://img.shields.io/badge/Version-1.0.0-orange?style=for-the-badge" alt="Version 1.0.0"/>
  <img src="https://img.shields.io/badge/Python-3.8+-green?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.8+"/>
  <img src="https://img.shields.io/badge/Status-Production-success?style=for-the-badge" alt="Production"/>
</p>

<p align="center">
  <b>Otomasi monitoring & input data realisasi GI 20kV untuk Operator Gardu Induk</b><br>
  <sub>Automation Toolkit untuk Operator Gardu Induk 20kV</sub>
</p>

---

## 🎯 Apa ini?

Toolkit CLI untuk mengotomasi pekerjaan rutin operator GI 20kV:

| Fitur | Deskripsi |
|-------|-----------|
| 🔄 **Sync Portal** | Sinkronisasi data SUPER-I APP → Portal APD Jakarta (otomatis!) |
| 📊 **Batch Input** | Input beban penyulang, trafo, tegangan per jam (skip manual satu-satu) |
| 🌐 **Web Dashboard** | Dashboard lokal untuk monitoring & smart-suggest |
| 💻 **CLI Interaktif** | Menu-driven interface untuk semua operasi |

---

## 🚀 Quick Start

### macOS / Linux

```bash
git clone https://github.com/digitalpencaksilat/superi-apps.git
cd superi-apps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Setup credentials lewat menu interaktif
.venv/bin/python3 superi_app.py    # → pilih [S] Setup
```

Pasang launcher global (opsional, supaya bisa panggil `superi` dari mana saja):
```bash
chmod +x launcher.sh
sudo ln -sf "$(pwd)/launcher.sh" /usr/local/bin/superi
```

### 🪟 Windows (Portable, tanpa install, tanpa admin)

Cocok untuk komputer kantor yang tidak punya akses install aplikasi.

1. **Download project** (zip dari GitHub atau pakai Git Bash kalau ada)
   - https://github.com/digitalpencaksilat/superi-apps → tombol `Code` → `Download ZIP`
   - Extract ke folder mana saja, mis. `C:\superi-apps\` atau bahkan Desktop

2. **Jalankan setup** (sekali saja)
   ```cmd
   setup_windows.bat
   ```
   Script ini otomatis:
   - Download Python 3.11 portable (~10 MB) ke folder `python\`
   - Install pip
   - Install dependencies (requests, flask, beautifulsoup4)
   - Buat `.superi_config.json` dari template
   
   **Tidak butuh admin, tidak install ke system, tidak ubah PATH.**

3. **Setup credentials**
   ```cmd
   superi.bat cli
   ```
   Pilih `[S] Setup` di menu, isi NIP+password SUPER-I dan Portal APD.

4. **Pakai**
   ```cmd
   superi.bat cli                              :: CLI interaktif
   superi.bat sync --type all --jam 09         :: Sync semua tipe jam 09
   superi.bat web                              :: Web dashboard
   ```

**Tips Windows:**
- Klik kanan `superi.bat` → **Send to → Desktop (create shortcut)** untuk akses cepat
- Pakai **Windows Terminal** (gratis di Microsoft Store) biar warna & emoji tampil rapi
- Tambahkan folder project ke `PATH` (Settings → Environment Variables → Path → New) supaya bisa panggil `superi cli` dari mana saja tanpa `cd`

---

## 📖 Penggunaan

### ⚡ `superi sync` — Sync ke Portal APD

**Fitur utama.** Otomatis ambil data dari SUPER-I APP lalu push ke Portal APD Jakarta.

```bash
# Menu interaktif (pilih tipe → jam → preview → konfirmasi)
superi sync

# Sync semua tipe data jam 09
superi sync --type all --jam 09

# Sync beban penyulang jam 08 s/d 10
superi sync --type penyulang --jam 08-10

# Sync beban trafo jam tertentu
superi sync --type trafo --jam 09

# Sync tegangan trafo
superi sync --type tegangan --jam 09

# Preview dulu tanpa nulis (dry-run)
superi sync --type all --jam 09 --dry-run

# Tanggal spesifik
superi sync --type all --jam 09 --date 2026-06-20
```

**Contoh output:**
```
🔄 SUPER-I → Portal APD Sync

============================================================
                    SYNC Beban Penyulang                    
============================================================
  ℹ SUPER-I APP: Logging in...
  ✓ SUPER-I login OK
  ℹ SUPER-I APP: Fetching penyulang data...
  ✓ Got 32 items from SUPER-I
  ℹ Portal APD: Logging in...
  ✓ Portal APD login OK
  ℹ Portal APD: Fetching grid...
  ✓ Got 32 items from Portal APD
  ℹ Mode: LIVE | Jam: 09-09 | Date: 2026-06-19

  [OK] CASABLANCA4 j09=125
  [OK] LABORATORIUM j09=100
  [OK] THERMOMETER j09=115
  ...

  Summary:
    Updates : 27
    Errors  : 0
    Skipped : 0
```

### 🌐 `superi web` — Web Dashboard

```bash
superi web
# → Akses di http://localhost:8888
```

Dashboard lokal dengan fitur:
- Smart-suggest (prediksi nilai beban berdasar histori)
- Batch input per periode
- Monitoring status per GI

### 💻 `superi cli` — CLI Interaktif

```bash
superi cli
```

### 📊 `superi input` — Scripting Mode

```bash
# Input beban penyulang
superi input --nip <NIP> --pass <PASSWORD> \
  --type beban-penyulang --gi 222 --id 2660 --periode 0 --value 150

# Lihat daftar penyulang
superi input --nip <NIP> --pass <PASSWORD> --list-penyulang --gi 222
```

---

## 🏗️ Arsitektur

```
┌─────────────────────┐       API (Bearer JWT)       ┌──────────────────────┐
│   SUPER-I APP       │◄─────────────────────────────►│   superi_sync.py     │
│   (Server)          │                               │                      │
└─────────────────────┘                               │   ┌──────────────┐   │
                                                      │   │  Fetch data  │   │
                                                      │   │  Compare     │   │
                                                      │   │  Update diff │   │
┌─────────────────────┐   HTTP Session (CodeIgniter)  │   └──────────────┘   │
│   Portal APD        │◄─────────────────────────────►│                      │
│   APD Jakarta       │                               └──────────────────────┘
└─────────────────────┘
         ▲
         │ jqxGrid update_beban
         │ (GET with full rowdata)
         ▼
    ┌──────────┐
    │  Beban   │  j00-j23 (Ampere)
    │  Trafo   │  j00-j23 (Ampere)
    │ Tegangan │  j00-j23 (MV, kV) + k00-k23 (HV, kV)
    └──────────┘
```

---

## 📁 Struktur File

```
superi-apps/
├── superi_sync.py              # 🔄 Sync engine (SUPER-I → Portal APD)
├── superi_app.py               # 💻 CLI interaktif
├── superi_web.py               # 🌐 Web dashboard (Flask)
├── superi_input.py             # 📊 Scripting mode (input via API)
├── templates/                  # HTML templates untuk web
├── .superi_config.json         # ⚙️ Credentials (gitignored!)
├── .superi_config.example.json # 📋 Template config
├── requirements.txt            # Dependencies
├── launcher.sh                 # 🍎 Launcher universal (macOS/Linux)
├── launch_cli.sh               # Launcher CLI (macOS/Linux)
├── launch_web.sh               # Launcher Web (macOS/Linux)
├── superi.bat                  # 🪟 Launcher Windows
├── setup_windows.bat           # 🪟 Setup portable Windows (Python + deps)
└── README.md                   # Dokumentasi ini
```

---

## ⚙️ Konfigurasi

Semua credentials disimpan di `.superi_config.json` (tidak di-commit ke git):

```json
{
  "nip": "NIP_ANDA",
  "password": "<PASSWORD>",
  "gi_id": "222",
  "portal_url": "http://10.3.187.6/apdjakarta",
  "portal_user": "username.portal",
  "portal_password": "<PASSWORD>",
  "portal_gi_id": "143"
}
```

Atau via environment variables:
```bash
export SUPERI_NIP=NIP_ANDA
export SUPERI_PASSWORD=<PASSWORD>
export PORTAL_USER=username.portal
export PORTAL_PASSWORD=<PASSWORD>
```

---

## 🔐 Security

- ❌ Credentials **TIDAK** di-commit ke repository
- ✅ Menggunakan config file (`.superi_config.json`) yang di-gitignore
- ✅ Support environment variables sebagai alternatif
- ✅ Dry-run mode untuk preview sebelum write ke produksi
- ✅ Auto-skip cell yang nilainya sudah sama (minimal writes)

---

## 📋 Data Types

| Tipe | Sumber | Tujuan | Kolom |
|------|--------|--------|-------|
| Beban Penyulang | 32 feeder × 24 jam | j00-j23 (Ampere) | Integer |
| Beban Trafo | 3 trafo × 24 jam | j00-j23 (Ampere) | Integer |
| Tegangan Trafo | 5 trafo × 24 jam | j00-j23 (MV) + k00-k23 (HV) | Float (kV) |

---

## 🛠️ Troubleshooting

| Problem | Solusi |
|---------|--------|
| Login SUPER-I gagal | Pastikan akun sudah absen masuk (clock-in) di aplikasi mobile |
| Login Portal gagal | Session cepat expired — script otomatis login ulang tiap run |
| TRAFO PS1/PS2 skip | Sudah difix — normalisasi nama handle perbedaan spasi |
| Portal 500 error | Pastikan format tanggal benar (YYYY-MM-DD) |

---

## 📦 Versioning

Project ini menggunakan [Semantic Versioning](https://semver.org/lang/id/).

**Versi saat ini:** `1.0.0`

```bash
superi sync --version    # cek versi
cat VERSION              # cek versi via file
```

Riwayat perubahan lengkap ada di [CHANGELOG.md](./CHANGELOG.md).

---

<p align="center">
  <b>⚡ Powered by SUPER-I APP Automation</b><br>
  <sub>Mengurangi pekerjaan manual operator GI 20kV</sub>
</p>
