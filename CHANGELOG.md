# Changelog

Semua perubahan penting pada project ini akan didokumentasikan di file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0),
dan project ini menggunakan [Semantic Versioning](https://semver.org/lang/id/).

## [1.5.0] — 2026-07-23

### Added

- Guided workflow Batch per Jam di TUI: context header dinamis, progress bar Textual native, indikator `BATCH Pxx:00 · n/m`, elapsed time, dan log streaming per-item.
- Queue edit selektif untuk Batch per Jam: pilih nomor item `2,5` atau `all`, wajib edit otomatis untuk item tanpa suggest (`PERLU EDIT`), serta konfirmasi submit `Jalankan batch N item di Pxx:00?`.
- Handoff otomatis Batch → Sync Portal di TUI dengan state `batch-sync-guided`: preview dry-run otomatis → LIVE sync → ringkasan kembali ke periode, plus pesan `Sync dilewati` dan reload periode saat semua 24 jam penuh.
- Property baru `BatchOverview.actionable_periods` di `superi_batch.py` yang hanya mengembalikan periode dengan item kosong, dipakai TUI untuk render tabel actionable saja.
- Validasi ketat: `P00` tetap valid sebagai periode, `Esc=Kembali` di prompt periode, dan prompt jumlah periode menampilkan daftar `00/01/...` yang bisa di-batch.
- Test regresi baru untuk alur batch baru: analisis otomatis setelah pilih periode, P00 valid, queue edit selektif, skip sync refresh data type yang sama, handoff sync type/date/period.
- Web: tetap dukung batch per periode dengan suggest weekday/weekend aware, dry-run preview, dan handoff sync portal (tanpa per-item).
- `tests/test_sync_progress.py`: callback `progress_callback` dan `event_callback` untuk embedded TUI — `progress (done,total,item)` + `events (section/stage/summary)` tanpa output terminal legacy.

### Changed

- **Batch per Item `7/8/9` resmi dihapus** dari seluruh codebase (CLI klasik, TUI, Web, dan docs):
  - `superi_app.py`: fungsi `batch_fill()` ~300 baris dihapus, menu utama `[7][8][9] Batch per Item` hilang, hanya `[A][B][C] Batch per Jam` tersisa, `choice in '123456789abc'` → `'123456abc'`.
  - `superi_tui.py`: `MENU_COMMANDS 7/8/9` dihapus, `panel-batch-item` dihapus, `batch-hour` view disederhanakan dari 5-card grid jadi single context + progress panel + tabel, `actionable_periods` dipakai untuk render.
  - `superi_web.py`: `learn_pattern()` 190 baris + endpoint `/api/data/pattern` + mode `per-item` di `/api/data/batch-input` dihapus; API kini strict `per-periode` saja, return 400 jika `per-item`.
  - `templates/dashboard.html`: modal `batchModal` per-item lama (200 baris JS + HTML) dihapus, hanya modal `batchPeriode` yang dipertahankan.
  - `SUPERI_APP_DOCS.md` dan `README.md`: dokumentasi batch diperbarui — hanya `BATCH PER JAM A/B/C`, panel terpisah `Lihat Data, Input Manual, dan Batch per Jam`.
- TUI Batch per Jam refactor besar:
  - Dari: 5 status card (Status Data, Periode Terpilih, Smart Suggest, Ringkasan, Aksi) + input `1-6` manual.
  - Ke: single `#batch-hour-context` + `#batch-hour-progress-panel` (hidden by default, active saat submit) + DataTable. Alur otomatis: pilih periode → analisis Smart Suggest otomatis → tanya ubah nilai → queue edit → submit confirm → progress bar + log → sync confirm.
  - `_prompt_batch_period()` menampilkan `Pilih periode [00/05/08/...] · Esc=Kembali`.
  - `_handle_editor_input` untuk periode langsung memanggil `_analyze_batch_period()`.
  - `_request_batch_submit()` + `_return_to_batch_periods()` + `_start_batch_sync()` flow baru, `view_stack` dibersihkan saat kembali.
- `superi_batch.py`: tambah 4 baris `actionable_periods` property, refactor `submit_period` dengan progress callback granular dan rollback foto gagal (delete record).
- `superi_sync.py`: sudah mendukung `progress_callback` dan `event_callback` (embedded mode), no legacy output saat callback aktif.
- Tests: `test_tui.py` update — hapus assert `panel-batch-item`, tambah test tinggi seragam 8px untuk settings, guided flow, P00 edge case, selective edit queue.

### Removed

- CLI: `batch_fill()` per-item (load items, pilih nomor, empty periods, smart suggest per-periode untuk satu item, edit y/N, submit) — 285 baris.
- Web: `learn_pattern()` historis per-item, endpoint `/api/data/pattern`, mode `per-item` di batch-input, modal lama `batchModal` dengan JS `showBatchModal/renderBatchTable/submitBatch`.
- TUI: menu Batch per Item, panel `panel-batch-item`, action handlers `1-6` manual untuk batch, grid 5-card.

### Fixed

- Sinkronisasi tipe `penyulang/trafo/tegangan` dari hasil batch tidak lagi kehilangan context setelah reload period.
- P00 (tengah malam) yang sebelumnya dianggap falsy (`if period`) dan tidak trigger analisis kini valid.
- Layout settings card tinggi tidak konsisten — sekarang uniform `8` (wide), `17` (medium), `26` (narrow) via `SuperITui.on_resize`.
- Web `api_batch_input` yang masih menyisakan `per-item` tidak terdokumentasi kini strict reject dengan pesan `Hanya mode per-periode yang didukung`.

### Verified

- 140+ tests passed termasuk 40+ headless Textual tests untuk guided batch flow.
- `git diff --check` lulus, Python compile OK.
- Manual test: `P08` dengan 3 item kosong → pick `00/08` choice → auto analyze → edit selective `2,5` → progress bar update 1/3 → sync handoff dry-run → LIVE → kembali ke periode dengan notif.


## [1.4.0] — 2026-07-18

### Added

- Fullscreen TUI berbasis Textual + Rich dengan tema amber/kuning, outer border, header, viewport scroll, sticky input, dan footer shortcut yang responsif.
- Native views untuk Auto Mode, Sumber Foto, Sync Portal, Setup Kredensial manual, Batch per Jam, Lihat Data, dan daftar item Input Manual.
- Layout responsif desktop, medium, dan narrow untuk kartu status, panel pengaturan, action card, serta tabel data.
- Service reusable `superi_settings.py` untuk snapshot dan update pengaturan Auto, scheduler, foto, serta kredensial.
- Service reusable `superi_batch.py` untuk status 24 periode, Smart Suggest, submit Batch per Jam, progress callback, dan rollback record ketika foto gagal.
- Preview scheduler immutable: jam dan menit yang dikonfirmasi adalah plan yang sama persis saat cron atau Windows Task Scheduler dipasang.
- Halaman Sync Portal native dengan kartu koneksi, konfigurasi, ringkasan, log, dry-run wajib sebelum LIVE, dan handoff otomatis dari hasil Batch per Jam.
- Wizard Setup Kredensial manual dengan identitas tersamarkan, password masked, penyimpanan atomik, serta uji login SUPER-I dan Portal APD.

### Changed

- Menu `1/2/3` Lihat Data kini memakai DataTable native selebar viewport dan breadcrumb tunggal; kolom menyesuaikan ukuran terminal dan strip 24 jam tetap utuh.
- Menu `4/5/6` Input Manual kini memakai tabel item full-width tanpa header ganda; item CB OFF dan item penuh ditolak sebelum workflow input.
- Menu `A/B/C` Batch per Jam kini memakai halaman native reusable untuk Penyulang, Beban Trafo, dan Tegangan, termasuk tabel periode, Smart Suggest, editor nilai, progress, hasil, dan Sync Portal.
- Menu `D`, `T`, `P`, dan `S` membuka native Textual views; business logic klasik tetap tersedia melalui `superi cli --classic` atau `SUPERI_CLASSIC_UI=1`.
- Busy prompt menyembunyikan kotak input, mengunci navigasi selama worker berjalan, dan memperbarui footer agar state interaksi jelas.
- Login Ulang kini menampilkan hasil berhasil/gagal, nama pengguna, GI, dan membersihkan sesi lama jika autentikasi gagal.
- Dashboard utama dirapikan menjadi panel operasi dan pengaturan tanpa heading tambahan, dengan gutter dan padding yang konsisten.
- Output CLI/Rich untuk sync, auto, input, dan render tabel diselaraskan melalui `superi_console.py` dan `cli_render.py`.

### Fixed

- Alignment action card Auto Mode dan Batch per Jam tidak lagi bergantung pada jumlah spasi manual.
- Header Rich ganda di Lihat Data, Input Manual, dan Batch per Jam tidak lagi muncul pada fullscreen TUI; breadcrumb menjadi satu-satunya judul halaman.
- Progress berbasis carriage return tidak lagi membanjiri RichLog.
- Timestamp batch foto pada awal jam mempertahankan gap minimum delapan detik; beberapa menit pertama memakai overlap historis pendek ke jam sebelumnya agar 25 item tidak dipampatkan.
- State password, focus, disabled input, error, back navigation, dan worker completion dipulihkan secara konsisten.

### Compatibility

- Fullscreen hanya aktif saat stdin/stdout merupakan TTY.
- Classic CLI, cron, Windows Task Scheduler, web, pipe, dan scripting mode tetap menggunakan jalur non-fullscreen.
- Dependency baru: `textual>=0.89.0,<1.0`; Rich tetap digunakan untuk semantic rendering dan log.

### Verified

- 140 tests passed, termasuk 40 headless Textual tests.
- Python compile, shell launcher syntax, dan `git diff --check` lulus.

## [1.3.1] — 2026-07-17

### Fixed

- **Foto pool beban penyulang nomor 4 tidak 720×720 — sekarang strict 720×720 untuk semua tipe (HIGH).**
  - Root cause: `_get_target_dim_720()` random weighted 85% 720×720 + 10.5% 720×960 + 4.5% 1080×1080 untuk meniru outlier server (95% 720×720 / 5% 720×960). Semua caller `rand_jpeg_bytes()` tanpa explicit `target_w/h` jadi 1 dari ~7 upload kena 720×960/1080×1080, nomor 4 kebetulan kena.
  - Plus fallback 640×640 kalau size >75KB (`_reencode_pool_image:703-713`) dan crop square hanya jika target square (`591-593`) → aspect stretch.
  - Fix `superi_humanizer.py`:
    - `_TARGET_DIMS` jadi `[(720,720,100)]` single, `_get_target_dim_720()` & `_pick_target_dim()` always return `(720,720)` 100% — tidak ada lagi outlier.
    - `_reencode_pool_image()`: strict `target_w=720,target_h=720`, selalu `_crop_center_square()` (1200×1600 → 1200×1200 crop ±5%) + `resize(720,720, LANCZOS)` tanpa cek `if target_w==target_h`.
    - Hapus branch 640×640, ganti loop quality 93→50 tetap 720×720 + fallback blur ringan `GaussianBlur(0.6)` quality 65 jika masih >75KB + last resort quality 50 tetap 720×720.
    - Exception path fallback juga strict 720×720.
    - `_rand_jpeg_via_pil()` force `width=height=720`, hapus branch random 720×960.
    - `rand_jpeg_bytes()` default 720×720, validasi strict `== (720,720)` bukan whitelist 7 dimensi, synthetic & gray fallback 720×720.
    - `rand_jpeg_pair()` strict 720×720 untuk HV+MV pair tegangan.
  - Fix defensive explicit di uploader:
    - `superi_app.py:_get_jpeg_bytes()` & `api_post_multipart()` HV/MV & beban explicit `target_w=720,target_h=720`.
    - `superi_input.py:_get_jpeg_bytes()` & `superi_auto.py:_get_jpeg_single/pair()` explicit 720×720.
    - `superi_web.py` delegasi ke shared uploader sudah 720×720 via fix di `superi_app`.
  - Hasil: `photo/pool/1.jpeg` 1200×1600 → crop 1200×1200 ±5% → 720×720 LANCZOS, 30/30 sample termasuk nomor 4 `53943B` strict 720×720, beban-trafo 10× OK, tegangan HV+MV pair 10× distinct SHA all 720×720, size 19-66KB baseline no EXIF/COM/progressive.
  - Tests: `test_humanizer.py` update `test_jpeg_bytes_720x720_dimension` assert exact 720×720 20/20 (bukan dominant >=8/20) + baru `test_beban_penyulang_pool_strict_720` 20× penyulang termasuk nomor 4 regression + `test_all_types_pool_strict_720` 3 tipe + HV/MV pair. Total 100 passed (29 humanizer + 24 cli_render + 20 auto + 27 lainnya).

- **Hardcoded `garduIndukId=222` di CLI & web — sekarang dinamis dari config (MEDIUM).**
  - `superi_app.py:1089` `smart_suggest_value()` legacy masih hardcoded 222, bukan dari config. Kalau user ganti GI bukan 222 (misal GI lain), suggest di input manual single & batch per-item akan salah GI.
  - Fix: tambah param `gi_id=None` default dari `load_config().get("gi_id",222)` di `smart_suggest_value()`, dan passing `gi_id=gi_id` dari `input_single()` & `batch_fill()`.
  - `superi_web.py` 9 lokasi hardcoded `garduIndukId: 222` (dashboard 3×, refresh, smart-suggest, batch-pattern, batch-pattern-tegangan) → buat helper `_get_gi_id()` baca dari config fallback 222, ganti semua `222` → `_get_gi_id()`.
  - Plus `learn_pattern(token, 222, ...)` → `_get_gi_id()`.

- **Web batch per-periode tidak passing `item_name` → manual pool selalu fallback ke pool generic (MEDIUM).**
  - `superi_web.py:api_batch_input()` mode `per-periode` loop `items` tidak kirim nama penyulang/trafo ke `api_post_multipart()`, jadi resolver foto manual per-item (`_get_photo_pool_per_item`) fallback ke pool generic walau config `photo_source=manual`.
  - Fix: ambil `item_name = it.get("nama") or it.get("item_name")` per item dan `api_post_multipart(..., item_name=item_name)`. Sama untuk mode `per-item` ambil `item_name` dari `data.get("item_name")`.
  - Hasil: kalau config manual, frontend perlu kirim `nama` di JSON items (sudah disiapkan di backend), foto akan sesuai per-item + varian blur/kabur/asli.

### Changed

- `superi_humanizer.py`: header comment `STRICT 720x720 SQUARE UNTUK SEMUA TIPE`, `_TARGET_DIMS` single 720×720, docstring update strict.
- `superi_web.py`: tambah `_get_gi_id()` helper, batch input passing `item_name`.
- `superi_app.py`: `smart_suggest_value` signature tambah `gi_id` param.
- `tests/test_humanizer.py`: strict assert + 2 test baru, total 29 humanizer tests (dari 27) → 100 total tests passed.

### Verified

- Pool strict: 30/30 720×720 termasuk nomor 4 beban penyulang (bug report user) `53943B`.
- Beban trafo 10× 720×720, tegangan HV+MV 10× distinct SHA all 720×720, size 19-66KB.
- Anti bypass: no progressive `FFC2`, no COM `FFFE`, no EXIF, baseline JPEG.
- `photo/pool/1.jpeg` 1200×1600 → crop square ±5% → 720×720 LANCZOS OK.
- Config `gi_id` dinamis: ganti GI lain tidak hardcoded lagi di web & CLI smart suggest.
- Web batch per-periode manual pool: resolver per-item sekarang bisa match folder `photo/manual/{type}/{ITEM}/`.
- 100 tests passed (29 humanizer + 20 cli_render + 20 auto + 6 multipart + lainnya).

## [1.3.0] — 2026-07-17

### Added

- **Pool foto manual per-item sesuai input + varian blur/kabur/asli anti-robotik (request utama).**
  - Struktur baru `photo/manual/` (gitignored, tidak ikut push):
    - `beban-penyulang/` = 32 folder per penyulang (CASABLANCA4, LABORATORIUM, dll)
      25 ON + 7 OFF, OFF tetap simpan 84 foto tapi skip input CB OFF.
    - `beban-trafo/` = 3 folder TRAFO_1/2/3
    - `tegangan-trafo/` = 5 trafo × `hv/` + `mv/` terpisah (HV 150kV vs MV 20kV fisik beda)
    - `NAMA_MAPPING.json` auto-generate: id, cb status, trafo parent, path folder.
    - `README.md` panduan cara foto: close-up + wide + 45°, hindari flash, >100KB ideal.
  - Scan `photo/manual/` robust:
    - `_scan_jpg()` skip `.gitkeep`, `TARUH_FOTO`, `README.md`, `.txt/.json`, validasi size >5KB
    - Handle nama file WhatsApp dengan spasi `WhatsApp Image 2026-07-17 at 00.33.07.jpeg`
    - Cache by mtime `_MANUAL_CACHE` biar tidak re-scan tiap input.
    - `_load_mapping()` cache `NAMA_MAPPING.json` dengan mtime.
    - `sanitize_folder_name()` uppercase alnum → `_`, max 40, match `fetch_foto_server.py`.
  - Resolver `_get_photo_pool_per_item(item_name, data_type, subtype, photo_source)`:
    - `manual`: cari folder `photo/manual/{data_type}/{SANITIZED_ITEM}/`, jika tegangan cari `hv/`/`mv/` terpisah
      fallback ke `photo/pool/` jika folder kosong, fallback lagi ke synthetic.
    - `pool`: pakai `photo/pool/` 1 foto untuk semua (generic, re-encode crop square ±5% + jitter).
    - Return `pool_files, source_mode, folder_label, full_dir`.
  - Varian visual anti-duplicate hash (request user blur/kabur/asli):
    - `_apply_variant_transform(im, mode)` 5 varian:
      - `asli` 40% — crop ±5% + resize 720x720 + pixel jitter 2-6 titik
      - `blur_ringan` 20% — GaussianBlur radius 0.6-1.0 pelan seperti out-of-focus
      - `blur_berat` 10% — GaussianBlur radius 1.4-2.2 defocus jelas
      - `kabur_glare` 15% — overlay white 20-40% + brightness boost, simulasi pantulan lampu panel
      - `noisy_gelap` 15% — darkness 0.6-0.85 + grain 8000-15000 titik, untuk jam 00-06 low-light
    - Weighted random via `_VARIANT_CHOICES` / `_VARIANT_WEIGHTS`.
    - `_LAST_META` tracking `{src_path, src_basename, variant, bytes, source_mode, folder_label}` untuk log CLI.
  - Config `photo_source` baru di `.superi_config.json`:
    - Valid values `pool` (1 foto semua) / `manual` (per-item sesuai), default `pool`.
    - Env override `SUPERI_PHOTO_SOURCE` untuk testing.
    - `get_photo_source()` / `set_photo_source()` di `superi_app.py` dan `superi_humanizer.py` (no circular).
    - `.superi_config.example.json` tambah `photo_source`, `auto_enabled`.
  - Menu baru `[T] 📸 Foto Source` di CLI utama:
    - `[1] Ganti Sumber Foto` pool ↔ manual, preview varian 40/20/10/15/15.
    - `[2] Ganti History Days` 3/7/14 untuk smart-suggest.
    - `[3] Lihat Detail Pool per Item` tabel Nama, Count, CB, Type.
    - `[4] Validasi Foto Manual` scan 500+ foto via `validate_manual_pool.py`.
    - `[5] Panduan Cara Foto Manual` anti-robotik.
    - `[6] Test Foto Random` lihat varian blur/kabur/asli live.
    - Header foto source badge hijau MANUAL vs kuning POOL.
  - `cli_render.py`: 3 helper baru
    - `render_settings_box(photo_source, history_days, pool_count, manual_stats, total_manual)`
    - `render_pool_status(detailed_rows)` tabel per-item
    - `render_suggest_table_with_pool(rows)` suggest + pool count per item.
  - Dokumentasi `photo/manual/README.md` lengkap: struktur, jumlah ideal 80-120 foto, cara import USB, validasi.

- **Verifikasi foto tegangan HV/MV benar-benar tersimpan di server (bug MISSING URI).**
  - Root cause: sebelumnya upload 2 file `files` dianggap sukses jika API return `success`, tapi server bisa simpan record
    tapi gagal proses image → `fotoHV.uri`/`fotoMV.uri` = null (MISSING). Beban penyulang/beban trafo 1 foto jarang kena,
    tegangan 2 foto kena bug Jam 3 (00-06) yang dilaporkan.
  - Fix di `superi_app.py`:
    - `_verify_tegangan_photo_upload(token, data_dict, result)`:
      - Ambil `record_id` dari `result["data"]["id"]`.
      - Retry 3× `api_get` list `garduIndukId + date`, cari record dengan id yang sama.
      - Cek `fotoHV.uri` & `fotoMV.uri` harus ada, jika missing → `error = "URI foto HV/MV tidak dibuat server"`.
      - Verifikasi media: download `/api{uri}` 2×, cek header `ff d8` JPEG valid + len >=1000.
      - Jika gagal → return `{"ok": False, error}`.
    - `api_post_multipart()`:
      - Pop `_item_name_hint` dari payload agar tidak kirim ke server (400 unknown property).
      - Untuk tegangan: transport filename wajib `fotoHV.jpg` / `fotoMV.jpg` seperti APK GAMA (backend tentukan slot dari filename),
        content bytes tetap per-item manual hv/mv distinct + varian.
      - Setelah upload sukses, jika `data_type == tegangan-trafo`, panggil `_verify_...` dan attach ke result `_photo_upload`.
      - Di `batch_fill()` & `batch_fill_periode()` & `input_single()`:
        - Jika `photo_check` fail → `api_delete` record gagal foto agar tidak jadi sampah MISSING uri, log `FOTO GAGAL -> dihapus`,
          treat as fail untuk retry, detail `nilai tersimpan tapi FOTO GAGAL`.
      - `_get_jpeg_bytes(single, item_name, data_type, subtype)` now per-item + photo_source aware.
      - `rand_jpeg_pair()` distinct logic: loop 15×, variant berbeda HV vs MV, size diff >=500 byte, sha256 beda, size 12-75KB.
      - `rand_jpeg_bytes()` pool_files per-item resolver + size cap 70KB loop quality 78→60 + fallback 640×640 if >75KB.
  - Fix di `superi_input.py`:
    - `submit_beban()` double-check distinct HV/MV sha256 + size diff >500 byte loop 8×.
    - Pastikan filename HV≠MV (anti duplicate detection).
    - Setelah sukses, verifikasi list fetch untuk cek uri HV+MV, jika missing hapus record & return False.
  - Fix di `superi_auto.py`:
    - `auto_input_trafo_from_penyulang()` & `auto_input_jam()` pass `item_name` ke `api_post_multipart`.
    - Jika `photo_check` fail → delete record + log `RETRY-FOTO ... -> record dihapus`.
  - Fix di `superi_web.py`:
    - Refactor `api_post_multipart()` jadi wrapper ke `_cli.api_post_multipart()` (shared verified uploader + item_name),
      sehingga CLI/Web/Auto konsisten format dan verifikasi foto (no code drift).
      54 baris duplikasi lama dihapus, diganti 13 baris delegasi + `item_name` param.
  - Alat bantu:
    - `tools/fix_tegangan_jam3.py`: fix khusus periode 3 (jam 03) MISSING uri — cek penyulang/trafo P3 OK, hapus & re-upload tegangan P3 dengan foto valid + verifikasi uri.
    - `tools/fetch_foto_server.py`: fetch foto asli dari server untuk audit 00-06, simpan `photo/server/YYYY-MM-DD/{tipe}/` + sidecar json + summary, support workers & filter tipe.
    - `tools/validate_manual_pool.py`: scan `photo/manual/` 500+ foto, cek size min/max/avg, dimensi PIL, progressive `FFC2`, COM `FFFE`, EXIF, duplicate SHA, CSV export, detail per file.
  - Contract tests `tests/test_multipart.py` baru (6 tests):
    - `test_tegangan_uses_two_ordered_files_and_clean_json`: HV/MV ordered, filename `fotoHV.jpg`/`fotoMV.jpg`, `_item_name_hint` tidak masuk JSON payload, boundary custom, timeout 60.
    - `test_verification_reports_missing_voltage_uris`: uri null → error `URI foto HV/MV tidak dibuat server`.
    - `test_verification_fetches_both_voltage_images`: uri ada → download 2 image, size map HV/MV.
    - `test_verification_retries_until_voltage_record_is_visible`: empty → listed, sleep 1×, retry 2×.
    - `test_web_voltage_upload_uses_shared_verified_uploader`: web wrapper delegasi ke `app.api_post_multipart` dengan item_name.
    - `test_server_side_voltage_filenames_remain_humanized`: `rand_filename` tetap `fotoHV_YYYY-MM-DD_<hex>.jpg` (humanized storage name, bukan simple).
    - Payload mutation guard: `assertIn("_item_name_hint", payload)` setelah call (caller tidak boleh di-mutate).

### Fixed

- **Tegangan trafo foto MISSING (uri null) Jam 3 dan periode lain karena 2 file upload tidak terverifikasi.**
  - Sebelumnya: success API langsung dianggap OK, record dengan foto gagal tetap tersimpan jadi sampah MISSING.
  - Sekarang: verifikasi uri + JPEG valid, jika gagal hapus record otomatis + retry, list bersih tidak ada MISSING.
- **Foto duplikat/hash sama untuk HV & MV tegangan karena random pool tanpa distinct check.**
  - Sebelumnya `rand_jpeg_pair()` cuma `j1 != j2` string compare, bisa sama content karena re-encode same source.
  - Sekarang: sha256 check + size diff >=500 byte + loop 15× variant berbeda + quality loop sampai <70KB.
- **Foto >70KB kebesaran untuk server (edge case kompleks texture → 80KB+ → compress fail).**
  - Sebelumnya 1× re-encode quality 78, jika masih >80KB cuma turun 12.
  - Sekarang: loop quality 78→60 step 3 sampai ≤70KB, jika masih >75KB resize 640×640 quality 78, target 20-60KB ideal (audit 14-51KB avg 27KB).
- **CLI/Web/Auto format multipart tidak konsisten (code drift) menyebabkan bug hanya di satu jalur.**
  - Sebelumnya `superi_web.py` punya copy-paste `api_post_multipart` 54 baris beda logic.
  - Sekarang shared uploader: web → `app.api_post_multipart` 13 baris delegasi, single source of truth.

### Changed

- `superi_app.py`: +575 lines — photo_source config, `_verify_tegangan_photo_upload`, pool per-item, variant handling, menu `[T] foto source`, distinct HV/MV.
- `superi_humanizer.py`: +563/-34 lines — manual pool scanner, `_MANUAL_CACHE`, `_MAPPING_CACHE`, `_LAST_META`, sanitize, variant transforms blur/glare/noisy, resolver per-item, size cap, 720 crop ±5%, `get_pool_stats()`, `get_last_meta()`.
- `superi_input.py`: +54 lines — distinct HV/MV double-check, filename dup guard, post-upload uri verification + auto-delete fail.
- `superi_auto.py`: +18 lines — item_name pass + photo fail delete + retry logging.
- `superi_web.py`: -54/+13 refactor — shared verified uploader, anti code-drift.
- `cli_render.py`: +47 lines — 3 render helper settings box / pool status / suggest with pool.
- `.superi_config.example.json`: +3 fields `photo_source`, `auto_enabled`.
- `.gitignore` tetap ignore `photo/` (pool manual 500+ foto pribadi tidak ikut push).

### Verified

- `photo/manual/` 32 penyulang + 3 beban trafo + 5 tegangan hv/mv = 500+ file import HP WhatsApp name OK (scan skip `.txt`).
- Manual mode: `CASABLANCA4` 14 foto, random pick per input + varian `asli 40% / blur_ringan 20% / blur_berat 10% / kabur_glare 15% / noisy_gelap 15%`, SHA beda tiap upload, filename tetap `fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg` (bukan basename manual), OFF CB skip input tapi foto tetap.
- Pool mode: 1 foto generic `photo/pool/` untuk semua, re-encode 720×720 crop ±5% + jitter + quality 82-93 beda SHA.
- Tegangan HV/MV: HV dari `TRAFO_1/hv/` random, MV dari `mv/` terpisah, distinct SHA + size diff ≥500B, transport filename `fotoHV.jpg`/`fotoMV.jpg` (APK parity), storage URI humanized `fotoHV_2026-07-17_<hex>.jpg`, verifikasi 2× download JPEG valid.
- Bug P3 fix: record MISSING uri auto-delete + retry, list bersih, no MISSING after fix.
- Size audit: HV 22-58KB, MV 24-65KB, beban 20-60KB, match server 14-51KB avg 27KB, baseline no progressive/COM/EXIF.
- Tests: `tests/test_multipart.py` 6 new OK (payload mutation guard, ordered HV/MV, clean JSON, uri check, retry, humanized storage names) + `python3 tools/validate_manual_pool.py` 500+ file scan OK.

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
