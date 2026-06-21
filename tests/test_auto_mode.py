#!/usr/bin/env python3
"""Regression tests for SUPER-I Auto Mode and Windows launcher wiring."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import superi_auto as auto  # noqa: E402


class AutoModeRetryTests(unittest.TestCase):
    def setUp(self):
        self.orig_get = auto.a.api_get
        self.orig_post = auto.a.api_post_multipart
        self.orig_hist = auto.a.fetch_history_bulk
        self.orig_suggest = auto.a.smart_suggest_from_cache
        self.orig_suggest_teg = auto.a.smart_suggest_tegangan_from_cache
        self.orig_sleep = auto.time.sleep
        auto.time.sleep = lambda *args, **kwargs: None

    def tearDown(self):
        auto.a.api_get = self.orig_get
        auto.a.api_post_multipart = self.orig_post
        auto.a.fetch_history_bulk = self.orig_hist
        auto.a.smart_suggest_from_cache = self.orig_suggest
        auto.a.smart_suggest_tegangan_from_cache = self.orig_suggest_teg
        auto.time.sleep = self.orig_sleep

    def test_retry_until_verified_filled(self):
        state = {"get_calls": 0, "post_calls": 0}
        empty = [{"id": 1, "nama": "PENYULANG TEST", "statusCB": "ON", "beban": []}]
        filled = [{"id": 1, "nama": "PENYULANG TEST", "statusCB": "ON", "beban": [{"periode": 8, "beban": 100}]}]

        def fake_get(token, path, params):
            state["get_calls"] += 1
            return {"data": {"items": filled if state["post_calls"] >= 2 else empty}}

        def fake_post(*args, **kwargs):
            state["post_calls"] += 1
            return 200, {"success": state["post_calls"] >= 2, "message": "temporary fail"}

        auto.a.api_get = fake_get
        auto.a.api_post_multipart = fake_post
        auto.a.fetch_history_bulk = lambda *a, **k: {1: {"periode_data": {8: {"all": [95, 100, 105]}}}}
        auto.a.smart_suggest_from_cache = lambda *a, **k: (100, "test")

        result = auto.auto_input_jam("token", "beban-penyulang", 222, "2026-06-21", 8, max_attempts=3, retry_delay=1)

        self.assertEqual(result["success"], 1)
        self.assertEqual(result["fail"], 0)
        self.assertEqual(state["post_calls"], 2)
        self.assertGreaterEqual(state["get_calls"], 3)

    def test_no_history_period_falls_back_to_other_periods(self):
        cache = {1: {"name": "PENYULANG TEST", "periode_data": {7: {"all": [90, 100, 110]}, 9: {"all": [120]}}}}
        val, hist = auto.fallback_beban_from_cache(cache, 1)
        self.assertEqual(val, 105)
        self.assertEqual(hist, [90, 100, 110, 120])

    def test_tegangan_fallback_keeps_rounding_rules(self):
        cache = {2: {"name": "TRAFO 2", "periode_data": {7: {"all": [{"mv": 20.31, "hv": 150}, {"mv": 20.45, "hv": 151}]}}}}
        mv, hv, mv_hist, hv_hist = auto.fallback_tegangan_from_cache(cache, 2)
        self.assertEqual(mv, 20.38)
        self.assertEqual(hv, 150)
        self.assertEqual(mv_hist, [20.31, 20.45])
        self.assertEqual(hv_hist, [150, 151])

    def test_anomaly_clamps_instead_of_skipping(self):
        self.assertEqual(auto.clamp_to_history(200, [80, 100, 120]), 120)
        self.assertEqual(auto.clamp_to_history(50, [80, 100, 120]), 80)
        is_anom, reason = auto.is_anomaly(200, [80, 100, 120])
        self.assertTrue(is_anom)
        self.assertIn("deviasi", reason)


class WindowsLauncherStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "superi.bat"), "r", encoding="utf-8") as f:
            cls.bat = f.read()
        with open(os.path.join(ROOT, "superi_app.py"), "r", encoding="utf-8") as f:
            cls.app = f.read()

    def test_launcher_sets_project_pythonpath(self):
        self.assertIn('set "PYTHONPATH=%SUPERI_DIR%;%PYTHONPATH%"', self.bat)

    def test_launcher_preflights_core_imports(self):
        self.assertIn("import requests, flask, bs4, superi_sync, superi_auto", self.bat)
        self.assertIn('"%PYTHON%" -m pip install -r requirements.txt', self.bat)

    def test_launcher_routes_auto_command(self):
        self.assertIn('if /i "%1"=="auto"', self.bat)
        self.assertIn('"%PYTHON%" superi_auto.py', self.bat)

    def test_windows_scheduler_cd_to_project_before_auto(self):
        self.assertIn('cmd /c cd /d "{SCRIPT_DIR}" && "{bat}" auto', self.app)

    def test_windows_scheduler_runs_every_5_minutes_and_logs(self):
        self.assertIn('"/sc", "minute", "/mo", "5"', self.app)
        self.assertIn('auto_task_log.txt', self.app)


if __name__ == "__main__":
    unittest.main(verbosity=2)
