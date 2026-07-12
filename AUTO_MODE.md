# 🤖 Panduan Auto Mode — Input & Sync Otomatis

Modul auto menjalankan input beban/tegangan + sync ke Portal APD **otomatis tanpa interaksi**, cocok untuk malam hari saat operator tidur.

## ⚠️ Syarat WAJIB (kalau tidak terpenuhi, auto gagal di jam itu)

1. **Komputer menyala & tidak sleep** di jam jadwal
2. **Terhubung jaringan internal PLN** (untuk Portal APD `10.3.187.6`)
3. **Akun SUPER-I sudah clock-in** (absen masuk) hari itu
4. **Internet aktif** (untuk SUPER-I APP)

## 🛡️ Safety Features

- **Anomaly guard**: nilai yang menyimpang >20% dari rata-rata histori akan di-SKIP (tidak diinput), dicatat sebagai warning di log
- **Window jam**: hanya jalan di rentang waktu tertentu (default 22:00-05:00)
- **Skip terisi**: item yang sudah ada datanya tidak ditimpa
- **Logging**: semua aktivitas tercatat di `auto_log.txt`
- **Toggle**: bisa di-on/off kapan saja tanpa hapus jadwal

## Konfigurasi Auto

```bash
superi auto --enable      # Aktifkan + set default (window 22-05)
superi auto --disable     # Nonaktifkan
superi auto --status      # Lihat status
```

Edit manual di `.superi_config.json`:
```json
{
  "auto_enabled": true,
  "auto_window_start": 22,
  "auto_window_end": 5,
  "auto_types": ["penyulang", "trafo", "tegangan"],
  "auto_sync_portal": true
}
```

## Test Manual Dulu (sebelum jadwalkan)

```bash
superi auto --jam 23 --dry-run    # Preview jam 23, tanpa input
superi auto --jam 23              # Beneran input jam 23
```

---

## 🍎 macOS — Setup Cron

1. Edit crontab:
   ```bash
   crontab -e
   ```

2. Tambahkan baris ini (jalan tiap jam, menit ke-5):
   ```
   5 22-23,0-5 * * * /Applications/XAMPP/htdocs/superi-apps/.venv/bin/python3 /Applications/XAMPP/htdocs/superi-apps/superi_auto.py >> /Applications/XAMPP/htdocs/superi-apps/auto_log.txt 2>&1
   ```
   
   Penjelasan `5 22-23,0-5 * * *`:
   - Menit 5, jam 22-23 dan 00-05, setiap hari
   - Auto mode internal juga cek window, jadi aman

3. Simpan & keluar. Cek terjadwal:
   ```bash
   crontab -l
   ```

**PENTING macOS**: Supaya laptop tidak sleep di malam hari, atur:
```bash
# Cegah sleep saat charger terpasang (System Settings → Battery → Options)
# Atau pakai caffeinate saat perlu:
caffeinate -s
```

---

## 🪟 Windows — Setup Task Scheduler

1. Buka **Task Scheduler** (cari di Start Menu)

2. **Create Basic Task**:
   - Name: `SUPER-I Auto Input`
   - Trigger: **Daily**, repeat **every 1 hour**
   - Action: **Start a program**
     - Program: `C:\superi-apps\superi.bat`
     - Arguments: `auto`
     - Start in: `C:\superi-apps`

3. **Settings tambahan** (penting):
   - ✅ "Run whether user is logged on or not"
   - ✅ "Wake the computer to run this task" (kalau mau bangunin dari sleep)
   - ✅ "Run task as soon as possible after a scheduled start is missed"

4. Auto mode internal cek window (22-05), jadi walau task jalan tiap jam, cuma eksekusi di malam hari.

**PENTING Windows**: Atur **Power Options** supaya tidak sleep, atau centang "Wake the computer to run this task".

---

## Cek Hasil

Lihat log aktivitas:
```bash
# macOS/Linux
tail -50 auto_log.txt

# Windows
type auto_log.txt
```

Contoh log sukses:
```
[2026-06-19 23:05:01] [INFO] AUTO MODE: jam 23:00, types=penyulang,trafo,tegangan
[2026-06-19 23:05:02] [INFO] SUPER-I login OK: JULIAN SUDIBYO PRATAMA
[2026-06-19 23:05:03] [INFO]   [OK] CASABLANCA4 P23: 35Ampere
[2026-06-19 23:05:15] [INFO] INPUT SELESAI: ✓27 ✗0 ⊘0 ⚠0
[2026-06-19 23:05:20] [INFO]   Sync ke Portal APD selesai
```

### Perhitungan Beban Trafo

Saat tipe `penyulang` dan `trafo` aktif, urutan Auto Mode selalu:

```text
input dan retry penyulang → ambil ulang data SUPER-I → hitung trafo → tegangan
```

- Hanya penyulang dengan `statusCB` `ON` yang dijumlahkan.
- Relasi penyulang ke trafo dibaca dari respons SUPER-I.
- Penyulang aktif tanpa data pada periode tersebut dihitung sebagai `0 A` dan
  dicatat sebagai fallback pada log.
- Beban trafo yang sudah terisi tidak ditimpa.
- Setelah input, data trafo diambil ulang untuk memastikan nilainya tersimpan;
  kegagalan akan mengikuti konfigurasi retry Auto Mode.

## Matikan Auto

```bash
superi auto --disable          # Stop auto (jadwal tetap ada tapi tidak eksekusi)
# atau hapus cron job / Task Scheduler task
```
