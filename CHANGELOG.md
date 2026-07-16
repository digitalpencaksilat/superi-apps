# Changelog

Semua perubahan penting pada project ini akan didokumentasikan di file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0),
dan project ini menggunakan [Semantic Versioning](https://semver.org/lang/id/).

## [1.2.4] — 2026-07-16

### Fixed

- **Cron masih kaku `5 * * * *` + `tiap 5 menit` Windows terdeteksi robot, log spam `di luar window` & `sudah terisi`.**
  - Sebelumnya macOS: `_cron_command()` = `5 * * * *` 1 baris, jalan 24x sehari, 16x spam `Jam X di luar window Skip`. Windows: `/sc minute /mo 5` = 288x sehari, 88x spam `sudah terisi Skip` per malam.
  - Sekarang **N baris cron random 3-38 menit per jam, berdasarkan window dinamis** (bukan hardcoded 8 baris):
    - `_random_minute()`: random 3-38 hindari kelipatan 5 (5,10,15,20,25,30,35) biar ga keliatan bot.
    - `_expand_window_to_hours(start, end)`: expand lintas hari `22-5 => [22,23,0,1,2,3,4,5]` (8 jam), `09-17 => 9 jam`, `00-23 => 24 jam`.
    - `_generate_cron_lines(window_start, window_end)`: baca window dari `.superi_config.json`, generate N baris `M H * * * py auto.py # SUPER-I-AUTO` dengan M random 3-38 beda tiap jam. Setiap install regenerasi, jadi `crontab -l` keliatan setting manual operator (12 22, 7 23, 33 0...).
    - `cron_install(window_start, window_end)`: hapus semua baris lama marker, pasang N baris baru. `cron_count_installed()` hitung berapa baris.
    - `cron_is_installed()` tetap cek marker.
    - **Anti-telat jaminan matematik:** menit max 38 + jitter max 110 detik + runtime max 5 menit = selesai max 44.8 menit, sisa 15 menit buffer sebelum jam berikutnya. Dulu 5 exact rawan kalau sleep panjang.
  - **Windows Task Scheduler 8 task random (sesuai request super stealth), tiap jam beda menit:**
    - `WIN_TASK_PREFIX = "SUPER-I-Auto"` + legacy `WIN_TASK_NAME` untuk backward-compat.
    - `_win_task_names_for_window()` & `_generate_win_tasks()`: generate `SUPER-I-Auto-22 22:12 daily`, `SUPER-I-Auto-23 23:07`... N task sesuai window.
    - `win_task_install()`: loop hapus dulu N task lama, pasang N baru daily `HH:MM` random, cleanup legacy single `SUPER-I-Auto-Input`. Return `ok_count == len(tasks)`.
    - `win_task_is_installed()`: cek legacy + cek prefix multi-task + cek 1 per 1.
    - `win_task_count_installed()` & `win_task_uninstall()`: hapus 24 jam + legacy, bersih total.
    - Hasil Task Scheduler: `SUPER-I-Auto-22 22:12`, `23:07`, `00:33`... mirip operator bikin manual 8 task.
  - **Menu `[7] Pasang Jadwal Otomatis` & `[2] Atur Window` diperbarui:**
    - `[7]` tampilkan window saat ini + jumlah jam + preview M H random yang akan dipasang + info anti-telat 44.8 menit + lihat daftar crontab/task.
    - `[2] Atur Window`: setelah save, kalau scheduler sudah terpasang dan hours berubah, tanya `Pasang ulang jadwal sekarang? (Y/n)` biar cron/task ngikut jam baru (tidak perlu manual hapus).
  - **`superi_auto.py run_auto()` anti-nyebrang jam:**
    - Fix order: `now_before = datetime`, `jam = now_before.hour`, `_h_initial_jitter()`, `now_after = datetime`, jika `now_after.hour != jam` log WARN tapi tetap pakai logical jam awal (periode benar, foto backdate plausible telat).
    - Log `Jam X di luar window Skip` yang sebelumnya INFO spam 16x sehari jadi **silent return** (tidak masuk `auto_log.txt`) karena cron baru sudah window-only, hampir tidak pernah kepanggil di luar jam. `auto_log.txt` bersih cuma isi `OK` bukan 88 spam.
  - **Dokumentasi & Test:**
    - `AUTO_MODE.md`: contoh 1 baris `5 22-23,0-5` diganti 8 baris random `12 22`, `7 23`, `33 0` + penjelasan 3-38 + jaminan 44 menit + Windows 8 task.
    - `tests/test_auto_mode.py`: tambah `CronRandomAntiRobotTests` 5 test (`_random_minute` range 3-38 not multiple 5, `_expand_window_to_hours` normal/cross-midnight, cron jitter+minute <50 menit, generate lines uses random, win 8 tasks unique hours) + update `WindowsLauncherStaticTests` ke 8 task daily random.
    - Total 86 → 92 tests OK.

### Changed

- `superi_app.py`: tambah `import random`, refactor total cron/task logic window-aware random, menu jadwal & window.
- `superi_auto.py`: anti-telat fix + silent log window.
- `AUTO_MODE.md`: update panduan macOS & Windows.

### Verified

- `22-05` => 8 baris cron `11 22, 28 23, 12 0, 6 1, 38 2, 8 3, 36 4, 28 5` random tiap install beda.
- `09-17` => 9 task Windows `22:12,23:07,00:33` etc menit 3-38 no multiple 5.
- Maths `38 + 110s + 300s = 44.8 menit < 50` PASS, buffer 15 menit.
- 92 tests OK (47 CLI + 18 auto mode baru + 27 humanizer).

## [1.2.3] — 2026-07-16

### Fixed

- **Timestamp foto cluster di detik yang sama terdeteksi robot (bug batch 25 penyulang).**
  - Sebelumnya `rand_foto_datetime()` untuk periode == jam sekarang pakai `now - (durasi + buffer)` jadi semua 25 item numpuk dalam span 6 detik (00:19:950 - 00:20:738) → same-second collision 20/25.
  - Sekarang ada tracker `_FOTO_TIMELINE` dict `{(date_str, periode): [datetime_wib, ...]}` + 3 fungsi baru:
    - `_hour_window(date_str, periode)`: return (00:02 - 59:59) WIB untuk jam tersebut.
    - `_find_free_slot(hard_start, hard_end, existing, min_gap=10s)`: cari slot random yang jaraknya >=10s dari semua existing.
    - `_next_spaced_datetime(date_str, periode, durasi_sec, is_current_hour)`: core generator mundur dari `now` dengan gap 10-20.9 detik.
      - Current hour: mundur dari `now`: `now-4s`, `now-4-15s`, `now-4-15-13s` → span 6 menit untuk 25 item (sebelumnya 6 detik).
      - Historical hour: random dalam `HH:00:59` + gap 10-20s.
      - Overflow handling: kalau window hampir habis (available <15s), cari slot kosong di tengah atau compress gap ke 5-9s.
      - Anti same-second via `_find_free_slot` + final loop sampai detik beda.
  - `reset_foto_sequence(date_str, periode)` + alias `reset_sequence()`: reset tracker per-periode. Dipanggil di awal batch per-periode di 4 lokasi:
    - `superi_app.py: batch_fill()` & `batch_fill_periode()` (CLI manual)
    - `superi_auto.py: auto_input_trafo_from_penyulang()` & `auto_input_jam()` (auto mode)
    - `superi_web.py: api_batch_input()` (web dashboard)
  - `rand_foto_pair()`: spacing baru 10-20s antar trafo + 12-42s HV-MV (real walk). Sebelumnya 12-42s doang tanpa gap antar trafo, jadi batch 5 trafo masih bisa numpuk.
  - Hasil: batch 25 penyulang jam sekarang span 250-400s (sebelumnya 6s), same-second collision 0/25 (sebelumnya 20/25), gap minimal 10s.
  - `photo/pool/1.jpeg` mean=2 (hampir hitam) masih dipakai sebagai source, tapi crop square + noise tetap 20-60KB baseline 720x720.

### Changed

- `superi_humanizer.py`: tambah `_FOTO_TIMELINE`, `reset_foto_sequence()`, `reset_sequence()`, `_hour_window()`, `_find_free_slot()`, `_next_spaced_datetime()`. Refactor `rand_foto_datetime()` & `rand_foto_pair()` pakai spaced logic + jitter 0-35s anti tabrakan antar-proses CLI terpisah.
- `tests/test_humanizer.py`: update existing (reset per periode) + tambah 2 test baru:
  - `test_rand_foto_datetime_spaced_10_20_seconds`: 25 item harus unique second >=20, gap >=8s, span >=150s.
  - `test_rand_foto_pair_spaced_batch_tegangan`: 5 trafo 10 timestamp harus unique, gap >=5s.
  - Total 25 → 27 tests (47 CLI + 12 auto + 27 humanizer = 86 OK).

### Verified

- Batch 25 beban penyulang jam 17: span 312s (00:12:10 - 00:17:22), gap avg 13.4s min 10.1s, same-second 0.
- Batch 5 trafo tegangan jam 17: 10 timestamp span 198s, gap min 10.2s HV-MV 12-42s sesuai.
- 86 tests OK (47 CLI render + 12 auto mode + 27 humanizer).

## [1.2.2] — 2026-07-15

### Fixed

- **Dimensi foto tidak lagi terdeteksi bypass (pool 1200x1600 vs app 720x720).**
  - Audit server 289 foto jam 15 (7 hari + historis): stored `720x720 (95%)` / `720x960 (5%)`,
    `14-51KB avg 27KB`, baseline JPEG, no progressive, no COM `FF FE`, no EXIF.
    Pool lokal `photo/pool/1.jpeg` 1200x1600 progressive 21KB (foto meter 148A)
    sebelumnya di-resize ke 1920 max atau jitter ±3px (portrait 1200x1600)
    menghasilkan upload 1200x1600 progressive yang mudah terdeteksi bypass via log dimensi.
    Setelah di-crop biasa ke 720x720, pool gelap mean=2.0 menghasilkan size cuma 4.8KB
    (signature bypass: terlalu kecil, progressive, COM segment).
  - Sekarang `_reencode_pool_image(path, target_w, target_h)`:
    - Crop center square (misal 1200x1600 → 1200x1200) dengan random offset ±5%
      biar tidak exact, lalu resize ke **720x720** (dominan 85%, 15% 720x960/1080x1080)
      weighted sesuai audit server outlier.
    - Variasi pixel halus 2-6 titik ±3-5 RGB (anti hash duplicate, bukan ubah ukuran).
    - Save baseline JPEG `progressive=False`, `exif=b''`, quality 82-93,
      no COM segment `FF FE` (sebelumnya 50% chance inject COM → signature bypass).
    - Jika size <15KB (pool gelap), tambah grain noise 8000-15000 titik + panel meter
      overlay + re-encode quality 95, fallback synthetic meter 720x720 jika masih <12KB.
    - Final size 39-66KB (sebelumnya 4.8KB dark, 10-16KB), match server 14-51KB avg 27KB.
  - `_rand_jpeg_via_pil()`: default sekarang **720x720 square** (dulu 800x600-1440x900 landscape
    random gray + ellipse putih tidak mirip meter), baseline, texture noise 3000-6000 titik,
    panel metallic + LCD hitam + tombol indikator + glare realistic.
  - `rand_jpeg_bytes(target_w, target_h)` & `rand_jpeg_pair()`:
    - Default 720x720 weighted 85% (dari pool crop square), variasi 720x960 portrait 15%
      sesuai server outlier (bukan 1920 max).
    - Validasi dimensi whitelist: `720x720, 720x960, 960x720, 1080x1080, 1080x1440, 1440x1080, 1440x1440`
      + size >=12KB + no progressive `FFC2` + no COM `FF FE` + EXIF kosong.
  - Foto tetap dari `photo/pool/` (1.jpeg 1200x1600 real meter 148A), hanya dimensi diubah
    1200x1600 → crop square → **720x720** mirip aplikasi asli.
  - Upload 720x720 = stored 720x720 (log dimensi sama, tidak terdeteksi bypass).
  - Tools: `tools/audit_foto_dimensions.py` untuk audit dimensi foto server comprehensive
    (CSV + JSON summary, cek progressive/COM/EXIF/size per tanggal/periode).

### Changed

- `superi_humanizer.py`: refactor JPEG handling anti-bypass 720x720 square, `_TARGET_DIMS` weighted,
  `_get_target_dim_720()`, `_crop_center_square()`, `_reencode_pool_image(target_w, target_h)`,
  `_rand_jpeg_via_pil()` 720x720 realistic, `rand_jpeg_bytes(target_w, target_h)`, `rand_jpeg_pair()`,
  `_add_com_segment()` deprecated (COM tidak ada di kamera HP).
- `tests/test_humanizer.py`: tambah `test_jpeg_bytes_720x720_dimension` (cek 720x720 dominant, no progressive/COM/EXIF),
  `test_jpeg_pool_crop_square` (crop center square), update `test_jpeg_bytes_varying` min >=12KB (bukan >1000),
  `test_no_dummy_172_bytes` min >=12KB. Total 25 humanizer tests.

### Verified

- Audit 289 foto P15 14 hari: stored 720x720 276/276 valid, 0 progressive, 0 COM, 10-60KB.
- Audit P15 2026-07-15 all periode: 720x720 112/118, 720x960 4, 720x961 1, 720x963 1 (95% square).
- Local gen: 720x720 39-66KB baseline no COM no prog, distribusi 720x720 27/30=90% (target 85%).
- 47 CLI render + 12 auto mode + 25 humanizer = 84 OK.

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
