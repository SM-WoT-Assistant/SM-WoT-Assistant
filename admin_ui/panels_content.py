"""Admin panel content controllers with real data.

Each panel is a CTkFrame subclass with refresh() and data-loading logic.
PanelDock uses build(parent) -> content and refresh(content) callbacks.
"""

import customtkinter
import threading
import time
from typing import Any, Optional, List


class StatusPanel(customtkinter.CTkFrame):
    """Status cards: admin version, game version, tanks, queue, errors."""

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._cards: dict = {}
        self._build()

    def _build(self) -> None:
        from admin_ui.widgets import card
        labels = [
            ("version", "Admin Version", "-"),
            ("wg_version", "Game Version", "-"),
            ("game_status", "Game Status", "No WoT"),
            ("tanks_raw", "Tanks (raw)", "0"),
            ("tanks_db", "Tanks (db)", "0"),
            ("queue", "Queue", "0"),
            ("last_scan", "Last Scan", "-"),
            ("mismatch", "Tanks / Prompts", "-"),
            ("errors", "Errors", "0"),
        ]
        for key, title, value in labels:
            c = card(self, title=title, value=value, width=280, height=60)
            c.pack(fill="x", padx=6, pady=3)
            self._cards[key] = c

    def refresh(self) -> None:
        if self.app is None:
            return
        try:
            from admin_backend.data import read_admin_version
            version = read_admin_version()
            self._cards["version"]._val_lbl.configure(text=version)
        except Exception as e:
            self._cards["version"]._val_lbl.configure(text=f"err: {e}")

        try:
            from admin_backend.data import check_wot_path
            wot_path = getattr(self.app, '_wot_path', '')
            exists, ver = check_wot_path(wot_path)
            self._cards["wg_version"]._val_lbl.configure(text=ver or "-")
            color = "#66cc66" if exists else "#cc6666"
            self._cards["game_status"]._val_lbl.configure(
                text="Connected" if exists else "No WoT", text_color=color)
        except Exception:
            pass

        try:
            from admin_backend.data import count_raw_tanks
            raw = count_raw_tanks()
            self._cards["tanks_raw"]._val_lbl.configure(text=str(raw))
        except Exception:
            pass

        try:
            from admin_backend.data import check_mismatch
            tank_db = getattr(self.app, 'tank_db', {})
            prompts = getattr(self.app, 'prompts', {})
            self._cards["tanks_db"]._val_lbl.configure(text=str(len(tank_db)))
            q = getattr(self.app, '_queue', [])
            self._cards["queue"]._val_lbl.configure(text=str(len(q)))
            self._cards["last_scan"]._val_lbl.configure(
                text=time.strftime("%H:%M") if getattr(self.app, '_last_scan', 0) > 0 else "-")
            prompts_only, tanks_only = check_mismatch(tank_db, prompts)
            mismatch = bool(prompts_only or tanks_only)
            color = "#cc6666" if mismatch else "#66cc66"
            self._cards["mismatch"]._val_lbl.configure(
                text=f"{len(tank_db)} / {len(prompts)}", text_color=color)
        except Exception:
            pass

        try:
            from admin_backend.data import get_errors_count
            errs = get_errors_count()
            color = "#cc6666" if errs > 0 else "#888888"
            self._cards["errors"]._val_lbl.configure(text=str(errs), text_color=color)
        except Exception:
            pass


class BuildsPanel(customtkinter.CTkFrame):
    """Build controls: Scan, Generate, Regen All + tank treeview."""

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._tree = None
        self._build()

    def _build(self) -> None:
        from admin_ui.widgets import primary_button, ghost_button
        btn_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=6, pady=6)
        primary_button(btn_frame, "Scan", width=80, command=self._on_scan).pack(side="left", padx=2)
        primary_button(btn_frame, "Generate Queue", width=110, command=self._on_gen_queue).pack(side="left", padx=2)
        ghost_button(btn_frame, "Regen All", width=80, command=self._on_regen_all).pack(side="left", padx=2)

        self._search = customtkinter.CTkEntry(self, placeholder_text="Search tanks...")
        self._search.pack(fill="x", padx=6, pady=(0, 4))
        self._search.bind("<KeyRelease>", self._on_search)

        self._tree_frame = customtkinter.CTkFrame(self, fg_color="#12141C")
        self._tree_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    def _on_scan(self) -> None:
        if self.app and hasattr(self.app, '_scan_now'):
            self.app._scan_now()

    def _on_gen_queue(self) -> None:
        if self.app and hasattr(self.app, '_gen_queue'):
            self.app._gen_queue()

    def _on_regen_all(self) -> None:
        if self.app and hasattr(self.app, '_gen_all'):
            self.app._gen_all()

    def _on_search(self, event=None) -> None:
        query = self._search.get().strip().lower()
        if not self._tree:
            return
        for item in self._tree.get_children():
            self._tree.delete(item)
        tank_db = getattr(self.app, 'tank_db', {})
        queue = getattr(self.app, '_queue', [])
        queue_set = set(queue)
        for tag in sorted(tank_db.keys()):
            if query and query not in tag.lower():
                continue
            name = tank_db[tag].get("name", tag)
            status = "queued" if tag in queue_set else "ready"
            self._tree.insert("", "end", values=(tag, name, status))

    def refresh(self) -> None:
        if self._tree is None:
            try:
                from tkinter import ttk
                style = ttk.Style()
                style.theme_use("clam")
                style.configure("Admin.Treeview",
                                background="#12141C", foreground="#DDE0EA",
                                fieldbackground="#12141C", borderwidth=0,
                                font=("Segoe UI", 10))
                style.configure("Admin.Treeview.Heading",
                                background="#181B26", foreground="#D4A843",
                                borderwidth=0, font=("Segoe UI", 10, "bold"))
                self._tree = ttk.Treeview(
                    self._tree_frame,
                    columns=("tag", "name", "status"),
                    show="headings",
                    style="Admin.Treeview",
                    height=20,
                )
                self._tree.heading("tag", text="Tag")
                self._tree.heading("name", text="Name")
                self._tree.heading("status", text="Status")
                self._tree.column("tag", width=150)
                self._tree.column("name", width=200)
                self._tree.column("status", width=80)
                scroll = customtkinter.CTkScrollbar(
                    self._tree_frame, command=self._tree.yview)
                self._tree.configure(yscrollcommand=scroll.set)
                self._tree.pack(side="left", fill="both", expand=True)
                scroll.pack(side="right", fill="y")
            except Exception:
                return
        self._on_search()


class CommunityPanel(customtkinter.CTkFrame):
    """Community monitoring: platform tiles."""

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._tiles: dict = {}
        self._build()

    def _build(self) -> None:
        platforms = [
            ("overview", "Builds Ver"),
            ("youtube", "YouTube"),
            ("reddit", "Reddit"),
            ("github", "GitHub"),
            ("kofi", "Ko-fi"),
            ("patreon", "Patreon"),
            ("installs", "Installs"),
            ("errors", "Errors"),
        ]
        strip = customtkinter.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", padx=6, pady=6)
        for key, label in platforms:
            tile = customtkinter.CTkFrame(strip, height=50, fg_color="#14161F", corner_radius=6)
            tile.pack(side="left", fill="both", expand=True, padx=2)
            customtkinter.CTkLabel(
                tile, text=label, font=customtkinter.CTkFont(size=9),
                text_color="#6E7284").pack(pady=(6, 0))
            val_lbl = customtkinter.CTkLabel(
                tile, text="-", font=customtkinter.CTkFont(size=13, weight="bold"),
                text_color="#DDE0EA")
            val_lbl.pack()
            hint_lbl = customtkinter.CTkLabel(
                tile, text="", font=customtkinter.CTkFont(size=8),
                text_color="#6E7284")
            hint_lbl.pack()
            self._tiles[key] = {"val": val_lbl, "hint": hint_lbl}

    def refresh(self) -> None:
        try:
            from admin_backend.data import get_community_stats
            stats = get_community_stats()
            for key, tile in self._tiles.items():
                if key == "overview":
                    v = stats.get("builds_ver")
                    tile["val"].configure(text=str(v) if v is not None else "-")
                elif key == "github":
                    gh = stats.get("github")
                    if gh:
                        tile["val"].configure(text=str(gh.get("total", 0)))
                    else:
                        tile["val"].configure(text="-")
                elif key == "installs":
                    tile["val"].configure(text=str(stats.get("installs", 0)))
                elif key == "errors":
                    tile["val"].configure(text=str(stats.get("errors", 0)))
                elif key == "patreon":
                    pr = stats.get("patreon")
                    if pr:
                        tile["val"].configure(text=str(pr.get("patrons", 0)))
                    else:
                        tile["val"].configure(text="-")
                elif key in ("youtube", "reddit", "kofi"):
                    tile["val"].configure(text="Chrome")
                    tile["hint"].configure(text="Manual login")
        except Exception:
            pass


class ErrorsPanel(customtkinter.CTkFrame):
    """Error reports from RTDB."""

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._tree = None
        self._build()

    def _build(self) -> None:
        self._tree_frame = customtkinter.CTkFrame(self, fg_color="#12141C")
        self._tree_frame.pack(fill="both", expand=True, padx=6, pady=6)

    def refresh(self) -> None:
        if self._tree is None:
            try:
                from tkinter import ttk
                style = ttk.Style()
                style.theme_use("clam")
                style.configure("Err.Treeview",
                                background="#12141C", foreground="#DDE0EA",
                                fieldbackground="#12141C", borderwidth=0,
                                font=("Segoe UI", 10))
                self._tree = ttk.Treeview(
                    self._tree_frame,
                    columns=("time", "type", "stage", "text"),
                    show="headings",
                    style="Err.Treeview",
                    height=20,
                )
                self._tree.heading("time", text="Time")
                self._tree.heading("type", text="Type")
                self._tree.heading("stage", text="Stage")
                self._tree.heading("text", text="Text")
                self._tree.column("time", width=120)
                self._tree.column("type", width=80)
                self._tree.column("stage", width=100)
                self._tree.column("text", width=300)
                scroll = customtkinter.CTkScrollbar(
                    self._tree_frame, command=self._tree.yview)
                self._tree.configure(yscrollcommand=scroll.set)
                self._tree.pack(side="left", fill="both", expand=True)
                scroll.pack(side="right", fill="y")
            except Exception:
                return
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            import firebase_reporter as fr
            url = fr._rtdb_url("error_reports.json?orderBy=%22timestamp%22&limitToLast=50")  # type: ignore[attr-defined]
            import requests
            resp = requests.get(url, timeout=10)
            if resp.ok:
                data = resp.json()
                if data:
                    for key, val in sorted(data.items(), key=lambda x: x[1].get("timestamp", 0), reverse=True)[:50]:
                        ts = val.get("timestamp", "")
                        if isinstance(ts, (int, float)):
                            ts = time.strftime("%m-%d %H:%M", time.localtime(ts))
                        self._tree.insert("", "end", values=(
                            ts, val.get("error_type", "-"), val.get("stage", "-"),
                            str(val.get("error_text", "-"))[:100]))
        except Exception:
            pass


class LogPanel(customtkinter.CTkFrame):
    """Log viewer: newest first, 1000 line cap."""

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self) -> None:
        self._textbox = customtkinter.CTkTextbox(
            self, font=customtkinter.CTkFont(family="Consolas", size=11))
        self._textbox.pack(fill="both", expand=True, padx=6, pady=6)
        self._textbox.insert("1.0", "Admin log output will appear here...\n")

    def append(self, text: str) -> None:
        self._textbox.insert("end", text + "\n")
        self._textbox.see("end")
        lines = float(self._textbox.index("end-1c").split(".")[0])
        if lines > 1000:
            self._textbox.delete("1.0", f"{lines - 1000}.0")

    def refresh(self) -> None:
        pass


# --- controller factory ---


def _controller(title: str, icon_id: str, frame_class, app: Any = None):
    def build(parent):
        return frame_class(parent, app=app)

    def refresh(frame):
        if hasattr(frame, "refresh"):
            frame.refresh()

    return {"title": title, "icon": icon_id, "build": build, "refresh": refresh}


def status_controller(app: Any = None):
    return _controller("Status", "status", StatusPanel, app)


def builds_controller(app: Any = None):
    return _controller("Builds", "builds", BuildsPanel, app)


def community_controller(app: Any = None):
    return _controller("Community", "community", CommunityPanel, app)


def errors_controller(app: Any = None):
    return _controller("Errors", "errors", ErrorsPanel, app)


def log_controller(app: Any = None):
    return _controller("Log", "log", LogPanel, app)
