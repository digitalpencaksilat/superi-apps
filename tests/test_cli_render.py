#!/usr/bin/env python3
"""Layout/render regression tests for SUPER-I CLI (pure string helpers)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cli_render as r  # noqa: E402


class FmtEmptyRangesTests(unittest.TestCase):
    def test_contiguous_runs_become_ranges(self):
        self.assertEqual(r.fmt_empty_ranges([0, 1, 2, 7, 8, 12, 13, 14, 15]),
                         "0-2, 7-8, 12-15")

    def test_singletons_stay_single(self):
        self.assertEqual(r.fmt_empty_ranges([3, 9, 20]), "3, 9, 20")

    def test_empty_list_returns_empty_symbol(self):
        self.assertEqual(r.fmt_empty_ranges([]), "∅")

    def test_unsorted_input_is_sorted(self):
        self.assertEqual(r.fmt_empty_ranges([8, 1, 2, 0]), "0-2, 8")


class FmtProgressTests(unittest.TestCase):
    def test_pads_to_total_width(self):
        self.assertEqual(r.fmt_progress(3, 8), "[03/08]")

    def test_double_digit_total(self):
        self.assertEqual(r.fmt_progress(5, 12), "[05/12]")

    def test_zero_indexed_first(self):
        self.assertEqual(r.fmt_progress(1, 8), "[01/08]")

    def test_single_digit_total_gets_two_digits(self):
        self.assertEqual(r.fmt_progress(2, 4), "[02/04]")


class FmtFillStripTests(unittest.TestCase):
    def test_24_chars_filled_then_empty(self):
        s = r.fmt_fill_strip([0, 1, 2])
        self.assertEqual(len(s), 24)
        self.assertEqual(s[:3], "███")
        self.assertEqual(s[3:], "░" * 21)

    def test_all_empty(self):
        self.assertEqual(r.fmt_fill_strip([]), "░" * 24)

    def test_all_filled(self):
        self.assertEqual(r.fmt_fill_strip(list(range(24))), "█" * 24)

    def test_unsorted_input(self):
        self.assertEqual(r.fmt_fill_strip([5, 2, 8]), r.fmt_fill_strip([2, 5, 8]))


class RenderItemTableTests(unittest.TestCase):
    def _items(self):
        return [
            {"id": 11, "nama": "CIBADAK", "statusCB": "ON",
             "beban": [{"periode": p, "beban": 100} for p in range(18)]},
            {"id": 22, "nama": "MANGGARAI", "statusCB": "OFF", "beban": []},
        ]

    def test_returns_lines_and_header(self):
        lines = r.render_item_table(self._items(), "beban-penyulang")
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 3)
        self.assertTrue(any("No" in ln and "Nama" in ln for ln in lines))

    def test_columns_align_at_same_offset(self):
        lines = r.render_item_table(self._items(), "beban-penyulang")
        # find "/24" position in each data row, assert consistent
        positions = []
        for ln in lines:
            if "/24" in ln and ln.lstrip().startswith("["):
                positions.append(ln.index("/24"))
        self.assertGreater(len(positions), 1)
        self.assertEqual(len(set(positions)), 1, f"/24 columns misaligned: {positions}")

    def test_cb_off_tagged(self):
        lines = r.render_item_table(self._items(), "beban-penyulang")
        self.assertTrue(any("CB OFF" in ln for ln in lines))

    def test_tegangan_uses_teg_key(self):
        items = [{"id": 1, "nama": "T1", "statusCB": "ON",
                  "tegangan": [{"periode": 0, "mv": 20, "hv": 150}]}]
        lines = r.render_item_table(items, "tegangan-trafo")
        self.assertTrue(any("1/24" in ln for ln in lines))


class RenderExistingDataTests(unittest.TestCase):
    def test_beban_wraps_six_per_line(self):
        entries = [{"periode": p, "beban": 100 + p} for p in range(9)]
        lines = r.render_existing_data(entries, "beban-penyulang")
        self.assertGreaterEqual(len(lines), 2)
        self.assertIn("P00", lines[1])
        self.assertIn("P05", lines[1])
        self.assertIn("P06", lines[2])

    def test_tegangan_shows_hv_and_mv(self):
        entries = [{"periode": 0, "mv": 20, "hv": 150}]
        lines = r.render_existing_data(entries, "tegangan-trafo")
        self.assertTrue(any("HV=150" in ln and "MV=20" in ln for ln in lines))

    def test_includes_fill_strip(self):
        entries = [{"periode": p, "beban": 1} for p in range(3)]
        lines = r.render_existing_data(entries, "beban-penyulang")
        self.assertTrue(any("█" in ln for ln in lines))

    def test_includes_range_line_for_beban(self):
        entries = [{"periode": p, "beban": v} for p, v in [(0, 90), (1, 110)]]
        lines = r.render_existing_data(entries, "beban-penyulang")
        self.assertTrue(any("Range:" in ln and "90" in ln and "110" in ln
                            for ln in lines))

    def test_empty_entries_returns_no_data_line(self):
        lines = r.render_existing_data([], "beban-penyulang")
        self.assertTrue(any("belum" in ln for ln in lines))


class RenderSuggestTableTests(unittest.TestCase):
    def test_columns_aligned(self):
        rows = [
            (1, "CIBADAK", "MV=20 HV=150", "weekday avg 20.0kV"),
            (2, "MANGGARAI", "?", "(tidak ada histori)"),
        ]
        lines = r.render_suggest_table(rows)
        hdr = next(ln for ln in lines if "Suggest" in ln)
        col = hdr.index("Suggest")
        for ln in lines:
            if ln.lstrip()[0:1].isdigit():
                self.assertTrue(ln[col] in ("M", "?", "1", "1"),
                                f"Unexpected char at Suggest col: '{ln[col]}'")

    def test_header_present(self):
        lines = r.render_suggest_table([(1, "X", "100A", "info")])
        self.assertTrue(any("Suggest" in ln for ln in lines))


class RenderSummaryBoxTests(unittest.TestCase):
    def test_contains_counts_and_box(self):
        s = r.render_summary_box(success=6, fail=1, total=7, label="beban")
        self.assertIn("6", s)
        self.assertIn("1", s)
        self.assertIn("━", s)
        self.assertIn("beban", s)

    def test_no_fail_omits_fail_line(self):
        s = r.render_summary_box(success=8, fail=0, total=8, label="tegangan")
        self.assertNotIn("0 gagal", s)


class FmtProgressLineTests(unittest.TestCase):
    def test_ok_line_shape(self):
        s = r.fmt_progress_line(3, 8, "P09", ok=True, detail="MV=20")
        self.assertTrue(s.startswith("[03/08]"))
        self.assertIn("P09", s)
        self.assertIn("✓", s)
        self.assertIn("MV=20", s)

    def test_fail_line_has_x(self):
        s = r.fmt_progress_line(3, 8, "P09", ok=False, detail="timeout")
        self.assertIn("✗", s)
        self.assertIn("timeout", s)

    def test_padded_to_42_chars(self):
        s = r.fmt_progress_line(1, 3, "P00", ok=True, detail="")
        self.assertEqual(len(s), 42)


class RenderDataViewTests(unittest.TestCase):
    def _beban_items(self):
        return [
            {"id": 11, "nama": "CIBADAK", "statusCB": "ON", "iMax": 400,
             "beban": [{"periode": p, "beban": 100} for p in range(18)]},
            {"id": 22, "nama": "TEBET BARAT", "statusCB": "OFF", "iMax": 300,
             "beban": []},
        ]

    def _teg_items(self):
        return [
            {"id": 1, "nama": "TRAFO 1", "isPS": False,
             "tegangan": [{"periode": 0, "mv": 20, "hv": 150}]},
        ]

    def test_returns_lines_with_header(self):
        lines = r.render_data_view(self._beban_items(), "beban-penyulang")
        self.assertIsInstance(lines, list)
        self.assertTrue(any("No" in ln and "Nama" in ln for ln in lines))

    def test_fill_strip_present(self):
        lines = r.render_data_view(self._beban_items(), "beban-penyulang")
        self.assertTrue(any("█" in ln or "░" in ln for ln in lines))

    def test_terisi_column_aligned(self):
        lines = r.render_data_view(self._beban_items(), "beban-penyulang")
        positions = [ln.index("/24") for ln in lines
                     if "/24" in ln and ("█" in ln or "░" in ln)]
        self.assertGreater(len(positions), 1)
        self.assertEqual(len(set(positions)), 1,
                         f"/24 columns misaligned: {positions}")

    def test_cb_off_shows_note_no_kosong(self):
        lines = r.render_data_view(self._beban_items(), "beban-penyulang")
        off_detail = [ln for ln in lines if "CB OFF" in ln and "→" in ln]
        self.assertTrue(off_detail)
        self.assertFalse(any("Kosong:" in ln for ln in off_detail))

    def test_tegangan_shows_mv_hv(self):
        lines = r.render_data_view(self._teg_items(), "tegangan-trafo")
        self.assertTrue(any("MV:" in ln and "HV:" in ln for ln in lines))

    def test_tegangan_has_type_column(self):
        lines = r.render_data_view(self._teg_items(), "tegangan-trafo")
        self.assertTrue(any("Type" in ln for ln in lines))
        self.assertTrue(any("GI" in ln for ln in lines))

    def test_detail_line_indented_with_arrow(self):
        lines = r.render_data_view(self._beban_items(), "beban-penyulang")
        self.assertTrue(any(ln.strip().startswith("→") for ln in lines))

    def test_range_in_detail_for_beban(self):
        lines = r.render_data_view(self._beban_items(), "beban-penyulang")
        self.assertTrue(any("Range:" in ln and "Rata2:" in ln for ln in lines))


class RenderDataSummaryTests(unittest.TestCase):
    def test_contains_counts(self):
        s = r.render_data_summary(3, 27, 45)
        self.assertIn("3", s)
        self.assertIn("27", s)
        self.assertIn("45", s)
        self.assertIn("72", s)  # 3*24

    def test_format(self):
        s = r.render_data_summary(2, 48, 0)
        self.assertIn("2 item", s)
        self.assertIn("48/48", s)


class FmtProgressBarTests(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(r.fmt_progress_bar(0, 32),
                         "[░░░░░░░░░░░░░░░░░░░░░░░░] 0/32 (0%)")
    def test_half(self):
        self.assertEqual(r.fmt_progress_bar(16, 32),
                         "[████████████░░░░░░░░░░░░] 16/32 (50%)")
    def test_full(self):
        self.assertEqual(r.fmt_progress_bar(32, 32),
                         "[████████████████████████] 32/32 (100%)")
    def test_total_zero_safe(self):
        self.assertIn("0/0", r.fmt_progress_bar(0, 0))
    def test_clamps_overshoot(self):
        self.assertEqual(r.fmt_progress_bar(40, 32),
                         r.fmt_progress_bar(32, 32))


class RenderSyncSummaryTests(unittest.TestCase):
    def test_no_fail_no_skip(self):
        lines = r.render_sync_summary("Beban Penyulang", 192, 0, 0, 768)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("  ┏"))
        self.assertTrue(lines[2].startswith("  ┗"))
        self.assertIn("✓ 192 update", lines[1])
        self.assertNotIn("gagal", lines[1])
        self.assertNotIn("skip", lines[1])
        self.assertIn("(192/768)", lines[1])
    def test_with_fail_and_skip(self):
        lines = r.render_sync_summary("Tegangan", 8, 2, 4, 240)
        self.assertIn("✗ 2 gagal", lines[1])
        self.assertIn("⊘ 4 skip", lines[1])
        self.assertIn("(10/240)", lines[1])
    def test_box_border_width_matches_inner(self):
        lines = r.render_sync_summary("X", 1, 0, 0, 4)
        self.assertEqual(len(lines[0]), len(lines[1]))
        self.assertEqual(len(lines[1]), len(lines[2]))


class SuperiAppImportTests(unittest.TestCase):
    def test_imports_with_cli_render(self):
        import importlib
        sa = importlib.import_module("superi_app")
        self.assertTrue(hasattr(sa, "ui"))
        self.assertIsNotNone(sa.ui)
        self.assertTrue(hasattr(sa, "_enable_win_vt100"))


if __name__ == "__main__":
    unittest.main()
