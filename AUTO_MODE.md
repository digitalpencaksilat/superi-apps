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

## 🍎 macOS — Setup Cron (Random Menit 3-38 Anti-Robotik)

**Cara otomatis (direkomendasikan):**
```bash
superi cli → [D] Auto Mode → [7] Pasang Jadwal Otomatis
```
Sistem otomatis bikin **N baris cron** sesuai window jam kamu, tiap jam menit random **3-38** (bukan 5 exact), + jitter 2-110 detik di dalam script.

Contoh hasil `crontab -l` untuk window `22-05` (8 jam = 8 baris):
```
12 22 * * * /Applications/XAMPP/htdocs/superi-apps/.venv/bin/python3 /Applications/XAMPP/htdocs/superi-apps/superi_auto.py >> /Applications/XAMPP/htdocs/superi-apps/auto_log.txt 2>&1 # SUPER-I-AUTO
7 23 * * * /Applications/XAMPP/htdocs/superi-apps/.venv/bin/python3 /Applications/XAMPP/htdocs/superi-apps/superi_auto.py >> /Applications/XAMPP/htdocs/superi-apps/auto_log.txt 2>&1 # SUPER-I-AUTO
33 0 * * * /Applications/XAMPP/htdocs/superi-apps/.venv/bin/python3 /Applications/XAMPP/htdocs/superi-apps/superi_auto.py >> /Applications/XAMPP/htdocs/superi-apps/auto_log.txt 2>&1 # SUPER-I-AUTO
19 1 * * * /Applications/XAMPP/htdocs/superi-apps/.venv/bin/python3 /Applications/XAMPP/htdocs/superi-apps/superi_auto.py >> /Applications/XAMPP/htdocs/superi-apps/auto_log.txt 2>&1 # SUPER-I-AUTO
4 2 * * * ...
27 3 * * * ...
11 4 * * * ...
36 5 * * * ...
```

**Kenapa random 3-38?** Biar mirip operator setting manual biar ga bentrok, bukan bot menit 5 terus. 
Jaminan tidak telat lewat jam: menit max 38 + jitter max 110 detik = mulai max 39:50 + runtime max 5 menit = selesai max 44, sisa 15 menit buffer sebelum jam berikutnya.

**Setiap install, menitnya regenerate** jadi beda-beda tiap hari (mirip setting manual baru).

Kalau mau manual edit:
```bash
crontab -e
# hapus semua # SUPER-I-AUTO lama, pasang 8 baris random baru sesuai window kamu
crontab -l  # cek
```

**PENTING macOS**: Supaya laptop tidak sleep di malam hari, atur:
```bash
# Cegah sleep saat charger terpasang (System Settings → Battery → Options)
# Atau pakai caffeinate saat perlu:
caffeinate -s
```

---

## 🪟 Windows — Setup Task Scheduler (8 Task Random Menit 3-38)

**Cara otomatis (direkomendasikan):**
```bat
superi cli → [D] Auto Mode → [7] Pasang Jadwal Otomatis
```
Sistem otomatis bikin **N task** sesuai window jam kamu (misal window 22-05 = 8 task), tiap task menit random **3-38 beda tiap jam**, daily.

Contoh Task Scheduler untuk window `22-05` (8 task):
```
SUPER-I-Auto-22  Daily  22:12  superi.bat auto
SUPER-I-Auto-23  Daily  23:07  superi.bat auto
SUPER-I-Auto-00  Daily  00:33  superi.bat auto
SUPER-I-Auto-01  Daily  01:19  superi.bat auto
SUPER-I-Auto-02  Daily  02:04  ...
SUPER-I-Auto-03  Daily  03:27  ...
SUPER-I-Auto-04  Daily  04:11  ...
SUPER-I-Auto-05  Daily  05:36  ...
```
Keliatan kayak operator bikin manual 8 task biar rapi, tiap jam beda menit, super stealth mirip Mac.

**Jaminan anti-telat sama:** menit 3-38 + jitter 110s + runtime 5 menit = selesai max 44.

Kalau mau manual:
1. Buka **Task Scheduler** (Start Menu)
2. Create Task **per jam**: Name `SUPER-I-Auto-22`, Trigger Daily `22:12`, Action `superi.bat auto` di folder project, ulangi untuk 23,00,01,02,03,04,05 dengan menit beda 3-38.
3. Settings: ✅ "Run whether user is logged on or not", ✅ "Wake the computer", ✅ "Run as soon as possible after missed"

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
