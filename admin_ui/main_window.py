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
import tkinter as tk
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
    info_controller,
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
        self.minsize(900, 500)
        self.configure(fg_color="#0E0E13")

        self._settings = _load_settings()

        # Restore saved window geometry or use defaults
        gw = self._settings.get("window_w")
        gh = self._settings.get("window_h")
        gx = self._settings.get("window_x")
        gy = self._settings.get("window_y")
        if gw and gh:
            self.geometry(f"{gw}x{gh}")
            if gx is not None and gy is not None:
                self.geometry(f"+{gx}+{gy}")
        else:
            self.geometry(f"{self.default_width}x{self.default_height}")
        self._log_lines: list = []

        self.tank_db: dict = {}
        self.prompts: dict = {}
        self._queue: list = []
        self._wot_path: str = self._settings.get("wot_path", "")
        if not self._wot_path:
            self._wot_path = self._resolve_wot_path("")
            if self._wot_path:
                self._settings["wot_path"] = self._wot_path
                _save_settings(self._settings)
        self._scanning = False
        self._generating = False
        self._auto_generate = False
        self._running = True
        self._last_heartbeat: float = 0
        self._last_errors_poll: float = 0
        self._errors_count = 0
        self._gen_progress: dict = {
            "running": False, "queue": [], "current_tag": None,
            "results": {}, "progress": (0, 0),
        }
        self._bg_reload_data = False

        # Splash state
        self.splash: Optional[tk.Toplevel] = None
        self._splash_shown_at: float = 0.0
        self._startup_target_percent: int = 0
        self._startup_display_percent: int = 0
        self._startup_ready: bool = False

        self.tray = AdminTray(on_open=self._tray_open, on_exit=self._tray_exit)

        self._build_layout()
        self._register_panels()
        self._show_splash()
        self._setup_close()
        self.after(100, self._validate_position)
        self.after(200, self._load_data)
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
        self._center.grid_propagate(False)

        self._scroll = customtkinter.CTkScrollableFrame(
            self._center, fg_color="#0E0E13",
            scrollbar_fg_color="#0E0E13",
            scrollbar_button_color="#2E3240",
            scrollbar_button_hover_color="#3E4250",
        )
        self._scroll.pack(fill="both", expand=True)

        self._statusbar = customtkinter.CTkFrame(self, height=26, fg_color="#14161F")
        self._statusbar.grid(row=2, column=0, sticky="ew")
        self._statusbar.grid_propagate(False)
        self._status_lbl = customtkinter.CTkLabel(
            self._statusbar, text="Ready",
            font=customtkinter.CTkFont(size=11),
            text_color="#6E7284",
        )
        self._status_lbl.pack(side="left", padx=12)

        self.panel_dock = PanelDock(self._scroll)

    def _show_splash(self) -> None:
        """Show a separate Toplevel splash window with logo + progress bar."""
        self.withdraw()

        sw, sh = 400, 300
        sx = self.winfo_screenwidth()
        sy = self.winfo_screenheight()
        x = (sx - sw) // 2
        y = (sy - sh) // 2

        self.splash = tk.Toplevel(self)
        self.splash.overrideredirect(True)
        self.splash.attributes("-topmost", True)
        self.splash.configure(bg="black")
        self.splash.geometry(f"{sw}x{sh}+{x}+{y}")

        self._splash_shown_at = time.time()
        self._startup_target_percent = 0
        self._startup_display_percent = 0
        self._startup_ready = False

        self._splash_canvas = tk.Canvas(
            self.splash, width=sw, height=sh, bg="black", highlightthickness=0)
        self._splash_canvas.pack()

        # Logo
        logo_path = _project_root / "logo.png"
        self._splash_logo_img = None
        if logo_path.exists():
            try:
                from PIL import Image, ImageTk
                img = Image.open(str(logo_path))
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                self._splash_logo_img = ImageTk.PhotoImage(img)
                self._splash_canvas.create_image(sw // 2, sh // 2 - 40, image=self._splash_logo_img)
            except Exception:
                pass

        # Title
        self._splash_canvas.create_text(
            sw // 2, sh // 2 + 10, text="SM WoT Assistant",
            fill="#D4A843", font=("Segoe UI", 16, "bold"))
        self._splash_canvas.create_text(
            sw // 2, sh // 2 + 35, text="Admin",
            fill="#6E7284", font=("Segoe UI", 12))

        # Status text
        self._splash_status_text = self._splash_canvas.create_text(
            sw // 2, sh - 50, text="Loading data...",
            fill="#bbbbbb", font=("Segoe UI", 9))

        # Percent text
        self._splash_percent_text = self._splash_canvas.create_text(
            sw - 34, sh - 20, text="0%",
            fill="#dddddd", font=("Segoe UI", 9))

        # Progress bar
        self._splash_pbar = self._splash_canvas.create_rectangle(
            0, sh - 10, 0, sh, fill="#D4A843", outline="")

        self._splash_canvas.itemconfigure(self._splash_status_text, text="Loading data...")
        self._animate_startup_progress()
        self.splash.deiconify()
        self.splash.lift()
        self.splash.update_idletasks()

    def _update_splash_progress(self, percent: int, text: str = None) -> None:
        """Update splash progress bar and status text."""
        if not self.splash or not self.splash.winfo_exists():
            return
        try:
            percent = max(0, min(100, int(percent)))
            self._startup_target_percent = percent
            self._startup_display_percent = percent
            if text:
                self._splash_canvas.itemconfigure(self._splash_status_text, text=text)
            self._splash_canvas.itemconfigure(
                self._splash_percent_text, text=f"{percent}%")
            sw = int(self._splash_canvas["width"])
            sh = int(self._splash_canvas["height"])
            x2 = int((sw * percent) / 100)
            self._splash_canvas.coords(self._splash_pbar, 0, sh - 8, x2, sh)
            self.splash.update_idletasks()
        except Exception:
            pass

    def _animate_startup_progress(self) -> None:
        """Smoothly animate progress bar toward target."""
        if not self.splash or not self.splash.winfo_exists():
            return
        try:
            sw = int(self._splash_canvas["width"])
            sh = int(self._splash_canvas["height"])
            target = int(self._startup_target_percent)
            current = int(self._startup_display_percent)
            if current < target:
                step = 2 if (target - current) > 8 else 1
                current = min(target, current + step)
                self._startup_display_percent = current
                x2 = int((sw * current) / 100)
                self._splash_canvas.coords(self._splash_pbar, 0, sh - 8, x2, sh)
                self._splash_canvas.itemconfigure(
                    self._splash_percent_text, text=f"{current}%")
            self.after(45, self._animate_startup_progress)
        except Exception:
            pass

    def _finish_startup_splash(self) -> None:
        """Destroy splash and show main window."""
        if not self._startup_ready:
            return
        shown_at = self._splash_shown_at
        elapsed_ms = int((time.time() - shown_at) * 1000) if shown_at else 9999
        min_visible_ms = 2000
        if elapsed_ms < min_visible_ms:
            self.after(min_visible_ms - elapsed_ms, self._finish_startup_splash)
            return
        try:
            if self.splash and self.splash.winfo_exists():
                self.splash.destroy()
        except Exception:
            pass
        finally:
            self.splash = None

        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _register_panels(self) -> None:
        self.panel_dock.add_panel(
            "status", "Status", "status",
            build=status_controller(self)["build"],
            refresh=status_controller(self)["refresh"],
            width=320,
        )
        self.panel_dock.add_panel(
            "info", "Info", "info",
            build=info_controller(self)["build"],
            refresh=info_controller(self)["refresh"],
            width=320,
        )
        self.panel_dock.add_panel(
            "builds", "Builds", "builds",
            build=builds_controller(self)["build"],
            refresh=builds_controller(self)["refresh"],
            width=400, collapsed=True,
        )
        self.panel_dock.add_panel(
            "community", "Community", "community",
            build=community_controller(self)["build"],
            refresh=community_controller(self)["refresh"],
            width=350,
        )
        self.panel_dock.add_panel(
            "errors", "Errors", "errors",
            build=errors_controller(self)["build"],
            refresh=errors_controller(self)["refresh"],
            width=350, collapsed=True,
        )
        self.panel_dock.add_panel(
            "log", "Log", "log",
            build=log_controller(self)["build"],
            refresh=log_controller(self)["refresh"],
            width=350, collapsed=True,
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
                        self._bg_reload_data = True
                except Exception:
                    pass
                time.sleep(10)

        def _bg_poll():
            if not self._running:
                return
            if getattr(self, "_bg_reload_data", False):
                self._bg_reload_data = False
                self._do_reload_data()
            self.after(1000, _bg_poll)

        threading.Thread(target=_loop, daemon=True).start()
        self.after(1000, _bg_poll)

    def _report_heartbeat(self) -> None:
        try:
            from admin_backend.data import read_admin_version
            ver = read_admin_version()
            import firebase_reporter as fr
            fr._put_json(  # type: ignore[attr-defined]
                fr._rtdb_url("admin_app/version"),  # type: ignore[attr-defined]
                {"version": ver, "last_seen": int(time.time()), "status": "idle"})
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

    def _resolve_wot_path(self, cli_wot_path: str) -> str:
        """Resolve WoT path: admin settings -> main app settings -> common paths."""
        import os
        candidates = []
        if cli_wot_path:
            candidates.append(cli_wot_path)
        if self._settings.get("wot_path"):
            candidates.append(self._settings["wot_path"])
        try:
            main_settings_path = os.path.join(
                os.environ.get("APPDATA", "."), "SM WoT Assistant", "settings.json")
            with open(main_settings_path, "r", encoding="utf-8") as f:
                main_settings = json.load(f)
                if main_settings.get("wot_path"):
                    candidates.append(main_settings["wot_path"])
        except Exception:
            pass
        candidates.extend([
            "C:/Games/World_of_Tanks_EU", "D:/Games/World_of_Tanks_EU",
            "E:/Games/World_of_Tanks_EU", "C:/Games/World_of_Tanks",
            "D:/Games/World_of_Tanks", "E:/Games/World_of_Tanks",
        ])
        for p in candidates:
            p = (p or "").strip()
            if p and os.path.exists(os.path.join(p, "version.xml")):
                return p
        return ""

    def _load_data(self) -> None:
        """Initial data load with splash progress updates."""
        self._update_splash_progress(10, "Loading tank database...")
        try:
            from admin_backend.data import load_tank_db, load_prompts_merged
            self.tank_db = load_tank_db()
            self._update_splash_progress(40, "Loading prompts...")
            self.prompts = load_prompts_merged()
            self._update_splash_progress(70, "Loading builds info...")
            self.log(f"Loaded {len(self.tank_db)} tanks, {len(self.prompts)} prompts")
        except Exception as e:
            self.log(f"Data load error: {e}")
        self._update_splash_progress(90, "Finalizing...")
        self._startup_ready = True
        self.after(200, self._finish_startup_splash)
        self.panel_dock.refresh()

    def _do_reload_data(self) -> None:
        """Background data reload (no splash)."""
        try:
            from admin_backend.data import load_tank_db, load_prompts_merged
            self.tank_db = load_tank_db()
            self.prompts = load_prompts_merged()
            self.log(f"Reloaded {len(self.tank_db)} tanks, {len(self.prompts)} prompts")
            self.after(0, self.panel_dock.refresh)
        except Exception as e:
            self.log(f"Data reload error: {e}")

    def _scan_now(self) -> None:
        if self._generating or self._scanning:
            self.log("Operation already running")
            return
        def _scan():
            self._generating = True
            self.after(0, lambda: self.set_status("Scanning...", "#ffaa00"))
            try:
                from admin_build_generator import detect_changed_tanks, _manifest_default_path
                changed = detect_changed_tanks(self._wot_path, _manifest_default_path())
                self._queue = changed
                if changed:
                    self.log(f"Found {len(changed)} tanks needing builds")
                else:
                    self.log("No tanks need builds")
                self.after(0, self.panel_dock.refresh)
            except Exception as e:
                self.log(f"Scan error: {e}")
            finally:
                self._generating = False
                self.after(0, lambda: self.set_status("Idle", "#66cc66"))
        threading.Thread(target=_scan, daemon=True).start()

    def _generate_now(self) -> None:
        if self._generating:
            self.log("Generation already running")
            return
        queue = list(self._queue)
        if not queue:
            self.log("Queue empty \u2014 run Scan first or wait for auto-detect")
            return
        def _gen_queue():
            self._generating = True
            self._gen_progress.update({
                "running": True, "queue": list(queue),
                "current_tag": None, "results": {}, "progress": (0, len(queue)),
            })
            self.after(0, lambda: self.set_status("Generating...", "#ffaa00"))
            driver = None
            try:
                from admin_build_generator import generate_builds, load_tank_db, load_prompts, _create_driver
                self.log(f"Generating {len(queue)} builds from queue...")
                driver = _create_driver()
                tank_db = load_tank_db()
                prompts = load_prompts()

                def _progress_cb(tag, status, current, total):
                    self._gen_progress["progress"] = (current, total)
                    if status == "generating":
                        self._gen_progress["current_tag"] = tag
                    elif status in ("ok", "fail"):
                        self._gen_progress["results"][tag] = status
                        if tag in self._gen_progress["queue"]:
                            self._gen_progress["queue"].remove(tag)

                ok, done_tags, reasons = generate_builds(
                    driver, tank_db, prompts,
                    queue=queue, wot_path=self._wot_path,
                    progress_callback=_progress_cb,
                )
                if ok:
                    count = len(done_tags)
                    self.log(f"Generation complete: {count} tanks built")
                    self._queue = [t for t in self._queue if t not in done_tags]
                else:
                    summary = reasons.get("summary", "unknown") if reasons else "failed"
                    self.log(f"Generation failed: {summary}")
                self.after(0, self.panel_dock.refresh)
            except Exception as e:
                self.log(f"Generate error: {e}")
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                self._generating = False
                self._gen_progress["running"] = False
                self._gen_progress["current_tag"] = None
                self.after(0, lambda: self.set_status("Idle", "#66cc66"))
        threading.Thread(target=_gen_queue, daemon=True).start()

    def _auto_generate_toggle(self) -> None:
        self._auto_generate = not getattr(self, "_auto_generate", False)
        self.log(f"Auto-generate: {'ON' if self._auto_generate else 'OFF'}")

    def _extract_now(self) -> None:
        if not self._wot_path:
            self.log("ERROR: WoT path not set \u2014 open Settings")
            return
        if self._scanning:
            self.log("Pipeline already running")
            return
        self.log("Starting extraction pipeline...")
        threading.Thread(target=self._do_extract, daemon=True).start()

    def _do_extract(self) -> None:
        self._scanning = True
        self.after(0, lambda: self.set_status("Extracting...", "#ffaa00"))
        try:
            from admin_build_generator import _extract_full_pipeline, _publish_tank_data
            import config as _cfg
            _extract_full_pipeline(self._wot_path)
            self.log("Extraction done \u2014 publishing to Firebase...")
            _publish_tank_data(_cfg.BASE_DIR, _cfg.USER_DATA_DIR)
            self.log("Pipeline complete \u2014 Firebase updated")
            self._bg_reload_data = True
        except Exception as e:
            self.log(f"Pipeline error: {e}")
        finally:
            self._scanning = False
            self.after(0, lambda: self.set_status("Idle", "#66cc66"))

    def _regen_all_db(self) -> None:
        if not self._wot_path:
            self.log("ERROR: WoT path not set \u2014 open Settings")
            return
        if self._scanning:
            self.log("Pipeline already running")
            return
        self.log("Regenerating ALL database...")
        threading.Thread(target=self._do_regen_all, daemon=True).start()

    def _do_regen_all(self) -> None:
        self._scanning = True
        self.after(0, lambda: self.set_status("Regenerating DB...", "#ffaa00"))
        try:
            from admin_build_generator import _extract_full_pipeline
            _extract_full_pipeline(self._wot_path)
            self.log("Full DB regeneration complete")
            self._bg_reload_data = True
        except Exception as e:
            self.log(f"Regen error: {e}")
        finally:
            self._scanning = False
            self.after(0, lambda: self.set_status("Idle", "#66cc66"))

    def _regen_all_builds(self) -> None:
        if self._generating:
            self.log("Generation already running")
            return
        def _force_gen():
            self._generating = True
            self.after(0, lambda: self.set_status("Force generating all...", "#ffaa00"))
            driver = None
            try:
                from admin_build_generator import generate_builds, load_tank_db, load_prompts, _create_driver
                driver = _create_driver()
                tank_db = load_tank_db()
                prompts = load_prompts()
                ok, done_tags, reasons = generate_builds(
                    driver, tank_db, prompts, force=True, wot_path=self._wot_path,
                )
                if ok:
                    self.log(f"Force generation complete: {len(done_tags)} tanks built")
                else:
                    summary = reasons.get("summary", "unknown") if reasons else "failed"
                    self.log(f"Force generation failed: {summary}")
                self.after(0, self.panel_dock.refresh)
            except Exception as e:
                self.log(f"Force gen error: {e}")
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                self._generating = False
                self.after(0, lambda: self.set_status("Idle", "#66cc66"))
        threading.Thread(target=_force_gen, daemon=True).start()

    def _toggle_lang(self) -> None:
        current = self._settings.get("language", "en")
        new_lang = "uk" if current == "en" else "en"
        self._settings["language"] = new_lang
        _save_settings(self._settings)
        self._lang_btn.configure(text=new_lang.upper())

    def _open_settings(self) -> None:
        dlg = customtkinter.CTkToplevel(self)
        dlg.title("Settings")
        dlg.geometry("440x460")
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

        sep = customtkinter.CTkFrame(dlg, height=1, fg_color="#2E3240")
        sep.pack(fill="x", padx=20, pady=8)

        customtkinter.CTkLabel(dlg, text="Dangerous Operations",
                               font=customtkinter.CTkFont(size=12, weight="bold"),
                               text_color="#cc6666").pack(anchor="w", padx=20, pady=(0, 4))

        def _confirm_extract():
            win = customtkinter.CTkToplevel(dlg)
            win.title("Confirm Extract")
            win.geometry("380x160")
            win.transient(dlg)
            win.grab_set()
            win.configure(fg_color="#1A1D28")
            customtkinter.CTkLabel(
                win, text="Run full extraction pipeline?\nThis reads from the game client and uploads to Firebase.",
                text_color="#DDE0EA", font=customtkinter.CTkFont(size=12),
                wraplength=340,
            ).pack(pady=(16, 12))
            bf = customtkinter.CTkFrame(win, fg_color="transparent")
            bf.pack(fill="x", padx=20, pady=(0, 12))
            def _do():
                win.destroy()
                dlg.destroy()
                self._extract_now()
            customtkinter.CTkButton(bf, text="Extract", width=80, fg_color="#cc6666",
                                    hover_color="#993333", text_color="white", command=_do).pack(side="right", padx=4)
            customtkinter.CTkButton(bf, text="Cancel", width=80, fg_color="transparent",
                                    text_color="#6E7284", border_width=1, border_color="#2E3240",
                                    command=win.destroy).pack(side="right", padx=4)

        customtkinter.CTkButton(
            dlg, text="Extract Pipeline", width=200, fg_color="#cc6666",
            hover_color="#993333", text_color="white",
            command=_confirm_extract,
        ).pack(padx=20, pady=2)

        def _confirm_regen():
            win = customtkinter.CTkToplevel(dlg)
            win.title("Confirm Regen All")
            win.geometry("380x160")
            win.transient(dlg)
            win.grab_set()
            win.configure(fg_color="#1A1D28")
            customtkinter.CTkLabel(
                win, text="Regenerate ENTIRE database?\nThis takes a very long time!",
                text_color="#DDE0EA", font=customtkinter.CTkFont(size=12),
                wraplength=340,
            ).pack(pady=(16, 12))
            bf = customtkinter.CTkFrame(win, fg_color="transparent")
            bf.pack(fill="x", padx=20, pady=(0, 12))
            def _do():
                win.destroy()
                dlg.destroy()
                self._regen_all_db()
            customtkinter.CTkButton(bf, text="Regen All", width=80, fg_color="#cc6666",
                                    hover_color="#993333", text_color="white", command=_do).pack(side="right", padx=4)
            customtkinter.CTkButton(bf, text="Cancel", width=80, fg_color="transparent",
                                    text_color="#6E7284", border_width=1, border_color="#2E3240",
                                    command=win.destroy).pack(side="right", padx=4)

        customtkinter.CTkButton(
            dlg, text="Regen All DB", width=200, fg_color="#cc6666",
            hover_color="#993333", text_color="white",
            command=_confirm_regen,
        ).pack(padx=20, pady=2)

        def _confirm_regen_builds():
            win = customtkinter.CTkToplevel(dlg)
            win.title("Confirm Regen All Builds")
            win.geometry("400x160")
            win.transient(dlg)
            win.grab_set()
            win.configure(fg_color="#1A1D28")
            customtkinter.CTkLabel(
                win, text="Regenerate ALL tank builds?\nThis re-runs AI for every tank \u2014 very slow!",
                text_color="#DDE0EA", font=customtkinter.CTkFont(size=12),
                wraplength=360,
            ).pack(pady=(16, 12))
            bf = customtkinter.CTkFrame(win, fg_color="transparent")
            bf.pack(fill="x", padx=20, pady=(0, 12))
            def _do():
                win.destroy()
                dlg.destroy()
                self._regen_all_builds()
            customtkinter.CTkButton(bf, text="Regen Builds", width=100, fg_color="#cc6666",
                                    hover_color="#993333", text_color="white", command=_do).pack(side="right", padx=4)
            customtkinter.CTkButton(bf, text="Cancel", width=80, fg_color="transparent",
                                    text_color="#6E7284", border_width=1, border_color="#2E3240",
                                    command=win.destroy).pack(side="right", padx=4)

        customtkinter.CTkButton(
            dlg, text="Regen All Builds", width=200, fg_color="#cc6666",
            hover_color="#993333", text_color="white",
            command=_confirm_regen_builds,
        ).pack(padx=20, pady=2)

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

    def _validate_position(self) -> None:
        """Reset to center if saved position is off-screen."""
        try:
            self.update_idletasks()
            geo = self.geometry() or ""  # WxH+X+Y
            parts = geo.replace("x", "+").split("+")
            x, y, w, h = int(parts[2]), int(parts[3]), int(parts[0]), int(parts[1])
            sx, sy = self.winfo_screenwidth(), self.winfo_screenheight()
            if x > sx or y > sy or x + w < 0 or y + h < 0:
                self.geometry("")  # center on screen
        except Exception:
            pass

    def _on_close(self) -> None:
        self._running = False
        # Save window geometry
        try:
            geo = self.geometry() or ""  # WxH+X+Y
            parts = geo.replace("x", "+").split("+")
            self._settings["window_w"] = int(parts[0])
            self._settings["window_h"] = int(parts[1])
            self._settings["window_x"] = int(parts[2])
            self._settings["window_y"] = int(parts[3])
            _save_settings(self._settings)
        except Exception:
            pass
        self.tray.stop()
        self.panel_dock.close_all()
        self.destroy()


def run() -> None:
    app = AdminApp()
    app.mainloop()


if __name__ == "__main__":
    run()
