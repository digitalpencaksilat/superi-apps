#!/usr/bin/env python3
"""Fullscreen Textual shell for the interactive SUPER-I workflows."""

from __future__ import annotations

import builtins
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from rich.markup import escape
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Input, Markdown, ProgressBar, RichLog, Static
from textual.worker import Worker, WorkerState

import superi_console as sc


MENU_COMMANDS = {
    "1": "view-feeder",
    "2": "view-transformer",
    "3": "view-voltage",
    "4": "input-feeder",
    "5": "input-transformer",
    "6": "input-voltage",
    "a": "batch-hour-feeder",
    "b": "batch-hour-transformer",
    "c": "batch-hour-voltage",
    "g": "change-date",
    "l": "login",
    "o": "logout",
    "s": "setup",
    "t": "photo-settings",
    "p": "sync",
    "d": "auto-settings",
    "0": "quit",
}


def can_run_fullscreen(argv=None) -> bool:
    """Return True only for an interactive terminal and no classic override."""
    argv = list(sys.argv[1:] if argv is None else argv)
    classic = "--classic" in argv or os.environ.get("SUPERI_CLASSIC_UI") == "1"
    return not classic and sys.stdin.isatty() and sys.stdout.isatty()


class MenuPanel(Static):
    """A titled dashboard panel containing a group of keyboard commands."""

    def __init__(self, title: str, content: str, *, id: str, classes: str = ""):
        super().__init__(content, id=id, classes=f"menu-panel {classes}".strip(), markup=True)
        self.border_title = title


class SettingRow(Horizontal):
    """One settings action with a separately aligned optional status."""

    def __init__(
        self,
        key: str,
        label: str,
        *,
        status_id: Optional[str] = None,
        dangerous: bool = False,
    ):
        super().__init__(classes="setting-row")
        self.key = key
        self.label = label
        self.status_id = status_id
        self.dangerous = dangerous

    def compose(self) -> ComposeResult:
        style = "bold red" if self.dangerous else "bold #ffc107"
        yield Static(
            f"[{style}][{escape(self.key)}][/] {escape(self.label)}",
            classes="setting-action",
        )
        yield Static("", id=self.status_id, classes="setting-status")


class SettingsPanel(Vertical):
    """A structured settings group rendered as its own bordered panel."""

    def __init__(self, title: str, rows: list[SettingRow], *, id: str):
        super().__init__(*rows, id=id, classes="settings-panel")
        self.border_title = title


class StatusCard(Static):
    """Reusable native card for settings snapshots."""

    def __init__(self, title: str, *, id: str, classes: str = ""):
        super().__init__("", id=id, classes=f"status-card {classes}".strip(), markup=True)
        self.border_title = title


class ThreadOutput:
    """File-like stream forwarding complete lines to the Textual viewport."""

    def __init__(self, app: "SuperITui"):
        self.app = app
        self._buffer = ""

    def write(self, data) -> int:
        text = str(data)
        self._buffer += text
        while "\n" in self._buffer or "\r" in self._buffer:
            newline = self._buffer.find("\n")
            carriage = self._buffer.find("\r")
            if carriage >= 0 and (newline < 0 or carriage < newline):
                # Terminal progress redraws the same line with CR. Keep only the
                # latest frame instead of flooding RichLog with every redraw.
                self._buffer = self._buffer[carriage + 1:]
                continue
            line, self._buffer = self._buffer.split("\n", 1)
            self.app.call_from_thread(self.app.write_output, line)
        return len(text)

    def flush(self):
        if self._buffer:
            text, self._buffer = self._buffer, ""
            self.app.call_from_thread(self.app.write_output, text)

    @property
    def encoding(self):
        return "utf-8"

    def isatty(self):
        return True


class ThreadAwareStream:
    """Route only the workflow worker thread away from the real terminal."""

    def __init__(self, original, app: "SuperITui"):
        self.original = original
        self.app = app

    def write(self, data):
        target = self.app.worker_output if self.app.is_workflow_thread() else self.original
        return target.write(data)

    def flush(self):
        target = self.app.worker_output if self.app.is_workflow_thread() else self.original
        return target.flush()

    def __getattr__(self, name):
        return getattr(self.original, name)


@dataclass
class PromptRequest:
    question: str
    default: Optional[str] = None
    choices: Optional[list[str]] = None
    password: bool = False
    pause: bool = False


class StickyPromptBackend:
    """Synchronously bridge a workflow thread to Textual's sticky Input."""

    def __init__(self, app: "SuperITui"):
        self.app = app
        self._event: Optional[threading.Event] = None
        self._result = ""
        self._cancelled = False

    @property
    def active(self) -> bool:
        return self._event is not None

    def ask(self, question, default=None, choices=None, password=False):
        request = PromptRequest(
            question=str(question),
            default=None if default is None else str(default),
            choices=[str(choice).lower() for choice in choices] if choices else None,
            password=password,
        )
        while True:
            value = self._wait(request)
            if request.choices and value.lower() not in request.choices:
                self.app.call_from_thread(
                    self.app.set_prompt_error,
                    "Pilihan valid: " + ", ".join(request.choices),
                )
                continue
            return value

    def confirm(self, question, default=False):
        suffix = "Y/n" if default else "y/N"
        value = self._wait(PromptRequest(f"{question} ({suffix})", default="y" if default else "n"))
        return value.strip().lower() in ("y", "yes")

    def pause(self, message):
        self._wait(PromptRequest(str(message), pause=True))

    def raw_input(self, prompt=""):
        return self._wait(PromptRequest(str(prompt).strip() or "Masukkan nilai"))

    def submit(self, value: str):
        if not self._event:
            return
        self._result = value
        self._event.set()

    def cancel(self):
        if not self._event:
            return
        self._cancelled = True
        self._result = ""
        self._event.set()

    def _wait(self, request: PromptRequest) -> str:
        event = threading.Event()
        self._event = event
        self._result = ""
        self._cancelled = False
        self.app.call_from_thread(self.app.show_prompt, request)
        event.wait()
        result = self._result
        self._event = None
        self.app.call_from_thread(self.app.hide_prompt_error)
        if request.pause:
            return ""
        if not result and request.default is not None and not self._cancelled:
            return request.default
        return result


class SuperITui(App[None]):
    """Fullscreen dashboard with modular menu panels and sticky input."""

    TITLE = "SUPER-I APP"
    SUB_TITLE = "GI MANGGARAI · Data Input & Sync Tool"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("ctrl+q", "request_quit", "Keluar", priority=True),
        Binding("escape", "back", "Kembali", priority=True),
        Binding("f1", "help", "Bantuan"),
        Binding("ctrl+l", "redraw", "Refresh"),
    ]

    CSS = """
    $amber: #ffc107;
    $amber-soft: #b28704;
    $amber-dark: #2b2204;
    $surface: #111111;
    $surface-soft: #191919;

    Screen {
        background: #050505;
        color: #f5f5f5;
    }

    #shell {
        width: 100%;
        height: 100%;
        border: round $amber;
        background: #090909;
    }

    #app-header {
        height: 4;
        padding: 0 2;
        background: $amber-dark;
        border-bottom: solid $amber-soft;
        content-align: left middle;
    }

    #content-scroll {
        height: 1fr;
        padding: 1 2;
        scrollbar-color: $amber;
        scrollbar-color-hover: #ffd54f;
        scrollbar-background: #111111;
    }

    #menu-grid {
        layout: grid;
        grid-size: 2 3;
        grid-columns: 1fr 1fr;
        grid-rows: auto auto auto;
        grid-gutter: 1 2;
        width: 100%;
        height: auto;
    }

    #menu-grid.narrow {
        grid-size: 1 4;
        grid-columns: 1fr;
        grid-rows: auto auto auto auto;
    }

    .menu-panel {
        height: auto;
        min-height: 7;
        padding: 1 2;
        border: round $amber-soft;
        background: $surface;
        color: #eeeeee;
    }

    #panel-batch-hour {
        column-span: 2;
    }

    #settings-section {
        column-span: 2;
        height: 8;
    }

    #menu-grid.narrow #settings-section {
        column-span: 1;
    }

    #menu-grid.narrow #panel-batch-hour {
        column-span: 1;
    }

    #settings-grid {
        layout: grid;
        grid-size: 3 1;
        grid-columns: 1fr 1fr 1fr;
        grid-rows: auto;
        grid-gutter: 0 1;
        width: 100%;
        height: 8;
    }

    #settings-grid.settings-medium {
        grid-size: 2 2;
        grid-columns: 1fr 1fr;
        grid-rows: auto auto;
        grid-gutter: 1 2;
        height: 17;
    }

    #settings-grid.settings-medium #settings-portal {
        column-span: 2;
    }

    #settings-grid.settings-narrow {
        grid-size: 1 3;
        grid-columns: 1fr;
        grid-rows: auto auto auto;
        grid-gutter: 1 0;
        height: 26;
    }

    #settings-grid.settings-narrow #settings-portal {
        column-span: 1;
    }

    .settings-panel {
        height: 8;
        padding: 1 2;
        border: round $amber-soft;
        background: $surface;
    }

    .setting-row {
        width: 100%;
        height: 1;
    }

    .setting-action {
        width: 1fr;
        height: 1;
        color: #eeeeee;
    }

    .setting-status {
        width: auto;
        min-width: 6;
        height: 1;
        padding-left: 1;
        text-align: right;
        color: #cccccc;
    }

    .native-view {
        display: none;
        width: 100%;
        height: auto;
    }

    .native-heading {
        height: 3;
        padding: 0 1;
        color: $amber;
        text-style: bold;
        content-align: left middle;
    }

    .native-grid {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 1fr;
        grid-gutter: 1 2;
        width: 100%;
        height: auto;
    }

    .native-grid.narrow {
        grid-size: 1;
        grid-columns: 1fr;
    }

    .status-card {
        height: auto;
        min-height: 8;
        padding: 1 2;
        border: round $amber-soft;
        background: $surface;
    }

    .action-card {
        column-span: 2;
        min-height: 7;
    }

    .native-grid.narrow .action-card {
        column-span: 1;
    }

    .native-table {
        width: 100%;
        height: auto;
        min-height: 16;
        border: round $amber-soft;
        background: $surface;
    }

    .data-summary {
        width: 100%;
        height: 3;
        padding: 0 2;
        border: round $amber-soft;
        background: $surface;
        content-align: left middle;
    }

    .native-log {
        height: auto;
        min-height: 18;
        border: round $amber-soft;
        background: #080808;
        scrollbar-color: $amber;
    }

    #sync-progress-panel {
        display: none;
        width: 100%;
        height: 5;
        padding: 0 2;
        border: round $amber-soft;
        background: #080808;
    }

    #batch-hour-context {
        width: 100%;
        height: 3;
        padding: 0 2;
        border: round $amber-soft;
        background: $surface;
        content-align: left middle;
    }

    #batch-hour-progress-panel {
        display: none;
        width: 100%;
        height: 5;
        padding: 0 2;
        border: round $amber-soft;
        background: #080808;
    }

    #batch-hour-progress-panel.active {
        display: block;
    }

    #batch-hour-progress-label {
        height: 1;
        color: $amber;
        text-style: bold;
    }

    #batch-hour-progress {
        width: 100%;
        height: 1;
        color: $amber;
        background: #24200f;
    }

    #sync-progress-panel.active {
        display: block;
    }

    #sync-progress-label {
        height: 1;
        color: $amber;
        text-style: bold;
    }

    #sync-progress {
        width: 100%;
        height: 1;
        color: $amber;
        background: #24200f;
    }

    #sync-progress-panel.success #sync-progress-label,
    #sync-progress-panel.success #sync-progress {
        color: #66bb6a;
    }

    #sync-progress-panel.failed #sync-progress-label,
    #sync-progress-panel.failed #sync-progress {
        color: #ef5350;
    }

    .native-markdown {
        height: auto;
        min-height: 20;
        padding: 1 2;
        border: round $amber-soft;
        background: $surface;
    }

    #operation-title {
        display: none;
        height: 3;
        padding: 0 1;
        color: $amber;
        text-style: bold;
        content-align: left middle;
    }

    #output-log {
        display: none;
        height: auto;
        min-height: 10;
        background: #090909;
        color: #eeeeee;
        scrollbar-color: $amber;
    }

    #prompt-panel {
        height: 6;
        padding: 0 2;
        border-top: solid $amber;
        background: #101010;
    }

    #prompt-panel.busy {
        height: 3;
        padding: 0 2;
        content-align: left middle;
    }

    #prompt-panel.busy #prompt-label {
        height: 2;
        content-align: left middle;
    }

    #prompt-panel.busy #sticky-input,
    #prompt-panel.busy #prompt-error {
        display: none;
    }

    #prompt-label {
        height: 1;
        color: $amber;
        text-style: bold;
    }

    #sticky-input {
        height: 3;
        border: round $amber-soft;
        background: #080808;
        color: white;
        padding: 0 1;
    }

    #sticky-input:focus {
        border: heavy $amber;
    }

    #prompt-error {
        height: 1;
        color: #ef5350;
    }

    #shortcut-footer {
        height: 2;
        padding: 0 2;
        background: $amber-dark;
        color: #d6c77a;
        content-align: center middle;
    }
    """

    def __init__(self, *, start_session: bool = True):
        super().__init__(ansi_color=False)
        self.start_session = start_session
        self.config = {}
        self.token = None
        self.user = None
        self.gi_id = None
        self.date_str = ""
        self.workflow_thread_id: Optional[int] = None
        self.worker_output = ThreadOutput(self)
        self.prompt_backend = StickyPromptBackend(self)
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._original_input = builtins.input
        self._busy = False
        self.current_view = "dashboard"
        self.view_stack = []
        self.pending_editor = None
        self.pending_values = {}
        self.pending_schedule_plan = None

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
            yield Static(id="app-header")
            with VerticalScroll(id="content-scroll"):
                with Container(id="menu-grid"):
                    yield MenuPanel("LIHAT DATA", "", id="panel-view")
                    yield MenuPanel("INPUT MANUAL", "", id="panel-input")
                    yield MenuPanel("BATCH PER JAM · + SYNC PORTAL", "", id="panel-batch-hour")
                    with Vertical(id="settings-section"):
                        with Container(id="settings-grid"):
                            yield SettingsPanel(
                                "AKUN & SESI",
                                [
                                    SettingRow("L", "Login Ulang"),
                                    SettingRow("S", "Setup Kredensial"),
                                    SettingRow("O", "Logout", dangerous=True),
                                ],
                                id="settings-session",
                            )
                            yield SettingsPanel(
                                "OPERASIONAL",
                                [
                                    SettingRow("G", "Tanggal", status_id="setting-date"),
                                    SettingRow("T", "Sumber Foto", status_id="setting-photo"),
                                    SettingRow("D", "Auto Mode", status_id="setting-auto"),
                                ],
                                id="settings-operational",
                            )
                            yield SettingsPanel(
                                "PORTAL & APLIKASI",
                                [
                                    SettingRow("P", "Sync Portal", status_id="setting-portal"),
                                    SettingRow("0", "Keluar", dangerous=True),
                                ],
                                id="settings-portal",
                            )
                with Vertical(id="auto-view", classes="native-view"):
                    yield Static("MENU UTAMA / PENGATURAN / AUTO MODE", classes="native-heading")
                    with Container(id="auto-grid", classes="native-grid"):
                        yield StatusCard("STATUS", id="auto-status-card")
                        yield StatusCard("JADWAL", id="auto-scheduler-card")
                        yield StatusCard("INPUT DATA", id="auto-types-card")
                        yield StatusCard("RETRY & PORTAL", id="auto-portal-card")
                        yield StatusCard("AKSI", id="auto-actions-card", classes="action-card")
                with Vertical(id="photo-view", classes="native-view"):
                    yield Static("MENU UTAMA / PENGATURAN / SUMBER FOTO", classes="native-heading")
                    with Container(id="photo-grid", classes="native-grid"):
                        yield StatusCard("SUMBER AKTIF", id="photo-source-card")
                        yield StatusCard("STATISTIK", id="photo-stats-card")
                        yield StatusCard("SMART SUGGEST", id="photo-history-card")
                        yield StatusCard("INFORMASI FOTO", id="photo-info-card")
                        yield StatusCard("AKSI", id="photo-actions-card", classes="action-card")
                with Vertical(id="sync-view", classes="native-view"):
                    yield Static("MENU UTAMA / PORTAL & APLIKASI / SYNC PORTAL", classes="native-heading")
                    with Container(id="sync-grid", classes="native-grid"):
                        yield StatusCard("KONEKSI", id="sync-connection-card")
                        yield StatusCard("KONFIGURASI", id="sync-config-card")
                        yield StatusCard("RINGKASAN", id="sync-summary-card")
                        yield StatusCard("AKSI", id="sync-actions-card")
                    with Vertical(id="sync-progress-panel"):
                        yield Static("Menunggu proses sync", id="sync-progress-label")
                        yield ProgressBar(total=100, show_eta=False, id="sync-progress")
                    yield RichLog(id="sync-log", classes="native-log sync-log", markup=True, wrap=True, highlight=False)
                with Vertical(id="setup-view", classes="native-view"):
                    yield Static("MENU UTAMA / AKUN & SESI / SETUP KREDENSIAL", classes="native-heading")
                    with Container(id="setup-grid", classes="native-grid"):
                        yield StatusCard("SUPER-I APP", id="setup-superi-card")
                        yield StatusCard("PORTAL APD JAKARTA", id="setup-portal-card")
                        yield StatusCard("PENYIMPANAN & KEAMANAN", id="setup-security-card")
                        yield StatusCard("HASIL TERAKHIR", id="setup-result-card")
                        yield StatusCard("AKSI", id="setup-actions-card", classes="action-card")
                with Vertical(id="batch-hour-view", classes="native-view"):
                    yield Static(id="batch-hour-heading", classes="native-heading")
                    yield Static(id="batch-hour-context")
                    with Vertical(id="batch-hour-progress-panel"):
                        yield Static("Menunggu proses batch", id="batch-hour-progress-label")
                        yield ProgressBar(total=100, show_eta=False, id="batch-hour-progress")
                    yield DataTable(id="batch-hour-table", classes="native-table", zebra_stripes=True)
                    yield RichLog(id="batch-hour-log", classes="native-log", markup=True, wrap=True, highlight=False)
                with Vertical(id="data-view", classes="native-view"):
                    yield Static(id="data-heading", classes="native-heading")
                    yield Static(id="data-summary", classes="data-summary")
                    yield DataTable(id="data-table", classes="native-table", zebra_stripes=True)
                with Vertical(id="manual-input-view", classes="native-view"):
                    yield Static(id="manual-input-heading", classes="native-heading")
                    yield Static(id="manual-input-summary", classes="data-summary")
                    yield DataTable(id="manual-input-table", classes="native-table", zebra_stripes=True)
                    yield RichLog(id="manual-input-log", classes="native-log", markup=True, wrap=True, highlight=False)
                with Vertical(id="table-view", classes="native-view"):
                    yield Static(id="table-heading", classes="native-heading")
                    yield DataTable(id="native-table", classes="native-table", zebra_stripes=True)
                with Vertical(id="log-view", classes="native-view"):
                    yield Static(id="log-heading", classes="native-heading")
                    yield RichLog(id="native-log", classes="native-log", markup=True, wrap=True, highlight=False)
                with Vertical(id="guide-view", classes="native-view"):
                    yield Static(id="guide-heading", classes="native-heading")
                    yield Markdown(id="native-guide", classes="native-markdown")
                yield Static(id="operation-title")
                yield RichLog(id="output-log", markup=True, wrap=True, highlight=False)
            with Vertical(id="prompt-panel"):
                yield Static("Pilih menu", id="prompt-label")
                yield Input(placeholder="Ketik nomor atau huruf menu...", id="sticky-input")
                yield Static("", id="prompt-error")
            yield Static(
                "Enter Pilih  ·  Esc Kembali  ·  PgUp/PgDn Scroll  ·  F1 Bantuan  ·  Ctrl+Q Keluar",
                id="shortcut-footer",
            )

    def on_mount(self):
        self._install_bridges()
        sc.set_interactive_backend(self.prompt_backend)
        self.refresh_dashboard()
        self.query_one("#sticky-input", Input).focus()
        if self.start_session:
            self.run_worker(self._startup, thread=True, name="startup", exit_on_error=False)

    def on_unmount(self):
        self._restore_bridges()
        sc.clear_interactive_backend(self.prompt_backend)

    def on_resize(self, event: events.Resize):
        grid = self.query_one("#menu-grid")
        grid.set_class(event.size.width < 96, "narrow")
        settings = self.query_one("#settings-grid")
        settings.set_class(event.size.width < 94, "settings-narrow")
        settings.set_class(94 <= event.size.width < 112, "settings-medium")
        self.query_one("#settings-section").styles.height = (
            26 if event.size.width < 94 else 17 if event.size.width < 112 else 8
        )
        self.query_one("#auto-grid").set_class(event.size.width < 94, "narrow")
        self.query_one("#photo-grid").set_class(event.size.width < 94, "narrow")
        self.query_one("#sync-grid").set_class(event.size.width < 94, "narrow")
        self.query_one("#setup-grid").set_class(event.size.width < 94, "narrow")
        if self.current_view == "data" and "data-items" in self.pending_values:
            self._render_data_table(
                self.pending_values["data-type"], self.pending_values["data-items"]
            )
        if self.current_view == "manual-input" and "manual-items" in self.pending_values:
            self._render_manual_input_table(
                self.pending_values["manual-data-type"], self.pending_values["manual-items"]
            )

    def _install_bridges(self):
        sys.stdout = ThreadAwareStream(self._original_stdout, self)
        sys.stderr = ThreadAwareStream(self._original_stderr, self)

        def tui_input(prompt=""):
            if self.is_workflow_thread():
                return self.prompt_backend.raw_input(prompt)
            return self._original_input(prompt)

        builtins.input = tui_input

    def _restore_bridges(self):
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        builtins.input = self._original_input

    def is_workflow_thread(self) -> bool:
        return self.workflow_thread_id == threading.get_ident()

    def refresh_dashboard(self):
        import superi_app as core

        self.config = core.load_config()
        photo = core.get_photo_source().upper()
        auto_on = self.config.get("auto_enabled", False)
        portal_ready = bool(self.config.get("portal_user") and self.config.get("portal_password"))
        user_name = self.user.get("namaLengkap", "Belum login") if self.user else "Belum login"
        roles = ", ".join(self.user.get("roles", [])) if self.user else ""
        online = "[bold green]● ONLINE[/]" if self.token else "[bold red]○ OFFLINE[/]"
        self.query_one("#app-header", Static).update(
            f"[bold #ffc107]SUPER-I APP[/]  [bold white]{escape(user_name)}[/]"
            f" [dim]{escape(roles)}[/]\n"
            f"{online}  ·  GI [bold]{self.gi_id or '-'}[/]  ·  {self.date_str or '-'}"
            f"  ·  FOTO [bold yellow]{photo}[/]  ·  AUTO "
            f"{'[bold green]ON[/]' if auto_on else '[bold red]OFF[/]'}"
        )

        self.query_one("#panel-view", Static).update(
            "[bold #ffc107][1][/] Beban Penyulang\n"
            "[bold #ffc107][2][/] Beban Trafo\n"
            "[bold #ffc107][3][/] Tegangan Trafo\n\n"
            "[dim]Tampilkan status dan kelengkapan 24 periode.[/]"
        )
        self.query_one("#panel-input", Static).update(
            "[bold #ffc107][4][/] Beban Penyulang\n"
            "[bold #ffc107][5][/] Beban Trafo\n"
            "[bold #ffc107][6][/] Tegangan Trafo\n\n"
            "[dim]Input satu item dan satu periode.[/]"
        )
        self.query_one("#panel-batch-hour", Static).update(
            "[bold #ffc107][A][/] Beban Penyulang\n"
            "[bold #ffc107][B][/] Beban Trafo\n"
            "[bold #ffc107][C][/] Tegangan Trafo\n\n"
            "[dim]Isi semua item pada satu jam, lalu sync.[/]"
        )
        self.query_one("#setting-date", Static).update(
            f"[dim]{escape(self.date_str or '-')}[/]"
        )
        self.query_one("#setting-photo", Static).update(
            f"[bold {'green' if photo == 'MANUAL' else 'yellow'}]{escape(photo)}[/]"
        )
        self.query_one("#setting-auto", Static).update(
            "[bold green]ON[/]" if auto_on else "[bold red]OFF[/]"
        )
        self.query_one("#setting-portal", Static).update(
            "[bold green]READY[/]" if portal_ready else "[bold yellow]SETUP[/]"
        )

    def _startup(self):
        import superi_app as core
        from datetime import datetime

        self.workflow_thread_id = threading.get_ident()
        try:
            self.date_str = datetime.now().strftime("%Y-%m-%d")
            config = core.load_config()
            if not config.get("nip"):
                self.call_from_thread(self.begin_operation, "SETUP KREDENSIAL")
                core.setup_config()
                config = core.load_config()
            self.config = config
            if config.get("nip"):
                self.call_from_thread(self.set_busy_prompt, "Menghubungkan ke SUPER-I...")
                self.token, self.user, self.gi_id = core.do_login(config)
        finally:
            self.workflow_thread_id = None
            self.call_from_thread(self.finish_operation)

    def begin_operation(self, title: str):
        self._busy = True
        self.query_one("#menu-grid").display = False
        title_widget = self.query_one("#operation-title", Static)
        title_widget.display = True
        title_widget.update(f"MENU UTAMA / [bold #ffc107]{escape(title)}[/]")
        log = self.query_one("#output-log", RichLog)
        log.clear()
        log.display = True
        self.set_busy_prompt("Menyiapkan proses...")

    def finish_operation(self):
        self._busy = False
        self.refresh_dashboard()
        self.query_one("#menu-grid").display = True
        self.query_one("#operation-title").display = False
        self.query_one("#output-log").display = False
        self.show_menu_prompt()

    def _hide_content_views(self):
        for selector in (
            "#menu-grid", "#auto-view", "#photo-view", "#sync-view", "#setup-view", "#batch-hour-view", "#data-view", "#manual-input-view", "#table-view",
            "#log-view", "#guide-view", "#operation-title", "#output-log",
        ):
            self.query_one(selector).display = False

    def _show_native_view(self, name: str, *, push: bool = True):
        if push and self.current_view != name:
            self.view_stack.append(self.current_view)
        self.current_view = name
        self._busy = False
        self._hide_content_views()
        self.query_one(f"#{name}-view").display = True
        self.hide_prompt_error()

    def show_dashboard_view(self):
        self.current_view = "dashboard"
        self.view_stack.clear()
        self._busy = False
        self._hide_content_views()
        self.refresh_dashboard()
        self.query_one("#menu-grid").display = True
        self.show_menu_prompt()

    def show_auto_view(self, *, push: bool = True, include_scheduler: bool = True):
        from superi_settings import get_auto_snapshot

        snapshot = get_auto_snapshot(include_scheduler=include_scheduler)
        self._show_native_view("auto", push=push)
        state = "[bold green]● AKTIF[/]" if snapshot.enabled else "[bold red]○ NONAKTIF[/]"
        hours = ", ".join(f"{hour:02d}" for hour in snapshot.hours)
        self.query_one("#auto-status-card", Static).update(
            f"Status              {state}\n"
            f"Window              [bold white]{snapshot.window_start:02d}:00-{snapshot.window_end:02d}:00[/]\n"
            f"Jam aktif           [bold yellow]{len(snapshot.hours)}[/]\n"
            f"[dim]{hours}[/]"
        )
        health_style = "green" if snapshot.scheduler_health == "COMPLETE" else "yellow" if snapshot.scheduler_health == "PARTIAL" else "red"
        self.query_one("#auto-scheduler-card", Static).update(
            f"Platform            [bold white]{escape(snapshot.scheduler_platform)}[/]\n"
            f"Status              [bold {health_style}]{snapshot.scheduler_health}[/]\n"
            f"Terpasang           [bold yellow]{snapshot.scheduler_installed}/{snapshot.scheduler_expected}[/]\n"
            "[dim]Menit acak 3-38 per jam aktif[/]"
        )
        labels = {"penyulang": "Penyulang", "trafo": "Trafo", "tegangan": "Tegangan"}
        type_lines = [f"{label:<19} {'[bold green]ON[/]' if key in snapshot.types else '[dim]OFF[/]'}" for key, label in labels.items()]
        self.query_one("#auto-types-card", Static).update("\n".join(type_lines))
        self.query_one("#auto-portal-card", Static).update(
            f"Sync Portal         {'[bold green]ON[/]' if snapshot.sync_portal else '[bold red]OFF[/]'}\n"
            f"Portal              {'[bold green]READY[/]' if snapshot.portal_ready else '[bold yellow]SETUP[/]'}\n"
            f"SUPER-I             {'[bold green]READY[/]' if snapshot.superi_ready else '[bold red]SETUP[/]'}\n"
            f"Retry               [bold yellow]{snapshot.retry_attempts}x[/] · {snapshot.retry_delay} detik"
        )
        toggle = "Nonaktifkan" if snapshot.enabled else "Aktifkan"
        toggle_action = f"{toggle} Auto Mode"
        self.query_one("#auto-actions-card", Static).update(
            f"[bold #ffc107][1][/] {toggle_action:<25}[bold #ffc107][2][/] Atur Window\n"
            "[bold #ffc107][3][/] Pilih Tipe Data          [bold #ffc107][4][/] Toggle Sync Portal\n"
            "[bold #ffc107][5][/] Test Dry-Run             [bold #ffc107][6][/] Lihat Log\n"
            "[bold #ffc107][7][/] Kelola Jadwal            [bold #ffc107][8][/] Panduan\n"
            "[bold red][0][/] Kembali"
        )
        self._set_native_prompt("Pilih aksi Auto Mode", "1-8 atau 0")

    def show_photo_view(self, *, push: bool = True):
        from superi_settings import get_photo_snapshot

        snapshot = get_photo_snapshot()
        self._show_native_view("photo", push=push)
        source_style = "green" if snapshot.effective_source == "manual" else "yellow"
        override = "\n[bold yellow]ENV OVERRIDE aktif[/]" if snapshot.source_origin == "env" else ""
        description = "Per-item sesuai input; HV/MV terpisah" if snapshot.effective_source == "manual" else "Foto generic untuk semua item"
        self.query_one("#photo-source-card", Static).update(
            f"Mode efektif        [bold {source_style}]{snapshot.effective_source.upper()}[/]\n"
            f"Mode konfigurasi    [bold white]{snapshot.configured_source.upper()}[/]\n"
            f"[dim]{description}[/]\n[dim]File sumber read-only[/]{override}"
        )
        error = f"\n[bold red]Scan gagal: {escape(snapshot.error)}[/]" if snapshot.error else ""
        self.query_one("#photo-stats-card", Static).update(
            f"Pool generic        [bold yellow]{snapshot.pool_count}[/] file\n"
            f"Penyulang           {snapshot.feeder_folders} folder / [bold green]{snapshot.feeder_files}[/] foto\n"
            f"Beban trafo         {snapshot.transformer_folders} folder / [bold green]{snapshot.transformer_files}[/] foto\n"
            f"Tegangan            HV {snapshot.voltage_hv} / MV {snapshot.voltage_mv}\n"
            f"Total manual        [bold green]{snapshot.total_manual}[/] foto{error}"
        )
        self.query_one("#photo-history-card", Static).update(
            f"History             [bold green]{snapshot.history_days} hari[/]\n"
            "Pilihan             [dim]3 / 7 / 14 hari[/]\n"
            "[dim]Dipakai untuk smart-suggest histori.[/]"
        )
        self.query_one("#photo-info-card", Static).update(
            "Output              [bold yellow]720 × 720[/]\n"
            "JPEG Quality        82-93\n"
            "Filename            [bold yellow]HUMANIZED[/]\n"
            "Varian              asli / blur / noisy"
        )
        self.query_one("#photo-actions-card", Static).update(
            "[bold #ffc107][1][/] Ganti Sumber Foto        [bold #ffc107][2][/] Ganti History\n"
            "[bold #ffc107][3][/] Detail Pool              [bold #ffc107][4][/] Validasi Foto\n"
            "[bold #ffc107][5][/] Panduan                  [bold #ffc107][6][/] Test Random\n"
            "[bold red][0][/] Kembali"
        )
        self._set_native_prompt("Pilih aksi Sumber Foto", "1-6 atau 0")

    def show_sync_view(self, *, push: bool = True):
        self._show_native_view("sync", push=push)
        cfg = self.config or {}
        superi_ready = bool(cfg.get("nip") and cfg.get("password"))
        portal_ready = bool(cfg.get("portal_user") and cfg.get("portal_password"))
        types = self.pending_values.setdefault("sync-types", ("penyulang",))
        start = self.pending_values.setdefault("sync-start", 0)
        end = self.pending_values.setdefault("sync-end", 23)
        date = self.pending_values.setdefault("sync-date", self.date_str)
        labels = {"penyulang": "Beban Penyulang", "trafo": "Beban Trafo", "tegangan": "Tegangan Trafo"}
        selected = ", ".join(labels[item] for item in types)
        self.query_one("#sync-connection-card", Static).update(
            f"SUPER-I APP        {'[bold green]READY[/]' if superi_ready else '[bold red]SETUP[/]'}\n"
            f"Portal APD         {'[bold green]READY[/]' if portal_ready else '[bold yellow]SETUP[/]'}\n"
            f"Sumber             [bold white]SUPER-I APP[/]\n"
            f"Tujuan             [bold white]Portal APD Jakarta[/]"
        )
        self.query_one("#sync-config-card", Static).update(
            f"Jenis data         [bold yellow]{escape(selected)}[/]\n"
            f"Rentang jam        [bold white]{start:02d}:00-{end:02d}:00[/]\n"
            f"Tanggal            [bold white]{escape(date)}[/]\n"
            "[dim]LIVE selalu didahului dry-run preview.[/]"
        )
        summary = self.pending_values.get("sync-summary", "Belum ada proses pada sesi ini.")
        self.query_one("#sync-summary-card", Static).update(summary)
        self.query_one("#sync-actions-card", Static).update(
            "[bold #ffc107][1][/] Pilih Jenis Data\n"
            "[bold #ffc107][2][/] Atur Rentang Jam\n"
            "[bold #ffc107][3][/] Atur Tanggal\n"
            "[bold #ffc107][4][/] Jalankan Dry-Run\n"
            "[bold green][5][/] Jalankan LIVE Sync\n"
            "[bold red][0][/] Kembali"
        )
        log = self.query_one("#sync-log", RichLog)
        if not getattr(self, "_sync_log_initialized", False):
            log.write("[dim]Log dry-run dan LIVE sync akan tampil di sini.[/]")
            self._sync_log_initialized = True
        self._set_native_prompt("Pilih aksi Sync Portal", "1-5 atau 0")

    @staticmethod
    def _mask_identity(value: str) -> str:
        if not value:
            return "—"
        if len(value) <= 4:
            return "•" * len(value)
        return f"{value[:2]}{'•' * min(8, len(value) - 4)}{value[-2:]}"

    def show_setup_view(self, *, push: bool = True):
        from superi_settings import get_credential_snapshot

        snapshot = get_credential_snapshot()
        self.config = __import__("superi_app").load_config()
        self._show_native_view("setup", push=push)
        superi_state = "[bold green]LENGKAP[/]" if snapshot.superi_ready else "[bold red]BELUM LENGKAP[/]"
        portal_state = "[bold green]READY[/]" if snapshot.portal_ready else "[bold yellow]OPSIONAL[/]"
        self.query_one("#setup-superi-card", Static).update(
            f"Status             {superi_state}\n"
            f"NIP                [bold white]{self._mask_identity(snapshot.nip)}[/]\n"
            f"Password           {'[bold green]TERSIMPAN[/]' if snapshot.superi_password_set else '[bold red]BELUM ADA[/]'}\n"
            "[dim]GI terdeteksi otomatis setelah login.[/]"
        )
        self.query_one("#setup-portal-card", Static).update(
            f"Status             {portal_state}\n"
            f"Username           [bold white]{self._mask_identity(snapshot.portal_user)}[/]\n"
            f"Password           {'[bold green]TERSIMPAN[/]' if snapshot.portal_password_set else '[dim]BELUM ADA[/]'}\n"
            "[dim]Diperlukan hanya untuk Sync Portal.[/]"
        )
        self.query_one("#setup-security-card", Static).update(
            f"File               [dim]{escape(snapshot.config_path)}[/]\n"
            "Password           [bold green]SELALU TERSEMBUNYI[/]\n"
            "Input kosong       [bold yellow]PERTAHANKAN NILAI LAMA[/]\n"
            "[dim]Pengaturan Auto, Foto, dan Scheduler tidak diubah.[/]"
        )
        result = self.pending_values.get("setup-result", "Belum ada perubahan pada sesi ini.")
        self.query_one("#setup-result-card", Static).update(result)
        self.query_one("#setup-actions-card", Static).update(
            "[bold #ffc107][1][/] Ubah Kredensial SUPER-I     [bold #ffc107][2][/] Ubah Kredensial Portal\n"
            "[bold #ffc107][3][/] Ubah Semua                 [bold #ffc107][4][/] Uji Login SUPER-I\n"
            "[bold #ffc107][5][/] Uji Koneksi Portal\n"
            "[bold red][0][/] Kembali"
        )
        self._set_native_prompt("Pilih aksi Setup Kredensial", "1-5 atau 0")

    def show_batch_hour_view(self, data_type: str, *, push: bool = True):
        labels = {
            "beban-penyulang": "BEBAN PENYULANG",
            "beban-trafo": "BEBAN TRAFO",
            "tegangan-trafo": "TEGANGAN TRAFO",
        }
        self._show_native_view("batch-hour", push=push)
        self.pending_values["batch-data-type"] = data_type
        self.query_one("#batch-hour-heading", Static).update(
            f"MENU UTAMA / BATCH PER JAM / {labels[data_type]}"
        )
        overview = self.pending_values.get("batch-overview")
        period = self.pending_values.get("batch-period")
        suggestions = self.pending_values.get("batch-suggestions", [])
        result = self.pending_values.get("batch-result")
        self.query_one("#batch-hour-progress-panel").remove_class("active")
        if overview and overview.data_type == data_type:
            if result:
                self._render_batch_result(overview, period, result)
            elif suggestions and period is not None:
                self._render_batch_suggestions(overview, period, suggestions)
            else:
                self._render_batch_overview(overview)
        else:
            self.query_one("#batch-hour-context", Static).update(
                f"[bold yellow]{labels[data_type].title()}[/] · {escape(self.date_str)} · [dim]Memuat periode yang tersedia...[/]"
            )
            self.query_one("#batch-hour-table").display = False
            self.query_one("#batch-hour-log").display = False
        if not overview or overview.data_type != data_type:
            self._load_batch_overview(data_type)

    def _render_batch_overview(self, overview):
        full = 24 - overview.incomplete_periods
        self.query_one("#batch-hour-context", Static).update(
            f"[bold yellow]{escape(overview.label)}[/] · {escape(overview.date)} · "
            f"{overview.active_items} item aktif · [green]{full} periode penuh[/] · "
            f"[yellow]{overview.incomplete_periods} bisa di-batch[/]"
        )
        table = self.query_one("#batch-hour-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Periode", "Item Kosong", "Aksi")
        for period in overview.actionable_periods:
            table.add_row(f"P{period:02d}:00", str(len(overview.empty_by_period[period])), "SIAP BATCH")
        table.display = True
        self.query_one("#batch-hour-log").display = False

    def _render_batch_suggestions(self, overview, period: int, suggestions):
        missing = sum(not item.valid for item in suggestions)
        self.query_one("#batch-hour-context", Static).update(
            f"[bold yellow]SMART SUGGEST · P{period:02d}:00[/] · {escape(overview.date)} · "
            f"[green]{len(suggestions) - missing} siap[/] · "
            f"[{'red' if missing else 'green'}]{missing} perlu edit[/]"
        )
        table = self.query_one("#batch-hour-table", DataTable)
        table.clear(columns=True)
        if overview.data_type == "tegangan-trafo":
            table.add_columns("No", "Nama", "MV", "HV", "Sumber Histori", "Status")
            for index, item in enumerate(suggestions, 1):
                table.add_row(str(index), item.item["nama"], str(item.value or "—"), str(item.hv or "—"), item.info, "SIAP" if item.valid else "PERLU EDIT")
        else:
            table.add_columns("No", "Nama", "Suggest", "Sumber Histori", "Status")
            for index, item in enumerate(suggestions, 1):
                table.add_row(str(index), item.item["nama"], f"{item.value} A" if item.value is not None else "—", item.info, "SIAP" if item.valid else "PERLU EDIT")
        table.display = True
        self.query_one("#batch-hour-log").display = False

    def _render_batch_result(self, overview, period: int, result):
        elapsed = self.pending_values.get("batch-elapsed", 0)
        minutes, seconds = divmod(int(elapsed), 60)
        self.query_one("#batch-hour-context", Static).update(
            f"[bold green]BATCH SELESAI · P{period:02d}:00[/] · Target {result.total} · "
            f"[green]{result.success} berhasil[/] · "
            f"[{'red' if result.failed else 'green'}]{result.failed} gagal[/] · {minutes}m {seconds}s"
        )
        log = self.query_one("#batch-hour-log", RichLog)
        if result.failures:
            log.write("")
            log.write("[bold red]ITEM GAGAL[/]")
            for name, reason in result.failures:
                log.write(f"  [red]✗[/] {escape(name)} · {escape(reason)}")
        self.query_one("#batch-hour-table").display = False
        log.display = True

    def show_data_view(self, data_type: str, *, push: bool = True):
        labels = {
            "beban-penyulang": "BEBAN PENYULANG",
            "beban-trafo": "BEBAN TRAFO",
            "tegangan-trafo": "TEGANGAN TRAFO",
        }
        self._show_native_view("data", push=push)
        self.pending_values["data-type"] = data_type
        self.query_one("#data-heading", Static).update(
            f"MENU UTAMA / LIHAT DATA / {labels[data_type]}"
        )
        self.query_one("#data-summary", Static).update(
            f"[bold yellow]{labels[data_type].title()}[/] · {escape(self.date_str)} · [dim]Memuat data...[/]"
        )
        table = self.query_one("#data-table", DataTable)
        table.clear(columns=True)
        self.current_view = "data-loading"
        self.set_busy_prompt(f"Memuat {labels[data_type].title()}...")

        def work():
            core = __import__("superi_app")
            if not self.token:
                self.token, self.user, self.gi_id = core.do_login(core.load_config())
                if not self.token:
                    raise RuntimeError("Login SUPER-I diperlukan untuk melihat data")
            endpoint = core.ENDPOINTS[data_type]
            response = core.api_get(
                self.token, endpoint["list"],
                {"garduIndukId": self.gi_id, "date": self.date_str},
            )
            self.pending_values["data-items"] = tuple(response.get("data", {}).get("items", []))

        self.run_worker(work, thread=True, name="data-load", exclusive=True, exit_on_error=False)

    def _render_data_table(self, data_type: str, items):
        import cli_render

        table = self.query_one("#data-table", DataTable)
        table.clear(columns=True)
        narrow = self.size.width < 94
        available = max(64, self.size.width - 10)
        if data_type == "tegangan-trafo":
            columns = ("No", "Nama", "Tipe", "Terisi", "24 Jam") if narrow else ("No", "Nama", "Tipe", "Terisi", "24 Jam", "Detail")
        else:
            columns = ("No", "Nama", "CB", "Terisi", "24 Jam") if narrow else ("No", "Nama", "iMax", "CB", "Terisi", "24 Jam", "Detail")
        if narrow:
            fixed = 4 + 5 + 7 + 24
            name_width = max(14, available - fixed - len(columns) * 2)
            widths = (4, name_width, 5, 7, 24)
        elif data_type == "tegangan-trafo":
            fixed = 4 + 5 + 7 + 24
            flexible = max(28, available - fixed - len(columns) * 2)
            name_width = max(14, flexible // 2)
            widths = (4, name_width, 5, 7, 24, flexible - name_width)
        else:
            fixed = 4 + 8 + 5 + 7 + 24
            flexible = max(28, available - fixed - len(columns) * 2)
            name_width = max(14, flexible // 2)
            widths = (4, name_width, 8, 5, 7, 24, flexible - name_width)
        for label, width in zip(columns, widths):
            table.add_column(label, width=width)
        data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
        total_filled = 0
        for index, item in enumerate(items, 1):
            entries = item.get(data_key, [])
            periods = sorted(entry["periode"] for entry in entries)
            total_filled += len(periods)
            strip = cli_render.fmt_fill_strip(periods)
            name = str(item.get("nama", "?"))
            if data_type == "tegangan-trafo":
                type_label = "PS" if item.get("isPS") else "GI"
                details = ""
                if entries:
                    mv = [entry.get("mv", 0) for entry in entries]
                    hv = [entry.get("hv", 0) for entry in entries]
                    details = f"MV {min(mv):.1f}-{max(mv):.1f} kV · HV {min(hv)}-{max(hv)} kV"
                row = (str(index), name, type_label, f"{len(periods)}/24", strip)
                table.add_row(*(row if narrow else row + (details,)))
            else:
                cb = "OFF" if item.get("statusCB") == "OFF" else "ON"
                values = [entry.get("beban", 0) for entry in entries]
                detail = "CB OFF" if cb == "OFF" else (
                    f"{min(values)}-{max(values)} A · avg {sum(values) / len(values):.0f} A" if values else "Belum ada data"
                )
                base = (str(index), name)
                if narrow:
                    table.add_row(*(base + (cb, f"{len(periods)}/24", strip)))
                else:
                    imax = item.get("iMax", "?")
                    table.add_row(*(base + (f"{imax} A" if imax != "?" else "?", cb, f"{len(periods)}/24", strip, detail)))
        total_slots = len(items) * 24
        total_empty = total_slots - total_filled
        self.query_one("#data-summary", Static).update(
            f"Item [bold white]{len(items)}[/]  ·  Terisi [bold green]{total_filled}[/]  ·  "
            f"Kosong [bold yellow]{total_empty}[/]  ·  Tanggal [bold white]{escape(self.date_str)}[/]"
        )
        table.cursor_type = "row"
        table.focus()

    def show_manual_input_view(self, data_type: str, *, push: bool = True):
        labels = {
            "beban-penyulang": "BEBAN PENYULANG",
            "beban-trafo": "BEBAN TRAFO",
            "tegangan-trafo": "TEGANGAN TRAFO",
        }
        self._show_native_view("manual-input", push=push)
        self.pending_values["manual-data-type"] = data_type
        self.query_one("#manual-input-heading", Static).update(
            f"MENU UTAMA / INPUT MANUAL / {labels[data_type]}"
        )
        self.query_one("#manual-input-summary", Static).update(
            f"[bold yellow]{labels[data_type].title()}[/] · {escape(self.date_str)} · [dim]Memuat daftar item...[/]"
        )
        self.query_one("#manual-input-table").display = True
        self.query_one("#manual-input-log").display = False
        self.current_view = "manual-input-loading"
        self.set_busy_prompt(f"Memuat item {labels[data_type].title()}...")

        def work():
            core = __import__("superi_app")
            if not self.token:
                self.token, self.user, self.gi_id = core.do_login(core.load_config())
                if not self.token:
                    raise RuntimeError("Login SUPER-I diperlukan untuk input manual")
            endpoint = core.ENDPOINTS[data_type]
            response = core.api_get(
                self.token, endpoint["list"],
                {"garduIndukId": self.gi_id, "date": self.date_str},
            )
            self.pending_values["manual-items"] = tuple(response.get("data", {}).get("items", []))

        self.run_worker(work, thread=True, name="manual-items-load", exclusive=True, exit_on_error=False)

    def _render_manual_input_table(self, data_type: str, items):
        import cli_render

        table = self.query_one("#manual-input-table", DataTable)
        table.clear(columns=True)
        narrow = self.size.width < 94
        available = max(64, self.size.width - 10)
        columns = ("No", "Nama", "Status", "Terisi", "24 Jam") if narrow else ("No", "Nama", "Status", "Terisi", "24 Jam", "Periode Kosong")
        fixed = 4 + 8 + 7 + 24
        flexible = max(20, available - fixed - len(columns) * 2)
        name_width = max(14, flexible if narrow else flexible // 2)
        widths = (4, name_width, 8, 7, 24) if narrow else (4, name_width, 8, 7, 24, flexible - name_width)
        for label, width in zip(columns, widths):
            table.add_column(label, width=width)
        key = "tegangan" if data_type == "tegangan-trafo" else "beban"
        total_filled = 0
        selectable = 0
        for index, item in enumerate(items, 1):
            entries = item.get(key, [])
            periods = sorted(entry["periode"] for entry in entries)
            empty = [period for period in range(24) if period not in periods]
            total_filled += len(periods)
            cb_off = item.get("statusCB") == "OFF"
            status = "CB OFF" if cb_off else "PENUH" if not empty else "SIAP"
            if not cb_off and empty:
                selectable += 1
            base = (str(index), str(item.get("nama", "?")), status, f"{len(periods)}/24", cli_render.fmt_fill_strip(periods))
            table.add_row(*(base if narrow else base + (("—" if cb_off else cli_render.fmt_empty_ranges(empty)),)))
        self.query_one("#manual-input-summary", Static).update(
            f"Item [bold white]{len(items)}[/]  ·  Bisa diinput [bold green]{selectable}[/]  ·  "
            f"Periode terisi [bold yellow]{total_filled}[/]  ·  Tanggal [bold white]{escape(self.date_str)}[/]"
        )
        table.cursor_type = "row"
        table.focus()

    def _handle_manual_item_selection(self, value: str):
        if value.lower() == "0":
            self.action_back()
            return
        items = self.pending_values.get("manual-items", ())
        try:
            index = int(value) - 1
        except ValueError:
            self.set_prompt_error("Masukkan nomor item yang tampil pada tabel")
            return
        if not 0 <= index < len(items):
            self.set_prompt_error("Nomor item tidak valid")
            return
        item = items[index]
        if item.get("statusCB") == "OFF":
            self.set_prompt_error(f"{item.get('nama', 'Item')} CB OFF dan tidak dapat diinput")
            return
        data_key = "tegangan" if self.pending_values["manual-data-type"] == "tegangan-trafo" else "beban"
        if len(item.get(data_key, [])) >= 24:
            self.set_prompt_error(f"{item.get('nama', 'Item')} sudah penuh 24/24")
            return
        self._start_manual_input(item)

    def _start_manual_input(self, item):
        data_type = self.pending_values["manual-data-type"]
        log = self.query_one("#manual-input-log", RichLog)
        log.clear()
        log.display = True
        self.query_one("#manual-input-table").display = False
        self.query_one("#manual-input-summary", Static).update(
            f"Target [bold yellow]{escape(item.get('nama', '?'))}[/]  ·  Tanggal [bold white]{escape(self.date_str)}[/]"
        )
        self.current_view = "manual-input-running"
        self.set_busy_prompt("Menyiapkan input manual...")

        def work():
            core = __import__("superi_app")
            self.workflow_thread_id = threading.get_ident()
            try:
                core.input_single(
                    self.token, data_type, self.gi_id, self.date_str, self.user,
                    selected_item=item, show_header=False,
                )
            finally:
                self.worker_output.flush()
                self.workflow_thread_id = None

        self.run_worker(work, thread=True, name="manual-input-operation", exclusive=True, exit_on_error=False)

    def _set_native_prompt(self, label: str, placeholder: str):
        self._busy = False
        self.query_one("#prompt-panel").remove_class("busy")
        self.query_one("#shortcut-footer", Static).update(
            "Enter Pilih  ·  Esc Kembali  ·  PgUp/PgDn Scroll  ·  F1 Bantuan  ·  Ctrl+Q Keluar"
        )
        self.query_one("#prompt-label", Static).update(f"[bold #ffc107]{escape(label)}[/]")
        widget = self.query_one("#sticky-input", Input)
        widget.disabled = False
        widget.password = False
        widget.value = ""
        widget.placeholder = placeholder
        widget.focus()

    def write_output(self, line: str):
        if self.current_view.startswith("sync"):
            target = self.query_one("#sync-log", RichLog)
        elif self.current_view.startswith("manual-input"):
            target = self.query_one("#manual-input-log", RichLog)
        elif self.current_view in ("auto-dry-run", "photo-validation"):
            target = self.query_one("#native-log", RichLog)
        else:
            target = self.query_one("#output-log", RichLog)
        if not line:
            target.write("")
            return
        text = Text.from_ansi(line)
        target.write(text)

    def show_prompt(self, request: PromptRequest):
        self._busy = True
        self.query_one("#prompt-panel").remove_class("busy")
        self.query_one("#shortcut-footer", Static).update(
            "Enter Kirim  ·  Esc Batal  ·  PgUp/PgDn Scroll  ·  Ctrl+Q Keluar"
        )
        label = request.question or "Masukkan nilai"
        if request.choices:
            label += "  [" + "/".join(request.choices) + "]"
        prompt = self.query_one("#prompt-label", Static)
        prompt.update(escape(label))
        input_widget = self.query_one("#sticky-input", Input)
        input_widget.disabled = False
        input_widget.password = request.password
        input_widget.value = request.default or ""
        input_widget.placeholder = "Tekan Enter untuk lanjut" if request.pause else "Masukkan jawaban..."
        input_widget.focus()
        input_widget.cursor_position = len(input_widget.value)

    def set_busy_prompt(self, message: str):
        self._busy = True
        self.query_one("#prompt-panel").add_class("busy")
        self.query_one("#shortcut-footer", Static).update(
            "Proses sedang berjalan  ·  Input dinonaktifkan  ·  PgUp/PgDn Scroll  ·  Ctrl+Q Keluar"
        )
        self.query_one("#prompt-label", Static).update(f"[bold yellow]{escape(message)}[/]")
        input_widget = self.query_one("#sticky-input", Input)
        input_widget.value = ""
        input_widget.password = False
        input_widget.disabled = True

    def show_menu_prompt(self):
        self.query_one("#prompt-panel").remove_class("busy")
        self.query_one("#shortcut-footer", Static).update(
            "Enter Pilih  ·  Esc Kembali  ·  PgUp/PgDn Scroll  ·  F1 Bantuan  ·  Ctrl+Q Keluar"
        )
        self.query_one("#prompt-label", Static).update("[bold #ffc107]Pilih menu[/]")
        input_widget = self.query_one("#sticky-input", Input)
        input_widget.disabled = False
        input_widget.password = False
        input_widget.value = ""
        input_widget.placeholder = "Contoh: 1, 4, A, P, atau D"
        input_widget.focus()

    def set_prompt_error(self, message: str):
        self.query_one("#prompt-error", Static).update(escape(message))

    def hide_prompt_error(self):
        self.query_one("#prompt-error", Static).update("")

    def on_input_submitted(self, event: Input.Submitted):
        value = event.value.strip()
        event.input.value = ""
        self.hide_prompt_error()
        if self.prompt_backend.active:
            self.prompt_backend.submit(value)
            self.set_busy_prompt("Memproses...")
            return
        if self.pending_editor:
            self._handle_editor_input(value)
            return
        if self.current_view == "auto":
            self._handle_auto_action(value.lower())
            return
        if self.current_view == "photo":
            self._handle_photo_action(value.lower())
            return
        if self.current_view == "sync":
            self._handle_sync_action(value.lower())
            return
        if self.current_view == "setup":
            self._handle_setup_action(value.lower())
            return
        if self.current_view == "batch-hour":
            self._handle_batch_hour_action(value.lower())
            return
        if self.current_view == "data":
            if value.lower() == "0":
                self.action_back()
            else:
                self.set_prompt_error("Gunakan 0 atau Esc untuk kembali.")
            return
        if self.current_view == "manual-input":
            self._handle_manual_item_selection(value)
            return
        if self.current_view == "manual-input-result":
            if value.lower() == "0":
                self.action_back()
            else:
                self.set_prompt_error("Gunakan 0 atau Esc untuk kembali.")
            return
        if self.current_view == "scheduler":
            self._handle_scheduler_action(value.lower())
            return
        if self.current_view in ("table", "log", "guide"):
            if value.lower() == "0":
                self.action_back()
            else:
                self.set_prompt_error("Gunakan 0 atau Esc untuk kembali.")
            return
        command = MENU_COMMANDS.get(value.lower())
        if not command:
            self.set_prompt_error("Menu tidak dikenal. Gunakan pilihan yang tampil di panel.")
            return
        if command == "quit":
            self.action_request_quit()
            return
        self.run_command(command)

    def run_command(self, command: str):
        if self._busy:
            return
        if command == "auto-settings":
            self.show_auto_view()
            return
        if command == "photo-settings":
            self.show_photo_view()
            return
        if command == "sync":
            self.show_sync_view()
            return
        if command == "setup":
            self.show_setup_view()
            return
        batch_types = {
            "batch-hour-feeder": "beban-penyulang",
            "batch-hour-transformer": "beban-trafo",
            "batch-hour-voltage": "tegangan-trafo",
        }
        if command in batch_types:
            for key in tuple(self.pending_values):
                if key.startswith("batch-"):
                    self.pending_values.pop(key, None)
            self.show_batch_hour_view(batch_types[command])
            return
        data_types = {
            "view-feeder": "beban-penyulang",
            "view-transformer": "beban-trafo",
            "view-voltage": "tegangan-trafo",
        }
        if command in data_types:
            self.show_data_view(data_types[command])
            return
        manual_types = {
            "input-feeder": "beban-penyulang",
            "input-transformer": "beban-trafo",
            "input-voltage": "tegangan-trafo",
        }
        if command in manual_types:
            self.show_manual_input_view(manual_types[command])
            return
        self.begin_operation(command.replace("-", " ").upper())
        self.run_worker(
            lambda: self._execute_command(command),
            thread=True,
            name="workflow",
            exclusive=True,
            exit_on_error=False,
        )

    def _execute_command(self, command: str):
        import superi_app as core

        self.workflow_thread_id = threading.get_ident()
        try:
            needs_login = command not in {
                "change-date", "setup", "photo-settings", "auto-settings", "logout"
            }
            if needs_login and not self.token:
                self.token, self.user, self.gi_id = core.do_login(core.load_config())
                if not self.token:
                    sc.pause("Login diperlukan. Tekan Enter untuk kembali...")
                    return

            mapping: dict[str, Callable[[], None]] = {
                "view-feeder": lambda: core.show_data(self.token, "beban-penyulang", self.gi_id, self.date_str),
                "view-transformer": lambda: core.show_data(self.token, "beban-trafo", self.gi_id, self.date_str),
                "view-voltage": lambda: core.show_data(self.token, "tegangan-trafo", self.gi_id, self.date_str),
                "input-feeder": lambda: core.input_single(self.token, "beban-penyulang", self.gi_id, self.date_str, self.user),
                "input-transformer": lambda: core.input_single(self.token, "beban-trafo", self.gi_id, self.date_str, self.user),
                "input-voltage": lambda: core.input_single(self.token, "tegangan-trafo", self.gi_id, self.date_str, self.user),
                "batch-hour-feeder": lambda: core.batch_fill_periode(self.token, "beban-penyulang", self.gi_id, self.date_str, self.user),
                "batch-hour-transformer": lambda: core.batch_fill_periode(self.token, "beban-trafo", self.gi_id, self.date_str, self.user),
                "batch-hour-voltage": lambda: core.batch_fill_periode(self.token, "tegangan-trafo", self.gi_id, self.date_str, self.user),
                "login": self._login,
                "setup": self._setup,
                "logout": self._logout,
                "change-date": self._change_date,
            }
            action = mapping.get(command)
            if action:
                action()
        except Exception as exc:
            print(f"\n  ✗ Error: {exc}")
            sc.pause("Tekan Enter untuk kembali...")
        finally:
            self.worker_output.flush()
            self.workflow_thread_id = None

    def _handle_auto_action(self, value: str):
        from superi_settings import get_auto_snapshot, set_auto_enabled, set_auto_sync

        if value == "0":
            self.action_back()
        elif value == "1":
            snapshot = get_auto_snapshot(include_scheduler=False)
            set_auto_enabled(not snapshot.enabled)
            self.notify("Status Auto Mode diperbarui", severity="information")
            self.show_auto_view(push=False)
        elif value == "2":
            snapshot = get_auto_snapshot(include_scheduler=False)
            self.pending_editor = "auto-window-start"
            self.pending_values = {"start": snapshot.window_start, "end": snapshot.window_end}
            self._set_editor_prompt("Jam mulai (0-23)", str(snapshot.window_start))
        elif value == "3":
            snapshot = get_auto_snapshot(include_scheduler=False)
            self.pending_editor = "auto-types"
            self._set_editor_prompt("Tipe: penyulang,trafo,tegangan", ",".join(snapshot.types))
        elif value == "4":
            snapshot = get_auto_snapshot(include_scheduler=False)
            set_auto_sync(not snapshot.sync_portal)
            self.notify("Sync Portal diperbarui", severity="information")
            self.show_auto_view(push=False)
        elif value == "5":
            self._start_auto_dry_run()
        elif value == "6":
            self._show_auto_log()
        elif value == "7":
            self._show_scheduler_view()
        elif value == "8":
            from superi_settings import AUTO_GUIDE
            self._show_guide("PANDUAN AUTO MODE", AUTO_GUIDE)
        else:
            self.set_prompt_error("Pilihan Auto Mode valid: 1-8 atau 0")

    def _handle_photo_action(self, value: str):
        from superi_settings import get_photo_snapshot

        if value == "0":
            self.action_back()
        elif value == "1":
            snapshot = get_photo_snapshot()
            self.pending_editor = "photo-source"
            self._set_editor_prompt("Sumber foto: manual atau pool", snapshot.configured_source)
        elif value == "2":
            snapshot = get_photo_snapshot()
            self.pending_editor = "history-days"
            self._set_editor_prompt("History days: 3, 7, atau 14", str(snapshot.history_days))
        elif value == "3":
            self._show_pool_details()
        elif value == "4":
            self._start_photo_validation()
        elif value == "5":
            from superi_settings import PHOTO_GUIDE
            self._show_guide("PANDUAN FOTO MANUAL", PHOTO_GUIDE)
        elif value == "6":
            self._start_photo_random_test()
        else:
            self.set_prompt_error("Pilihan Sumber Foto valid: 1-6 atau 0")

    def _handle_sync_action(self, value: str):
        if value == "0":
            self.action_back()
        elif value == "1":
            current = self.pending_values.get("sync-types", ("penyulang",))
            self.pending_editor = "sync-types"
            self._set_editor_prompt(
                "Jenis: penyulang, trafo, tegangan, atau semua",
                "semua" if len(current) == 3 else ",".join(current),
            )
        elif value == "2":
            self.pending_editor = "sync-window-start"
            self._set_editor_prompt("Jam mulai (0-23)", str(self.pending_values.get("sync-start", 0)))
        elif value == "3":
            self.pending_editor = "sync-date"
            self._set_editor_prompt("Tanggal Sync (YYYY-MM-DD)", self.pending_values.get("sync-date", self.date_str))
        elif value == "4":
            self._start_sync(dry_run=True)
        elif value == "5":
            self._start_sync(dry_run=True, offer_live=True)
        else:
            self.set_prompt_error("Pilihan Sync Portal valid: 1-5 atau 0")

    def _handle_setup_action(self, value: str):
        if value == "0":
            self.action_back()
        elif value in ("1", "2", "3"):
            self.pending_values["setup-draft"] = {}
            self.pending_values["setup-scope"] = value
            if value in ("1", "3"):
                self.pending_editor = "setup-nip"
                self._set_editor_prompt("Langkah 1 · NIP SUPER-I (kosong = pertahankan)", "")
            else:
                self.pending_editor = "setup-portal-user"
                self._set_editor_prompt("Langkah 1 · Username Portal (kosong = pertahankan)", "")
        elif value == "4":
            self._start_credential_test("superi")
        elif value == "5":
            self._start_credential_test("portal")
        else:
            self.set_prompt_error("Pilihan Setup Kredensial valid: 1-5 atau 0")

    def _handle_batch_hour_action(self, value: str):
        if value == "0":
            self.action_back()
        else:
            self.set_prompt_error("Ikuti prompt yang tampil, atau gunakan 0 untuk kembali")

    def _set_editor_prompt(self, label: str, default: str, *, password: bool = False):
        self._busy = False
        self.query_one("#prompt-panel").remove_class("busy")
        self.query_one("#prompt-label", Static).update(f"[bold #ffc107]{escape(label)}[/]")
        widget = self.query_one("#sticky-input", Input)
        widget.value = default
        widget.disabled = False
        widget.password = password
        widget.placeholder = "Kosongkan untuk mempertahankan nilai lama" if password else "Masukkan nilai..."
        widget.focus()
        widget.cursor_position = len(default)

    def _handle_editor_input(self, value: str):
        from superi_settings import install_scheduler, set_auto_types, set_auto_window, set_history_days, set_photo_source, uninstall_scheduler

        editor = self.pending_editor
        try:
            if editor == "auto-window-start":
                start = int(value)
                if not 0 <= start <= 23:
                    raise ValueError("Jam mulai harus 0-23")
                self.pending_values["start"] = start
                self.pending_editor = "auto-window-end"
                self._set_editor_prompt("Jam akhir (0-23)", str(self.pending_values["end"]))
                return
            if editor == "auto-window-end":
                set_auto_window(self.pending_values["start"], int(value))
                self.pending_editor = None
                self.show_auto_view(push=False)
            elif editor == "auto-types":
                set_auto_types([item.strip().lower() for item in value.split(",")])
                self.pending_editor = None
                self.show_auto_view(push=False)
            elif editor == "photo-source":
                set_photo_source(value.strip().lower())
                self.pending_editor = None
                self.refresh_dashboard()
                self.show_photo_view(push=False)
            elif editor == "history-days":
                set_history_days(int(value))
                self.pending_editor = None
                self.show_photo_view(push=False)
            elif editor == "sync-types":
                raw = [item.strip().lower() for item in value.split(",") if item.strip()]
                valid = ("penyulang", "trafo", "tegangan")
                selected = valid if "semua" in raw else tuple(item for item in valid if item in raw)
                if not selected:
                    raise ValueError("Pilih penyulang, trafo, tegangan, atau semua")
                self.pending_values["sync-types"] = tuple(selected)
                self.pending_editor = None
                self.show_sync_view(push=False)
            elif editor == "sync-window-start":
                start = int(value)
                if not 0 <= start <= 23:
                    raise ValueError("Jam mulai harus 0-23")
                self.pending_values["sync-start"] = start
                self.pending_editor = "sync-window-end"
                self._set_editor_prompt("Jam akhir (0-23)", str(self.pending_values.get("sync-end", 23)))
                return
            elif editor == "sync-window-end":
                end = int(value)
                start = self.pending_values["sync-start"]
                if not 0 <= end <= 23:
                    raise ValueError("Jam akhir harus 0-23")
                if end < start:
                    raise ValueError("Jam akhir tidak boleh sebelum jam mulai")
                self.pending_values["sync-end"] = end
                self.pending_editor = None
                self.show_sync_view(push=False)
            elif editor == "sync-date":
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError("Format tanggal harus YYYY-MM-DD")
                from datetime import datetime
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    raise ValueError("Tanggal tidak valid") from None
                self.pending_values["sync-date"] = value
                self.pending_editor = None
                self.show_sync_view(push=False)
            elif editor == "sync-live-confirm":
                self.pending_editor = None
                if value.lower() in ("y", "yes"):
                    self._start_sync(dry_run=False)
                elif self.pending_values.get("batch-sync-guided"):
                    self._return_to_batch_periods("Sync LIVE dibatalkan")
                else:
                    self.show_sync_view(push=False)
            elif editor == "setup-nip":
                if value:
                    self.pending_values["setup-draft"]["nip"] = value
                self.pending_editor = "setup-password"
                self._set_editor_prompt("Langkah 2 · Password SUPER-I (kosong = pertahankan)", "", password=True)
                return
            elif editor == "setup-password":
                if value:
                    self.pending_values["setup-draft"]["password"] = value
                if self.pending_values.get("setup-scope") == "3":
                    self.pending_editor = "setup-portal-user"
                    self._set_editor_prompt("Langkah 3 · Username Portal (kosong = pertahankan)", "")
                    return
                self._request_setup_confirmation()
            elif editor == "setup-portal-user":
                if value:
                    self.pending_values["setup-draft"]["portal_user"] = value
                self.pending_editor = "setup-portal-password"
                step = "Langkah 4" if self.pending_values.get("setup-scope") == "3" else "Langkah 2"
                self._set_editor_prompt(f"{step} · Password Portal (kosong = pertahankan)", "", password=True)
                return
            elif editor == "setup-portal-password":
                if value:
                    self.pending_values["setup-draft"]["portal_password"] = value
                self._request_setup_confirmation()
            elif editor == "setup-save-confirm":
                self.pending_editor = None
                if value.lower() in ("y", "yes"):
                    self._save_credential_draft()
                else:
                    self.pending_values.pop("setup-draft", None)
                    self.pending_values["setup-result"] = "[bold yellow]DIBATALKAN[/]\n[dim]Tidak ada perubahan yang disimpan.[/]"
                    self.show_setup_view(push=False)
            elif editor == "batch-period":
                period = int(value)
                overview = self.pending_values["batch-overview"]
                if not 0 <= period <= 23:
                    raise ValueError("Periode harus 0-23")
                if not overview.empty_by_period[period]:
                    raise ValueError(f"Periode P{period:02d} sudah penuh")
                self.pending_values["batch-period"] = period
                self.pending_values.pop("batch-suggestions", None)
                self.pending_values.pop("batch-result", None)
                self.pending_editor = None
                self._analyze_batch_period()
            elif editor == "batch-edit-confirm":
                if value.lower() in ("y", "yes"):
                    self.pending_editor = "batch-edit-selection"
                    invalid = [str(index) for index, suggestion in enumerate(self.pending_values["batch-suggestions"], 1) if not suggestion.valid]
                    default = ",".join(invalid)
                    self._set_editor_prompt("Nomor item yang diubah (contoh 2,5 atau all)", default)
                else:
                    invalid = [index for index, suggestion in enumerate(self.pending_values["batch-suggestions"]) if not suggestion.valid]
                    if invalid:
                        self.set_prompt_error("Item tanpa suggest wajib dilengkapi")
                        self.pending_values["batch-edit-queue"] = invalid
                        self.pending_values["batch-edit-position"] = 0
                        self._prompt_batch_edit()
                    else:
                        self._request_batch_submit()
            elif editor == "batch-edit-selection":
                suggestions = self.pending_values["batch-suggestions"]
                raw = value.strip().lower()
                if raw == "all":
                    selected = list(range(len(suggestions)))
                else:
                    numbers = [part.strip() for part in raw.split(",") if part.strip()]
                    if not numbers:
                        raise ValueError("Pilih minimal satu nomor item")
                    selected = []
                    for part in numbers:
                        number = int(part)
                        if not 1 <= number <= len(suggestions):
                            raise ValueError(f"Nomor item harus 1-{len(suggestions)}")
                        if number - 1 not in selected:
                            selected.append(number - 1)
                invalid = [index for index, suggestion in enumerate(suggestions) if not suggestion.valid]
                selected.extend(index for index in invalid if index not in selected)
                self.pending_values["batch-edit-queue"] = selected
                self.pending_values["batch-edit-position"] = 0
                self._prompt_batch_edit()
            elif editor == "batch-edit-value":
                self._apply_batch_edit(value, voltage=False)
            elif editor == "batch-edit-mv":
                self._apply_batch_edit(value, voltage=True)
            elif editor == "batch-edit-hv":
                self._apply_batch_hv(value)
            elif editor == "batch-submit-confirm":
                self.pending_editor = None
                if value.lower() in ("y", "yes"):
                    self._submit_batch_period()
                else:
                    self._prompt_batch_period()
            elif editor == "batch-sync-confirm":
                self.pending_editor = None
                if value.lower() in ("y", "yes"):
                    self._start_batch_sync()
                else:
                    self._return_to_batch_periods("Sync dilewati")
            elif editor in ("batch-reload-confirm", "batch-sync-failed"):
                self.pending_editor = None
                self._return_to_batch_periods("Data periode dimuat ulang")
            elif editor == "batch-sync-summary":
                self.pending_editor = None
                self._return_to_batch_periods("Sync Portal selesai")
            elif editor == "scheduler-install-confirm":
                self.pending_editor = None
                if value.lower() in ("y", "yes"):
                    plan = self.pending_schedule_plan
                    self._run_scheduler_operation(lambda: install_scheduler(plan.start, plan.end, plan=plan), "Memasang jadwal...")
                else:
                    self._show_scheduler_view()
                self.pending_schedule_plan = None
            elif editor == "scheduler-remove-confirm":
                self.pending_editor = None
                if value.lower() in ("y", "yes"):
                    self._run_scheduler_operation(uninstall_scheduler, "Menghapus jadwal...")
                else:
                    self._show_scheduler_view()
        except (ValueError, TypeError) as exc:
            self.set_prompt_error(str(exc))
            widget = self.query_one("#sticky-input", Input)
            widget.value = value
            widget.focus()

    def _load_batch_overview(self, data_type: str):
        from superi_batch import load_overview

        self.current_view = "batch-hour-loading"
        self.set_busy_prompt("Memuat data dan status 24 periode...")

        def work():
            if not self.token:
                core = __import__("superi_app")
                self.token, self.user, self.gi_id = core.do_login(core.load_config())
                if not self.token:
                    raise RuntimeError("Login SUPER-I diperlukan untuk memuat data batch")
            overview = load_overview(self.token, data_type, self.gi_id, self.date_str)
            self.pending_values["batch-overview"] = overview

        self.run_worker(work, thread=True, name="batch-load", exclusive=True, exit_on_error=False)

    def _prompt_batch_period(self):
        overview = self.pending_values.get("batch-overview")
        if not overview or not overview.items:
            self.pending_editor = None
            self._set_native_prompt("Tidak ada item. Tekan 0 atau Esc untuk kembali", "0")
            return
        if not overview.actionable_periods:
            self.pending_editor = None
            self.query_one("#batch-hour-context", Static).update(
                f"[bold green]{escape(overview.label)} · Semua 24 periode sudah lengkap[/] · {escape(overview.date)}"
            )
            self._set_native_prompt("Semua periode penuh. Tekan 0 atau Esc untuk kembali", "0")
            return
        self._render_batch_overview(overview)
        choices = "/".join(f"{period:02d}" for period in overview.actionable_periods)
        self.pending_editor = "batch-period"
        self._set_editor_prompt(f"Pilih periode [{choices}] · Esc=Kembali", f"{overview.actionable_periods[0]:02d}")

    def _analyze_batch_period(self):
        from superi_batch import analyze_period

        overview = self.pending_values["batch-overview"]
        period = self.pending_values["batch-period"]
        self.current_view = "batch-hour-analyzing"
        self.set_busy_prompt(f"Menganalisis histori untuk P{period:02d}:00...")
        self.query_one("#batch-hour-context", Static).update(
            f"[bold yellow]Menganalisis Smart Suggest · P{period:02d}:00[/] · "
            f"{len(overview.empty_by_period[period])} item"
        )

        def work():
            self.pending_values["batch-suggestions"] = analyze_period(
                overview, period, self.token, self.gi_id
            )

        self.run_worker(work, thread=True, name="batch-analyze", exclusive=True, exit_on_error=False)

    def _prompt_batch_edit(self):
        suggestions = self.pending_values["batch-suggestions"]
        queue = self.pending_values.get("batch-edit-queue", [])
        position = self.pending_values.get("batch-edit-position", 0)
        if position >= len(queue):
            if any(not suggestion.valid for suggestion in suggestions):
                self.set_prompt_error("Masih ada nilai yang wajib dilengkapi")
                self.pending_values["batch-edit-queue"] = [index for index, suggestion in enumerate(suggestions) if not suggestion.valid]
                self.pending_values["batch-edit-position"] = 0
                self._prompt_batch_edit()
                return
            self.pending_editor = None
            self.show_batch_hour_view(self.pending_values["batch-data-type"], push=False)
            self.notify("Edit nilai selesai", severity="information")
            self._request_batch_submit()
            return
        index = queue[position]
        suggestion = suggestions[index]
        name = suggestion.item["nama"]
        if self.pending_values["batch-data-type"] == "tegangan-trafo":
            self.pending_editor = "batch-edit-mv"
            self._set_editor_prompt(
                f"Edit {position + 1}/{len(queue)} · Item {index + 1} · {name} · MV (kV)",
                "" if suggestion.value is None else str(suggestion.value),
            )
        else:
            self.pending_editor = "batch-edit-value"
            self._set_editor_prompt(
                f"Edit {position + 1}/{len(queue)} · Item {index + 1} · {name} · Ampere",
                "" if suggestion.value is None else str(suggestion.value),
            )

    def _parse_batch_number(self, value: str, current):
        if not value.strip():
            if current is None:
                raise ValueError("Nilai wajib diisi karena tidak ada suggest")
            return current
        number = float(value)
        if number <= 0:
            raise ValueError("Nilai harus lebih besar dari 0")
        return number

    def _apply_batch_edit(self, value: str, *, voltage: bool):
        suggestions = self.pending_values["batch-suggestions"]
        queue = self.pending_values["batch-edit-queue"]
        position = self.pending_values["batch-edit-position"]
        index = queue[position]
        suggestion = suggestions[index]
        suggestion.value = self._parse_batch_number(value, suggestion.value)
        if voltage:
            self.pending_editor = "batch-edit-hv"
            self._set_editor_prompt(
                f"Item {index + 1}/{len(suggestions)} · {suggestion.item['nama']} · HV (kV)",
                "" if suggestion.hv is None else str(suggestion.hv),
            )
            return
        self.pending_values["batch-edit-position"] = position + 1
        self._prompt_batch_edit()

    def _apply_batch_hv(self, value: str):
        suggestions = self.pending_values["batch-suggestions"]
        queue = self.pending_values["batch-edit-queue"]
        position = self.pending_values["batch-edit-position"]
        index = queue[position]
        suggestion = suggestions[index]
        suggestion.hv = self._parse_batch_number(value, suggestion.hv)
        self.pending_values["batch-edit-position"] = position + 1
        self._prompt_batch_edit()

    def _request_batch_submit(self):
        suggestions = self.pending_values.get("batch-suggestions", [])
        period = self.pending_values.get("batch-period")
        if not suggestions or any(not suggestion.valid for suggestion in suggestions):
            self.set_prompt_error("Lengkapi semua nilai yang berstatus PERLU EDIT")
            return
        self.pending_editor = "batch-submit-confirm"
        self._set_editor_prompt(f"Jalankan batch {len(suggestions)} item di P{period:02d}:00? (y/N)", "n")

    def _submit_batch_period(self):
        from superi_batch import submit_period

        overview = self.pending_values["batch-overview"]
        period = self.pending_values["batch-period"]
        suggestions = self.pending_values["batch-suggestions"]
        log = self.query_one("#batch-hour-log", RichLog)
        log.clear()
        log.display = True
        self.query_one("#batch-hour-table").display = False
        self.current_view = "batch-hour-submitting"
        self.pending_values["batch-started-at"] = time.monotonic()
        self.set_busy_prompt(f"Menginput {len(suggestions)} item pada P{period:02d}:00...")
        progress_panel = self.query_one("#batch-hour-progress-panel")
        progress_panel.add_class("active")
        self.query_one("#batch-hour-progress", ProgressBar).update(total=len(suggestions), progress=0)
        self.query_one("#batch-hour-progress-label", Static).update(f"BATCH P{period:02d}:00 · Menyiapkan {len(suggestions)} item...")

        def progress(done, total, name, ok, detail):
            style = "green" if ok else "red"
            self.call_from_thread(log.write, f"[{style}][{done:02d}/{total:02d}] {escape(name)} · {'OK' if ok else 'GAGAL'} · {escape(detail)}[/]")
            self.call_from_thread(self.query_one("#batch-hour-progress", ProgressBar).update, total=total, progress=done)
            self.call_from_thread(
                self.query_one("#batch-hour-progress-label", Static).update,
                f"BATCH P{period:02d}:00 · {done}/{total} · {escape(name)} · {'BERHASIL' if ok else 'GAGAL'}",
            )
            self.pending_values["batch-progress"] = (done, total, name)

        def work():
            result = submit_period(overview, period, suggestions, self.token, progress=progress)
            self.pending_values["batch-result"] = result
            self.pending_values["batch-elapsed"] = time.monotonic() - self.pending_values["batch-started-at"]

        self.run_worker(work, thread=True, name="batch-submit", exclusive=True, exit_on_error=False)

    def _start_batch_sync(self):
        overview = self.pending_values["batch-overview"]
        period = self.pending_values["batch-period"]
        type_map = {
            "beban-penyulang": "penyulang",
            "beban-trafo": "trafo",
            "tegangan-trafo": "tegangan",
        }
        self.pending_values["sync-types"] = (type_map[overview.data_type],)
        self.pending_values["sync-start"] = period
        self.pending_values["sync-end"] = period
        self.pending_values["sync-date"] = overview.date
        self.pending_values["batch-sync-guided"] = True
        self.show_sync_view()
        self._start_sync(dry_run=True, offer_live=True)

    def _return_to_batch_periods(self, message: str = ""):
        data_type = self.pending_values.get("batch-data-type", "beban-penyulang")
        self.pending_editor = None
        self.pending_values.pop("batch-sync-guided", None)
        for key in (
            "batch-overview", "batch-period", "batch-suggestions", "batch-result",
            "batch-edit-queue", "batch-edit-position", "batch-progress",
            "batch-started-at", "batch-elapsed",
        ):
            self.pending_values.pop(key, None)
        self.view_stack = [view for view in self.view_stack if view != "batch-hour"]
        self.show_batch_hour_view(data_type, push=False)
        if message:
            self.notify(message, severity="information")

    def _request_setup_confirmation(self):
        draft = self.pending_values.get("setup-draft", {})
        if not draft:
            self.pending_values["setup-result"] = "[bold yellow]TIDAK ADA PERUBAHAN[/]\n[dim]Semua input dikosongkan.[/]"
            self.pending_editor = None
            self.show_setup_view(push=False)
            return
        labels = {
            "nip": "NIP SUPER-I",
            "password": "Password SUPER-I",
            "portal_user": "Username Portal",
            "portal_password": "Password Portal",
        }
        changed = ", ".join(labels[key] for key in draft)
        self.pending_values["setup-result"] = (
            "[bold yellow]MENUNGGU KONFIRMASI[/]\n"
            f"Field berubah      [bold white]{escape(changed)}[/]\n"
            "[dim]Password tidak ditampilkan.[/]"
        )
        self.show_setup_view(push=False)
        self.pending_editor = "setup-save-confirm"
        self._set_editor_prompt("Simpan perubahan kredensial? (y/N)", "n")

    def _save_credential_draft(self):
        import superi_sync
        from superi_settings import update_credentials

        draft = self.pending_values.pop("setup-draft", {})
        superi_changed = bool({"nip", "password"} & draft.keys())
        update_credentials(**draft)
        self.config = __import__("superi_app").load_config()
        if superi_changed:
            self.token = self.user = self.gi_id = None
        # superi_sync caches credentials at import time.
        superi_sync._CFG = dict(self.config)
        superi_sync.SUPER_I_NIP = self.config.get("nip", "")
        superi_sync.SUPER_I_PASS = self.config.get("password", "")
        superi_sync.PORTAL_USER = self.config.get("portal_user", "")
        superi_sync.PORTAL_PASS = self.config.get("portal_password", "")
        self.pending_values["setup-result"] = (
            "[bold green]BERHASIL DISIMPAN[/]\n"
            f"Field diperbarui   [bold white]{len(draft)}[/]\n"
            f"Sesi SUPER-I       {'[bold yellow]PERLU LOGIN ULANG[/]' if superi_changed else '[bold green]TETAP AKTIF[/]'}"
        )
        self.refresh_dashboard()
        self.show_setup_view(push=False)

    def _start_credential_test(self, target: str):
        from superi_settings import get_credential_snapshot

        snapshot = get_credential_snapshot()
        ready = snapshot.superi_ready if target == "superi" else snapshot.portal_ready
        label = "SUPER-I APP" if target == "superi" else "Portal APD"
        if not ready:
            self.set_prompt_error(f"Kredensial {label} belum lengkap")
            return
        self.pending_values["setup-result"] = (
            f"Target             [bold white]{label}[/]\n"
            "Status             [bold yellow]MENGUJI KONEKSI[/]\n"
            "[dim]Kredensial tidak ditampilkan pada log.[/]"
        )
        self.show_setup_view(push=False)
        self.current_view = "setup-testing"
        self.set_busy_prompt(f"Menguji koneksi {label}...")

        def work():
            if target == "superi":
                core = __import__("superi_app")
                token, user, gi_id = core.do_login(core.load_config())
                ok = bool(token)
                if ok:
                    self.token, self.user, self.gi_id = token, user, gi_id
            else:
                import superi_sync
                cfg = __import__("superi_app").load_config()
                old_user, old_pass = superi_sync.PORTAL_USER, superi_sync.PORTAL_PASS
                try:
                    superi_sync.PORTAL_USER = cfg.get("portal_user", "")
                    superi_sync.PORTAL_PASS = cfg.get("portal_password", "")
                    ok = superi_sync.PortalPLN().login()
                finally:
                    superi_sync.PORTAL_USER, superi_sync.PORTAL_PASS = old_user, old_pass
            self._credential_test_ok = ok

        self._credential_test_target = label
        self.run_worker(work, thread=True, name="credential-test", exclusive=True, exit_on_error=False)

    def _start_sync(self, *, dry_run: bool, offer_live: bool = False):
        import superi_sync

        cfg = self.config or {}
        if not (cfg.get("nip") and cfg.get("password")):
            self.set_prompt_error("Kredensial SUPER-I belum lengkap. Gunakan menu Setup.")
            return
        if not (cfg.get("portal_user") and cfg.get("portal_password")):
            self.set_prompt_error("Kredensial Portal APD belum lengkap. Gunakan menu Setup.")
            return

        types = tuple(self.pending_values.get("sync-types", ("penyulang",)))
        start = int(self.pending_values.get("sync-start", 0))
        end = int(self.pending_values.get("sync-end", 23))
        date = self.pending_values.get("sync-date", self.date_str)
        mode = "DRY-RUN PREVIEW" if dry_run else "LIVE SYNC"
        log = self.query_one("#sync-log", RichLog)
        log.clear()
        log.write(f"[bold yellow]{mode}[/]  [dim]{escape(date)} · {start:02d}:00-{end:02d}:00[/]")
        self.pending_values["sync-summary"] = (
            f"Mode               [bold {'yellow' if dry_run else 'green'}]{mode}[/]\n"
            "Status             [bold yellow]SEDANG BERJALAN[/]\n"
            f"Jenis              [bold white]{len(types)} tipe data[/]\n"
            "[dim]Detail proses tersedia pada log di bawah.[/]"
        )
        self.show_sync_view(push=False)
        progress_panel = self.query_one("#sync-progress-panel")
        progress_panel.remove_class("success", "failed")
        progress_panel.add_class("active")
        self.query_one("#sync-progress", ProgressBar).update(total=100, progress=0)
        self.query_one("#sync-progress-label", Static).update(f"{mode} · Menyiapkan koneksi...")
        self.current_view = "sync-running"
        self._sync_offer_live = bool(offer_live)
        self._sync_last_ok = False
        self._sync_results = []
        self.set_busy_prompt(f"{mode.title()} sedang berjalan...")

        def work():
            old_rich = superi_sync.RICH
            self.workflow_thread_id = threading.get_ident()
            results = []
            try:
                # Rich live rendering targets the real terminal; plain ANSI output is
                # safely forwarded line-by-line into the Textual log viewport.
                superi_sync.RICH = False
                labels = {"penyulang": "Beban Penyulang", "trafo": "Beban Trafo", "tegangan": "Tegangan Trafo"}
                for index, data_type in enumerate(types, start=1):
                    label = labels[data_type]

                    def update_progress(done, total, item, *, index=index, label=label):
                        self.call_from_thread(
                            self._update_sync_progress,
                            index,
                            len(types),
                            label,
                            done,
                            total,
                            item,
                        )

                    def sync_event(event, data, *, index=index):
                        self.call_from_thread(self._write_sync_event, event, data, index, len(types))

                    results.append(
                        superi_sync.do_sync(
                            data_type,
                            start,
                            end,
                            date,
                            dry_run=dry_run,
                            progress_callback=update_progress,
                            event_callback=sync_event,
                        )
                    )
                ok = all(results)
                self._sync_results = results
                self._sync_last_ok = ok
                self.call_from_thread(self._write_sync_final, results)
                status = "PREVIEW SIAP" if dry_run and ok else "SELESAI" if ok else "SEBAGIAN GAGAL"
                style = "green" if ok else "yellow"
                self.pending_values["sync-summary"] = (
                    f"Mode               [bold {'yellow' if dry_run else 'green'}]{mode}[/]\n"
                    f"Status             [bold {style}]{status}[/]\n"
                    f"Jenis diproses     [bold white]{len(types)}[/]\n"
                    f"Rentang            [bold white]{start:02d}:00-{end:02d}:00[/]"
                )
            finally:
                self.worker_output.flush()
                self.workflow_thread_id = None
                superi_sync.RICH = old_rich

        self.run_worker(work, thread=True, name="sync-operation", exclusive=True, exit_on_error=False)

    def _update_sync_progress(
        self,
        index: int,
        type_count: int,
        label: str,
        done: int,
        total: int,
        item: str,
    ):
        total = max(total, 1)
        self.query_one("#sync-progress", ProgressBar).update(total=total, progress=min(done, total))
        item_text = f" · {escape(item)}" if item else ""
        self.query_one("#sync-progress-label", Static).update(
            f"Jenis {index}/{type_count} · {escape(label)} · {done}/{total} cell{item_text}"
        )

    def _write_sync_event(self, event: str, data: dict, index: int, type_count: int):
        log = self.query_one("#sync-log", RichLog)
        if event == "section":
            if index > 1:
                log.write("")
            log.write(f"[bold #ffc107]{escape(data['label']).upper()}[/]")
        elif event == "stage":
            log.write(f"  [cyan]·[/] {escape(data['message'])}")
        elif event == "stage_ok":
            log.write(f"  [bold green]✓[/] {escape(data['message'])}")
        elif event == "error":
            log.write(f"  [bold red]✗[/] {escape(data['message'])}")
        elif event == "sample":
            log.write(f"  [cyan]•[/] {escape(data['message'])}")
        elif event == "warning":
            log.write(f"  [bold yellow]⚠[/] {escape(data['message'])}")
            for detail in data.get("details", ()):
                log.write(f"    [dim]• {escape(detail)}[/]")
        elif event == "summary":
            style = "green" if data["failed"] == 0 else "yellow"
            log.write(
                f"  [bold {style}]Selesai[/] · "
                f"[green]{data['updated']} diperbarui[/] · "
                f"[dim]{data['skipped']} dilewati[/] · "
                f"[{'red' if data['failed'] else 'dim'}]{data['failed']} gagal[/]"
            )

    def _write_sync_final(self, results):
        completed = sum(bool(result) for result in results)
        style = "green" if completed == len(results) else "yellow"
        log = self.query_one("#sync-log", RichLog)
        log.write("")
        log.write("[bold #ffc107]HASIL AKHIR[/]")
        log.write(
            f"  [bold {style}]{completed}/{len(results)} jenis berhasil[/]"
        )

    def _handle_scheduler_action(self, value: str):
        if value == "0":
            self.action_back()
        elif value == "1":
            from superi_settings import build_schedule_plan, get_auto_snapshot
            snapshot = get_auto_snapshot(include_scheduler=False)
            self.pending_schedule_plan = build_schedule_plan(snapshot.window_start, snapshot.window_end)
            log = self.query_one("#native-log", RichLog)
            log.write("\n[bold yellow]Preview jadwal yang akan dipasang:[/]")
            for name, hour, minute in self.pending_schedule_plan.entries:
                log.write(f"  {hour:02d}:{minute:02d}  [dim]{escape(name)}[/]")
            self.pending_editor = "scheduler-install-confirm"
            self._set_editor_prompt("Ganti/pasang jadwal otomatis? (y/N)", "n")
        elif value == "2":
            self.pending_editor = "scheduler-remove-confirm"
            self._set_editor_prompt("Hapus semua jadwal SUPER-I? (y/N)", "n")
        elif value == "3":
            self._show_scheduler_view()
        else:
            self.set_prompt_error("Pilihan Scheduler valid: 1, 2, 3, atau 0")

    def _run_scheduler_operation(self, operation, message: str):
        log = self.query_one("#native-log", RichLog)
        self.current_view = "scheduler-operation"
        self.set_busy_prompt(message)

        def work():
            ok, result = operation()
            self.call_from_thread(log.write, f"\n[bold {'green' if ok else 'red'}]{escape(str(result))}[/]")

        self.run_worker(work, thread=True, name="native-operation", exit_on_error=False)

    def _prepare_table(self, heading: str, columns: list[str]):
        self._show_native_view("table")
        self.query_one("#table-heading", Static).update(f"[bold #ffc107]{escape(heading)}[/]")
        table = self.query_one("#native-table", DataTable)
        table.clear(columns=True)
        table.add_columns(*columns)
        self._set_native_prompt("Tekan 0 atau Esc untuk kembali", "0")
        return table

    def _show_pool_details(self):
        from superi_settings import get_pool_details

        detail = get_pool_details()
        table = self._prepare_table("SUMBER FOTO / DETAIL POOL", ["Kategori", "Item", "Foto", "CB/HV", "MV", "Status"])
        for name, count, cb, status in detail.feeders:
            table.add_row("Penyulang", name, str(count), cb, "—", status)
        for name, count, status in detail.transformers:
            table.add_row("Beban Trafo", name, str(count), "—", "—", status)
        for name, hv, mv, total, status in detail.voltages:
            table.add_row("Tegangan", name, str(total), str(hv), str(mv), status)

    def _show_guide(self, heading: str, markdown_text: str):
        self._show_native_view("guide")
        self.query_one("#guide-heading", Static).update(f"[bold #ffc107]{escape(heading)}[/]")
        self.query_one("#native-guide", Markdown).update(markdown_text)
        self._set_native_prompt("Tekan 0 atau Esc untuk kembali", "0")

    def _prepare_native_log(self, heading: str):
        self._show_native_view("log")
        self.query_one("#log-heading", Static).update(f"[bold #ffc107]{escape(heading)}[/]")
        log = self.query_one("#native-log", RichLog)
        log.clear()
        self._set_native_prompt("Tekan 0 atau Esc untuk kembali", "0")
        return log

    def _show_auto_log(self):
        from superi_settings import _core

        log = self._prepare_native_log("AUTO MODE / LOG AKTIVITAS")
        path = Path(_core().SCRIPT_DIR) / "auto_log.txt"
        if not path.exists():
            log.write("[bold yellow]Belum ada log. Jalankan test dry-run terlebih dahulu.[/]")
            return
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        for line in lines:
            style = "bold red" if "[ERROR]" in line else "bold yellow" if "[WARN]" in line else "cyan" if "[INFO]" in line else "white"
            log.write(f"[{style}]{escape(line)}[/]")
        log.write(f"\n[dim]File: {escape(str(path))}[/]")

    def _show_scheduler_view(self):
        from superi_settings import get_auto_snapshot, scheduler_lines

        log = self._prepare_native_log("AUTO MODE / JADWAL OTOMATIS")
        snapshot = get_auto_snapshot(include_scheduler=True)
        log.write(f"Platform  : [bold yellow]{snapshot.scheduler_platform}[/]")
        log.write(f"Window    : {snapshot.window_start:02d}:00-{snapshot.window_end:02d}:00")
        log.write(f"Health    : [bold {'green' if snapshot.scheduler_health == 'COMPLETE' else 'yellow' if snapshot.scheduler_health == 'PARTIAL' else 'red'}]{snapshot.scheduler_health}[/]")
        log.write(f"Terpasang : {snapshot.scheduler_installed}/{snapshot.scheduler_expected}\n")
        for line in scheduler_lines():
            log.write(escape(line))
        log.write("\n[bold #ffc107][1][/] Pasang/Pasang Ulang  [bold red][2][/] Hapus  [bold #ffc107][3][/] Refresh  [bold red][0][/] Kembali")
        self.current_view = "scheduler"
        self._set_native_prompt("Pilih aksi Scheduler", "1, 2, 3, atau 0")

    def _start_auto_dry_run(self):
        log = self._prepare_native_log("AUTO MODE / TEST DRY-RUN")
        log.write("[bold yellow]Menjalankan dry-run. Tidak ada input atau sync Portal yang ditulis.[/]")
        self.current_view = "auto-dry-run"
        self.set_busy_prompt("Dry-run sedang berjalan...")

        def work():
            import superi_auto
            self.workflow_thread_id = threading.get_ident()
            try:
                superi_auto.run_auto(force_jam=__import__("datetime").datetime.now().hour, dry_run=True)
            finally:
                self.worker_output.flush()
                self.workflow_thread_id = None

        self.run_worker(work, thread=True, name="native-operation", exit_on_error=False)

    def _start_photo_validation(self):
        log = self._prepare_native_log("SUMBER FOTO / VALIDASI FOTO MANUAL")
        log.write("[bold yellow]Memindai file foto manual...[/]")
        self.current_view = "photo-validation"
        self.set_busy_prompt("Validasi foto sedang berjalan...")

        def work():
            import subprocess
            import superi_app as core
            script = os.path.join(core.SCRIPT_DIR, "tools", "validate_manual_pool.py")
            result = subprocess.run([sys.executable, script], cwd=core.SCRIPT_DIR, capture_output=True, text=True)
            for line in (result.stdout + result.stderr).splitlines():
                self.call_from_thread(log.write, Text.from_ansi(line))
            self.call_from_thread(log.write, f"\n[bold {'green' if result.returncode == 0 else 'red'}]Exit code: {result.returncode}[/]")

        self.run_worker(work, thread=True, name="native-operation", exit_on_error=False)

    def _start_photo_random_test(self):
        from superi_settings import filename_samples, run_photo_random_test

        self._show_native_view("table")
        self.current_view = "photo-random"
        self.query_one("#table-heading", Static).update("[bold #ffc107]SUMBER FOTO / TEST RANDOM[/]")
        table = self.query_one("#native-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Item", "Tipe", "Run", "Size", "Source", "Variant", "Mode", "Error")
        self.set_busy_prompt("Membuat sampel foto di memory...")

        def work():
            rows = run_photo_random_test()
            samples = filename_samples()

            def render():
                for row in rows:
                    table.add_row(row.item, row.data_type, row.run, f"{row.size // 1024} KB" if row.size else "—", row.source[:24], row.variant, row.mode, row.error[:30])
                for kind, filename in samples:
                    table.add_row("Filename", kind, "—", "—", filename, "—", "—", "")

            self.call_from_thread(render)

        self.run_worker(work, thread=True, name="native-operation", exit_on_error=False)

    def _login(self):
        import superi_app as core

        self.token, self.user, self.gi_id = core.do_login(core.load_config())
        print()
        if self.token:
            name = self.user.get("namaLengkap", "Pengguna") if self.user else "Pengguna"
            sc.ok(f"LOGIN ULANG BERHASIL · {name} · GI {self.gi_id or '-'}")
            sc.pause("Login berhasil. Tekan Enter untuk kembali...")
        else:
            self.user = self.gi_id = None
            sc.err("LOGIN ULANG GAGAL")
            sc.warn_msg("Periksa NIP, password, koneksi jaringan, lalu coba kembali.")
            sc.pause("Login gagal. Tekan Enter untuk kembali...")

    def _setup(self):
        import superi_app as core
        core.setup_config()
        self.config = core.load_config()
        self.token = None

    def _logout(self):
        import superi_app as core
        did_logout, config = core.do_logout_interactive(self.user)
        if did_logout:
            self.config = config
            self.token = self.user = self.gi_id = None

    def _change_date(self):
        value = sc.prompt_ask("Tanggal (YYYY-MM-DD)", default=self.date_str)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            self.date_str = value
        else:
            sc.warn_msg("Format tanggal harus YYYY-MM-DD")
            sc.pause("Tekan Enter untuk kembali...")

    def on_worker_state_changed(self, event: Worker.StateChanged):
        if event.worker.name == "manual-items-load" and event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            data_type = self.pending_values.get("manual-data-type", "beban-penyulang")
            self.current_view = "manual-input"
            if event.state == WorkerState.ERROR:
                self.query_one("#manual-input-summary", Static).update(
                    f"[bold red]GAGAL MEMUAT ITEM[/] · [dim]{escape(str(event.worker.error))}[/]"
                )
                self.query_one("#sync-progress-label", Static).update(
                    f"GAGAL · {message}"
                )
            elif event.state == WorkerState.SUCCESS:
                ok = getattr(self, "_sync_last_ok", False)
                results = getattr(self, "_sync_results", [])
                completed = sum(bool(result) for result in results)
                status = "SELESAI" if ok else "SEBAGIAN GAGAL"
                self.query_one("#sync-progress-label", Static).update(
                    f"{status} · {completed}/{len(results)} jenis berhasil"
                )
            else:
                items = self.pending_values.get("manual-items", ())
                self._render_manual_input_table(data_type, items)
                if not items:
                    self.query_one("#manual-input-summary", Static).update(
                        f"[bold yellow]Tidak ada item untuk {escape(self.date_str)}[/]"
                    )
            self._set_native_prompt("Pilih nomor item, atau 0 untuk kembali", "Contoh: 1")
            return
        if event.worker.name == "manual-input-operation" and event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            self.current_view = "manual-input-result"
            if event.state == WorkerState.ERROR:
                self.query_one("#manual-input-log", RichLog).write(
                    f"[bold red]Error: {escape(str(event.worker.error))}[/]"
                )
            self._set_native_prompt("Input selesai. Tekan 0 atau Esc untuk kembali", "0")
            return
        if event.worker.name == "data-load" and event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            data_type = self.pending_values.get("data-type", "beban-penyulang")
            self.current_view = "data"
            if event.state == WorkerState.ERROR:
                self.query_one("#data-summary", Static).update(
                    f"[bold red]GAGAL MEMUAT DATA[/] · [dim]{escape(str(event.worker.error))}[/]"
                )
            else:
                self._render_data_table(data_type, self.pending_values.get("data-items", ()))
                if not self.pending_values.get("data-items"):
                    self.query_one("#data-summary", Static).update(
                        f"[bold yellow]Tidak ada data untuk {escape(self.date_str)}[/]"
                    )
            self._set_native_prompt("Tekan 0 atau Esc untuk kembali", "0")
            return
        if event.worker.name in ("batch-load", "batch-analyze", "batch-submit") and event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            data_type = self.pending_values.get("batch-data-type", "beban-penyulang")
            self.current_view = "batch-hour"
            if event.state == WorkerState.ERROR:
                message = escape(str(event.worker.error))
                self.query_one("#batch-hour-context", Static).update(
                    f"[bold red]PROSES GAGAL[/] · [dim]{message}[/]"
                )
                self._set_native_prompt("Tekan 0 atau Esc untuk kembali", "0")
                return
            if event.worker.name == "batch-load":
                self.show_batch_hour_view(data_type, push=False)
                overview = self.pending_values.get("batch-overview")
                self._prompt_batch_period()
            elif event.worker.name == "batch-analyze":
                self.show_batch_hour_view(data_type, push=False)
                suggestions = self.pending_values.get("batch-suggestions", [])
                self.pending_editor = "batch-edit-confirm"
                self._set_editor_prompt(f"Ubah nilai Smart Suggest ({len(suggestions)} item)? (y/N)", "n")
            else:
                result = self.pending_values.get("batch-result")
                if result:
                    self.show_batch_hour_view(data_type, push=False)
                    if result.success:
                        self.pending_editor = "batch-sync-confirm"
                        period = self.pending_values["batch-period"]
                        self._set_editor_prompt(
                            f"Sync {result.success} hasil P{period:02d}:00 ke Portal APD? (y/N)", "n"
                        )
                    else:
                        self._set_native_prompt("Semua input gagal. Tekan Enter untuk memuat ulang", "")
                        self.pending_editor = "batch-reload-confirm"
            return
        if event.worker.name == "credential-test" and event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            label = getattr(self, "_credential_test_target", "Koneksi")
            ok = event.state == WorkerState.SUCCESS and getattr(self, "_credential_test_ok", False)
            message = "Koneksi dan autentikasi berhasil." if ok else (
                str(event.worker.error) if event.state == WorkerState.ERROR else "Koneksi atau autentikasi gagal."
            )
            self.pending_values["setup-result"] = (
                f"Target             [bold white]{escape(label)}[/]\n"
                f"Status             [bold {'green' if ok else 'red'}]{'BERHASIL' if ok else 'GAGAL'}[/]\n"
                f"[dim]{escape(message)}[/]"
            )
            self.current_view = "setup"
            self.show_setup_view(push=False)
            return
        if event.worker.name == "sync-operation" and event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            offer_live = getattr(self, "_sync_offer_live", False)
            guided = bool(self.pending_values.get("batch-sync-guided"))
            self._sync_offer_live = False
            self.current_view = "sync"
            if event.state == WorkerState.ERROR:
                message = escape(str(event.worker.error))
                self.query_one("#sync-log", RichLog).write(f"[bold red]Worker error: {message}[/]")
                self.pending_values["sync-summary"] = (
                    "Mode               [bold yellow]SYNC[/]\n"
                    "Status             [bold red]GAGAL[/]\n"
                    f"[dim]{message}[/]"
                )
            progress_panel = self.query_one("#sync-progress-panel")
            if event.state == WorkerState.SUCCESS and getattr(self, "_sync_last_ok", False):
                progress_panel.add_class("success")
            else:
                progress_panel.add_class("failed")
            self.show_sync_view(push=False)
            if event.state == WorkerState.SUCCESS and offer_live and getattr(self, "_sync_last_ok", False):
                if guided:
                    self._start_sync(dry_run=False)
                else:
                    self.pending_editor = "sync-live-confirm"
                    self._set_editor_prompt("Preview selesai. Lanjut LIVE Sync? (y/N)", "n")
            elif guided and not offer_live:
                self.pending_editor = "batch-sync-summary"
                status = "selesai" if getattr(self, "_sync_last_ok", False) else "sebagian gagal"
                self._set_editor_prompt(f"Sync Portal {status}. Tekan Enter untuk kembali ke periode", "")
            elif guided:
                self.pending_editor = "batch-sync-failed"
                self._set_editor_prompt("Preview sync gagal. Muat ulang periode? (Y/n)", "y")
            else:
                self._set_native_prompt("Pilih aksi Sync Portal", "1-5 atau 0")
            return
        if event.worker.name == "native-operation" and event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            if event.state == WorkerState.ERROR:
                self.query_one("#native-log", RichLog).write(f"[bold red]Error: {escape(str(event.worker.error))}[/]")
            if self.current_view == "photo-random":
                self._set_native_prompt("Tekan 0 atau Esc untuk kembali", "0")
            elif self.current_view == "scheduler-operation":
                self.current_view = "scheduler"
                self._set_native_prompt("Pilih aksi Scheduler", "1, 2, 3, atau 0")
            else:
                self._set_native_prompt("Tekan 0 atau Esc untuk kembali", "0")
            return
        if event.worker.name not in ("workflow", "startup"):
            return
        if event.state == WorkerState.ERROR:
            self.write_output(f"✗ Worker error: {event.worker.error}")
        if event.state in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            self.finish_operation()

    def action_back(self):
        if self.prompt_backend.active:
            self.prompt_backend.cancel()
            return
        if self._busy:
            self.set_prompt_error("Proses masih berjalan; tunggu hingga selesai.")
            return
        self.pending_editor = None
        input_widget = self.query_one("#sticky-input", Input)
        input_widget.value = ""
        input_widget.password = False
        if self.current_view == "dashboard":
            self.finish_operation()
            return
        previous = self.view_stack.pop() if self.view_stack else "dashboard"
        if previous == "auto":
            self.show_auto_view(push=False)
        elif previous == "photo":
            self.show_photo_view(push=False)
        elif previous == "sync":
            self.show_sync_view(push=False)
        elif previous == "setup":
            self.show_setup_view(push=False)
        elif previous == "batch-hour":
            self.show_batch_hour_view(self.pending_values.get("batch-data-type", "beban-penyulang"), push=False)
        elif previous == "manual-input":
            self.show_manual_input_view(self.pending_values.get("manual-data-type", "beban-penyulang"), push=False)
        else:
            self.show_dashboard_view()

    def action_request_quit(self):
        if self.prompt_backend.active:
            self.prompt_backend.cancel()
        self.exit()

    def action_help(self):
        self.notify(
            "Ketik kode menu pada input bawah. Enter memilih, Esc kembali, PgUp/PgDn scroll, Ctrl+Q keluar.",
            title="Bantuan SUPER-I",
            timeout=6,
        )

    def action_redraw(self):
        self.refresh(layout=True)


def run_tui():
    SuperITui().run()


if __name__ == "__main__":
    run_tui()
