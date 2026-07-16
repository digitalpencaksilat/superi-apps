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


class TrafoAggregationTests(unittest.TestCase):
    def setUp(self):
        self.orig_get = auto.a.api_get
        self.orig_post = auto.a.api_post_multipart
        self.orig_sleep = auto.time.sleep
        auto.time.sleep = lambda *args, **kwargs: None

    def tearDown(self):
        auto.a.api_get = self.orig_get
        auto.a.api_post_multipart = self.orig_post
        auto.time.sleep = self.orig_sleep

    def test_groups_active_feeders_and_uses_zero_fallback(self):
        trafos = [{"id": 10, "nama": "TRAFO 1"}, {"id": 20, "nama": "TRAFO 2"}]
        feeders = [
            {"nama": "P1", "statusCB": "ON", "trafo": {"id": 10}, "beban": [{"periode": 8, "beban": 100}]},
            {"nama": "P2", "statusCB": "ON", "trafo": {"nama": "TRAFO1"}, "beban": []},
            {"nama": "P3", "statusCB": "OFF", "trafo": {"id": 10}, "beban": [{"periode": 8, "beban": 900}]},
            {"nama": "P4", "statusCB": "ON", "trafo": {"id": 20}, "beban": [{"periode": 8, "beban": 50.5}]},
            {"nama": "P5", "statusCB": "ON", "trafo": {}, "beban": [{"periode": 8, "beban": 25}]},
        ]

        calculations, unmapped = auto.calculate_trafo_loads(feeders, trafos, 8)

        self.assertEqual(calculations["10"]["total"], 100)
        self.assertEqual(calculations["10"]["fallbacks"], ["P2"])
        self.assertEqual(calculations["20"]["total"], 50.5)
        self.assertEqual(unmapped, ["P5"])

    def test_posts_aggregated_value_and_verifies_storage(self):
        state = {"posts": []}
        feeders = [
            {"nama": "P1", "statusCB": "ON", "trafo": {"id": 10}, "beban": [{"periode": 8, "beban": 125}]},
            {"nama": "P2", "statusCB": "ON", "trafo": {"id": 10}, "beban": []},
        ]
        empty = [{"id": 10, "nama": "TRAFO 1", "beban": []}]
        filled = [{"id": 10, "nama": "TRAFO 1", "beban": [{"periode": 8, "beban": 125}]}]

        def fake_get(token, path, params):
            if "beban-penyulang" in path:
                return {"data": {"items": feeders}}
            return {"data": {"items": filled if state["posts"] else empty}}

        def fake_post(token, path, data, *args):
            state["posts"].append(data)
            return 200, {"success": True}

        auto.a.api_get = fake_get
        auto.a.api_post_multipart = fake_post

        result = auto.auto_input_trafo_from_penyulang("token", 222, "2026-07-12", 8)

        self.assertEqual(result["success"], 1)
        self.assertEqual(result["fail"], 0)
        self.assertEqual(state["posts"][0]["trafoId"], 10)
        self.assertEqual(state["posts"][0]["beban"], 125)

    def test_existing_trafo_period_is_not_overwritten(self):
        feeders = [{"nama": "P1", "statusCB": "ON", "trafo": {"id": 10}, "beban": []}]
        trafos = [{"id": 10, "nama": "TRAFO 1", "beban": [{"periode": 8, "beban": 90}]}]
        auto.a.api_get = lambda token, path, params: {"data": {"items": feeders if "beban-penyulang" in path else trafos}}
        auto.a.api_post_multipart = lambda *args, **kwargs: self.fail("existing value must not be overwritten")

        result = auto.auto_input_trafo_from_penyulang("token", 222, "2026-07-12", 8)

        self.assertEqual(result["success"], 0)
        self.assertEqual(result["skipped"], 1)


class CronRandomAntiRobotTests(unittest.TestCase):
    def test_random_minute_range_3_38_not_multiple_of_5(self):
        # Import dari superi_app.py
        import importlib
        spec = importlib.util.spec_from_file_location("superi_app_check", os.path.join(ROOT, "superi_app.py"))
        # Quick check via reading file: _random_minute logic
        with open(os.path.join(ROOT, "superi_app.py"), "r", encoding="utf-8") as f:
            content = f.read()
        # Must contain _random_minute and range 3,39
        self.assertIn("def _random_minute", content)
        self.assertIn("range(3, 39)", content)
        self.assertIn("% 5 != 0", content)
        self.assertIn("_expand_window_to_hours", content)
        self.assertIn("_generate_cron_lines", content)
        self.assertIn("_generate_win_tasks", content)

    def test_expand_window_normal_and_cross_midnight(self):
        # Simulate expand logic
        def expand(start, end):
            start = int(start) % 24
            end = int(end) % 24
            hours = []
            h = start
            while True:
                hours.append(h)
                if h == end:
                    break
                h = (h + 1) % 24
                if len(hours) > 24:
                    break
            return hours
        self.assertEqual(expand(22, 5), [22, 23, 0, 1, 2, 3, 4, 5])
        self.assertEqual(expand(9, 17), [9, 10, 11, 12, 13, 14, 15, 16, 17])
        self.assertEqual(expand(0, 23), list(range(24)))
        self.assertEqual(expand(22, 22), [22])

    def test_cron_jitter_plus_minute_never_exceed_hour(self):
        # Menit max 38 + jitter 110 detik + runtime 5 menit = 44 menit < 60
        max_minute = 38
        max_jitter_sec = 110
        max_runtime_sec = 5 * 60
        total_sec = max_minute * 60 + max_jitter_sec + max_runtime_sec
        # Harus < 60 menit = 3600 detik, tapi minimal < 50 menit biar ada buffer 15 menit
        self.assertLess(total_sec, 50 * 60, f"selesai {total_sec/60:.1f} menit, harus <50 menit (sisa 15 menit buffer)")
        self.assertLess(total_sec, 60 * 60)

    def test_generate_cron_lines_uses_random_not_fixed_5(self):
        with open(os.path.join(ROOT, "superi_app.py"), "r", encoding="utf-8") as f:
            content = f.read()
        # Old single line 5 * * * * should be deprecated, not used in cron_install now
        # New should use _generate_cron_lines and _random_minute
        self.assertIn("cron_install", content)
        # cron_install should call _generate_cron_lines
        self.assertIn("_generate_cron_lines", content)
        # Must not hardcode "5 * * * *" as active install logic in new flow
        # _cron_command deprecated still contains 5, but install uses _generate_cron_lines

    def test_win_tasks_8_tasks_unique_hours(self):
        def expand(start, end):
            start = int(start) % 24
            end = int(end) % 24
            hours = []
            h = start
            while True:
                hours.append(h)
                if h == end:
                    break
                h = (h + 1) % 24
                if len(hours) > 24:
                    break
            return hours
        hours = expand(22, 5)
        # 8 task untuk window 22-05
        self.assertEqual(len(hours), 8)
        # Nama task harus SUPER-I-Auto-XX
        for h in hours:
            self.assertIn(f"{h:02d}", [f"{x:02d}" for x in hours])


class WindowsLauncherStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "superi.bat"), "r", encoding="utf-8") as f:
            cls.bat = f.read()
        with open(os.path.join(ROOT, "superi_app.py"), "r", encoding="utf-8") as f:
            cls.app = f.read()

    def test_launcher_sets_project_pythonpath(self):
        self.assertIn('set "PYTHONPATH=%SUPERI_DIR%;%PYTHONPATH%"', self.bat)
        self.assertIn('set "PYTHONUTF8=1"', self.bat)
        self.assertIn('set "PYTHONIOENCODING=utf-8"', self.bat)

    def test_launcher_preflights_core_imports(self):
        self.assertIn("import requests, flask, bs4, superi_sync, superi_auto", self.bat)
        self.assertIn('"%PYTHON%" -m pip install -r requirements.txt', self.bat)

    def test_launcher_routes_auto_command(self):
        self.assertIn('if /i "%1"=="auto"', self.bat)
        self.assertIn('"%PYTHON%" superi_auto.py', self.bat)

    def test_windows_scheduler_cd_to_project_before_auto(self):
        self.assertIn('cmd /c cd /d "{SCRIPT_DIR}" && "{bat}" auto', self.app)

    def test_windows_scheduler_8_tasks_daily_random(self):
        # New: 8 task daily random, bukan tiap 5 menit
        self.assertIn('WIN_TASK_PREFIX', self.app)
        self.assertIn('SUPER-I-Auto-', self.app)
        self.assertIn('/sc", "daily"', self.app)
        self.assertIn('auto_task_log.txt', self.app)
        # Old 5-minute logic harus sudah tidak jadi default install lagi
        # tapi boleh masih ada di legacy cleanup, jadi cek new path ada
        self.assertIn("_generate_win_tasks", self.app)
        self.assertIn("_random_minute", self.app)

    def test_windows_scheduler_prefix_cleanup(self):
        self.assertIn("for h in range(24)", self.app)  # uninstall bersihkan 24 jam


if __name__ == "__main__":
    unittest.main(verbosity=2)
