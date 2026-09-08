"""Admin main window — CustomTkinter with embedded grid panels.

Entry point for the new admin application. Panels are CTkFrames
inside the main window, arranged horizontally via grid.
"""

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

import customtkinter

_this_dir = Path(__file__).resolve().parent
_project_root = _this_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from admin_ui.panels import PanelDock
from admin_ui.panels_content import (
    status_controller,
    builds_controller,
    community_controller,
    errors_controller,
    log_controller,
)
from admin_ui.tray import AdminTray

logger = logging.getLogger(__name__)

APPDATA_DIR = Path(os.environ.get("APPDATA", "")) / "SM WoT Assistant"
SETTINGS_FILE = APPDATA_DIR / "admin_settings.json"


def _load_settings() -> dict:
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_settings(settings: dict) -> None:
    try:
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except Exception:
        pass


class AdminApp(customtkinter.CTk):
    """Admin desktop application with embedded horizontal panels."""

    def __init__(self) -> None:
        theme_path = Path(__file__).parent / "theme.json"
        customtkinter.set_appearance_mode("dark")
        if theme_path.exists():
            customtkinter.set_default_color_theme(str(theme_path))
        else:
            customtkinter.set_default_color_theme("dark-blue")

        super().__init__()

        self.default_width = 1200
        self.default_height = 700
        self.title("SM WoT Assistant \u2014 Admin")
        self.geometry(f"{self.default_width}x{self.default_height}")
        self.minsize(900, 500)
        self.configure(fg_color="#0E0E13")

        self._settings = _load_settings()
        self._log_lines: list = []

        self.tank_db: dict = {}
        self.prompts: dict = {}
        self._queue: list = []
        self._last_scan: float = 0
        self._wot_path: str = self._settings.get("wot_path", "")
        self._scanning = False
        self._generating = False
        self._running = True
        self._last_heartbeat: float = 0
        self._last_errors_poll: float = 0
        self._errors_count = 0

        self.tray = AdminTray(on_open=self._tray_open, on_exit=self._tray_exit)

        self._build_layout()
        self._register_panels()
        self._setup_close()
        self.after(500, self._load_data)
        self.after(500, self._start_background)
        self.after(1000, self._start_tray)

    def _build_layout(self) -> None:
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self._topbar = customtkinter.CTkFrame(self, height=44, fg_color="#14161F")
        self._topbar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self._topbar.grid_propagate(False)
        customtkinter.CTkLabel(
            self._topbar, text="SM WoT Assistant",
            font=customtkinter.CTkFont(size=16, weight="bold"),
            text_color="#D4A843",
        ).pack(side="left", padx=(12, 4), pady=8)
        customtkinter.CTkLabel(
            self._topbar, text="Admin",
            font=customtkinter.CTkFont(size=14),
            text_color="#6E7284",
        ).pack(side="left", padx=(0, 12), pady=8)

        self._status_pill = customtkinter.CTkLabel(
            self._topbar, text="\u25cf Idle",
            font=customtkinter.CTkFont(size=11),
            text_color="#66cc66",
        )
        self._status_pill.pack(side="right", padx=12)

        self._lang_btn = customtkinter.CTkButton(
            self._topbar, text="EN", width=36, height=28,
            fg_color="transparent", hover_color="#1A1D28",
            text_color="#6E7284", border_width=1, border_color="#2E3240",
            command=self._toggle_lang,
        )
        self._lang_btn.pack(side="right", padx=4)

        self._settings_btn = customtkinter.CTkButton(
            self._topbar, text="\u2699", width=36, height=28,
            fg_color="transparent", hover_color="#1A1D28",
            text_color="#6E7284", font=customtkinter.CTkFont(size=18),
            command=self._open_settings,
        )
        self._settings_btn.pack(side="right", padx=4)

        self._center = customtkinter.CTkFrame(self, fg_color="#0E0E13")
        self._center.grid(row=1, column=0, sticky="nsew")
        self._center.grid_columnconfigure(0, weight=1)
        self._center.grid_rowconfigure(0, weight=1)

        self._statusbar = customtkinter.CTkFrame(self, height=26, fg_color="#14161F")
        self._statusbar.grid(row=2, column=0, sticky="ew")
        self._statusbar.grid_propagate(False)
        self._status_lbl = customtkinter.CTkLabel(
            self._statusbar, text="Ready",
            font=customtkinter.CTkFont(size=11),
            text_color="#6E7284",
        )
        self._status_lbl.pack(side="left", padx=12)

        self.panel_dock = PanelDock(self._center)

    def _register_panels(self) -> None:
        self.panel_dock.add_panel(
            "status", "Status", "status",
            build=status_controller(self)["build"],
            refresh=status_controller(self)["refresh"],
            width=320,
        )
        self.panel_dock.add_panel(
            "builds", "Builds", "builds",
            build=builds_controller(self)["build"],
            refresh=builds_controller(self)["refresh"],
            width=400,
        )
        self.panel_dock.add_panel(
            "community", "Community", "community",
            build=community_controller(self)["build"],
            refresh=community_controller(self)["refresh"],
            width=300,
        )
        self.panel_dock.add_panel(
            "errors", "Errors", "errors",
            build=errors_controller(self)["build"],
            refresh=errors_controller(self)["refresh"],
            width=350,
        )
        self.panel_dock.add_panel(
            "log", "Log", "log",
            build=log_controller(self)["build"],
            refresh=log_controller(self)["refresh"],
            width=350,
        )
        self.panel_dock.restore()

    def _start_tray(self) -> None:
        self.tray.start(root=self)

    def _start_background(self) -> None:
        def _loop():
            while self._running:
                try:
                    now = time.time()
                    if now - self._last_heartbeat > 86400:
                        self._last_heartbeat = now
                        self._report_heartbeat()
                    if now - self._last_errors_poll > 86400:
                        self._last_errors_poll = now
                        try:
                            from admin_backend.data import get_errors_count
                            self._errors_count = get_errors_count()
                            self.after(0, self.panel_dock.refresh)
                        except Exception:
                            pass
                except Exception as e:
                    self.after(0, lambda e=e: self.log(f"BG error: {e}"))
                time.sleep(10)
        threading.Thread(target=_loop, daemon=True).start()

    def _report_heartbeat(self) -> None:
        try:
            import firebase_reporter as fr
            fr._put_json(  # type: ignore[attr-defined]
                fr._rtdb_url("admin_app/version"),  # type: ignore[attr-defined]
                {"version": "1.0.46", "last_seen": int(time.time()), "status": "idle"})
        except Exception:
            pass

    def _tray_open(self) -> None:
        self.after(0, self._restore_from_tray)

    def _restore_from_tray(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_exit(self) -> None:
        self.after(0, self._on_close)

    def _load_data(self) -> None:
        try:
            from admin_backend.data import load_tank_db, load_prompts_merged
            self.tank_db = load_tank_db()
            self.prompts = load_prompts_merged()
            self.log(f"Loaded {len(self.tank_db)} tanks, {len(self.prompts)} prompts")
            self.panel_dock.refresh()
        except Exception as e:
            self.log(f"Data load error: {e}")

    def _scan_now(self) -> None:
        if self._scanning:
            self.log("Scan already running")
            return
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self) -> None:
        self._scanning = True
        self.log("Scanning for changes...")
        try:
            from admin_backend.data import get_queue
            changed = get_queue(self.tank_db, self.prompts, self._wot_path)
            self._last_scan = time.time()
            self._queue = changed
            if changed:
                self.log(f"Found {len(changed)} changed tanks")
                for t in changed[:10]:
                    self.log(f"  {t}")
            else:
                self.log("No changes detected")
            self.after(0, self.panel_dock.refresh)
        except Exception as e:
            self.log(f"Scan error: {e}")
        finally:
            self._scanning = False

    def _gen_queue(self) -> None:
        if not self._queue:
            self.log("Queue is empty \u2014 run Scan first")
            return
        self.log(f"Generation queued for {len(self._queue)} tanks")

    def _gen_all(self) -> None:
        self.log(f"Regen all: {len(self.tank_db)} tanks")

    def _toggle_lang(self) -> None:
        current = self._settings.get("language", "en")
        new_lang = "uk" if current == "en" else "en"
        self._settings["language"] = new_lang
        _save_settings(self._settings)
        self._lang_btn.configure(text=new_lang.upper())

    def _open_settings(self) -> None:
        dlg = customtkinter.CTkToplevel(self)
        dlg.title("Settings")
        dlg.geometry("440x340")
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color="#1A1D28")

        customtkinter.CTkLabel(
            dlg, text="Settings",
            font=customtkinter.CTkFont(size=16, weight="bold"),
            text_color="#D4A843",
        ).pack(pady=(16, 12))

        customtkinter.CTkLabel(dlg, text="WoT Path:", text_color="#DDE0EA",
                               font=customtkinter.CTkFont(size=12)).pack(anchor="w", padx=20)
        path_entry = customtkinter.CTkEntry(dlg, width=400)
        path_entry.insert(0, self._wot_path)
        path_entry.pack(padx=20, pady=(0, 8))

        autostart_var = customtkinter.BooleanVar(value=self._settings.get("launch_on_game_start", False))
        customtkinter.CTkCheckBox(
            dlg, text="Start with Windows (via tray watcher)",
            variable=autostart_var, text_color="#DDE0EA",
            font=customtkinter.CTkFont(size=12),
        ).pack(anchor="w", padx=20, pady=4)

        customtkinter.CTkLabel(dlg, text=f"Current language: {self._settings.get('language', 'en').upper()}",
                               text_color="#6E7284",
                               font=customtkinter.CTkFont(size=11)).pack(anchor="w", padx=20, pady=4)

        def _save():
            self._wot_path = path_entry.get().strip()
            self._settings["wot_path"] = self._wot_path
            self._settings["launch_on_game_start"] = autostart_var.get()
            _save_settings(self._settings)
            self._apply_autostart(autostart_var.get())
            self.log(f"Settings saved: wot_path={self._wot_path}")
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        btn_frame = customtkinter.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(16, 12))
        customtkinter.CTkButton(
            btn_frame, text="Save", width=100,
            fg_color="#D4A843", hover_color="#B8922E", text_color="#12141C",
            command=_save,
        ).pack(side="right", padx=4)
        customtkinter.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="transparent", hover_color="#2E3240", text_color="#6E7284",
            border_width=1, border_color="#2E3240",
            command=_cancel,
        ).pack(side="right", padx=4)

    def _apply_autostart(self, enabled: bool) -> None:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            if enabled:
                import sys as _sys
                if getattr(_sys, 'frozen', False):
                    exe = _sys.executable
                else:
                    exe = f'"{_sys.executable}"'
                winreg.SetValueEx(key, "SM_WoT_Assistant_Admin", 0, winreg.REG_SZ, str(exe))
            else:
                try:
                    winreg.DeleteValue(key, "SM_WoT_Assistant_Admin")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            self.log(f"Autostart registry error: {e}")

    def notify(self, title: str, message: str) -> None:
        self.tray.show_notification(title, message)

    def log(self, text: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {text}"
        self._log_lines.append(line)
        if len(self._log_lines) > 1000:
            self._log_lines = self._log_lines[-1000:]
        for panel_id, panel in self.panel_dock.panels.items():
            if panel_id == "log" and panel["body"] is not None:
                panel["body"].append(line)

    def set_status(self, text: str, color: str = "#66cc66") -> None:
        self._status_lbl.configure(text=text)
        self._status_pill.configure(text=f"\u25cf {text}", text_color=color)

    def _setup_close(self) -> None:
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        self._running = False
        self.tray.stop()
        self.panel_dock.close_all()
        self.destroy()


def run() -> None:
    app = AdminApp()
    app.mainloop()


if __name__ == "__main__":
    run()
