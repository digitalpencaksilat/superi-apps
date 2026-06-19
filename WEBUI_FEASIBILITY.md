# Web-Based UI/UX untuk SUPER-I APP Automation

## Feasibility Analysis

### 1. TEKNOLOGI STACK (Rekomendasi)

**Backend:**
```
Python Flask / FastAPI
├── REST API endpoints (wrap script existingnya)
├── Session management (JWT token)
├── Database: SQLite untuk cache/history
└── CORS enabled untuk frontend
```

**Frontend:**
```
HTML5 + CSS3 + JavaScript (vanilla / minimal framework)
├── Responsive design (mobile-friendly)
├── Real-time data update (WebSocket opsional)
├── Dark mode (monitoring center theme)
└── Akses lokal atau via LAN
```

**Hosting:**
```
Opsi 1: Lokal (localhost:8000)
  ✓ Sederhana, cepat
  ✓ Tidak butuh internet
  ✓ Data aman di lokal
  ✗ Hanya bisa diakses dari satu PC

Opsi 2: Server internal PLN
  ✓ Bisa diakses dari beberapa PC di LAN
  ✓ Multi-user
  ✗ Butuh setup server
  ✗ Butuh IT support

Opsi 3: Cloud (AWS/GCP/Heroku)
  ✓ Bisa diakses dari mana saja
  ✗ Butuh internet
  ✗ Biaya hosting
  ✗ Data sensitivity (pastikan komplit)
```

---

### 2. FITUR YANG BISA DIIMPLEMENTASIKAN

#### Dashboard Monitoring
```
┌─────────────────────────────────────────────┐
│  SUPER-I APP Monitor Dashboard              │
├─────────────────────────────────────────────┤
│ User: MOHAMMAD FARHAN | GI: GI MANGGARAI    │
│ Status: AKTIF (Shift Malam 22:00-08:00)     │
├─────────────────────────────────────────────┤
│                                              │
│  BEBAN PENYULANG                             │
│  ┌──────────────────────────────────────┐   │
│  │ CASABLANCA4       | 8/24 | [▓▓▓░░░░░] │   │
│  │ STERIL            | 8/24 | [▓▓▓░░░░░] │   │
│  │ LABORATORIUM      | 8/24 | [▓▓▓░░░░░] │   │
│  │ AKUPUNTUR         | 8/24 | [▓▓▓░░░░░] │   │
│  │ FISIOTERAPI       | 0/24 | [░░░░░░░░] ⛔ │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  BEBAN TRAFO                                 │
│  ┌──────────────────────────────────────┐   │
│  │ TRAFO 1           | 8/24 | [▓▓▓░░░░░] │   │
│  │ TRAFO 2           | 8/24 | [▓▓▓░░░░░] │   │
│  │ TRAFO 3           | 8/24 | [▓▓▓░░░░░] │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  TEGANGAN TRAFO                              │
│  ┌──────────────────────────────────────┐   │
│  │ TRAFO 1: HV=151kV MV=20.4kV | 8/24   │   │
│  │ TRAFO 2: HV=150kV MV=20.3kV | 8/24   │   │
│  │ TRAFO 3: HV=149kV MV=20.5kV | 8/24   │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  [REFRESH] [EXPORT] [SETTINGS]               │
└─────────────────────────────────────────────┘
```

#### Input Form
```
┌──────────────────────────────────────┐
│  INPUT: Beban Penyulang              │
├──────────────────────────────────────┤
│                                       │
│  Pilih Item: [CASABLANCA4  ▼]         │
│  Status: ON | iMax: 300A              │
│                                       │
│  Data Existing (P00-P07):             │
│  P00: 35A  P01: 40A  P02: 38A         │
│  P03: 42A  P04: 90A  P05: 125A        │
│  P06: 170A P07: 165A                  │
│                                       │
│  Pilih Periode:    [8 ▼]              │
│  Saran dari P07:   125A ↓             │
│  Nilai (Ampere):   [125________]      │
│                                       │
│  Durasi (menit):   [120________]      │
│  Tanggal:          [2026-06-19]       │
│                                       │
│  [SUBMIT]  [BATAL]                    │
└──────────────────────────────────────┘
```

#### Fitur Lain
- ✓ History — lihat data yang sudah diinput
- ✓ Export — download ke Excel/CSV
- ✓ Multi-user login
- ✓ Permission control (siapa bisa input apa)
- ✓ Notifikasi — periode belum terisi sebelum shift selesai
- ✓ Auto-refresh — data terbaru setiap 30 detik

---

### 3. ARSITEKTUR TEKNIS

```
┌─────────────────────────┐
│   Web Browser           │
│  (Chrome, Firefox)      │
└────────────┬────────────┘
             │ HTTP/WebSocket
             ↓
┌─────────────────────────┐
│   Flask/FastAPI Server  │
│   (http://localhost:8000)
│                         │
│  ├─ /api/auth/login     │
│  ├─ /api/data/list      │
│  ├─ /api/data/input     │
│  ├─ /api/data/delete    │
│  ├─ /api/export         │
│  └─ /api/history        │
└────────────┬────────────┘
             │
             ↓
┌─────────────────────────┐
│   Python Script Layer   │
│  (superi_input.py)      │
│  - Login SUPER-I APP    │
│  - Fetch data           │
│  - POST/DELETE          │
└────────────┬────────────┘
             │
             ↓
┌─────────────────────────┐
│  SUPER-I APP API        │
│  (super-i-app.         │
│   plnes.co.id/api)     │
└─────────────────────────┘
```

---

### 4. ROADMAP DEVELOPMENT

**Phase 1 (1-2 minggu): MVP**
```
✓ Setup Flask + HTML form
✓ Backend: wrap superi_input.py API
✓ Frontend: Simple table + input form
✓ Auth: Login form → simpan JWT di session
✓ Test: Input beban penyulang + trafo via web
```

**Phase 2 (1-2 minggu): Enhancement**
```
✓ Dashboard dengan progress bar
✓ Multi-select untuk batch input
✓ Data history + export Excel
✓ Auto-refresh setiap 30 detik
✓ Dark mode
```

**Phase 3 (optional): Advanced**
```
✓ WebSocket real-time update
✓ Multi-user dengan permission
✓ Cronjob scheduling (input otomatis)
✓ Mobile app (PWA)
```

---

### 5. ESTIMASI EFFORT

| Task | Waktu | Kompleksitas |
|------|-------|--------------|
| Backend setup | 2-3 jam | Easy |
| Frontend form | 4-5 jam | Easy |
| Integrasikan script | 3-4 jam | Medium |
| Testing | 2-3 jam | Medium |
| Deployment lokal | 1-2 jam | Easy |
| **Total Phase 1** | **~14 jam** | **Medium** |

---

### 6. KEUNTUNGAN WEB vs CLI

| Aspek | CLI (superi_app.py) | Web |
|------|---------------------|-----|
| UX | Text menu | Visual dashboard |
| Multi-user | Tidak | Ya |
| Mobile access | Tidak | Ya (via browser) |
| Automation | Mudah | Butuh scheduler |
| Setup | Sederhana | Butuh server |
| Maintenance | Minimal | Perlu monitoring |
| Data logging | Tidak built-in | Mudah |

---

### 7. REKOMENDASI

**Untuk saat ini:**
- ✅ **Gunakan CLI + superi_app.py** — sudah cukup powerful, interface interaktif
- ✅ Dokumentasi sudah lengkap
- ✅ Bisa langsung digunakan

**Untuk jangka panjang (3-6 bulan ke depan):**
- 🔄 **Pertimbangkan web** kalau:
  - Ada operator lain yang perlu input dari PC berbeda
  - Butuh tracking/history yang lebih baik
  - Ingin dashboard monitoring
  - Ada budget untuk server maintenance

**Alternatif middle-ground:**
- 📊 Buat **simple web dashboard** (read-only) untuk monitoring
- 🖥️ Input tetap via CLI untuk operasional

---

### 8. NEXT STEP

Pilih salah satu:

**Opsi A: Lanjut dengan CLI** ✅
- Fokus pada automation (cron job)
- Buat dashboard monitoring sederhana (tidak perlu input di web)

**Opsi B: Mulai web development**
- Setup Flask skeleton
- Integrasi dengan script existing
- Buat MVP dashboard + input form

**Opsi C: Hybrid**
- CLI tetap sebagai utama (automation-friendly)
- Web sebagai companion (visual monitoring)

Mana yang kamu prefer?
