#!/usr/bin/env python3
"""Regression tests for the optional sync progress callback."""

import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import superi_sync  # noqa: E402


class SyncProgressCallbackTests(unittest.TestCase):
    def test_callback_reports_initial_and_completed_cells(self):
        progress = []
        superi_data = {"Item A": [10, 20]}
        portal_grid = {"Item A": {"j00": "0", "j01": "0"}}

        with patch.object(superi_sync, "superi_login", return_value="token"), patch.object(
            superi_sync, "fetch_superi_data", return_value=superi_data
        ), patch.object(superi_sync.PortalPLN, "login", return_value=True), patch.object(
            superi_sync.PortalPLN, "fetch_grid", return_value=portal_grid
        ), patch.object(superi_sync.PortalPLN, "update_cell", return_value=True), patch.object(
            superi_sync, "RICH", False
        ):
            result = superi_sync.do_sync(
                "penyulang",
                0,
                1,
                "2026-07-18",
                dry_run=False,
                progress_callback=lambda done, total, item: progress.append((done, total, item)),
            )

        self.assertTrue(result)
        self.assertEqual(progress[0], (0, 2, ""))
        self.assertEqual(progress[-1], (2, 2, "Item A"))
        self.assertEqual([entry[0] for entry in progress], [0, 1, 2])

    def test_embedded_events_replace_legacy_terminal_output(self):
        events = []
        output = StringIO()
        superi_data = {"Item A": [10, 20]}
        portal_grid = {"Item A": {"j00": "0", "j01": "0"}}

        with patch.object(superi_sync, "superi_login", return_value="token"), patch.object(
            superi_sync, "fetch_superi_data", return_value=superi_data
        ), patch.object(superi_sync.PortalPLN, "login", return_value=True), patch.object(
            superi_sync.PortalPLN, "fetch_grid", return_value=portal_grid
        ), patch.object(superi_sync.PortalPLN, "update_cell", return_value=True), patch.object(
            superi_sync, "RICH", False
        ), redirect_stdout(output):
            result = superi_sync.do_sync(
                "penyulang",
                0,
                1,
                "2026-07-18",
                dry_run=False,
                progress_callback=lambda *_: None,
                event_callback=lambda event, data: events.append((event, data)),
            )

        self.assertTrue(result)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(
            [event for event, _ in events],
            ["section", "stage", "stage_ok", "stage", "stage_ok", "stage", "stage_ok", "stage", "stage_ok", "stage", "summary"],
        )

    def test_cli_fallback_remains_when_no_callbacks_are_used(self):
        output = StringIO()
        superi_data = {"Item A": [10]}
        portal_grid = {"Item A": {"j00": "0"}}

        with patch.object(superi_sync, "superi_login", return_value="token"), patch.object(
            superi_sync, "fetch_superi_data", return_value=superi_data
        ), patch.object(superi_sync.PortalPLN, "login", return_value=True), patch.object(
            superi_sync.PortalPLN, "fetch_grid", return_value=portal_grid
        ), patch.object(superi_sync.PortalPLN, "update_cell", return_value=True), patch.object(
            superi_sync, "RICH", False
        ), redirect_stdout(output):
            self.assertTrue(superi_sync.do_sync("penyulang", 0, 0, "2026-07-18", dry_run=False))

        self.assertIn("████", output.getvalue())


if __name__ == "__main__":
    unittest.main()
