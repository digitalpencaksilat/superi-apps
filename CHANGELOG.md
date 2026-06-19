# Changelog

Semua perubahan penting pada project ini akan didokumentasikan di file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/),
dan project ini menggunakan [Semantic Versioning](https://semver.org/lang/id/).

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

[1.0.0]: https://github.com/digitalpencaksilat/superi-apps/releases/tag/v1.0.0
