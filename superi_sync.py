#!/usr/bin/env python3
"""
SUPER-I APP → Portal PLN Sync Tool (Rich Edition - Tema Kuning)
=================================================================
Otomatis fetch data dari SUPER-I APP API lalu sync ke Portal PLN APD Jakarta.

Usage:
  superi sync                    # Menu interaktif (via superi_app)
  superi sync --type all --jam 08       # Sync semua tipe jam 08
  superi sync --type penyulang --jam 09  # Sync beban penyulang jam 09
  superi sync --type trafo --jam 08-10   # Sync beban trafo jam 08 s/d 10
  superi sync --type tegangan --jam 08   # Sync tegangan trafo jam 08
  superi sync --dry-run                  # Preview tanpa nulis

Tanggal default: hari ini. Override: --date 2026-06-19
"""

import json
import sys
import time
import os
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, List, Optional, Tuple

__version__ = "1.4.0"

# ============ PATHS ============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import cli_render

try:
    import superi_humanizer as hu
except Exception:
    hu = None

# Rich console (tema kuning) - fallback jika tidak ada
try:
    import superi_console as sc
    console = sc.console
    RICH = True
except ImportError:
    try:
        from rich.console import Console
        from rich.theme import Theme
        console = Console(theme=Theme({
            "ok": "bold green",
            "err": "bold red",
            "warn": "bold yellow",
            "info": "cyan",
        }), highlight=False)
        RICH = True
        sc = None
    except ImportError:
        console = None
        RICH = False
        sc = None


def _h_sleep(a=0.4, b=1.9):
    if hu:
        hu.human_sleep(a, b)
    else:
        time.sleep(0.55)


def _h_shuffled(seq):
    return hu.shuffled(seq) if hu else list(seq)

# ============ CONFIG LOADER ============
def _load_config():
    cfg_path = os.path.join(SCRIPT_DIR, ".superi_config.json")
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r") as f:
                cfg = json.load(f)
        except Exception as e:
            if RICH and console:
                console.print(f"  [err]✗ Gagal membaca .superi_config.json: {e}[/]")
            else:
                print(f"  \033[91m✗ Gagal membaca .superi_config.json: {e}\033[0m")
    return cfg

_CFG = _load_config()

def _get(key: str, env_key: str, default: str = "") -> str:
    """Priority: ENV var → config file → default."""
    return os.environ.get(env_key) or _CFG.get(key) or default

# ============ SUPER-I API CONFIG ============
SUPER_I_API = "https://super-i-app.plnes.co.id/api"
SUPER_I_AUTH = f"{SUPER_I_API}/auth/login-mobile"
SUPER_I_NIP = _get("nip", "SUPERI_NIP")
SUPER_I_PASS = _get("password", "SUPERI_PASSWORD")
SUPER_I_GI_ID = int(_get("gi_id", "SUPERI_GI_ID", "222"))

SUPER_I_ENDPOINTS = {
    "penyulang": "/gama/opgi-20kv/operator-gi/beban-penyulang",
    "trafo": "/gama/opgi-20kv/operator-gi/beban-trafo",
    "tegangan": "/gama/opgi-20kv/operator-gi/tegangan-trafo",
}

# ============ PORTAL PLN CONFIG ============
PORTAL_URL = _get("portal_url", "PORTAL_URL", "http://10.3.187.6/apdjakarta")
PORTAL_USER = _get("portal_user", "PORTAL_USER")
PORTAL_PASS = _get("portal_password", "PORTAL_PASSWORD")
PORTAL_GI_ID = _get("portal_gi_id", "PORTAL_GI_ID", "143")

PORTAL_ENDPOINTS = {
    "penyulang": {
        "get": "/opdistbeban/beban_penyulang_c/get_beban_penyulang",
        "update": "/opdistbeban/beban_penyulang_c/update_beban",
    },
    "trafo": {
        "get": "/opdistbeban/beban_trafo_c/get_beban_trafo",
        "update": "/opdistbeban/beban_trafo_c/update_beban",
    },
    "tegangan": {
        "get": "/opdistbeban/teg_trafo_c/get_teg_trafo",
        "update": "/opdistbeban/teg_trafo_c/update_beban",
    },
}

# ============ UI (Rich themed yellow) ============
def _rich_header(t):
    if RICH and console and sc:
        sc.header(t)
    elif RICH and console:
        from rich.panel import Panel
        console.print(Panel(f"[bold bright_yellow]{t}[/]", border_style="bright_yellow", box=console.box if hasattr(console, 'box') else None))
    else:
        print(f"\n{'━'*60}\n  {t}\n{'━'*60}")

def header(t):
    _rich_header(t)

def ok(t):
    if RICH and console and sc:
        sc.ok(t)
    elif RICH and console:
        console.print(f"  [ok]✓ {t}[/]" if hasattr(console, 'print') else f"  ✓ {t}")
    else:
        print(f"  \033[92m✓ {t}\033[0m")

def err(t):
    if RICH and console and sc:
        sc.err(t)
    elif RICH and console:
        console.print(f"  [err]✗ {t}[/]")
    else:
        print(f"  \033[91m✗ {t}\033[0m")

def info(t):
    if RICH and console and sc:
        sc.info_msg(t)
    elif RICH and console:
        console.print(f"  [cyan]ℹ {t}[/]")
    else:
        print(f"  \033[96mℹ {t}\033[0m")

def warn(t):
    if RICH and console and sc:
        sc.warn_msg(t)
    elif RICH and console:
        console.print(f"  [warn]⚠ {t}[/]")
    else:
        print(f"  \033[93m⚠ {t}\033[0m")

# Progress helpers
_progress_instance = None
_progress_task = None

def _get_progress():
    """Lazy create progress dengan tema kuning."""
    global _progress_instance
    if not RICH or not console:
        return None
    if _progress_instance is not None:
        return _progress_instance
    if sc:
        _progress_instance = sc.make_simple_progress()
        if _progress_instance is None:
            # fallback
            from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn
            _progress_instance = Progress(
                TextColumn("[progress.description]{task.description}", style="white"),
                BarColumn(bar_width=24, style="dim yellow", complete_style="bright_yellow", finished_style="green"),
                TaskProgressColumn(style="bold bright_yellow"),
                MofNCompleteColumn(),
                TextColumn("[dim]{task.fields[extra]}[/]", justify="left"),
                console=console,
                transient=False,
            )
    else:
        from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn
        _progress_instance = Progress(
            TextColumn("[progress.description]{task.description}", style="white"),
            BarColumn(bar_width=24, style="dim yellow", complete_style="bright_yellow", finished_style="green"),
            TaskProgressColumn(style="bold bright_yellow"),
            MofNCompleteColumn(),
            TextColumn("[dim]{task.fields[extra]}[/]", justify="left"),
            console=console,
            transient=False,
        )
    return _progress_instance

# For compatibility: live_progress used inside do_sync loop
_active_progress = None
_active_task = None
_total_cells_ref = 0

def _start_live_progress(total, label="Sync"):
    """Start Rich progress bar, returns task id."""
    global _active_progress, _active_task, _total_cells_ref
    if not RICH or not console:
        return None
    try:
        prog = _get_progress()
        if prog is None:
            return None
        # If already started, reuse; else start
        if not hasattr(prog, '_started') or not prog._started:
            prog.start()
            prog._started = True
        from rich.progress import Progress
        _active_progress = prog
        _total_cells_ref = total
        _active_task = prog.add_task(f"[bold bright_yellow]{label}[/]", total=total, extra="")
        return _active_task
    except Exception:
        return None

def _update_live_progress(done, name=""):
    """Update existing rich progress."""
    global _active_progress, _active_task
    if _active_progress is None or _active_task is None:
        return
    try:
        nm = name[:18] if name else ""
        _active_progress.update(_active_task, completed=done, extra=nm)
    except Exception:
        pass

def _stop_live_progress():
    """Stop rich progress."""
    global _active_progress, _active_task
    if _active_progress is None:
        return
    try:
        _active_progress.stop()
        _active_progress._started = False
    except Exception:
        pass
    _active_progress = None
    _active_task = None

def live_progress(done, total, name=""):
    """Progress bar - now menggunakan Rich jika tersedia, fallback ke old style."""
    if RICH and _active_progress is not None:
        _update_live_progress(done, name)
    else:
        # Fallback old style
        nm = name[:18].ljust(18) if name else ""
        tail = f"  {nm}" if nm else ""
        sys.stdout.write(f"\r  {cli_render.fmt_progress_bar(done, total)}{tail} ✓\033[K")
        sys.stdout.flush()

def summary_box(label, ok_count, fail_count, skip_count, total):
    """Box ringkasan sync dengan tema kuning."""
    if RICH and console:
        if sc:
            sc.sync_summary(label, ok_count, fail_count, skip_count, total)
        else:
            from rich.panel import Panel
            inner = f"Ringkasan {label}: [bold green]✓ {ok_count} update[/]"
            if fail_count:
                inner += f"  [bold red]✗ {fail_count} gagal[/]"
            if skip_count:
                inner += f"  [dim]⊘ {skip_count} skip[/]"
            inner += f"  [dim]({ok_count+fail_count}/{total})[/]"
            border = "green" if fail_count == 0 else "bright_yellow"
            console.print(Panel(inner, border_style=border, width=66))
    else:
        for line in cli_render.render_sync_summary(label, ok_count, fail_count, skip_count, total):
            print(line)

# ============ SUPER-I API CLIENT ============
def superi_login() -> Optional[str]:
    """Login ke SUPER-I API, return token."""
    try:
        req = urllib.request.Request(SUPER_I_AUTH,
            data=json.dumps({"nip": SUPER_I_NIP, "password": SUPER_I_PASS}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.loads(resp.read())
        if d.get("success"):
            return d["data"]["access_token"]
    except Exception as e:
        err(f"SUPER-I login error: {e}")
    return None

def superi_get(path: str, token: str, params: dict = None):
    """GET request ke SUPER-I API."""
    url = f"{SUPER_I_API}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def fetch_superi_data(data_type: str, token: str, date_str: str) -> Dict:
    """Fetch data dari SUPER-I API."""
    ep = SUPER_I_ENDPOINTS[data_type]
    status, data = superi_get(ep, token, params={"garduIndukId": SUPER_I_GI_ID, "date": date_str})

    if status != 200:
        err(f"SUPER-I fetch failed: HTTP {status}")
        return {}

    items = data.get("data", {}).get("items", [])
    result = {}

    for item in items:
        nama = item.get("nama", "").strip()
        if not nama:
            continue

        if data_type == "tegangan":
            entries = item.get("tegangan", [])
            mv = [None] * 24
            hv = [None] * 24
            for e in entries:
                p = e.get("periode", -1)
                if 0 <= p < 24:
                    mv[p] = e.get("mv")
                    hv[p] = e.get("hv")
            result[nama] = {"mv": mv, "hv": hv}
        else:
            entries = item.get("beban", [])
            jams = [None] * 24
            for e in entries:
                p = e.get("periode", -1)
                if 0 <= p < 24:
                    jams[p] = e.get("beban")
            result[nama] = jams

    return result

# ============ PORTAL PLN CLIENT ============
try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

class PortalPLN:
    def __init__(self):
        if not REQUESTS_OK:
            raise ImportError("requests library needed. Run: pip install requests")
        self.session = requests.Session()

    def login(self) -> bool:
        try:
            r = self.session.post(f"{PORTAL_URL}/login/validate",
                data={'userid': PORTAL_USER, 'password': PORTAL_PASS},
                allow_redirects=True, timeout=10)
            return r.status_code == 200
        except:
            return False

    def fetch_grid(self, data_type: str, date_str: str) -> Dict:
        ep = PORTAL_ENDPOINTS[data_type]["get"]
        try:
            r = self.session.get(f"{PORTAL_URL}{ep}",
                params={'gi': PORTAL_GI_ID, 'dt1': f"{date_str} 00:00:00"}, timeout=15)
            if r.status_code != 200:
                return {}
            data = r.json()
            grid = {}
            for row in data:
                key = row.get('feeder') or row.get('no_trafo') or ''
                key = key.strip()
                if key:
                    grid[key] = row
            return grid
        except:
            return {}

    def update_cell(self, data_type: str, rowdata: Dict, col: str, value) -> bool:
        ep = PORTAL_ENDPOINTS[data_type]["update"]
        params = {'col': col}
        for k, v in rowdata.items():
            params[k] = '' if v is None else v
        params[col] = value
        try:
            r = self.session.get(f"{PORTAL_URL}{ep}", params=params, timeout=10)
            if r.status_code == 200:
                resp = r.json()
                return resp.get('status') == 'success'
        except:
            pass
        return False

# ============ SYNC ENGINE (Rich Progress + Yellow Theme) ============
def do_sync(data_type: str, jam_start: int, jam_end: int, date_str: str, dry_run: bool = True):
    """Full sync: fetch SUPER-I → push Portal PLN. Rich progress + yellow theme."""

    type_labels = {"penyulang": "Beban Penyulang", "trafo": "Beban Trafo", "tegangan": "Tegangan Trafo"}

    # Header with yellow theme
    header(f"SYNC {type_labels[data_type]}")

    # 1. SUPER-I: fetch
    if RICH and console and sc:
        from rich.status import Status
        with console.status(f"[bold bright_yellow]SUPER-I APP: Logging in...[/]", spinner="dots", spinner_style="bright_yellow"):
            token = superi_login()
    else:
        info("SUPER-I APP: Logging in...")
        token = superi_login()

    if not token:
        err("SUPER-I login failed")
        return False

    if not (RICH and sc):
        ok("SUPER-I login OK")
    else:
        console.print(f"  [bold green]✓[/] SUPER-I login OK")

    if RICH and console and sc:
        with console.status(f"[bold bright_yellow]Fetching {data_type} data...[/]", spinner="dots", spinner_style="bright_yellow"):
            superi_data = fetch_superi_data(data_type, token, date_str)
    else:
        info(f"SUPER-I APP: Fetching {data_type} data...")
        superi_data = fetch_superi_data(data_type, token, date_str)

    if not superi_data:
        err("No data from SUPER-I")
        return False

    if RICH and console:
        console.print(f"  [bold green]✓[/] Got [bold bright_yellow]{len(superi_data)}[/] items from SUPER-I")
    else:
        ok(f"Got {len(superi_data)} items from SUPER-I")

    # 2. Portal PLN: login + fetch grid
    if RICH and console and sc:
        with console.status(f"[bold bright_yellow]Portal PLN: Logging in...[/]", spinner="dots", spinner_style="bright_yellow"):
            pln = PortalPLN()
            portal_ok = pln.login()
    else:
        info("Portal PLN: Logging in...")
        pln = PortalPLN()
        portal_ok = pln.login()

    if not portal_ok:
        err("Portal PLN login failed")
        return False

    if RICH and console:
        console.print(f"  [bold green]✓[/] Portal PLN login OK")
    else:
        ok("Portal PLN login OK")

    if RICH and console and sc:
        with console.status(f"[bold bright_yellow]Portal PLN: Fetching grid...[/]", spinner="dots", spinner_style="bright_yellow"):
            grid = pln.fetch_grid(data_type, date_str)
    else:
        info("Portal PLN: Fetching grid...")
        grid = pln.fetch_grid(data_type, date_str)

    if not grid:
        err("Portal PLN grid fetch failed")
        return False

    if RICH and console:
        console.print(f"  [bold green]✓[/] Got [bold bright_yellow]{len(grid)}[/] items from Portal PLN")
    else:
        ok(f"Got {len(grid)} items from Portal PLN")

    # 3. Sync
    mode_label = "DRY-RUN" if dry_run else "LIVE"
    mode_style = "bold yellow" if dry_run else "bold green"
    n_hours = jam_end - jam_start + 1
    cells_per_item = (n_hours * 2) if data_type == "tegangan" else n_hours
    total_cells = len(superi_data) * cells_per_item

    if RICH and console:
        console.print(f"  Mode [{mode_style}]{mode_label}[/] · Jam [bold bright_yellow]{jam_start:02d}-{jam_end:02d}[/] · {len(superi_data)} item · {total_cells} cell")
    else:
        mode = f"\033[93mDRY-RUN\033[0m" if dry_run else f"\033[92mLIVE\033[0m"
        info(f"Mode {mode} · Jam {jam_start:02d}-{jam_end:02d} · {len(superi_data)} item · {total_cells} cell")

    if RICH and console:
        console.print()

    updates = 0; errors = 0; skipped = 0
    error_list = []
    dry_samples = []
    done = 0

    def _normalize(s: str) -> str:
        return ''.join(s.upper().split())

    grid_normalized = {_normalize(k): (k, v) for k, v in grid.items()}

    # Rich progress setup for LIVE mode
    rich_prog = None
    rich_task = None
    use_rich_prog = RICH and not dry_run and console and console.is_terminal

    if use_rich_prog:
        try:
            if sc:
                rich_prog = sc.make_simple_progress()
            if rich_prog is None:
                from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn
                rich_prog = Progress(
                    TextColumn("[progress.description]{task.description}", style="white"),
                    BarColumn(bar_width=24, style="dim yellow", complete_style="bright_yellow", finished_style="green"),
                    TaskProgressColumn(style="bold bright_yellow"),
                    MofNCompleteColumn(),
                    TextColumn("[dim]{task.fields[extra]}[/]", justify="left"),
                    console=console,
                    transient=False,
                )
            rich_prog.start()
            rich_task = rich_prog.add_task(f"[bold bright_yellow]Sync {type_labels[data_type]}[/]", total=total_cells, extra="")
        except Exception:
            rich_prog = None
            rich_task = None

    for name, values in _h_shuffled(list(superi_data.items())):
        rowdata = None
        if name in grid:
            rowdata = grid[name]
        else:
            norm = _normalize(name)
            if norm in grid_normalized:
                _, rowdata = grid_normalized[norm]

        if rowdata is None:
            skipped += cells_per_item
            done += cells_per_item
            if rich_prog and rich_task is not None:
                try:
                    rich_prog.update(rich_task, completed=done, extra=name[:16])
                except Exception:
                    pass
            elif not dry_run:
                live_progress(done, total_cells, name)
            continue

        if data_type == "tegangan":
            mv_vals = values.get("mv", [])
            hv_vals = values.get("hv", [])
            for h in range(jam_start, jam_end + 1):
                if h < len(mv_vals) and mv_vals[h] is not None:
                    col = f"j{h:02d}"
                    existing = rowdata.get(col)
                    if existing is not None and abs(float(existing) - float(mv_vals[h])) < 0.001:
                        skipped += 1
                    elif dry_run:
                        updates += 1
                        if len(dry_samples) < 6:
                            dry_samples.append(f"{name} {col}(MV): {existing} → {mv_vals[h]}")
                    else:
                        if pln.update_cell(data_type, rowdata, col, mv_vals[h]):
                            updates += 1
                        else:
                            errors += 1; error_list.append(f"{name} {col}(MV)={mv_vals[h]}")
                        _h_sleep(0.5, 1.9)
                else:
                    skipped += 1
                done += 1
                if rich_prog and rich_task is not None:
                    try:
                        rich_prog.update(rich_task, completed=done, extra=name[:16])
                    except Exception:
                        pass
                elif not dry_run:
                    live_progress(done, total_cells, name)

                if h < len(hv_vals) and hv_vals[h] is not None:
                    col = f"k{h:02d}"
                    existing = rowdata.get(col)
                    if existing is not None and abs(float(existing) - float(hv_vals[h])) < 0.001:
                        skipped += 1
                    elif dry_run:
                        updates += 1
                        if len(dry_samples) < 6:
                            dry_samples.append(f"{name} {col}(HV): {existing} → {hv_vals[h]}")
                    else:
                        if pln.update_cell(data_type, rowdata, col, hv_vals[h]):
                            updates += 1
                        else:
                            errors += 1; error_list.append(f"{name} {col}(HV)={hv_vals[h]}")
                        _h_sleep(0.5, 1.9)
                else:
                    skipped += 1
                done += 1
                if rich_prog and rich_task is not None:
                    try:
                        rich_prog.update(rich_task, completed=done, extra=name[:16])
                    except Exception:
                        pass
                elif not dry_run:
                    live_progress(done, total_cells, name)
        else:
            jams = values if isinstance(values, list) else []
            for h in range(jam_start, jam_end + 1):
                if h >= len(jams) or jams[h] is None:
                    skipped += 1
                    done += 1
                    if rich_prog and rich_task is not None:
                        try:
                            rich_prog.update(rich_task, completed=done, extra=name[:16])
                        except Exception:
                            pass
                    elif not dry_run:
                        live_progress(done, total_cells, name)
                    continue
                col = f"j{h:02d}"
                existing = rowdata.get(col)
                if existing is not None and str(existing) == str(jams[h]):
                    skipped += 1
                elif dry_run:
                    updates += 1
                    if len(dry_samples) < 6:
                        dry_samples.append(f"{name} {col}: {existing} → {jams[h]}")
                else:
                    if pln.update_cell(data_type, rowdata, col, jams[h]):
                        updates += 1
                    else:
                        errors += 1; error_list.append(f"{name} {col}={jams[h]}")
                    _h_sleep(0.5, 1.9)
                done += 1
                if rich_prog and rich_task is not None:
                    try:
                        rich_prog.update(rich_task, completed=done, extra=name[:16])
                    except Exception:
                        pass
                elif not dry_run:
                    live_progress(done, total_cells, name)

    # End live bar, summary
    if rich_prog:
        try:
            rich_prog.stop()
        except Exception:
            pass
    if not dry_run and not rich_prog:
        print()

    summary_box(type_labels[data_type], updates, errors, skipped, total_cells)

    if dry_run and dry_samples:
        if RICH and console:
            console.print(f"  [dim]Contoh perubahan:[/]")
            for s in dry_samples:
                console.print(f"    [cyan]{s}[/]")
        else:
            print(f"  Contoh perubahan:")
            for s in dry_samples:
                print(f"    {s}")

    if error_list:
        warn(f"{len(error_list)} error: " + "; ".join(error_list[:5]) + (" …" if len(error_list) > 5 else ""))

    return errors == 0

# ============ CLI ARGS ============
def main():
    args = sys.argv[1:]

    if '--help' in args or '-h' in args:
        if RICH and console:
            from rich.panel import Panel
            help_text = __doc__ or "SUPER-I Sync Tool"
            console.print(Panel(help_text.strip(), title="[bold bright_yellow]Help[/]", border_style="bright_yellow"))
        else:
            print(__doc__)
        sys.exit(0)

    if '--version' in args or '-v' in args:
        if RICH and console:
            console.print(f"[bold bright_yellow]superi sync[/] v{__version__}")
        else:
            print(f"superi sync v{__version__}")
        sys.exit(0)

    data_type = None
    jam_start = 0; jam_end = 23
    date_str = datetime.now().strftime("%Y-%m-%d")
    dry_run = '--dry-run' in args

    for i, a in enumerate(args):
        if a == '--type' and i+1 < len(args):
            t = args[i+1]
            if t == 'all':
                data_type = 'all'
            elif t in ('penyulang', 'trafo', 'tegangan'):
                data_type = t
        elif a == '--jam' and i+1 < len(args):
            v = args[i+1]
            if '-' in v:
                jam_start, jam_end = map(int, v.split('-'))
            else:
                jam_start = jam_end = int(v)
        elif a == '--date' and i+1 < len(args):
            date_str = args[i+1]

    if data_type:
        types = ["penyulang", "trafo", "tegangan"] if data_type == 'all' else [data_type]
        for dt in types:
            success = do_sync(dt, jam_start, jam_end, date_str, dry_run=dry_run)
            if not success and not dry_run:
                sys.exit(1)
        sys.exit(0)

    if RICH and console:
        console.print(f"\n  [dim]Menu sync sekarang tergabung di SUPER-I CLI.[/]")
        console.print(f"  Jalankan:  [bold bright_yellow]superi cli[/]   →  pilih [bold cyan][P] Sync ke Portal APD[/]")
        console.print(f"  Atau non-interactive: [dim]superi sync --type all --jam 08 --dry-run[/]\n")
    else:
        print(f"\n  Menu sync sekarang tergabung di SUPER-I CLI.")
        print(f"  Jalankan:  superi cli   →  pilih [P] Sync ke Portal APD")
        print(f"  Atau non-interactive: superi sync --type all --jam 08 --dry-run\n")
    sys.exit(0)

if __name__ == '__main__':
    main()
