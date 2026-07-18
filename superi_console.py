#!/usr/bin/env python3
"""
SUPER-I APP - Rich Console Singleton (Tema Kuning)
===================================================
Console terpusat dengan tema kuning (yellow) yang kompatibel:
- macOS Terminal / iTerm2 / Warp (truecolor)
- Windows 10+ Windows Terminal (truecolor + emoji)
- Windows legacy cmd.exe (16 colors, VT100 enabled via ctypes)
- Cron / piped (auto-strip colors)

Menghandle:
- VT100 enable di Windows
- Theme kuning konsisten
- Helper untuk header, panel, status, prompt, progress
"""

import os
import sys
import subprocess
import platform

# --- Windows VT100 enable (agar ANSI + emoji + \r progress jalan) ---------
def _enable_win_vt100():
    """Enable VT100 escape processing on Windows 10+."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        # Also try for STD_ERROR
        try:
            h2 = kernel32.GetStdHandle(-12)
            m2 = ctypes.c_ulong()
            kernel32.GetConsoleMode(h2, ctypes.byref(m2))
            kernel32.SetConsoleMode(h2, m2.value | 0x0004)
        except Exception:
            pass
    except Exception:
        pass

_enable_win_vt100()

# --- Rich imports --------------------------------------------------------
try:
    from rich.console import Console
    from rich.theme import Theme
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.box import ROUNDED, DOUBLE, HEAVY, MINIMAL, ASCII
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn, BarColumn,
        TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn,
        MofNCompleteColumn
    )
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.rule import Rule
    from rich.columns import Columns
    from rich.align import Align
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None  # type: ignore
    Theme = None  # type: ignore

# --- Tema Kuning ---------------------------------------------------------
# Kuning utama #FFC107 (Amber 500) -> warm, readable di dark background macOS/Windows Terminal
# Fallback: bright_yellow (ANSI 93) untuk cmd.exe legacy
# Semua border/header/accent kuning. Success tetap hijau (semantic), error merah.
CUSTOM_THEME = {
    # Primary kuning
    "primary": "bold #FFC107",
    "primary.bold": "bold #FFB300",
    "primary.dim": "#FF8F00 dim",
    "accent": "#FFCA28",
    "accent2": "#FFD54F",
    "header": "bold #FFC107",
    "header.title": "bold #FFEB3B",
    "border": "#FFC107",
    "border.dim": "#FF8F00 dim",
    # Semantic
    "ok": "bold #66BB6A",
    "ok.dim": "green",
    "success": "bold #66BB6A",
    "err": "bold #EF5350",
    "error": "bold #EF5350",
    "warn": "bold #FFCA28",
    "warning": "bold #FFCA28",
    "info": "bold #4FC3F7",
    "info.dim": "#29B6F6 dim",
    # Text
    "muted": "dim white",
    "dim2": "dim",
    "key": "bold #FFD54F",
    "value": "white",
    "number": "bold #FFCA28",
    "label": "#FFECB3",
    # Table
    "table.header": "bold #FFC107",
    "table.border": "#FF8F00",
    "row.even": "white",
    "row.odd": "dim white",
    "cb_off": "bold #EF5350",
    "cb_on": "bold #66BB6A",
    # Special
    "prompt": "bold #FFCA28",
    "prompt.choice": "cyan",
    "prompt.default": "dim white",
    "progress.bar": "#FFC107",
    "progress.desc": "white",
    "progress.percentage": "bold #FFCA28",
    "highlight": "bold #FFEB3B",
    "link": "#4FC3F7 underline",
} if RICH_AVAILABLE else {}

def _make_console(stderr=False, no_color=None):
    """Buat console dengan theme kuning. Auto-detect terminal."""
    if not RICH_AVAILABLE:
        return None

    # Respect env vars: FORCE_COLOR, NO_COLOR handled by Rich automatically
    # Untuk cron/non-TTY -> no_color atau is_terminal False
    force_terminal = None
    if os.environ.get("FORCE_COLOR") == "1":
        force_terminal = True
    if os.environ.get("NO_COLOR"):
        no_color = True

    _theme = Theme(CUSTOM_THEME)

    # Console utama
    # - highlight=False: jangan auto-highlight angka (agar "VA-202" dll aman)
    # - markup=True: enable [bold yellow] syntax
    c = Console(
        theme=_theme,
        stderr=stderr,
        highlight=False,
        markup=True,
        force_terminal=force_terminal,
        no_color=no_color,
        legacy_windows=False,  # kita sudah enable VT100 sendiri, biar Rich tidak force downgrade
    )
    return c

# Singleton consoles
console = _make_console(stderr=False) if RICH_AVAILABLE else None
err_console = _make_console(stderr=True) if RICH_AVAILABLE else None
# Plain console untuk file log (tanpa warna)
plain_console = _make_console(no_color=True) if RICH_AVAILABLE else None

# Optional interactive backend used by the Textual fullscreen shell. Keeping
# this indirection here lets the existing synchronous workflows request input
# without knowing whether they run in a normal terminal or a TUI worker.
_interactive_backend = None


def set_interactive_backend(backend):
    """Install a backend implementing ask(), confirm(), and pause()."""
    global _interactive_backend
    _interactive_backend = backend


def clear_interactive_backend(backend=None):
    """Remove the current backend, optionally only when it matches backend."""
    global _interactive_backend
    if backend is None or _interactive_backend is backend:
        _interactive_backend = None

# Helpers for non-rich fallback (keep old API working)
def _fallback_print(*args, **kwargs):
    print(*args, **kwargs)

# --- Clear ---------------------------------------------------------------
def clear():
    """Clear screen cross-platform, pakai Rich jika ada."""
    if RICH_AVAILABLE and console:
        try:
            console.clear()
            return
        except Exception:
            pass
    os.system('clear' if os.name != 'nt' else 'cls')

# --- Banners & Headers ----------------------------------------------------
SUPERI_BANNER = r"""
╔═╗╦ ╦╔═╗╔═╗╦═╗   ╦   ╔═╗╔═╗╔═╗
╚═╗║ ║╠═╝║╣ ╠╦╝   ║   ╠═╣╠═╝╚═╗
╚═╝╚═╝╩  ╚═╝╩╚═   ╩   ╩ ╩╩  ╚═╝
"""

def banner(subtitle="GI MANGGARAI · PLN"):
    """Tampilkan banner SUPER-I."""
    if not RICH_AVAILABLE or not console:
        print(f"\n  SUPER-I APP")
        if subtitle:
            print(f"  {subtitle}")
        print("  " + "─" * 50)
        return
    # Panel kuning dengan title
    txt = Text()
    txt.append("SUPER-I", style="bold #FFC107")
    txt.append(" APP", style="bold white")
    txt.append(f"\n{subtitle}", style="dim white")
    console.print(Panel(txt, box=DOUBLE, border_style="bright_yellow", padding=(0, 2), width=62))

def header(title, subtitle=None):
    """Header section dengan garis kuning."""
    if not RICH_AVAILABLE or not console:
        print(f"\n{'━'*60}\n  {title}\n{'━'*60}")
        if subtitle:
            print(f"  {subtitle}")
        return
    # Rule kuning + Panel untuk title
    # Gunakan Panel DOUBLE border kuning
    content = f"[bold bright_yellow]{title}[/]"
    if subtitle:
        content += f"\n[dim white]{subtitle}[/]"
    console.print()
    console.print(Panel(content, box=DOUBLE, border_style="bright_yellow", padding=(0, 1), width=62))

def sub_header(title):
    """Sub header kecil dengan arrow kuning."""
    if not RICH_AVAILABLE or not console:
        print(f"\n  ▸ {title}\n  {'─'*50}")
        return
    console.print()
    console.print(Rule(f"[bold bright_yellow]▸ {title}[/]", style="bright_yellow", align="left"))
    # console.print(f"  [dim]{'─'*50}[/]")

def status_bar(user, gi_id, date_str):
    """Status bar user info di box kuning."""
    if not RICH_AVAILABLE or not console:
        print(f"  ┌─────────────────────────────────────────────────────┐")
        if user:
            print(f"  │  ● {user.get('namaLengkap','?')} ({', '.join(user.get('roles',[]))})")
            print(f"  │  📍 GI: {gi_id}  📅 {date_str}")
        else:
            print(f"  │  ○ Belum login  📅 {date_str}")
        print(f"  └─────────────────────────────────────────────────────┘")
        return

    if user:
        nama = user.get('namaLengkap', '?')
        roles = ', '.join(user.get('roles', []))
        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="bold green")
        grid.add_column(style="white")
        grid.add_column(style="dim white")
        grid.add_row("●", f"[bold white]{nama}[/]", f"({roles})" if roles else "")
        grid.add_row("📍", f"GI: {gi_id}", f"📅 {date_str}")
        panel = Panel(grid, box=ROUNDED, border_style="bright_yellow", width=60, padding=(0,1))
    else:
        grid = Table.grid(padding=(0,1))
        grid.add_column()
        grid.add_column()
        grid.add_row("○", f"[red]Belum login[/]  📅 {date_str}")
        panel = Panel(grid, box=ROUNDED, border_style="dim", width=60, padding=(0,1))
    console.print(panel)

# --- Print helpers themed yellow ------------------------------------------
def ok(msg):
    if RICH_AVAILABLE and console:
        console.print(f"  [ok]✓ {msg}[/]")
    else:
        print(f"  ✓ {msg}")

def err(msg):
    if RICH_AVAILABLE and console:
        console.print(f"  [err]✗ {msg}[/]")
    else:
        print(f"  ✗ {msg}")

def warn_msg(msg):
    if RICH_AVAILABLE and console:
        console.print(f"  [warn]⚠ {msg}[/]")
    else:
        print(f"  ⚠ {msg}")

def info_msg(msg):
    if RICH_AVAILABLE and console:
        console.print(f"  [info]ℹ {msg}[/]")
    else:
        print(f"  ℹ {msg}")

def dim_msg(msg):
    if RICH_AVAILABLE and console:
        console.print(f"  [dim]{msg}[/]")
    else:
        print(f"  {msg}")

# --- Panels ---------------------------------------------------------------
def success_panel(msg, title="Sukses"):
    if not RICH_AVAILABLE or not console:
        print(f"  ✓ {title}: {msg}")
        return
    console.print(Panel(f"[bold green]{msg}[/]", title=f"[bold green]{title}[/]", border_style="green", box=ROUNDED, padding=(0,1)))

def error_panel(msg, title="Error"):
    if not RICH_AVAILABLE or not console:
        print(f"  ✗ {title}: {msg}")
        return
    console.print(Panel(f"[bold red]{msg}[/]", title=f"[bold red]{title}[/]", border_style="red", box=ROUNDED, padding=(0,1)))

def warning_panel(msg, title="Peringatan"):
    if not RICH_AVAILABLE or not console:
        print(f"  ⚠ {title}: {msg}")
        return
    console.print(Panel(f"[yellow]{msg}[/]", title=f"[bold yellow]{title}[/]", border_style="bright_yellow", box=ROUNDED, padding=(0,1)))

def info_panel(msg, title="Info"):
    if not RICH_AVAILABLE or not console:
        print(f"  ℹ {title}: {msg}")
        return
    console.print(Panel(f"{msg}", title=f"[bold cyan]{title}[/]", border_style="cyan", box=ROUNDED, padding=(0,1)))

def summary_box(success, fail, total, label):
    """Box ringkasan batch submit - tema kuning border."""
    inner = f"Ringkasan {label}: [bold green]✓ {success} berhasil[/]"
    if fail:
        inner += f"  [bold red]✗ {fail} gagal[/]"
    inner += f"  [dim]({success}/{total})[/]"

    if not RICH_AVAILABLE or not console:
        bar = "━" * (len(f"  Ringkasan {label}: {success} berhasil") + 10)
        print(f"  ┏{bar}┓\n  ┃  Ringkasan {label}: ✓ {success} berhasil" + (f"  ✗ {fail} gagal" if fail else "") + f"  ({success}/{total})┃\n  ┗{bar}┛")
        return

    border = "green" if fail == 0 else "yellow" if fail < success else "red"
    console.print(Panel(inner, box=ROUNDED, border_style=border, width=62, padding=(0,1)))

def sync_summary(label, ok_count, fail_count, skip_count, total):
    inner = f"Ringkasan {label}: [bold green]✓ {ok_count} update[/]"
    if fail_count:
        inner += f"  [bold red]✗ {fail_count} gagal[/]"
    if skip_count:
        inner += f"  [dim]⊘ {skip_count} skip[/]"
    inner += f"  [dim]({ok_count+fail_count}/{total})[/]"

    if not RICH_AVAILABLE or not console:
        for line in [f"  ┏{'━'*50}┓", f"  ┃  {inner}┃", f"  ┗{'━'*50}┛"]:
            print(line)
        return

    border = "green" if fail_count == 0 else "yellow"
    console.print(Panel(inner, box=ROUNDED, border_style=border, width=66, padding=(0,1)))

# --- Progress factories ----------------------------------------------------
def make_progress(transient=False, with_eta=True):
    """Buat Progress bar bertema kuning."""
    if not RICH_AVAILABLE or not console:
        return None
    cols = [
        SpinnerColumn(style="bright_yellow"),
        TextColumn("[progress.description]{task.description}", style="white"),
        BarColumn(bar_width=None, style="dim yellow", complete_style="bright_yellow", finished_style="green"),
        TaskProgressColumn(style="bold bright_yellow"),
        MofNCompleteColumn(),
    ]
    if with_eta:
        cols.extend([
            TextColumn("•", style="dim"),
            TimeElapsedColumn(),
            TextColumn("•", style="dim"),
            TimeRemainingColumn(),
        ])
    return Progress(*cols, console=console, transient=transient, expand=False)

def make_simple_progress():
    """Progress sederhana tanpa spinner (untuk sync)."""
    if not RICH_AVAILABLE or not console:
        return None
    return Progress(
        TextColumn("[progress.description]{task.description}", style="white"),
        BarColumn(bar_width=24, style="dim yellow", complete_style="bright_yellow", finished_style="green"),
        TaskProgressColumn(style="bold bright_yellow"),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[extra]}[/]", justify="left"),
        console=console,
        transient=False,
    )

# --- Prompt wrappers -------------------------------------------------------
def prompt_ask(question, default=None, choices=None, show_default=True, password=False):
    """Prompt dengan tema kuning. Fallback ke input() jika Rich tak ada."""
    if _interactive_backend is not None:
        return _interactive_backend.ask(
            question,
            default=default,
            choices=choices,
            password=password,
        )
    if not RICH_AVAILABLE or not console:
        if default:
            v = input(f"  {question} [{default}]: ").strip()
            return v if v else default
        return input(f"  {question}: ").strip()

    # Rich path
    try:
        if choices:
            return Prompt.ask(
                f"  [bold bright_yellow]{question}[/]",
                choices=choices,
                default=default,
                show_default=show_default,
                console=console,
                password=password,
            )
        else:
            return Prompt.ask(
                f"  [bold bright_yellow]{question}[/]",
                default=default,
                show_default=show_default,
                console=console,
                password=password,
            )
    except Exception:
        # fallback jika non-interaktif
        if default:
            v = input(f"  {question} [{default}]: ").strip()
            return v if v else default
        return input(f"  {question}: ").strip()

def confirm_ask(question, default=False):
    """Confirm dengan tema kuning."""
    if _interactive_backend is not None:
        return _interactive_backend.confirm(question, default=default)
    if not RICH_AVAILABLE or not console:
        suffix = "Y/n" if default else "y/N"
        v = input(f"  {question} ({suffix}): ").strip().lower()
        if not v:
            return default
        return v in ("y", "yes")
    try:
        return Confirm.ask(
            f"  [bold bright_yellow]{question}[/]",
            default=default,
            console=console,
        )
    except Exception:
        v = input(f"  {question} (y/n): ").strip().lower()
        return v == "y"

def pause(msg="Tekan Enter untuk kembali..."):
    """Pause - tekan Enter."""
    if _interactive_backend is not None:
        _interactive_backend.pause(msg)
        return
    if not RICH_AVAILABLE or not console:
        input(f"  {msg}")
        return
    try:
        console.print(f"  [dim]{msg}[/]", end="")
        input()
    except (EOFError, KeyboardInterrupt):
        console.print()

# --- Tables helpers --------------------------------------------------------
def make_table(title=None, show_lines=False, border_style="bright_yellow", **kwargs):
    """Factory Table dengan tema kuning."""
    if not RICH_AVAILABLE:
        return None
    return Table(
        title=f"[bold bright_yellow]{title}[/]" if title else None,
        title_style="bold bright_yellow",
        header_style="bold bright_yellow",
        border_style=border_style,
        box=ROUNDED,
        show_lines=show_lines,
        **kwargs,
    )

# --- Logging helpers (for auto mode) --------------------------------------
def log_to_file_and_console(msg, level="INFO", log_file=None):
    """
    Log dual: console berwarna (Rich) + file plain tanpa ANSI.
    Tetap kompatibel dengan auto_log.txt existing.
    """
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plain_line = f"[{ts}] [{level}] {msg}"

    # File always plain
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(plain_line + "\n")
        except Exception:
            pass

    # Console colored via Rich if available and terminal
    if not RICH_AVAILABLE or not console or not console.is_terminal:
        # Non-rich or non-tty (cron) -> plain print
        try:
            print(plain_line)
        except UnicodeEncodeError:
            print(plain_line.encode("ascii", "replace").decode("ascii"))
        return

    # Rich colored
    level_style = {
        "INFO": "bold cyan",
        "WARN": "bold bright_yellow",
        "ERROR": "bold red",
        "DRY": "magenta",
        "OK": "bold green",
    }.get(level, "white")
    console.print(f"[dim][{ts}][/][{level_style}] [{level}][/{level_style}] {msg}")

# --- Utility: render Table to string (for tests / non-rich compat) ----------
def table_to_string(table):
    """Render Table ke string plain (untuk test kompatibilitas)."""
    if not RICH_AVAILABLE or not console:
        return str(table)
    try:
        from io import StringIO
        tmp = Console(file=StringIO(), theme=Theme(CUSTOM_THEME), highlight=False, width=100, force_terminal=True, color_system="truecolor")
        tmp.print(table)
        return tmp.file.getvalue()
    except Exception:
        return str(table)

# --- Version & Debug --------------------------------------------------------
def print_version(version="1.4.0"):
    if not RICH_AVAILABLE or not console:
        print(f"SUPER-I APP v{version}")
        return
    console.print(Panel(f"[bold bright_yellow]SUPER-I APP[/] [white]v{version}[/]\n[dim]GI MANGGARAI - PLN • Automation Toolkit[/]", box=ROUNDED, border_style="bright_yellow", padding=(0,1)))
