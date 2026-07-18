#!/usr/bin/env python3
"""Shared settings services for classic and Textual SUPER-I interfaces."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AutoSnapshot:
    enabled: bool
    window_start: int
    window_end: int
    hours: tuple[int, ...]
    types: tuple[str, ...]
    sync_portal: bool
    retry_attempts: int
    retry_delay: int
    portal_ready: bool
    superi_ready: bool
    scheduler_platform: str
    scheduler_installed: int
    scheduler_expected: int
    scheduler_health: str


@dataclass(frozen=True)
class PhotoSnapshot:
    effective_source: str
    configured_source: str
    source_origin: str
    history_days: int
    pool_count: int
    feeder_folders: int
    feeder_files: int
    transformer_folders: int
    transformer_files: int
    voltage_folders: int
    voltage_hv: int
    voltage_mv: int
    voltage_total: int
    total_manual: int
    error: str = ""


@dataclass(frozen=True)
class PoolDetail:
    feeders: tuple[tuple[str, int, str, str], ...] = field(default_factory=tuple)
    transformers: tuple[tuple[str, int, str], ...] = field(default_factory=tuple)
    voltages: tuple[tuple[str, int, int, int, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PhotoTestRow:
    item: str
    data_type: str
    run: str
    size: int
    source: str
    variant: str
    mode: str
    error: str = ""


@dataclass(frozen=True)
class SchedulePlan:
    platform: str
    start: int
    end: int
    entries: tuple[tuple[str, int, int], ...]
    cron_lines: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CredentialSnapshot:
    nip: str
    superi_password_set: bool
    portal_user: str
    portal_password_set: bool
    config_path: str

    @property
    def superi_ready(self) -> bool:
        return bool(self.nip and self.superi_password_set)

    @property
    def portal_ready(self) -> bool:
        return bool(self.portal_user and self.portal_password_set)


def _core():
    import superi_app

    return superi_app


def get_credential_snapshot() -> CredentialSnapshot:
    core = _core()
    cfg = core.load_config()
    return CredentialSnapshot(
        nip=str(cfg.get("nip", "")),
        superi_password_set=bool(cfg.get("password")),
        portal_user=str(cfg.get("portal_user", "")),
        portal_password_set=bool(cfg.get("portal_password")),
        config_path=str(core.CONFIG_FILE),
    )


def update_credentials(
    *,
    nip: Optional[str] = None,
    password: Optional[str] = None,
    portal_user: Optional[str] = None,
    portal_password: Optional[str] = None,
) -> CredentialSnapshot:
    """Atomically apply supplied credential fields; None preserves old values."""
    core = _core()
    cfg = core.load_config()
    updates = {
        "nip": nip,
        "password": password,
        "portal_user": portal_user,
        "portal_password": portal_password,
    }
    for key, value in updates.items():
        if value is not None:
            cfg[key] = str(value).strip()
    if not cfg.get("nip") or not cfg.get("password"):
        raise ValueError("NIP dan password SUPER-I wajib lengkap")
    cfg.setdefault("portal_url", "http://10.3.187.6/apdjakarta")
    cfg.setdefault("portal_gi_id", "143")
    cfg.setdefault("gi_id", "222")
    core.save_config(cfg)
    return get_credential_snapshot()


def get_auto_snapshot(include_scheduler: bool = True) -> AutoSnapshot:
    core = _core()
    cfg = core.load_config()
    start = int(cfg.get("auto_window_start", 22))
    end = int(cfg.get("auto_window_end", 5))
    hours = tuple(core._expand_window_to_hours(start, end))
    expected = len(hours)
    installed = 0
    scheduler_platform = "Task Scheduler" if platform.system() == "Windows" else "cron"
    if include_scheduler:
        try:
            installed = core.win_task_count_installed() if platform.system() == "Windows" else core.cron_count_installed()
        except Exception:
            installed = 0
    health = "BELUM"
    if installed >= expected and expected:
        health = "COMPLETE"
    elif installed:
        health = "PARTIAL"
    return AutoSnapshot(
        enabled=bool(cfg.get("auto_enabled", False)),
        window_start=start,
        window_end=end,
        hours=hours,
        types=tuple(t for t in ("penyulang", "trafo", "tegangan") if t in cfg.get("auto_types", ["penyulang", "trafo", "tegangan"])),
        sync_portal=bool(cfg.get("auto_sync_portal", True)),
        retry_attempts=int(cfg.get("auto_retry_attempts", 5)),
        retry_delay=int(cfg.get("auto_retry_delay", 10)),
        portal_ready=bool(cfg.get("portal_user") and cfg.get("portal_password")),
        superi_ready=bool(cfg.get("nip") and cfg.get("password")),
        scheduler_platform=scheduler_platform,
        scheduler_installed=installed,
        scheduler_expected=expected,
        scheduler_health=health,
    )


def set_auto_enabled(enabled: bool) -> AutoSnapshot:
    core = _core()
    cfg = core.load_config()
    cfg["auto_enabled"] = bool(enabled)
    cfg.setdefault("auto_window_start", 22)
    cfg.setdefault("auto_window_end", 5)
    cfg.setdefault("auto_types", ["penyulang", "trafo", "tegangan"])
    cfg.setdefault("auto_sync_portal", True)
    cfg.setdefault("auto_retry_attempts", 5)
    cfg.setdefault("auto_retry_delay", 10)
    core.save_config(cfg)
    return get_auto_snapshot(include_scheduler=False)


def set_auto_window(start: int, end: int) -> AutoSnapshot:
    if not 0 <= int(start) <= 23 or not 0 <= int(end) <= 23:
        raise ValueError("Jam harus berada di antara 0 dan 23")
    core = _core()
    cfg = core.load_config()
    cfg["auto_window_start"] = int(start)
    cfg["auto_window_end"] = int(end)
    core.save_config(cfg)
    return get_auto_snapshot(include_scheduler=False)


def set_auto_types(types) -> AutoSnapshot:
    selected = [t for t in ("penyulang", "trafo", "tegangan") if t in set(types)]
    if not selected:
        raise ValueError("Minimal satu tipe data harus dipilih")
    core = _core()
    cfg = core.load_config()
    cfg["auto_types"] = selected
    core.save_config(cfg)
    return get_auto_snapshot(include_scheduler=False)


def set_auto_sync(enabled: bool) -> AutoSnapshot:
    core = _core()
    cfg = core.load_config()
    cfg["auto_sync_portal"] = bool(enabled)
    core.save_config(cfg)
    return get_auto_snapshot(include_scheduler=False)


def build_schedule_plan(start: int, end: int) -> SchedulePlan:
    core = _core()
    if platform.system() == "Windows":
        tasks = tuple(core._generate_win_tasks(start, end))
        return SchedulePlan("Task Scheduler", start, end, tasks)
    lines = tuple(core._generate_cron_lines(start, end))
    entries = []
    for line in lines:
        parts = line.split()
        entries.append((f"SUPER-I-Auto-{int(parts[1]):02d}", int(parts[1]), int(parts[0])))
    return SchedulePlan("cron", start, end, tuple(entries), lines)


def install_scheduler(start: int, end: int, plan: Optional[SchedulePlan] = None):
    core = _core()
    plan = plan or build_schedule_plan(start, end)
    if platform.system() == "Windows":
        return core.win_task_install(start, end, planned_tasks=plan.entries)
    return core.cron_install(start, end, planned_lines=plan.cron_lines)


def uninstall_scheduler():
    core = _core()
    return core.win_task_uninstall() if platform.system() == "Windows" else core.cron_uninstall()


def scheduler_lines() -> list[str]:
    core = _core()
    if platform.system() == "Windows":
        lines = []
        for h in range(24):
            name = f"{core.WIN_TASK_PREFIX}-{h:02d}"
            result = subprocess.run(["schtasks", "/query", "/tn", name, "/fo", "list", "/v"], capture_output=True, text=True)
            if result.returncode == 0:
                lines.append(name)
                lines.extend("  " + line for line in result.stdout.splitlines()[:8])
        return lines
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if core.CRON_MARKER in line or "superi_auto" in line]


def get_photo_snapshot() -> PhotoSnapshot:
    core = _core()
    cfg = core.load_config()
    configured = str(cfg.get("photo_source", "pool")).lower()
    env_source = os.environ.get("SUPERI_PHOTO_SOURCE", "").strip().lower()
    origin = "env" if env_source in ("pool", "manual") else "config" if "photo_source" in cfg else "default"
    effective = core.get_photo_source()
    stats = {"pool": 0, "manual": {}, "total_manual": 0}
    error = ""
    try:
        if core.hu and hasattr(core.hu, "get_pool_stats"):
            stats = core.hu.get_pool_stats()
        else:
            error = "Humanizer tidak tersedia"
    except Exception as exc:
        error = str(exc)
    manual = stats.get("manual", {})
    bp = manual.get("beban-penyulang", {})
    bt = manual.get("beban-trafo", {})
    tt = manual.get("tegangan-trafo", {})
    return PhotoSnapshot(
        effective_source=effective,
        configured_source=configured if configured in ("pool", "manual") else "pool",
        source_origin=origin,
        history_days=core.get_history_days(),
        pool_count=int(stats.get("pool", 0)),
        feeder_folders=int(bp.get("folders", 0)),
        feeder_files=int(bp.get("files", 0)),
        transformer_folders=int(bt.get("folders", 0)),
        transformer_files=int(bt.get("files", 0)),
        voltage_folders=int(tt.get("folders", 0)),
        voltage_hv=int(tt.get("hv", 0)),
        voltage_mv=int(tt.get("mv", 0)),
        voltage_total=int(tt.get("total", 0)),
        total_manual=int(stats.get("total_manual", 0)),
        error=error,
    )


def set_photo_source(source: str) -> PhotoSnapshot:
    if not _core().set_photo_source(source):
        raise ValueError("Sumber foto harus pool atau manual")
    return get_photo_snapshot()


def set_history_days(days: int) -> PhotoSnapshot:
    if int(days) not in (3, 7, 14):
        raise ValueError("History harus 3, 7, atau 14 hari")
    core = _core()
    cfg = core.load_config()
    cfg["history_days"] = int(days)
    core.save_config(cfg)
    return get_photo_snapshot()


def get_pool_details() -> PoolDetail:
    core = _core()
    base = Path(core.SCRIPT_DIR) / "photo" / "manual"
    image_ext = {".jpg", ".jpeg", ".png"}
    off_names = set()
    mapping = base / "NAMA_MAPPING.json"
    try:
        data = json.loads(mapping.read_text(encoding="utf-8"))
        off_names = {name for name, item in data.get("beban-penyulang", {}).items() if item.get("cb") == "OFF"}
    except Exception:
        pass

    def count(path: Path):
        try:
            return sum(1 for item in path.iterdir() if item.is_file() and item.suffix.lower() in image_ext)
        except Exception:
            return 0

    feeders = []
    path = base / "beban-penyulang"
    if path.is_dir():
        for folder in sorted((p for p in path.iterdir() if p.is_dir()), key=lambda p: p.name):
            cb = "OFF" if folder.name in off_names else "ON"
            feeders.append((folder.name, count(folder), cb, "Skip input; foto disimpan" if cb == "OFF" else "Siap"))
    transformers = []
    path = base / "beban-trafo"
    if path.is_dir():
        for folder in sorted((p for p in path.iterdir() if p.is_dir()), key=lambda p: p.name):
            transformers.append((folder.name, count(folder), "Siap"))
    voltages = []
    path = base / "tegangan-trafo"
    if path.is_dir():
        for folder in sorted((p for p in path.iterdir() if p.is_dir()), key=lambda p: p.name):
            hv, mv = count(folder / "hv"), count(folder / "mv")
            voltages.append((folder.name, hv, mv, hv + mv, "Terpisah" if hv and mv else "Periksa folder"))
    return PoolDetail(tuple(feeders), tuple(transformers), tuple(voltages))


def run_photo_random_test(source: Optional[str] = None) -> list[PhotoTestRow]:
    core = _core()
    if not core.hu:
        raise RuntimeError("Humanizer tidak tersedia")
    source = source or core.get_photo_source()
    rows = []
    items = [("CASABLANCA4", "beban-penyulang"), ("LABORATORIUM", "beban-penyulang"), ("TRAFO 1", "beban-trafo")]
    for item, data_type in items:
        for run in range(1, 4):
            try:
                payload = core.hu.rand_jpeg_bytes(item_name=item, data_type=data_type, photo_source=source)
                meta = dict(core.hu.get_last_meta())
                rows.append(PhotoTestRow(item, data_type, str(run), len(payload), meta.get("src_basename", "—"), meta.get("variant", "—"), meta.get("source_mode", "—")))
            except Exception as exc:
                rows.append(PhotoTestRow(item, data_type, str(run), 0, "—", "—", "—", str(exc)))
    for subtype in ("HV", "MV"):
        try:
            payload = core.hu.rand_jpeg_bytes(item_name="TRAFO 1", data_type="tegangan-trafo", subtype=subtype, photo_source=source)
            meta = dict(core.hu.get_last_meta())
            rows.append(PhotoTestRow("TRAFO 1", "tegangan-trafo", subtype, len(payload), meta.get("src_basename", "—"), meta.get("variant", "—"), meta.get("folder_label", subtype)))
        except Exception as exc:
            rows.append(PhotoTestRow("TRAFO 1", "tegangan-trafo", subtype, 0, "—", "—", "—", str(exc)))
    return rows


def filename_samples() -> list[tuple[str, str]]:
    core = _core()
    if not core.hu or not hasattr(core.hu, "rand_filename"):
        return []
    ts = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%dT%H:%M:%S.123Z")
    return [(kind, core.hu.rand_filename(ts, idx=0, data_type=kind, subtype="HV" if "tegangan" in kind else None)) for kind in ("beban-penyulang", "beban-trafo", "tegangan-trafo")]


PHOTO_GUIDE = """# Panduan Foto Manual

## Mengapa per-item?
Foto manual membedakan panel fisik setiap penyulang dan trafo. Mode pool lebih cepat, tetapi visual sumbernya sama untuk semua item.

## Cara mengambil foto
- Penyulang: 2-3 foto, close-up, wide, dan sudut 45 derajat.
- Beban trafo: full panel dan close meter.
- Tegangan trafo: pisahkan foto HV dan MV ke folder `hv/` dan `mv/`.
- Simpan di `photo/manual/{tipe}/{NAMA}/`.

## Transformasi output
- Ukuran 720x720 dengan crop jitter.
- JPEG baseline quality 82-93 tanpa EXIF.
- Varian: asli 40%, blur ringan 20%, blur berat 10%, glare 15%, noisy gelap 15%.
- Filename upload tetap humanized.

## CB OFF dan lifecycle
Foto untuk tujuh penyulang CB OFF tetap disimpan, tetapi input dilewati. File sumber bersifat read-only dan tidak dihapus setelah digunakan.
"""


AUTO_GUIDE = """# Panduan Auto Mode

## Scheduler otomatis
Satu jadwal dibuat untuk setiap jam aktif. Menit dipilih acak antara 3-38 dan menghindari kelipatan lima.

## macOS / Linux
Gunakan menu **Kelola Jadwal** untuk memasang cron secara otomatis. Terminal mungkin memerlukan izin Full Disk Access.

## Windows
Gunakan menu yang sama untuk membuat Task Scheduler `SUPER-I-Auto-HH`. Task menjalankan `superi.bat auto` dari folder project.

## Syarat
- Komputer menyala dan tidak sleep.
- Akun SUPER-I sudah clock-in.
- Jaringan internal PLN dan internet tersedia.
- Auto Mode harus aktif walaupun scheduler sudah terpasang.
"""
