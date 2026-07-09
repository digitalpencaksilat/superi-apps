"""Pure string-rendering helpers for the SUPER-I CLI.

Every function here returns a string (or list of strings) and performs NO
printing, NO network access, and NO input(). This keeps all layout math
unit-testable. Flow functions in superi_app.py import these and print them.
"""


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
    """Compact multi-line view of already-filled periodes.

    Line 1: 24-slot fill strip.
    Then wrapped rows of `P00:100A` (beban) or `P00:HV=150/MV=20` (tegangan),
    6 entries per line. Finally a Range/rata2 line (beban only).
    """
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
    """Aligned suggestion table. rows = list[(no, nama, value_str, info)].

    Columns: No | Nama | Suggest | Info
    """
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
    """Single-line live progress string for submit loops.

    Caller prints this with \\r (no newline) to overwrite in place,
    then prints a final \\n when the loop ends.
    """
    mark = "✓" if ok else "✗"
    tail = f"  {detail}" if detail else ""
    # pad to ~42 chars so short labels overwrite longer previous ones
    base = f"{fmt_progress(n, total)} {label} {mark}{tail}"
    return base.ljust(42)[:42]


# Column widths for render_data_view
_DATA_NAMA_W = 20
_DATA_IMAX_W = 5
_DATA_CB_W = 4
_DATA_TYPE_W = 4
_STRIP_HDR = "Strip (24 jam)"


def render_data_view(items, data_type):
    """Return aligned lines for the 'Lihat Data' view with 24-slot fill strips.

    Per item: one table row (No | Nama | iMax+CB or Type | Terisi | Strip)
    plus an indented detail line with value ranges and kosong ranges.
    CB-OFF beban items show a "CB OFF" note instead of kosong ranges.
    """
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

        # Detail line (indented)
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
    """[████████░░░░░░░░] 16/32 (50%). Pure string, no ANSI.

    Clamps n to [0, total]; total<=0 returns an empty bar with '0/0'.
    """
    if total <= 0:
        return f"[{_EMPTY * width}] 0/0"
    n = min(max(n, 0), total)
    filled = int(round(width * n / total))
    bar = _FILLED * filled + _EMPTY * (width - filled)
    pct = int(round(100 * n / total))
    return f"[{bar}] {n}/{total} ({pct}%)"


def render_sync_summary(label, ok_count, fail_count, skip_count, total):
    """Boxed one-line sync summary (3 lines). Pure string, no ANSI inside inner.

    Mirip render_summary_box tapi dengan field skip + label panjang bebas.
    Border width = len(inner) so the box always aligns.
    """
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
