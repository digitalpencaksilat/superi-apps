# Changelog

Semua perubahan penting pada project ini akan didokumentasikan di file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/),
dan project ini menggunakan [Semantic Versioning](https://semver.org/lang/id/).

## [1.1.1] — 2026-07-12

### Added

- Auto Mode menghitung beban trafo dari akumulasi beban penyulang aktif yang
  sudah tersimpan di SUPER-I untuk periode yang sama.
- Penyulang aktif yang tetap kosong setelah proses input dan retry menggunakan
  fallback `0 A`, dengan nama penyulang dicatat pada log Auto Mode.
- Pengujian regresi untuk pemetaan penyulang-trafo, status CB, fallback nol,
  perlindungan data trafo yang sudah ada, dan verifikasi hasil penyimpanan.

### Changed

- Urutan proses Auto Mode dinormalisasi menjadi penyulang, trafo, lalu tegangan
  agar kalkulasi trafo selalu membaca data penyulang terbaru dari SUPER-I.
- Input otomatis beban trafo tidak lagi menggunakan smart-suggest historis.
  Relasi trafo dibaca dari objek penyulang menggunakan ID, dengan nama
  ternormalisasi sebagai fallback.

### Fixed

- Hasil input beban trafo kini diverifikasi dengan mengambil ulang data
  SUPER-I dan di-retry jika belum tersimpan.
- Penyulang berstatus CB `OFF` tidak ikut dijumlahkan dan beban trafo yang
  sudah terisi tidak ditimpa.

## [1.1.0] — 2026-07-12

### Added

- **Auto Mode terjadwal** untuk menjalankan input dan sinkronisasi otomatis,
  termasuk retry, pengaturan melalui CLI/Web, serta instalasi jadwal cron dan
  Windows Task Scheduler.
- **Dukungan Windows portable** dengan launcher, setup Python lokal, dan
  penanganan encoding console Windows.
- **Renderer CLI terpusat** untuk tabel input, batch fill, ringkasan dinamis,
  indikator keterisian 24 periode, serta test otomatis untuk hasil render.
- **Halaman Auto Mode dan Setup pada Web UI**, dilengkapi progress sinkronisasi
  serta smart-suggest yang konsisten dengan CLI.
- **Menu sinkronisasi Portal APD pada CLI** dan API library pada
  `superi_sync.py` agar proses sinkronisasi dapat digunakan ulang oleh modul
  lain.
- **Konfigurasi `history_days`** untuk memilih periode analisis smart-suggest
  selama 3, 7, atau 14 hari, dengan nilai default 7 hari pada CLI dan Web.

### Changed

- Tampilan menu dan halaman CLI dirapikan agar konsisten, termasuk tabel data
  yang menyesuaikan lebar terminal dan ringkasan status pengisian.
- Smart-suggest CLI dan Web diselaraskan agar menggunakan pola
  weekday/weekend, pembulatan beban, serta aturan tegangan masing-masing trafo.
- Launcher macOS/Linux menggunakan interpreter virtual environment secara
  konsisten, sementara proses Windows dijalankan tanpa kebutuhan instalasi
  tingkat sistem.
- Konfigurasi Portal APD disatukan dengan konfigurasi utama aplikasi.

### Fixed

- Perhitungan saran tegangan menggunakan histori pada periode jam yang sesuai.
- Pembulatan MV mengikuti aturan masing-masing trafo dan HV trafo PS mengikuti
  MV trafo sumber.
- Batch tegangan Web tidak lagi menghasilkan kolom kosong akibat konteks
  weekday/weekend yang hilang.
- Auto Mode lebih tahan terhadap kegagalan sementara melalui retry yang lebih
  aman, jadwal Windows lima-menitan, dan penanganan output console.
- Kotak ringkasan CLI tidak lagi memotong angka pada terminal dengan lebar
  berbeda.

## [1.0.0] — 2026-06-19

### 🎉 Initial Release

Rilis pertama SUPER-I APP Automation Toolkit dengan fitur lengkap untuk
otomasi pekerjaan operator Gardu Induk 20kV.

### ✨ Added

- **`superi sync`** — Sync engine SUPER-I APP → Portal APD Jakarta
  - Sinkronisasi otomatis Beban Penyulang (32 feeder × 24 jam)
  - Sinkronisasi otomatis Beban Trafo (3 trafo × 24 jam)
  - Sinkronisasi otomatis Tegangan Trafo (5 trafo × MV+HV × 24 jam)
  - Mode interaktif (menu-driven) dan mode argumen CLI
  - Dry-run mode untuk preview sebelum write ke produksi
  - Auto-skip cell dengan nilai sama (minimal writes)
  - Normalisasi nama trafo (handle "TRAFO PS 1" vs "TRAFO PS1")
- **`superi cli`** — CLI interaktif untuk operasi manual
- **`superi web`** — Web dashboard lokal (Flask, port 8888)
  - Smart-suggest berbasis histori (weekday/weekend aware)
  - Batch input per periode jam
  - Parallel fetch dengan ThreadPoolExecutor
- **`superi input`** — Scripting mode untuk input via API
  - Bearer JWT authentication via `/api/auth/login-mobile`
  - Support Beban Penyulang, Beban Trafo, Tegangan Trafo
- **Konfigurasi aman**: credentials via `.superi_config.json` (gitignored)
  atau environment variables
- **Launcher universal**: `superi <command>` dapat dipanggil dari direktori manapun

### 🔐 Security

- Credentials tidak di-commit ke repository
- Template config tersedia di `.superi_config.example.json`
- Support env var override (SUPERI_NIP, SUPERI_PASSWORD, PORTAL_USER, dst.)

### 📚 Documentation

- README interaktif dengan badges, contoh output, arsitektur diagram
- Troubleshooting guide untuk error umum
- Konfigurasi & deployment instructions

[1.1.1]: https://github.com/digitalpencaksilat/superi-apps/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/digitalpencaksilat/superi-apps/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/digitalpencaksilat/superi-apps/releases/tag/v1.0.0
