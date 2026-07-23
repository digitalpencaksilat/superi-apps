# SUPER-I APP Automation Tool

## Dokumentasi Proyek

**Versi:** 1.0 | **Update:** 19 Juni 2026  
**Author:** SUPER-I APP Operator  
**Lokasi:** GI MANGGARAI, UP5 DKI Jakarta dan Banten, PLN

---

## 1. OVERVIEW

Tools untuk menginput data monitoring GI (Gardu Induk) ke sistem **SUPER-I APP** 
tanpa menggunakan aplikasi mobile. Mendukung input 3 jenis data:

| Jenis | Keterangan | Unit |
|-------|-----------|------|
| Beban Penyulang | Arus beban per feeder/penyulang | Ampere |
| Beban Trafo | Arus beban per transformator | Ampere |
| Tegangan Trafo | Tegangan HV (sisi 150kV) dan MV (sisi 20kV) per trafo | kV |

### Arsitektur

```
┌──────────────┐     REST API      ┌─────────────────────┐
│  superi_app  │ ───────────────→  │  SUPER-I APP Server  │
│  (Python CLI)│ ←───────────────  │  (NestJS + Next.js)  │
└──────────────┘     JSON/Multipart└─────────────────────┘
```

### Prasyarat Sistem

- Python 3.8+ (stdlib only — tidak butuh pip install)
- Akun SUPER-I APP dengan role "Operator GI 20kV"
- User harus sudah **absen masuk** (check-in via app mobile) sebelum input data

---

## 2. INSTALASI & SETUP

### File Proyek

```
~/
├── superi_app.py          # Script interaktif (menu-based)
├── superi_input.py        # Script CLI (command-line / automation)
└── .superi_config.json    # Konfigurasi kredensial (auto-generated)
```

### Setup Awal

```bash
# Clone/copy script ke home
cp superi_app.py ~/
cp superi_input.py ~/

# Jalankan pertama kali — akan minta NIP + password
python3 ~/superi_app.py
```

Isi kredensial:
```
NIP: NIP_ANDA
Password: ********
```

Konfigurasi disimpan di `~/.superi_config.json`. Gardu Induk **otomatis terdeteksi** 
dari data absensi user — tidak perlu diisi manual.

### Environment Variables (opsional)

```bash
export SUPERI_NIP="NIP_ANDA"
export SUPERI_PASS="YOUR_PASSWORD_HERE"
```

---

## 3. API REFERENCE

### Base URL
```
https://super-i-app.plnes.co.id/api
```

### 3.1 Authentication

**Login:**
```
POST /auth/login-mobile
Content-Type: application/json

Body: {"nip":"NIP_ANDA","password":"<PASSWORD>"}

Response 201:
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "user": {
      "namaLengkap": "MOHAMMAD FARHAN",
      "roles": ["Operator GI 20kV"],
      "UPId": "UP5"
    }
  }
}
```

Semua request selanjutnya menggunakan header:
```
Authorization: Bearer {access_token}
```

### 3.2 Absensi (Shift)

**Cek status absensi:**
```
GET /absensi/info?timezone=Asia/Jakarta

Response 200:
{
  "shift": { "ketentuan": {"nama": "MALAM", "startHour": 22, "endHour": 8} },
  "absen": { "absenMasuk": "...", "absenKeluar": null, "statusIn": "ON TIME" },
  "keterangan": "SEDANG BERLANGSUNG",
  "absenLocation": {
    "coordinates": [{"nama": "GI MANGGARAI", "latitude": -6.213, "longitude": 106.846}]
  }
}
```

**Absen Masuk:**
```
POST /absensi
Content-Type: application/json

Body: {
  "data": "{\"type\":\"MASUK\",\"timezone\":\"Asia/Jakarta\",\"latitude\":\"-6.213\",\"longitude\":\"106.846\",\"failedAttempt\":0,\"face\":[\"base64...\"]}"
}
```

⚠️ Endpoint absensi saat ini belum bisa diakses via script (butuh foto wajah).

### 3.3 BEBAN PENYULANG

**List:**
```
GET /gama/opgi-20kv/operator-gi/beban-penyulang?garduIndukId={gi_id}&date=YYYY-MM-DD

Response:
{
  "data": {
    "items": [{
      "id": 2660,
      "nama": "CASABLANCA4",
      "iMax": 300,
      "statusCB": "ON",
      "garduInduk": {"id": 222, "nama": "GI MANGGARAI"},
      "trafo": {"nama": "TRAFO 2"},
      "beban": [
        {"id": ..., "periode": 0, "beban": 35, "durasi": 0.1,
         "foto": {"uri": "...", "date": "...", "address": "...", "latitude": ..., "longitude": ...}},
        ...
      ]
    }]
  }
}
```

**Input (201 Created):**
```
POST /gama/opgi-20kv/operator-gi/beban-penyulang/input
Content-Type: multipart/form-data

Fields:
  data    = JSON string {"penyulangId":2660,"timezone":"Asia/Jakarta","periode":0,"tanggal":19,"bulan":5,"tahun":2026,"durasi":0.1,"beban":150,"foto":{...}}
  file    = JPEG image (field name: "file" singular)
```

**Delete:**
```
DELETE /gama/opgi-20kv/operator-gi/beban-penyulang/{entry_id}
```

### 3.4 BEBAN TRAFO

**List:**
```
GET /gama/opgi-20kv/operator-gi/beban-trafo?garduIndukId={gi_id}&date=YYYY-MM-DD
```

**Input (sama format beban penyulang):**
```
POST /gama/opgi-20kv/operator-gi/beban-trafo/input
Content-Type: multipart/form-data

Fields:
  data    = JSON string {"trafoId":22241,...}
  file    = JPEG image (field name: "file" singular)
```

### 3.5 TEGANGAN TRAFO

**List:**
```
GET /gama/opgi-20kv/operator-gi/tegangan-trafo?garduIndukId={gi_id}&date=YYYY-MM-DD

Response:
{
  "data": {
    "items": [{
      "id": 22241,
      "nama": "TRAFO 1",
      "isPS": 0,
      "tegangan": [
        {"id": ..., "periode": 0, "mv": 20.4, "hv": 150, "durasi": 0.2,
         "fotoHV": {"uri": "...", "date": "...", "address": "...", "latitude": ..., "longitude": ...},
         "fotoMV": {"uri": "...", "date": "...", "address": "...", "latitude": ..., "longitude": ...}},
        ...
      ]
    }]
  }
}
```

**Input (201 Created):**
```
POST /gama/opgi-20kv/operator-gi/tegangan-trafo/input
Content-Type: multipart/form-data

Fields:
  data    = JSON string {"trafoId":22241,"timezone":"Asia/Jakarta","periode":0,"tanggal":19,"bulan":5,"tahun":2026,"durasi":0.1,"mv":20.4,"hv":150,"fotoHV":{...},"fotoMV":{...}}
  files   = JPEG image HV (field name: "files" PLURAL)
  files   = JPEG image MV (field name: "files" PLURAL — same name, 2 files)
```

⚠️ **PERBEDAAN PENTING:**
- Beban: field upload = **`file`** (singular, 1 foto)
- Tegangan: field upload = **`files`** (plural, 2 foto HV + MV)

---

## 4. DATA REFERENCE

### 4.1 Gardu Induk
| ID | Nama |
|----|------|
| 222 | GI MANGGARAI |

### 4.2 Trafo
| ID | Nama | Tipe | iMax |
|----|------|------|------|
| 22241 | TRAFO 1 | GI | 1732A |
| 22242 | TRAFO 2 | GI | 1732A |
| 22243 | TRAFO 3 | GI | 1732A |
| 22244 | TRAFO PS 1 | PS | — |
| 22245 | TRAFO PS 2 | PS | — |

### 4.3 Penyulang GI MANGGARAI (ID: 222)

| ID | Nama | iMax | CB | Trafo |
|----|------|------|----|-------|
| 2660 | CASABLANCA4 | 300A | ON | TRAFO 2 |
| 2661 | STERIL | 300A | ON | TRAFO 3 |
| 2662 | LABORATORIUM | 300A | ON | TRAFO 1 |
| 2663 | MICROSCOPE | 300A | ON | TRAFO 1 |
| 2664 | STYSTOSCOP | 300A | ON | TRAFO 1 |
| 2665 | AKUPUNTUR | 300A | ON | TRAFO 1 |
| 2666 | FISIOTERAPI | 300A | **OFF** | TRAFO 1 |
| 2667 | ORTOPEDI | 300A | ON | TRAFO 3 |
| 2668 | THERMOMETER | 300A | ON | TRAFO 3 |
| ... | ... | ... | ... | ... |
| 2672 | RONTGEN | 300A | **OFF** | TRAFO 2 |
| 3341 | KOPEL C-A (DKTAS) | — | **OFF** | — |
| 2687 | PINSET | 300A | **OFF** | TRAFO 2 |
| 3342 | KOPEL A-D (GDPLA) | — | **OFF** | — |

### 4.4 Pola Nilai Beban (18 Juni 2026)

**CASABLANCA4 (Penyulang):**
```
Jam 00-06: 30-40A   (malam/pagi, beban rendah)
Jam 07-15: 85-170A  (siang, beban puncak)
Jam 16-20: 95-165A  (sore, beban menurun)
Jam 21-23: 40-80A   (malam, beban rendah)
```

**TRAFO 1 (Beban):**
```
Jam 00-06: 330-370A
Jam 07-15: 440-650A
Jam 16-20: 540-630A
Jam 21-23: 355-525A
```

**TRAFO 1 (Tegangan):**
```
HV: 144-151 kV (fluktuasi harian, malam naik, siang turun)
MV: 20.3-20.5 kV (stabil)
```

### 4.5 Bulan (0-indexed!)

Server menggunakan bulan 0-indexed (Januari=0). Script sudah handle otomatis.

| Bulan | Index |
|-------|-------|
| Januari | 0 |
| Juni | 5 |
| Desember | 11 |

### 4.6 Shift Kerja

| Shift | Jam | Identifier |
|-------|-----|-----------|
| Pagi | 08:00-15:00 | P |
| Sore | 16:00-22:00 | S1 |
| Malam | 22:00-07:00 | M |

---

## 5. CARA PAKAI

### 5.1 Script Interaktif (`superi_app.py`)

```bash
python3 ~/superi_app.py
```

**Tampilan menu:**
```
╔══════════════════════════════════════════╗
║  SUPER-I APP - Data Input Tool           ║
╚══════════════════════════════════════════╝
  User: MOHAMMAD FARHAN | Role: Operator GI 20kV
  GI: 222 | Tanggal: 2026-06-19

  ═══════════ DATA ═══════════
  [1] Lihat Beban Penyulang
  [2] Lihat Beban Trafo
  [3] Lihat Tegangan Trafo

  ═══════════ INPUT ═══════════
  [4] Input Beban Penyulang
  [5] Input Beban Trafo
  [6] Input Tegangan Trafo

  ═══════ BATCH PER JAM ═══════
  [A] Beban Penyulang
  [B] Beban Trafo
  [C] Tegangan Trafo

  ═══════════ LAIN ═══════════
  [G] Ganti Tanggal
  [L] Login Ulang
  [0] Keluar
```

**Flow input:**
1. Pilih [4]/[5]/[6]
2. Pilih item dari daftar (⛔ CB OFF ditandai, tidak bisa dipilih)
3. Pilih periode kosong
4. Nilai disarankan dari **periode 1 jam sebelumnya** — tekan Enter untuk terima
5. Konfirmasi → data terkirim

**Batch per jam:** pilih satu periode, tinjau Smart Suggest untuk semua item kosong,
jalankan input dengan progress, lalu lanjutkan Sync Portal bila diperlukan.

### 5.2 Script CLI (`superi_input.py`)

Untuk automation, scripting, atau cronjob.

```bash
# Lihat data
python3 ~/superi_input.py -n NIP_ANDA -p <PASSWORD> --list-penyulang --gi 222

# Input beban penyulang
python3 ~/superi_input.py -n NIP_ANDA -p <PASSWORD> \
  --type beban-penyulang --gi 222 --id 2660 --periode 8 --value 125

# Input beban trafo
python3 ~/superi_input.py -n NIP_ANDA -p <PASSWORD> \
  --type beban-trafo --gi 222 --id 22241 --periode 8 --value 500

# Input tegangan trafo (MV + HV)
python3 ~/superi_input.py -n NIP_ANDA -p <PASSWORD> \
  --type tegangan-trafo --gi 222 --id 22241 --periode 8 --value 20.4 --hv 148

# Delete entry
python3 ~/superi_input.py -n NIP_ANDA -p <PASSWORD> \
  --type beban-penyulang --delete 2848454
```

---

## 6. TROUBLESHOOTING

### "Kamu belum melakukan absen masuk"
User harus check-in dulu via aplikasi mobile. Script tidak bisa melakukan absensi 
karena butuh foto wajah.

### "Input dimulai pada jam XX:00"
Sistem hanya menerima input untuk periode yang sudah dimulai. Tidak bisa menginput 
periode yang belum tiba waktunya. Untuk tanggal kemarin, semua periode 0-23 bisa.

### "Beban sudah terinput, mohon refresh aplikasi!"
Data untuk periode tersebut sudah ada. Gunakan delete dulu jika ingin mengganti.

### CB OFF
Penyulang dengan Circuit Breaker OFF tidak bisa diinput — tidak ada arus mengalir. 
Ditandai dengan ⛔ di script interaktif.

### 500 Internal Server Error
Kemungkinan backend issue. Coba lagi nanti. Jika persisten, laporkan ke developer.

---

## 7. PENGEMBANGAN SELANJUTNYA

### Ide Enhancement

1. **Auto-suggest dari hari sebelumnya** — jika hari ini belum ada data, ambil 
   dari jam yang sama di hari sebelumnya

2. **Cron job otomatis** — input data setiap jam menggunakan akun yang sedang 
   aktif shift

3. **Absensi automation** — teliti cara melakukan absensi via API (foto wajah 
   mungkin bisa di-bypass untuk testing)

4. **Web dashboard** — tampilan web sederhana untuk monitoring + input

5. **Notifikasi** — alert jika ada penyulang yang belum terisi mendekati akhir shift

6. **Export data** — export ke Excel/CSV untuk laporan

### Yang Perlu Diteliti Lebih Lanjut

- **Absensi API**: Format request absensi (POST /absensi). Saat ini hanya GET 
  yang berfungsi. POST butuh foto wajah (face array) — format persisnya belum 
  terpecahkan, selalu 500.

- **Endpoint upload foto**: Untuk produksi, sebaiknya pakai foto asli bukan JPEG 
  dummy. Perlu diketahui endpoint untuk upload foto ke `/media/images/`.

### Kontak Developer Backend
Untuk pertanyaan teknis API, kontak tim developer SUPER-I APP.

---

## 8. CHANGELOG

| Tanggal | Versi | Perubahan |
|---------|-------|-----------|
| 19 Jun 2026 | 1.0 | Initial release. Support Beban Penyulang, Beban Trafo, Tegangan Trafo. |
| 19 Jun 2026 | 1.0.1 | Auto-detect GI ID. Suggest dari periode sebelumnya. CB OFF protection. |
