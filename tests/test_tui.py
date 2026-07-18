#!/usr/bin/env python3
"""Headless regression tests for the fullscreen Textual shell."""

import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from textual.widgets import Input  # noqa: E402

import superi_tui as tui  # noqa: E402
import superi_settings as settings  # noqa: E402
import superi_batch as batch  # noqa: E402


class TuiCapabilityTests(unittest.TestCase):
    def test_classic_flag_disables_fullscreen(self):
        with patch.object(sys.stdin, "isatty", return_value=True), patch.object(
            sys.stdout, "isatty", return_value=True
        ):
            self.assertFalse(tui.can_run_fullscreen(["--classic"]))

    def test_non_tty_disables_fullscreen(self):
        with patch.object(sys.stdin, "isatty", return_value=False), patch.object(
            sys.stdout, "isatty", return_value=True
        ):
            self.assertFalse(tui.can_run_fullscreen([]))

    def test_tty_enables_fullscreen(self):
        with patch.dict(os.environ, {}, clear=False), patch.object(
            sys.stdin, "isatty", return_value=True
        ), patch.object(sys.stdout, "isatty", return_value=True):
            os.environ.pop("SUPERI_CLASSIC_UI", None)
            self.assertTrue(tui.can_run_fullscreen([]))


class TuiLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_has_operation_and_settings_panels_with_sticky_input(self):
        app = tui.SuperITui(start_session=False)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            self.assertIsNotNone(app.query_one("#panel-view"))
            self.assertIsNotNone(app.query_one("#panel-input"))
            self.assertIsNotNone(app.query_one("#panel-batch-item"))
            self.assertIsNotNone(app.query_one("#panel-batch-hour"))
            self.assertIsNotNone(app.query_one("#settings-session"))
            self.assertIsNotNone(app.query_one("#settings-operational"))
            self.assertIsNotNone(app.query_one("#settings-portal"))
            sticky = app.query_one("#sticky-input", Input)
            self.assertTrue(sticky.has_focus)
            self.assertEqual(app.query_one("#prompt-panel").styles.height.value, 6)

    async def test_wide_settings_use_three_columns(self):
        app = tui.SuperITui(start_session=False)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            settings = app.query_one("#settings-grid")
            self.assertFalse(settings.has_class("settings-medium"))
            self.assertFalse(settings.has_class("settings-narrow"))

    async def test_medium_settings_use_two_columns(self):
        app = tui.SuperITui(start_session=False)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            settings = app.query_one("#settings-grid")
            self.assertTrue(settings.has_class("settings-medium"))
            self.assertFalse(settings.has_class("settings-narrow"))

    async def test_narrow_terminal_switches_grid_class(self):
        app = tui.SuperITui(start_session=False)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            self.assertTrue(app.query_one("#menu-grid").has_class("narrow"))
            self.assertTrue(app.query_one("#settings-grid").has_class("settings-narrow"))

    async def test_settings_statuses_are_separate_widgets(self):
        app = tui.SuperITui(start_session=False)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            self.assertIsNotNone(app.query_one("#setting-date"))
            self.assertIsNotNone(app.query_one("#setting-photo"))
            self.assertIsNotNone(app.query_one("#setting-auto"))
            self.assertIsNotNone(app.query_one("#setting-portal"))

    async def test_menu_submission_dispatches_command(self):
        app = tui.SuperITui(start_session=False)
        called = []
        app.run_command = called.append
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            sticky = app.query_one("#sticky-input", Input)
            sticky.value = "4"
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(called, ["input-feeder"])

    async def test_invalid_menu_shows_error(self):
        app = tui.SuperITui(start_session=False)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            sticky = app.query_one("#sticky-input", Input)
            sticky.value = "xyz"
            await pilot.press("enter")
            await pilot.pause()
            self.assertIn("Menu tidak dikenal", str(app.query_one("#prompt-error").render()))

    async def test_worker_receives_answer_from_sticky_input(self):
        app = tui.SuperITui(start_session=False)
        answers = []

        def workflow():
            app.workflow_thread_id = __import__("threading").get_ident()
            try:
                answers.append(app.prompt_backend.ask("Nilai Ampere", default="100"))
            finally:
                app.workflow_thread_id = None

        async with app.run_test(size=(100, 30)) as pilot:
            app.begin_operation("TEST INPUT")
            app.run_worker(workflow, thread=True, name="prompt-test", exit_on_error=False)
            await pilot.pause()
            sticky = app.query_one("#sticky-input", Input)
            self.assertEqual(sticky.value, "100")
            sticky.value = "125"
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(answers, ["125"])

    async def test_auto_command_opens_native_view(self):
        app = tui.SuperITui(start_session=False)
        with patch("superi_settings.get_auto_snapshot") as snapshot:
            snapshot.return_value = settings.AutoSnapshot(
                False, 22, 5, (22, 23, 0, 1, 2, 3, 4, 5),
                ("penyulang", "trafo", "tegangan"), True, 5, 10,
                True, True, "cron", 8, 8, "COMPLETE",
            )
            async with app.run_test(size=(120, 40)) as pilot:
                app.run_command("auto-settings")
                await pilot.pause()
                self.assertEqual(app.current_view, "auto")
                self.assertTrue(app.query_one("#auto-view").display)
                self.assertFalse(app.query_one("#menu-grid").display)

    async def test_photo_command_opens_native_view(self):
        app = tui.SuperITui(start_session=False)
        with patch("superi_settings.get_photo_snapshot") as snapshot:
            snapshot.return_value = settings.PhotoSnapshot(
                "manual", "manual", "config", 7, 1, 32, 320,
                3, 30, 5, 20, 20, 40, 390,
            )
            async with app.run_test(size=(120, 40)) as pilot:
                app.run_command("photo-settings")
                await pilot.pause()
                self.assertEqual(app.current_view, "photo")
                self.assertTrue(app.query_one("#photo-view").display)
                self.assertFalse(app.query_one("#menu-grid").display)

    async def test_sync_command_opens_native_view(self):
        app = tui.SuperITui(start_session=False)
        app.config = {
            "nip": "123",
            "password": "secret",
            "portal_user": "portal",
            "portal_password": "secret",
        }
        app.date_str = "2026-07-18"
        async with app.run_test(size=(120, 40)) as pilot:
            app.run_command("sync")
            await pilot.pause()
            self.assertEqual(app.current_view, "sync")
            self.assertTrue(app.query_one("#sync-view").display)
            self.assertFalse(app.query_one("#menu-grid").display)
            self.assertIn(
                "Portal APD Jakarta",
                str(app.query_one("#sync-connection-card").render()),
            )

    async def test_sync_view_is_responsive_and_edits_hour_range(self):
        app = tui.SuperITui(start_session=False)
        app.date_str = "2026-07-18"
        async with app.run_test(size=(80, 28)) as pilot:
            app.show_sync_view()
            await pilot.pause()
            self.assertTrue(app.query_one("#sync-grid").has_class("narrow"))

            app._handle_sync_action("2")
            sticky = app.query_one("#sticky-input", Input)
            sticky.value = "8"
            await pilot.press("enter")
            sticky.value = "10"
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(app.pending_values["sync-start"], 8)
            self.assertEqual(app.pending_values["sync-end"], 10)
            self.assertIn(
                "08:00-10:00",
                str(app.query_one("#sync-config-card").render()),
            )

    async def test_busy_prompt_hides_input_and_native_prompt_restores_it(self):
        app = tui.SuperITui(start_session=False)
        async with app.run_test(size=(100, 30)) as pilot:
            app.set_busy_prompt("Sync sedang berjalan...")
            await pilot.pause()
            prompt_panel = app.query_one("#prompt-panel")
            sticky = app.query_one("#sticky-input", Input)
            self.assertTrue(prompt_panel.has_class("busy"))
            self.assertFalse(sticky.display)
            self.assertTrue(sticky.disabled)
            self.assertTrue(app._busy)

            app._set_native_prompt("Pilih aksi", "1-5 atau 0")
            await pilot.pause()
            self.assertFalse(prompt_panel.has_class("busy"))
            self.assertTrue(sticky.display)
            self.assertFalse(sticky.disabled)
            self.assertFalse(app._busy)

    async def test_setup_command_opens_native_masked_view(self):
        app = tui.SuperITui(start_session=False)
        snapshot = settings.CredentialSnapshot(
            "1234567890", True, "portal-user", True, "/project/.superi_config.json"
        )
        with patch("superi_settings.get_credential_snapshot", return_value=snapshot), patch(
            "superi_app.load_config", return_value={"nip": "1234567890"}
        ):
            async with app.run_test(size=(120, 40)) as pilot:
                app.run_command("setup")
                await pilot.pause()
                self.assertEqual(app.current_view, "setup")
                self.assertTrue(app.query_one("#setup-view").display)
                content = str(app.query_one("#setup-superi-card").render())
                self.assertNotIn("1234567890", content)
                self.assertIn("12", content)
                self.assertIn("90", content)

    async def test_setup_password_editor_is_masked(self):
        app = tui.SuperITui(start_session=False)
        snapshot = settings.CredentialSnapshot("123", True, "portal", True, "/config")
        with patch("superi_settings.get_credential_snapshot", return_value=snapshot):
            async with app.run_test(size=(100, 32)) as pilot:
                app.show_setup_view()
                app._handle_setup_action("1")
                sticky = app.query_one("#sticky-input", Input)
                sticky.value = ""
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.pending_editor, "setup-password")
                self.assertTrue(sticky.password)
                self.assertEqual(sticky.value, "")

    async def test_setup_narrow_layout_and_superi_save_invalidates_session(self):
        app = tui.SuperITui(start_session=False)
        app.token, app.user, app.gi_id = "token", {"namaLengkap": "User"}, 222
        snapshot = settings.CredentialSnapshot("123", True, "portal", True, "/config")
        with patch("superi_settings.get_credential_snapshot", return_value=snapshot), patch(
            "superi_settings.update_credentials", return_value=snapshot
        ) as update, patch("superi_app.load_config", return_value={"nip": "456"}), patch(
            "importlib.reload", side_effect=lambda module: module
        ):
            async with app.run_test(size=(80, 28)) as pilot:
                app.show_setup_view()
                await pilot.pause()
                self.assertTrue(app.query_one("#setup-grid").has_class("narrow"))
                app.pending_values["setup-draft"] = {"nip": "456", "password": "new-secret"}
                app._save_credential_draft()
                update.assert_called_once_with(nip="456", password="new-secret")
                self.assertIsNone(app.token)
                self.assertIsNone(app.user)
                self.assertIsNone(app.gi_id)

    async def test_relogin_displays_success_result(self):
        app = tui.SuperITui(start_session=False)
        user = {"namaLengkap": "Operator GI"}
        with patch("superi_app.load_config", return_value={"nip": "123"}), patch(
            "superi_app.do_login", return_value=("token", user, 222)
        ), patch("superi_console.ok") as ok, patch("superi_console.pause") as pause:
            app._login()

        self.assertEqual(app.token, "token")
        ok.assert_called_once_with("LOGIN ULANG BERHASIL · Operator GI · GI 222")
        pause.assert_called_once_with("Login berhasil. Tekan Enter untuk kembali...")

    async def test_relogin_displays_failure_and_clears_identity(self):
        app = tui.SuperITui(start_session=False)
        app.token, app.user, app.gi_id = "old", {"namaLengkap": "Old"}, 222
        with patch("superi_app.load_config", return_value={"nip": "123"}), patch(
            "superi_app.do_login", return_value=(None, None, None)
        ), patch("superi_console.err") as err, patch(
            "superi_console.warn_msg"
        ) as warn, patch("superi_console.pause") as pause:
            app._login()

        self.assertIsNone(app.token)
        self.assertIsNone(app.user)
        self.assertIsNone(app.gi_id)
        err.assert_called_once_with("LOGIN ULANG GAGAL")
        warn.assert_called_once()
        pause.assert_called_once_with("Login gagal. Tekan Enter untuk kembali...")

    async def test_batch_hour_commands_open_native_view_without_classic_header(self):
        app = tui.SuperITui(start_session=False)
        overview = batch.BatchOverview(
            "beban-penyulang", "Beban Penyulang", "2026-07-18",
            ({"id": 1, "nama": "P1", "beban": []},),
            tuple((({"id": 1, "nama": "P1", "beban": []},) for _ in range(24))),
        )
        app.date_str = "2026-07-18"
        app.token, app.gi_id = "token", 222
        with patch("superi_batch.load_overview", return_value=overview), patch(
            "superi_app.batch_fill_periode"
        ) as classic:
            async with app.run_test(size=(120, 40)) as pilot:
                app.run_command("batch-hour-feeder")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.current_view, "batch-hour")
                self.assertTrue(app.query_one("#batch-hour-view").display)
                self.assertIn(
                    "MENU UTAMA / BATCH PER JAM / BEBAN PENYULANG",
                    str(app.query_one("#batch-hour-heading").render()),
                )
                classic.assert_not_called()

    async def test_batch_voltage_suggestions_use_mv_hv_columns(self):
        app = tui.SuperITui(start_session=False)
        item = {"id": 1, "nama": "TRAFO 1", "tegangan": [], "_batch_type": "tegangan-trafo"}
        overview = batch.BatchOverview(
            "tegangan-trafo", "Tegangan Trafo", "2026-07-18", (item,),
            tuple(((item,) for _ in range(24))),
        )
        app.pending_values.update({
            "batch-overview": overview,
            "batch-period": 8,
            "batch-suggestions": [batch.BatchSuggestion(item, 20.4, 150, "History 7 hari")],
        })
        with patch("superi_app.get_history_days", return_value=7):
            async with app.run_test(size=(100, 32)) as pilot:
                app.show_batch_hour_view("tegangan-trafo")
                await pilot.pause()
                columns = [column.label.plain for column in app.query_one("#batch-hour-table").columns.values()]
                self.assertIn("MV", columns)
                self.assertIn("HV", columns)

    async def test_batch_sync_handoff_keeps_type_date_and_period(self):
        app = tui.SuperITui(start_session=False)
        overview = batch.BatchOverview("beban-trafo", "Beban Trafo", "2026-07-18", (), tuple(() for _ in range(24)))
        app.pending_values.update({
            "batch-overview": overview,
            "batch-period": 9,
            "batch-result": batch.BatchResult(3, 3, 0),
        })
        called = []
        app.show_sync_view = lambda *args, **kwargs: called.append(True)
        async with app.run_test(size=(100, 30)) as pilot:
            app.current_view = "batch-hour"
            app._handle_batch_hour_action("5")
            await pilot.pause()
            self.assertEqual(app.pending_values["sync-types"], ("trafo",))
            self.assertEqual(app.pending_values["sync-start"], 9)
            self.assertEqual(app.pending_values["sync-end"], 9)
            self.assertEqual(app.pending_values["sync-date"], "2026-07-18")
            self.assertEqual(called, [True])

    async def test_view_data_command_uses_native_full_width_table_without_classic_header(self):
        app = tui.SuperITui(start_session=False)
        app.date_str = "2026-07-18"
        app.token, app.gi_id = "token", 222
        items = [{
            "id": 1,
            "nama": "PENYULANG SATU",
            "statusCB": "ON",
            "iMax": 400,
            "beban": [{"periode": 8, "beban": 125}],
        }]
        response = {"data": {"items": items}}
        with patch("superi_app.api_get", return_value=response), patch(
            "superi_app.show_data"
        ) as classic:
            async with app.run_test(size=(120, 40)) as pilot:
                app.run_command("view-feeder")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.current_view, "data")
                self.assertTrue(app.query_one("#data-view").display)
                self.assertIn(
                    "MENU UTAMA / LIHAT DATA / BEBAN PENYULANG",
                    str(app.query_one("#data-heading").render()),
                )
                self.assertEqual(app.query_one("#data-table").styles.width.value, 100.0)
                classic.assert_not_called()

    async def test_view_voltage_narrow_table_keeps_24_hour_strip(self):
        app = tui.SuperITui(start_session=False)
        app.date_str = "2026-07-18"
        app.token, app.gi_id = "token", 222
        items = [{
            "id": 1,
            "nama": "TRAFO 1",
            "isPS": False,
            "tegangan": [{"periode": 8, "mv": 20.4, "hv": 150}],
        }]
        with patch("superi_app.api_get", return_value={"data": {"items": items}}):
            async with app.run_test(size=(80, 28)) as pilot:
                app.run_command("view-voltage")
                await pilot.pause()
                await pilot.pause()
                table = app.query_one("#data-table")
                columns = [column.label.plain for column in table.columns.values()]
                self.assertEqual(columns, ["No", "Nama", "Tipe", "Terisi", "24 Jam"])
                row = table.get_row_at(0)
                self.assertEqual(len(str(row[-1])), 24)

    async def test_manual_input_command_uses_native_full_width_item_table(self):
        app = tui.SuperITui(start_session=False)
        app.date_str = "2026-07-18"
        app.token, app.gi_id = "token", 222
        items = [{"id": 1, "nama": "PENYULANG SATU", "statusCB": "ON", "beban": []}]
        with patch("superi_app.api_get", return_value={"data": {"items": items}}), patch(
            "superi_app.input_single"
        ) as classic:
            async with app.run_test(size=(120, 40)) as pilot:
                app.run_command("input-feeder")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.current_view, "manual-input")
                self.assertTrue(app.query_one("#manual-input-view").display)
                self.assertIn(
                    "MENU UTAMA / INPUT MANUAL / BEBAN PENYULANG",
                    str(app.query_one("#manual-input-heading").render()),
                )
                self.assertEqual(app.query_one("#manual-input-table").styles.width.value, 100.0)
                classic.assert_not_called()

    async def test_manual_input_rejects_cb_off_before_workflow(self):
        app = tui.SuperITui(start_session=False)
        app.pending_values.update({
            "manual-data-type": "beban-penyulang",
            "manual-items": ({"id": 1, "nama": "PENYULANG OFF", "statusCB": "OFF", "beban": []},),
        })
        app._start_manual_input = unittest.mock.Mock()
        async with app.run_test(size=(100, 30)) as pilot:
            app.current_view = "manual-input"
            app._handle_manual_item_selection("1")
            await pilot.pause()
            app._start_manual_input.assert_not_called()
            self.assertIn("CB OFF", str(app.query_one("#prompt-error").render()))

    async def test_manual_selected_item_skips_duplicate_header_and_table(self):
        app = tui.SuperITui(start_session=False)
        app.token, app.user, app.gi_id = "token", {"namaLengkap": "User"}, 222
        app.date_str = "2026-07-18"
        item = {"id": 1, "nama": "TRAFO 1", "beban": []}
        app.pending_values["manual-data-type"] = "beban-trafo"
        with patch("superi_app.input_single") as workflow:
            async with app.run_test(size=(100, 30)) as pilot:
                app._start_manual_input(item)
                await pilot.pause()
                await pilot.pause()
                workflow.assert_called_once_with(
                    "token", "beban-trafo", 222, "2026-07-18", app.user,
                    selected_item=item, show_header=False,
                )

    async def test_auto_toggle_uses_settings_service(self):
        app = tui.SuperITui(start_session=False)
        snap = settings.AutoSnapshot(
            False, 22, 5, (22, 23, 0, 1, 2, 3, 4, 5),
            ("penyulang",), True, 5, 10, False, True,
            "cron", 0, 8, "BELUM",
        )
        with patch("superi_settings.get_auto_snapshot", return_value=snap), patch(
            "superi_settings.set_auto_enabled"
        ) as toggle:
            async with app.run_test(size=(120, 40)) as pilot:
                app.show_auto_view()
                await pilot.pause()
                app._handle_auto_action("1")
                toggle.assert_called_once_with(True)

    async def test_native_child_back_returns_to_photo(self):
        app = tui.SuperITui(start_session=False)
        snapshot = settings.PhotoSnapshot(
            "pool", "pool", "default", 7, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0
        )
        with patch("superi_settings.get_photo_snapshot", return_value=snapshot), patch(
            "superi_settings.get_pool_details", return_value=settings.PoolDetail()
        ):
            async with app.run_test(size=(100, 32)) as pilot:
                app.show_photo_view()
                app._show_pool_details()
                await pilot.pause()
                self.assertEqual(app.current_view, "table")
                app.action_back()
                await pilot.pause()
                self.assertEqual(app.current_view, "photo")


class SettingsServiceTests(unittest.TestCase):
    def test_auto_types_require_one_selection(self):
        with self.assertRaises(ValueError):
            settings.set_auto_types([])

    def test_auto_window_validates_hours(self):
        with self.assertRaises(ValueError):
            settings.set_auto_window(24, 5)

    def test_history_validates_domain(self):
        with self.assertRaises(ValueError):
            settings.set_history_days(5)

    def test_update_credentials_preserves_unsupplied_values(self):
        core = unittest.mock.Mock()
        core.CONFIG_FILE = "/project/.superi_config.json"
        core.load_config.side_effect = [
            {"nip": "123", "password": "old", "portal_user": "portal", "portal_password": "keep"},
            {"nip": "123", "password": "new", "portal_user": "portal", "portal_password": "keep"},
        ]
        with patch("superi_settings._core", return_value=core):
            snapshot = settings.update_credentials(password="new")

        saved = core.save_config.call_args.args[0]
        self.assertEqual(saved["nip"], "123")
        self.assertEqual(saved["password"], "new")
        self.assertEqual(saved["portal_password"], "keep")
        self.assertTrue(snapshot.superi_ready)

    def test_cron_schedule_plan_keeps_generated_minutes(self):
        lines = (
            "3 22 * * * command # SUPER-I-AUTO",
            "7 23 * * * command # SUPER-I-AUTO",
            "11 0 * * * command # SUPER-I-AUTO",
        )
        core = unittest.mock.Mock()
        core._generate_cron_lines.return_value = lines
        with patch("superi_settings._core", return_value=core), patch(
            "superi_settings.platform.system", return_value="Darwin"
        ):
            plan = settings.build_schedule_plan(22, 0)

        self.assertEqual(
            plan.entries,
            (
                ("SUPER-I-Auto-22", 22, 3),
                ("SUPER-I-Auto-23", 23, 7),
                ("SUPER-I-Auto-00", 0, 11),
            ),
        )
        self.assertEqual(plan.cron_lines, lines)

    def test_install_scheduler_reuses_exact_cron_plan(self):
        plan = settings.SchedulePlan(
            "cron",
            22,
            22,
            (("SUPER-I-Auto-22", 22, 13),),
            ("13 22 * * * command # SUPER-I-AUTO",),
        )
        core = unittest.mock.Mock()
        core.cron_install.return_value = True, ""
        with patch("superi_settings._core", return_value=core), patch(
            "superi_settings.platform.system", return_value="Darwin"
        ):
            result = settings.install_scheduler(22, 22, plan=plan)

        self.assertEqual(result, (True, ""))
        core.cron_install.assert_called_once_with(
            22, 22, planned_lines=plan.cron_lines
        )

    def test_install_scheduler_reuses_exact_windows_plan(self):
        plan = settings.SchedulePlan(
            "Task Scheduler",
            22,
            23,
            (
                ("SUPER-I-Auto-22", 22, 13),
                ("SUPER-I-Auto-23", 23, 17),
            ),
        )
        core = unittest.mock.Mock()
        core.win_task_install.return_value = True, "2 task terpasang"
        with patch("superi_settings._core", return_value=core), patch(
            "superi_settings.platform.system", return_value="Windows"
        ):
            result = settings.install_scheduler(22, 23, plan=plan)

        self.assertEqual(result, (True, "2 task terpasang"))
        core.win_task_install.assert_called_once_with(
            22, 23, planned_tasks=plan.entries
        )


class BatchServiceTests(unittest.TestCase):
    def test_load_overview_skips_cb_off_and_filled_periods(self):
        items = [
            {"id": 1, "nama": "ON", "statusCB": "ON", "beban": [{"periode": 8, "beban": 100}]},
            {"id": 2, "nama": "EMPTY", "statusCB": "ON", "beban": []},
            {"id": 3, "nama": "OFF", "statusCB": "OFF", "beban": []},
        ]
        core = unittest.mock.Mock()
        core.ENDPOINTS = {"beban-penyulang": {"label": "Beban Penyulang", "list": "/list"}}
        core.api_get.return_value = {"data": {"items": items}}
        with patch.dict(sys.modules, {"superi_app": core}):
            overview = batch.load_overview("token", "beban-penyulang", 222, "2026-07-18")

        self.assertEqual([item["nama"] for item in overview.empty_by_period[8]], ["EMPTY"])
        self.assertEqual(overview.active_items, 2)

    def test_submit_rolls_back_record_when_photo_fails(self):
        item = {"id": 1, "nama": "TRAFO 1", "_batch_type": "tegangan-trafo"}
        overview = batch.BatchOverview("tegangan-trafo", "Tegangan Trafo", "2026-07-18", (item,), tuple(() for _ in range(24)))
        core = unittest.mock.Mock()
        core.ENDPOINTS = {"tegangan-trafo": {"id_field": "trafoId", "value_field": "mv", "input": "/input", "delete": "/delete", "file_field": "files", "num_photos": 2}}
        core.hu = None
        core.DUMMY_JPEG = b"jpeg"
        core._human_shuffled.side_effect = lambda values: values
        core._human_durasi.return_value = 0.1
        core._human_foto_pair_dicts.return_value = ({}, {})
        core.api_post_multipart.return_value = (200, {"success": True, "data": {"id": 99}, "_photo_upload": {"ok": False}})
        with patch.dict(sys.modules, {"superi_app": core}):
            result = batch.submit_period(overview, 8, [batch.BatchSuggestion(item, 20.4, 150)], "token")

        self.assertEqual(result.failed, 1)
        core.api_delete.assert_called_once_with("token", "/delete/99")


if __name__ == "__main__":
    unittest.main()
