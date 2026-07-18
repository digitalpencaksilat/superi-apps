"""Pure string-rendering helpers for the SUPER-I CLI + Rich renderables.

Every original fmt_* / render_* function keeps returning string/list[str] and performs
NO printing, NO network, NO input - so tests remain valid.
New *_rich() helpers return Rich renderables (Table, Panel, etc) with tema KUNING.

Backward compatibility: all old signatures are preserved.
Added: rich_tables_* returning Rich Table/Panel with yellow theme (Windows + macOS safe).
"""

# ---- Original pure helpers (keep for backwards compat & tests) ----

def fmt_empty_ranges(empty):
    """Compact a list of periode ints into range notation.

    [0,1,2,7,8,12,13,14,15] -> "0-2, 7-8, 12-15"
    []                       -> "∅"
    Input is normalised (sorted, de-duplicated) defensively.
    """
    if not empty:
        return "∅"
    nums = sorted(set(int(p) for p in empty))
    parts = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}" if start == prev else f"{start}-{prev}")
        start = prev = n
    parts.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(parts)


def fmt_progress(n, total):
    """[01/08] style counter, zero-padded to at least 2 digits."""
    w = max(2, len(str(total)))
    return f"[{n:0{w}d}/{total:0{w}d}]"


_FILLED = "█"
_EMPTY = "░"


def fmt_fill_strip(periods, width=24):
    """24-char strip: █ = filled, ░ = empty. periode 0..23 maps to index."""
    filled = set(int(p) for p in periods if 0 <= int(p) < width)
    return "".join(_FILLED if i in filled else _EMPTY for i in range(width))


# Column widths for render_item_table
_NAMA_W = 20
_STATUS_W = 6
_TERISI_W = 6  # fits "Terisi" (6 chars) + data like "18/24"


def _data_key(data_type):
    return "tegangan" if data_type == "tegangan-trafo" else "beban"


def _pad(s, w):
    return str(s)[:w].ljust(w)


def _rpad(s, w):
    return str(s)[:w].rjust(w)


def _truncate(s, w):
    s = str(s)
    return s if len(s) <= w else s[: w - 1] + "…"


def render_item_table(items, data_type):
    """Return a list of aligned string lines for an item list.

    Columns: No | Nama | Status | Terisi | Kosong
    CB-OFF rows are tagged and their kosong shows ∅.
    """
    key = _data_key(data_type)
    lines = []
    header = (f"  No  {_pad('Nama', _NAMA_W)}  "
              f"{_pad('Status', _STATUS_W)}  "
              f"{_rpad('Terisi', _TERISI_W)}  Kosong")
    lines.append(header)
    lines.append("  " + "─" * (3 + _NAMA_W + _STATUS_W + _TERISI_W + 2 * 4 + 8))
    for i, item in enumerate(items, 1):
        nama = _truncate(item.get("nama", "?"), _NAMA_W)
        entries = item.get(key, [])
        periods = [e["periode"] for e in entries]
        empty = [p for p in range(24) if p not in periods]
        cb_off = item.get("statusCB") == "OFF"
        status = "CB OFF" if cb_off else "ON"
        kosong = "∅" if cb_off else fmt_empty_ranges(empty)
        terisi_str = f"{len(periods)}/24"
        lines.append(
            f"  [{i}] {nama:<{_NAMA_W}}  {status:<{_STATUS_W}}  "
            f"{terisi_str:>{_TERISI_W}}  {kosong}"
        )
    return lines


_PER_LINE = 6


def render_existing_data(entries, data_type):
    """Compact multi-line view of already-filled periodes."""
    if not entries:
        return ["  (belum ada data)"]
    sorted_e = sorted(entries, key=lambda x: x["periode"])
    periods = [e["periode"] for e in sorted_e]
    lines = [f"  {fmt_fill_strip(periods)}  {len(periods)}/24"]

    is_teg = data_type == "tegangan-trafo"
    chunk = []
    for e in sorted_e:
        p = e["periode"]
        if is_teg:
            chunk.append(f"P{p:02d}:HV={e['hv']}/MV={e['mv']}")
        else:
            chunk.append(f"P{p:02d}:{e['beban']}A")
        if len(chunk) == _PER_LINE:
            lines.append("  " + "  ".join(chunk))
            chunk = []
    if chunk:
        lines.append("  " + "  ".join(chunk))

    if not is_teg:
        vals = [e["beban"] for e in sorted_e]
        avg = sum(vals) / len(vals)
        lines.append(f"  Range: {min(vals)}-{max(vals)}A | Rata2: {avg:.0f}A")
    return lines


_SUG_NAMA_W = 18


def render_suggest_table(rows):
    """Aligned suggestion table. rows = list[(no, nama, value_str, info)]."""
    lines = []
    header = (f"  No  {_pad('Nama', _SUG_NAMA_W)}  "
              f"{_pad('Suggest', 14)}  Info")
    lines.append(header)
    lines.append("  " + "─" * (3 + _SUG_NAMA_W + 14 + 2 * 4 + 6))
    for no, nama, val, info in rows:
        lines.append(
            f"  {no:<2}  {_truncate(str(nama), _SUG_NAMA_W):<{_SUG_NAMA_W}}  "
            f"{str(val)[:14]:<14}  {info}"
        )
    return lines


def render_summary_box(success, fail, total, label):
    """Boxed one-line summary of a batch submit result."""
    inner = f"  Ringkasan {label}: ✓ {success} berhasil"
    if fail:
        inner += f"  ✗ {fail} gagal"
    inner += f"  ({success}/{total})"
    bar = "━" * len(inner)
    return "\n".join([
        f"  ┏{bar}┓",
        f"  ┃{inner}┃",
        f"  ┗{bar}┛",
    ])


def fmt_progress_line(n, total, label, ok=True, detail=""):
    """Single-line live progress string for submit loops."""
    mark = "✓" if ok else "✗"
    tail = f"  {detail}" if detail else ""
    base = f"{fmt_progress(n, total)} {label} {mark}{tail}"
    return base.ljust(42)[:42]


# Column widths for render_data_view
_DATA_NAMA_W = 20
_DATA_IMAX_W = 5
_DATA_CB_W = 4
_DATA_TYPE_W = 4
_STRIP_HDR = "Strip (24 jam)"


def render_data_view(items, data_type):
    """Return aligned lines for the 'Lihat Data' view with 24-slot fill strips."""
    key = _data_key(data_type)
    is_teg = data_type == "tegangan-trafo"
    strip_col = _pad(_STRIP_HDR, 24)
    lines = []

    if is_teg:
        header = (f"  {_pad('No', 2)}  {_pad('Nama', _DATA_NAMA_W)}  "
                  f"{_pad('Type', _DATA_TYPE_W)}  "
                  f"{_rpad('Terisi', _TERISI_W)}  {strip_col}")
    else:
        header = (f"  {_pad('No', 2)}  {_pad('Nama', _DATA_NAMA_W)}  "
                  f"{_pad('iMax', _DATA_IMAX_W)}  {_pad('CB', _DATA_CB_W)}  "
                  f"{_rpad('Terisi', _TERISI_W)}  {strip_col}")
    lines.append(header)
    lines.append("  " + "─" * len(header))

    for i, item in enumerate(items, 1):
        nama = _truncate(item.get("nama", "?"), _DATA_NAMA_W)
        entries = item.get(key, [])
        periods = sorted(e["periode"] for e in entries)
        empty = [p for p in range(24) if p not in periods]
        strip = fmt_fill_strip(periods)
        terisi = f"{len(periods)}/24"
        cb_off = item.get("statusCB") == "OFF"

        if is_teg:
            type_label = "PS" if item.get("isPS") else "GI"
            lines.append(f"  {i:<2}  {nama:<{_DATA_NAMA_W}}  "
                         f"{type_label:<{_DATA_TYPE_W}}  "
                         f"{terisi:>{_TERISI_W}}  {strip}")
        else:
            i_max = item.get("iMax", "?")
            i_max_str = f"{i_max}A" if i_max != "?" else "?"
            cb = "OFF" if cb_off else "ON"
            lines.append(f"  {i:<2}  {nama:<{_DATA_NAMA_W}}  "
                         f"{i_max_str:<{_DATA_IMAX_W}}  {cb:<{_DATA_CB_W}}  "
                         f"{terisi:>{_TERISI_W}}  {strip}")

        details = []
        if not is_teg:
            trafo = item.get("trafo", {}).get("nama", "")
            if trafo:
                details.append(f"TRAFO: {trafo}")

        if entries:
            if is_teg:
                mv_vals = [e["mv"] for e in entries]
                hv_vals = [e["hv"] for e in entries]
                details.append(
                    f"MV: {min(mv_vals):.1f}-{max(mv_vals):.1f}kV · "
                    f"HV: {min(hv_vals)}-{max(hv_vals)}kV")
            else:
                vals = [e["beban"] for e in entries]
                avg = sum(vals) / len(vals)
                details.append(f"Range: {min(vals)}-{max(vals)}A · Rata2: {avg:.0f}A")

        if cb_off and not is_teg:
            details.append("CB OFF — tidak ada arus")
        elif empty:
            details.append(f"Kosong: {fmt_empty_ranges(empty)}")

        if details:
            lines.append(f"      → {' · '.join(details)}")

    return lines


def render_data_summary(total_items, total_filled, total_empty):
    """One-line footer summary for the 'Lihat Data' view."""
    total_slots = total_items * 24
    return (f"  Total: {total_items} item · "
            f"{total_filled}/{total_slots} periode terisi · "
            f"{total_empty} masih kosong")


def fmt_progress_bar(n, total, width=24):
    """[████████░░░░░░░░] 16/32 (50%). Pure string, no ANSI."""
    if total <= 0:
        return f"[{_EMPTY * width}] 0/0"
    n = min(max(n, 0), total)
    filled = int(round(width * n / total))
    bar = _FILLED * filled + _EMPTY * (width - filled)
    pct = int(round(100 * n / total))
    return f"[{bar}] {n}/{total} ({pct}%)"


def render_sync_summary(label, ok_count, fail_count, skip_count, total):
    """Boxed one-line sync summary (3 lines). Pure string."""
    inner = f"  Ringkasan {label}: ✓ {ok_count} update"
    if fail_count:
        inner += f"  ✗ {fail_count} gagal"
    if skip_count:
        inner += f"  ⊘ {skip_count} skip"
    inner += f"  ({ok_count + fail_count}/{total})"
    w = len(inner)
    return [
        f"  ┏{'━' * w}┓",
        f"  ┃{inner}┃",
        f"  ┗{'━' * w}┛",
    ]


def render_settings_box(photo_source, history_days, pool_count, manual_stats, total_manual):
    """Box untuk settings foto source."""
    src_label = "MANUAL (per-item sesuai)" if photo_source == "manual" else "POOL (1 foto untuk semua)"
    lines = []
    lines.append(f"  Foto Source : {photo_source.upper()} - {src_label}")
    lines.append(f"  History     : {history_days} hari")
    lines.append(f"  Pool generic: {pool_count} file di photo/pool/")
    if manual_stats:
        bp = manual_stats.get("beban-penyulang", {})
        bt = manual_stats.get("beban-trafo", {})
        tt = manual_stats.get("tegangan-trafo", {})
        lines.append(f"  Manual penyulang: {bp.get('folders',0)} folder / {bp.get('files',0)} foto (25 ON + 7 OFF tetap)")
        lines.append(f"  Manual beban    : {bt.get('folders',0)} folder / {bt.get('files',0)} foto")
        lines.append(f"  Manual tegangan : {tt.get('folders',0)} trafo / HV {tt.get('hv',0)} + MV {tt.get('mv',0)} = {tt.get('total',0)} foto (hv/mv terpisah)")
        lines.append(f"  Total manual    : {total_manual} foto")
    lines.append(f"  Filename    : fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg (humanizer tetap, bukan basename manual)")
    lines.append(f"  OFF         : 7 penyulang CB OFF tetap simpan tapi skip input")
    lines.append(f"  Varian      : asli 40%, blur_ringan 20%, blur_berat 10%, kabur_glare 15%, noisy_gelap 15%")
    return lines


def render_pool_status(detailed_rows):
    """Render per-item pool status: list of (nama, count, on/off, type_label)."""
    lines = []
    lines.append(f"  {'Nama':<22} {'Count':<6} {'CB':<4} {'Type'}")
    lines.append("  " + "─" * 50)
    for nama, cnt, cb, typ in detailed_rows:
        lines.append(f"  {str(nama)[:22]:<22} {cnt:<6} {cb:<4} {typ}")
    return lines


def render_suggest_table_with_pool(rows):
    """Like render_suggest_table but rows = (no, nama, value, pool_cnt, info)."""
    lines = []
    header = (f"  No  {_pad('Nama', _SUG_NAMA_W)}  "
              f"{_pad('Suggest', 14)}  {_pad('Foto', 8)}  Info")
    lines.append(header)
    lines.append("  " + "─" * (3 + _SUG_NAMA_W + 14 + 8 + 3 * 4 + 6))
    for no, nama, val, pool_cnt, info in rows:
        pool_str = f"{pool_cnt} ref" if pool_cnt > 0 else "pool"
        lines.append(
            f"  {no:<2}  {_truncate(str(nama), _SUG_NAMA_W):<{_SUG_NAMA_W}}  "
            f"{str(val)[:14]:<14}  {pool_str:<8}  {info}"
        )
    return lines


# ==========================================================================
# RICH RENDERABLES - Tema Kuning (Windows + macOS compatible)
# ==========================================================================
# Import Rich lazily — if not available (tests without rich) fall back to None.

try:
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box as _box
    from rich.tree import Tree
    from rich.columns import Columns
    _RICH_OK = True
except ImportError:
    _RICH_OK = False
    Table = None  # type: ignore
    Panel = None  # type: ignore
    Text = None  # type: ignore

# Yellow theme constants (compatible with 16-color cmd.exe and truecolor modern terminal)
YELLOW = "bright_yellow"
YELLOW_DIM = "yellow"
YELLOW_BOLD = "bold bright_yellow"
GREEN = "bold green"
RED = "bold red"
CYAN = "bold cyan"
DIM = "dim"
WHITE_BOLD = "bold white"


def _rich_available():
    return _RICH_OK


def item_table_rich(items, data_type, title=None):
    """Return Rich Table with yellow theme for item list."""
    if not _RICH_OK:
        # fallback: return plain lines joined
        return "\n".join(render_item_table(items, data_type))
    key = _data_key(data_type)
    label_map = {
        "beban-penyulang": "Beban Penyulang",
        "beban-trafo": "Beban Trafo",
        "tegangan-trafo": "Tegangan Trafo",
    }
    title = title or label_map.get(data_type, data_type)
    table = Table(
        title=f"[bold bright_yellow]{title}[/]",
        title_style=YELLOW_BOLD,
        header_style=YELLOW_BOLD,
        border_style=YELLOW,
        box=_box.ROUNDED,
        show_lines=False,
        row_styles=["", "dim"],
        expand=False,
    )
    table.add_column("No", justify="right", style="cyan", width=4)
    table.add_column("Nama", min_width=18, max_width=24, overflow="ellipsis", style="white")
    table.add_column("Status", justify="center", width=7)
    table.add_column("Terisi", justify="right", style="bold bright_yellow", width=6)
    table.add_column("Kosong", overflow="fold", style="dim white")

    for i, item in enumerate(items, 1):
        nama = item.get("nama", "?")
        entries = item.get(key, [])
        periods = [e["periode"] for e in entries]
        empty = [p for p in range(24) if p not in periods]
        cb_off = item.get("statusCB") == "OFF"
        if cb_off:
            status_txt = Text("CB OFF", style=RED)
            kosong_txt = Text("∅", style=DIM)
            row_style = "on #3a0000" if _RICH_OK else None
        else:
            status_txt = Text("ON", style=GREEN)
            kosong_txt = Text(fmt_empty_ranges(empty), style=DIM)
            row_style = None
        terisi_txt = Text(f"{len(periods)}/24", style=YELLOW_BOLD if len(periods) < 24 else GREEN)
        no_txt = f"[{i}]"

        if cb_off:
            table.add_row(no_txt, nama, status_txt, terisi_txt, kosong_txt, style="red dim")
        else:
            table.add_row(no_txt, nama, status_txt, terisi_txt, kosong_txt)

    return table


def data_view_rich(items, data_type, date_str=None):
    """Return Rich Table for 'Lihat Data' view with strip and detail lines."""
    if not _RICH_OK:
        return "\n".join(render_data_view(items, data_type))
    key = _data_key(data_type)
    is_teg = data_type == "tegangan-trafo"
    label_map = {
        "beban-penyulang": f"Beban Penyulang · {date_str}" if date_str else "Beban Penyulang",
        "beban-trafo": f"Beban Trafo · {date_str}" if date_str else "Beban Trafo",
        "tegangan-trafo": f"Tegangan Trafo · {date_str}" if date_str else "Tegangan Trafo",
    }
    title = label_map.get(data_type, data_type)

    table = Table(
        title=f"[bold bright_yellow]{title}[/]",
        header_style=YELLOW_BOLD,
        border_style=YELLOW,
        box=_box.ROUNDED,
        show_lines=False,
        expand=False,
        title_style=YELLOW_BOLD,
    )
    table.add_column("No", justify="right", width=4, style="cyan")
    table.add_column("Nama", min_width=18, max_width=22, overflow="ellipsis", style="white")
    if is_teg:
        table.add_column("Type", justify="center", width=4)
    else:
        table.add_column("iMax", justify="right", width=6)
        table.add_column("CB", justify="center", width=4)
    table.add_column("Terisi", justify="right", width=6, style="bold bright_yellow")
    table.add_column("Strip 24 jam", min_width=24, max_width=26, overflow="fold")
    table.add_column("Detail", overflow="fold", style="dim white", max_width=50)

    for i, item in enumerate(items, 1):
        nama = item.get("nama", "?")
        entries = item.get(key, [])
        periods = sorted(e["periode"] for e in entries)
        empty = [p for p in range(24) if p not in periods]
        strip = fmt_fill_strip(periods)
        # color strip: filled part yellow, empty dim
        strip_txt = Text()
        for ch in strip:
            if ch == _FILLED:
                strip_txt.append(ch, style=YELLOW_BOLD)
            else:
                strip_txt.append(ch, style=DIM)

        terisi_txt = Text(f"{len(periods)}/24", style=YELLOW_BOLD if len(periods) < 24 else GREEN)
        cb_off = item.get("statusCB") == "OFF"

        # detail
        details = []
        if not is_teg:
            trafo = item.get("trafo", {}).get("nama", "")
            if trafo:
                details.append(f"TRAFO: {trafo}")
        if entries:
            if is_teg:
                mv_vals = [e["mv"] for e in entries]
                hv_vals = [e["hv"] for e in entries]
                details.append(f"MV:{min(mv_vals):.1f}-{max(mv_vals):.1f}kV HV:{min(hv_vals)}-{max(hv_vals)}kV")
            else:
                vals = [e["beban"] for e in entries]
                avg = sum(vals) / len(vals)
                details.append(f"{min(vals)}-{max(vals)}A avg {avg:.0f}A")
        if cb_off and not is_teg:
            details.append("CB OFF")
        elif empty:
            details.append(f"Kosong:{fmt_empty_ranges(empty)}")

        detail_str = " · ".join(details)

        if is_teg:
            type_label = "PS" if item.get("isPS") else "GI"
            type_txt = Text(type_label, style=CYAN if type_label == "PS" else "white")
            table.add_row(str(i), nama, type_txt, terisi_txt, strip_txt, detail_str)
        else:
            i_max = item.get("iMax", "?")
            i_max_str = f"{i_max}A" if i_max != "?" else "?"
            cb_txt = Text("OFF", style=RED) if cb_off else Text("ON", style=GREEN)
            style_row = "red dim" if cb_off else None
            if style_row:
                table.add_row(str(i), nama, i_max_str, cb_txt, terisi_txt, strip_txt, detail_str, style=style_row)
            else:
                table.add_row(str(i), nama, i_max_str, cb_txt, terisi_txt, strip_txt, detail_str)

    return table


def suggest_table_rich(rows, title="Smart Suggest"):
    """Return Rich Table for suggestion rows (no, nama, value, info)."""
    if not _RICH_OK:
        return "\n".join(render_suggest_table(rows))
    table = Table(
        title=f"[bold bright_yellow]{title}[/]",
        header_style=YELLOW_BOLD,
        border_style=YELLOW,
        box=_box.ROUNDED,
        show_lines=False,
        title_style=YELLOW_BOLD,
    )
    table.add_column("No", justify="right", width=4, style="cyan")
    table.add_column("Nama", min_width=14, max_width=20, overflow="ellipsis", style="white")
    table.add_column("Suggest", style="bold bright_yellow", min_width=10)
    table.add_column("Info", style="dim white", overflow="fold", max_width=40)

    for no, nama, val, info in rows:
        # highlight missing
        if val in ("?", "?A", None) or "?" in str(val):
            val_txt = Text(str(val), style=RED)
        else:
            val_txt = Text(str(val), style=YELLOW_BOLD)
        table.add_row(str(no), str(nama)[:20], val_txt, str(info))

    return table


def suggest_table_with_pool_rich(rows, title="Smart Suggest + Foto"):
    """Rich version of render_suggest_table_with_pool."""
    if not _RICH_OK:
        return "\n".join(render_suggest_table_with_pool(rows))
    table = Table(
        title=f"[bold bright_yellow]{title}[/]",
        header_style=YELLOW_BOLD,
        border_style=YELLOW,
        box=_box.ROUNDED,
        show_lines=False,
        title_style=YELLOW_BOLD,
    )
    table.add_column("No", justify="right", width=4, style="cyan")
    table.add_column("Nama", min_width=14, max_width=18, overflow="ellipsis", style="white")
    table.add_column("Suggest", style="bold bright_yellow", min_width=10)
    table.add_column("Foto", style="dim", width=8)
    table.add_column("Info", style="dim white", overflow="fold", max_width=36)

    for no, nama, val, pool_cnt, info in rows:
        pool_str = f"{pool_cnt} ref" if pool_cnt > 0 else "pool"
        pool_txt = Text(pool_str, style=GREEN if pool_cnt > 0 else DIM)
        val_txt = Text(str(val), style=YELLOW_BOLD) if val not in ("?", "?A") else Text(str(val), style=RED)
        table.add_row(str(no), str(nama)[:18], val_txt, pool_txt, str(info))

    return table


def summary_panel_rich(success, fail, total, label):
    """Return Rich Panel summary box with yellow border."""
    if not _RICH_OK:
        return render_summary_box(success, fail, total, label)
    if fail == 0:
        border = "green"
        icon = "✓"
        msg = f"[bold green]{icon} {success}/{total} berhasil[/] — [bold bright_yellow]{label}[/]"
    elif fail < success:
        border = "bright_yellow"
        msg = f"[bold green]✓ {success}[/] berhasil  [bold red]✗ {fail} gagal[/]  [dim]({success}/{total})[/] — [bold bright_yellow]{label}[/]"
    else:
        border = "red"
        msg = f"[bold green]✓ {success}[/]  [bold red]✗ {fail} gagal[/]  [dim]({success}/{total})[/] — [bold bright_yellow]{label}[/]"

    return Panel(msg, title=f"[bold bright_yellow]Ringkasan[/]", border_style=border, box=_box.ROUNDED, padding=(0, 1), width=66)


def sync_summary_rich(label, ok_count, fail_count, skip_count, total):
    """Return Rich Panel for sync summary."""
    if not _RICH_OK:
        return "\n".join(render_sync_summary(label, ok_count, fail_count, skip_count, total))
    parts = [f"[bold green]✓ {ok_count} update[/]"]
    if fail_count:
        parts.append(f"[bold red]✗ {fail_count} gagal[/]")
    if skip_count:
        parts.append(f"[dim]⊘ {skip_count} skip[/]")
    parts.append(f"[dim]({ok_count+fail_count}/{total})[/]")
    inner = "  ".join(parts) + f" — [bold bright_yellow]{label}[/]"

    if fail_count == 0:
        border = "green" if skip_count == 0 else "bright_yellow"
    else:
        border = "red" if fail_count > ok_count else "bright_yellow"

    return Panel(inner, title=f"[bold bright_yellow]Sync {label}[/]", border_style=border, box=_box.ROUNDED, padding=(0, 1), width=72)


def existing_data_rich(entries, data_type):
    """Return Rich Panel + Table for existing data (compact)."""
    if not _RICH_OK:
        return "\n".join(render_existing_data(entries, data_type))
    if not entries:
        return Panel("[dim](belum ada data)[/]", border_style="dim", box=_box.ROUNDED)

    sorted_e = sorted(entries, key=lambda x: x["periode"])
    periods = [e["periode"] for e in sorted_e]

    # Strip
    strip = fmt_fill_strip(periods)
    strip_text = Text()
    for ch in strip:
        strip_text.append(ch, style=YELLOW_BOLD if ch == _FILLED else DIM)
    strip_text.append(f"  {len(periods)}/24", style="bold bright_yellow")

    # Entries in columns
    is_teg = data_type == "tegangan-trafo"
    cols = []
    for e in sorted_e:
        p = e["periode"]
        if is_teg:
            cols.append(f"P{p:02d}:HV={e['hv']}/MV={e['mv']}")
        else:
            cols.append(f"P{p:02d}:{e['beban']}A")

    # Build grid table (6 per row)
    from rich.table import Table as RichTable
    grid = RichTable.grid(padding=(0, 1))
    # We chunk 6 per row -> create rows manually as Text
    row_texts = []
    for i in range(0, len(cols), 6):
        chunk = cols[i:i + 6]
        row_texts.append("  ".join(chunk))

    # Range line
    extra = ""
    if not is_teg and sorted_e:
        vals = [e["beban"] for e in sorted_e]
        avg = sum(vals) / len(vals)
        extra = f"Range: {min(vals)}-{max(vals)}A | Rata2: {avg:.0f}A"

    body = Text()
    body.append_text(strip_text)
    body.append("\n")
    for rt in row_texts:
        body.append(rt + "\n", style="white")
    if extra:
        body.append(extra, style="dim white")

    return Panel(body, title=f"[bold bright_yellow]Data Existing {len(periods)}/24[/]", border_style=YELLOW, box=_box.ROUNDED, padding=(0, 1))


def pool_status_rich(detailed_rows, title="Pool Status"):
    """Return Rich Table for pool status."""
    if not _RICH_OK:
        return "\n".join(render_pool_status(detailed_rows))
    table = Table(
        title=f"[bold bright_yellow]{title}[/]",
        header_style=YELLOW_BOLD,
        border_style=YELLOW,
        box=_box.ROUNDED,
        show_lines=False,
    )
    table.add_column("Nama", min_width=18, style="white")
    table.add_column("Count", justify="right", style=YELLOW_BOLD)
    table.add_column("CB", justify="center")
    table.add_column("Type", style="dim white")

    for nama, cnt, cb, typ in detailed_rows:
        cb_txt = Text(cb, style=RED if cb == "OFF" else GREEN)
        table.add_row(str(nama)[:22], str(cnt), cb_txt, str(typ))

    return table


def settings_rich(photo_source, history_days, pool_count, manual_stats, total_manual):
    """Return Rich Panel for settings box."""
    if not _RICH_OK:
        return "\n".join(render_settings_box(photo_source, history_days, pool_count, manual_stats, total_manual))

    src_label = "MANUAL (per-item sesuai)" if photo_source == "manual" else "POOL (1 foto untuk semua)"
    src_style = GREEN if photo_source == "manual" else YELLOW

    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold bright_yellow", width=16)
    grid.add_column(style="white")

    grid.add_row("Foto Source:", Text(f"{photo_source.upper()} - {src_label}", style=src_style))
    grid.add_row("History:", f"{history_days} hari")
    grid.add_row("Pool generic:", f"{pool_count} file di photo/pool/")

    if manual_stats:
        bp = manual_stats.get("beban-penyulang", {})
        bt = manual_stats.get("beban-trafo", {})
        tt = manual_stats.get("tegangan-trafo", {})
        grid.add_row("Manual penyulang:", f"{bp.get('folders',0)} folder / {bp.get('files',0)} foto (25 ON + 7 OFF)")
        grid.add_row("Manual beban:", f"{bt.get('folders',0)} folder / {bt.get('files',0)} foto")
        grid.add_row("Manual tegangan:", f"{tt.get('folders',0)} trafo / HV {tt.get('hv',0)} + MV {tt.get('mv',0)} = {tt.get('total',0)} foto")
        grid.add_row("Total manual:", f"{total_manual} foto")

    grid.add_row("Filename:", "fotoBebanPenyulang_YYYY-MM-DD_<hex>.jpg (humanizer tetap)")
    grid.add_row("OFF:", "7 penyulang CB OFF tetap simpan tapi skip input")
    grid.add_row("Varian:", "asli 40%, blur_ringan 20%, blur_berat 10%, kabur_glare 15%, noisy_gelap 15%")

    return Panel(grid, title="[bold bright_yellow]Pengaturan Foto & Pool[/]", border_style=YELLOW, box=_box.ROUNDED, padding=(0, 1))
