# Changelog

Semua perubahan penting pada project ini akan didokumentasikan di file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0),
dan project ini menggunakan [Semantic Versioning](https://semver.org/lang/id/).

## [1.2.1] — 2026-07-15

### Fixed

- **Durasi input tidak lagi robotik 3-6 menit per entry (P16 LABORATORIUM 4.3s vs CASABLANCA4 3.91 menit).**
  - Server SUPER-I menyimpan `durasi` dalam **menit**, bukan detik. `rand_durasi()` sebelumnya return `2-7` (detik) langsung → disimpan sebagai `2-7 menit` → tampil `3.49 menit / 6.21 menit` di UI resmi.
  - Sekarang `rand_durasi()` return `0.033-0.116 menit` (`2-7 detik`), `rand_durasi_tegangan()` `0.13-0.58 menit` (`8-35 detik`). Manual avg: beban `0.105 menit=6.35s`, tegangan `0.305 menit=18.3s`. Verified via live API fetch P16 LABORATORIUM `0.0724 menit=4.34s` vs CASABLANCA4 outlier `3.91 menit=234s`.
  - Fallback `0.1` di 4 modul (`superi_app`, `superi_auto`, `superi_input`, `superi_web`) diganti `rand_durasi_for_type()` agar tidak hardcode `0.1`.
  - `foto.date` sekarang korelasi dengan durasi: `now - (durasi + buffer 0.5-2.8s)` untuk hari ini, max 90s. Sebelumnya `20-180 detik` & `60-220 detik` sehingga durasi 4 detik tapi foto 3 menit lalu (inkonsisten).

- **Foto URI & address tidak lagi terdeteksi robot (GI MANGGARAI statis vs alamat lengkap).**
  - Manual: `fotoBebanPenyulang_2026-07-15_707ab3a0bbe0d9a5.jpg` + `Jl. Swadaya 1 No.36, RT.3/RW.8, Manggarai, Kec. Tebet, Jakarta Selatan, DKI Jakarta 12850, Indonesia` + lat/lon jitter ±5-15m.
  - Project lama: `IMG_20260715_162847_...jpg` / `foto_...` / `8hex.jpg` + `GI MANGGARAI` + lat/lon `-6.213/106.846` statis.
  - Sekarang `rand_filename()` generates `fotoBebanPenyulang_YYYY-MM-DD_<hex16>.jpg`, `fotoBebanTrafo_`, `fotoHV_`, `fotoMV_` (parity 2255 samples manual).
  - `rand_location()` pool 13 alamat real GI Manggarai area (dari API manual 5 hari), jitter koordinat, 5% chance `Lat=-6.213..., Long=106.846...` format, variasi nomor jalan ±1.
  - `rand_foto_dict()` & `rand_foto_pair_dicts()` return dict lengkap `{date, address, latitude, longitude}` realistis, HV/MV lokasi berdekatan (2-6m).
  - `api_post_multipart()` di semua 4 modul sekarang infer `data_type` dari path dan pakai filename manual pattern.

### Changed

- `superi_app.py`: `_human_foto_date/durasi/pair` → sinkron durasi+foto, `_human_foto_dict/pair_dicts`, `_infer_data_type_from_path`, batch fill per-item & per-jam pakai lokasi real.
- `superi_auto.py`: `_h_durasi(data_type)`, `_h_foto_dict/pair_dicts`, trafo agregasi & auto jam pakai durasi menit + lokasi real.
- `superi_input.py`: `_h_durasi/foto_dict/pair_dicts/filename` dengan `data_type` param.
- `superi_web.py`: same + `api_post_multipart` with data_type hint, batch/per-periode/scripting input fix.
- `tests/test_humanizer.py`: 13 → 23 tests, tambah `test_rand_durasi_converts_to_2_7_seconds`, `test_filename_manual_pattern`, `test_location_realistic`, `test_foto_dict/pair_dicts`, `test_foto_datetime_with_durasi_correlated`.

### Verified

- Dry-run P17: LABORATORIUM `0.0898 menit=5.39s`, CASABLANCA4 `0.0951 menit=5.71s` (sebelumnya `3.91/6.93 menit`).
- 47 CLI render tests + 12 auto mode tests + 23 humanizer tests = 82 OK.

## [1.2.0] — 2026-07-15

### Added

- **Fitur Logout Akun (Web + CLI) dengan Auto-disable Cron & Auto Mode otomatis.**
  - **Web:** Tombol Keluar (Logout) di header dashboard, setup, dan auto pages
    kini menggunakan POST form + dialog konfirmasi yang menyebutkan
    Auto Mode akan OTOMATIS NONAKTIF dan cron/Task Scheduler akan OTOMATIS
    DIHAPUS saat logout.
  - **Web:** Endpoint `POST /logout` (GET|POST backward-compat) dan
    `POST /api/auth/logout` untuk AJAX. Setelah logout redirect ke
    `/login?logged_out=1` dengan banner sukses.
  - **CLI:** Menu interaktif `[O] Logout` di `superi_app.py` + command
    `superi logout` / `superi lo` di launcher (macOS/Linux & Windows).
    Mendukung opsi `--yes`, `--purge-all`, `--keep-portal`,
    `--keep-scheduler`.
  - **3-Lapis Safety Net** untuk memastikan background job benar-benar mati
    setelah logout: (1) flag `auto_enabled=False`, (2) wipe kredensial
    `nip/password` sehingga login auto gagal, (3) uninstall cron/Task
    Scheduler (`# SUPER-I-AUTO` / `SUPER-I-Auto-Input`).
  - Backup otomatis `.superi_config.json.bak` sebelum wipe untuk safety
    re-login.
  - Setting non-kredensial (`gi_id`, `portal_url`, `history_days`,
    `portal_gi_id`) dipertahankan agar setup ulang mudah.
- **Login ulang dijamin tidak bermasalah** setelah logout: token hanya
  di RAM / session, akun di server PLN utuh, tinggal `[S] Setup` baru.

### Changed

- **`secret_key` Flask dipersist ke file `.flask_secret`** (permission 600,
  gitignored) agar session tidak hilang setiap restart server.
  Prioritas: env `FLASK_SECRET_KEY` > file `.flask_secret` > generate baru.
- `session["nip"]` dan `session["password"]` **dihapus dari Flask session**
  (security fix) — tidak lagi simpan plaintext di cookie store.
- Login page (`login.html`) tampilkan banner sukses setelah logout dan
  detail solusi saat 401 Unauthorized.

### Fixed

- **Penanganan error 401 Unauthorized** (NIP/password salah) sekarang
  ramah & informatif:
  - CLI `login()` & `do_login()` tangkap `HTTPError 401` dan tampilkan
    penyebab + 4 langkah solusi (cek NIP tanpa spasi, password sesuai,
    akun aktif, clock-in).
  - Web `login()` log `Login 401 Unauthorized: NIP atau password salah`
    dan halaman login tampilkan box solusi + link ke server PLN.
  - Auto Mode log jika 401: solusi `superi cli → [S] Setup`.
  - Mencegah kebingungan bahwa logout merusak kredensial (padahal
    password di config memang sudah salah sejak awal).
- Typo f-string `->` (U+2192) yang menyebabkan `SyntaxError` di
  `superi_app.py` saat logout flow.

### Security

- `.flask_secret` dan `.superi_config.json.bak` ditambahkan ke `.gitignore`.

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

[1.2.1]: https://github.com/digitalpencaksilat/superi-apps/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/digitalpencaksilat/superi-apps/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/digitalpencaksilat/superi-apps/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/digitalpencaksilat/superi-apps/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/digitalpencaksilat/superi-apps/releases/tag/v1.0.0
