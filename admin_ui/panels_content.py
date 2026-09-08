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
            ("version", "Admin Version", "-", None),
            ("wg_version", "Game Version", "-", None),
            ("game_status", "Game Status", "No WoT", None),
            ("tanks_raw", "Tanks (raw)", "0", None),
            ("tanks_db", "Tanks (db)", "0", None),
            ("queue", "Queue", "0", None),
            ("last_scan", "Last Scan", "-", None),
            ("mismatch", "Tanks / Prompts", "-", None),
            ("errors", "Errors", "0", None),
        ]
        for key, title, value, drilldown_key in labels:
            c = card(self, title=title, value=value, width=280, height=60,
                     command=lambda dk=drilldown_key: self._open_drilldown(dk) if dk else None)
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

    def _open_drilldown(self, card_key: str) -> None:
        """Open a detail toptop for a specific card."""
        if card_key == "tanks_db":
            self._drilldown_tanks_db()
        elif card_key == "queue":
            self._drilldown_queue()
        elif card_key == "errors":
            self._drilldown_errors()
        elif card_key == "mismatch":
            self._drilldown_mismatch()

    def _drilldown_tanks_db(self) -> None:
        import tkinter as tk
        dlg = customtkinter.CTkToplevel(self)
        dlg.title("Tanks Database")
        dlg.geometry("600x500")
        dlg.transient(self.winfo_toplevel())
        dlg.configure(fg_color="#1A1D28")
        customtkinter.CTkLabel(dlg, text="Tanks Database",
                               font=customtkinter.CTkFont(size=14, weight="bold"),
                               text_color="#D4A843").pack(pady=(12, 4))
        search = customtkinter.CTkEntry(dlg, placeholder_text="Search tanks...")
        search.pack(fill="x", padx=12, pady=(0, 4))
        from tkinter import ttk
        style = ttk.Style()
        style.configure("Drill.Treeview", background="#12141C", foreground="#DDE0EA",
                        fieldbackground="#12141C", font=("Segoe UI", 10))
        tree = ttk.Treeview(dlg, columns=("tag", "name", "tier"), show="headings",
                            style="Drill.Treeview", height=20)
        tree.heading("tag", text="Tag")
        tree.heading("name", text="Name")
        tree.heading("tier", text="Tier")
        tree.column("tag", width=150)
        tree.column("name", width=250)
        tree.column("tier", width=60)
        scroll = customtkinter.CTkScrollbar(dlg, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True, padx=(12, 0))
        scroll.pack(side="right", fill="y", padx=(0, 12))
        def refresh_tree(q=""):
            for item in tree.get_children():
                tree.delete(item)
            tank_db = self.app.tank_db if self.app else {}
            for tag in sorted(tank_db.keys()):
                if q and q not in tag.lower():
                    continue
                name = tank_db[tag].get("name", tag)
                tier = tank_db[tag].get("tier", "?")
                tree.insert("", "end", values=(tag, name, tier))
        refresh_tree()
        search.bind("<KeyRelease>", lambda e: refresh_tree(search.get().strip().lower()))

    def _drilldown_queue(self) -> None:
        dlg = customtkinter.CTkToplevel(self)
        dlg.title("Queue (Changed Tanks)")
        dlg.geometry("500x400")
        dlg.transient(self.winfo_toplevel())
        dlg.configure(fg_color="#1A1D28")
        customtkinter.CTkLabel(dlg, text="Changed Tanks",
                               font=customtkinter.CTkFont(size=14, weight="bold"),
                               text_color="#D4A843").pack(pady=(12, 4))
        from tkinter import ttk
        tree = ttk.Treeview(dlg, columns=("tag", "name"), show="headings", height=18)
        tree.heading("tag", text="Tag")
        tree.heading("name", text="Name")
        tree.column("tag", width=200)
        tree.column("name", width=250)
        tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        queue = self.app._queue if self.app else []
        tank_db = self.app.tank_db if self.app else {}
        for tag in queue:
            name = tank_db.get(tag, {}).get("name", tag)
            tree.insert("", "end", values=(tag, name))

    def _drilldown_errors(self) -> None:
        dlg = customtkinter.CTkToplevel(self)
        dlg.title("Error Reports")
        dlg.geometry("700x500")
        dlg.transient(self.winfo_toplevel())
        dlg.configure(fg_color="#1A1D28")
        customtkinter.CTkLabel(dlg, text="Recent Errors",
                               font=customtkinter.CTkFont(size=14, weight="bold"),
                               text_color="#D4A843").pack(pady=(12, 4))
        from tkinter import ttk
        tree = ttk.Treeview(dlg, columns=("time", "type", "stage", "text"), show="headings", height=18)
        tree.heading("time", text="Time")
        tree.heading("type", text="Type")
        tree.heading("stage", text="Stage")
        tree.heading("text", text="Text")
        tree.column("time", width=120)
        tree.column("type", width=80)
        tree.column("stage", width=100)
        tree.column("text", width=350)
        tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
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
                        tree.insert("", "end", values=(
                            ts, val.get("error_type", "-"), val.get("stage", "-"),
                            str(val.get("error_text", "-"))[:100]))
        except Exception:
            pass

    def _drilldown_mismatch(self) -> None:
        dlg = customtkinter.CTkToplevel(self)
        dlg.title("Tanks vs Prompts Mismatch")
        dlg.geometry("600x400")
        dlg.transient(self.winfo_toplevel())
        dlg.configure(fg_color="#1A1D28")
        customtkinter.CTkLabel(dlg, text="Mismatch Analysis",
                               font=customtkinter.CTkFont(size=14, weight="bold"),
                               text_color="#D4A843").pack(pady=(12, 4))
        try:
            from admin_backend.data import check_mismatch
            tank_db = self.app.tank_db if self.app else {}
            prompts = self.app.prompts if self.app else {}
            prompts_only, tanks_only = check_mismatch(tank_db, prompts)
            if prompts_only:
                customtkinter.CTkLabel(dlg, text=f"Prompts without tank DB ({len(prompts_only)}):",
                                       text_color="#cc6666",
                                       font=customtkinter.CTkFont(size=11)).pack(anchor="w", padx=12)
                for t in prompts_only[:20]:
                    customtkinter.CTkLabel(dlg, text=f"  {t}", text_color="#DDE0EA",
                                           font=customtkinter.CTkFont(size=10)).pack(anchor="w", padx=20)
            if tanks_only:
                customtkinter.CTkLabel(dlg, text=f"Tanks without prompts ({len(tanks_only)}):",
                                       text_color="#cc6666",
                                       font=customtkinter.CTkFont(size=11)).pack(anchor="w", padx=12, pady=(8, 0))
                for t in tanks_only[:20]:
                    customtkinter.CTkLabel(dlg, text=f"  {t}", text_color="#DDE0EA",
                                           font=customtkinter.CTkFont(size=10)).pack(anchor="w", padx=20)
            if not prompts_only and not tanks_only:
                customtkinter.CTkLabel(dlg, text="No mismatch — all OK",
                                       text_color="#66cc66",
                                       font=customtkinter.CTkFont(size=12)).pack(pady=20)
        except Exception as e:
            customtkinter.CTkLabel(dlg, text=f"Error: {e}", text_color="#cc6666").pack(pady=20)


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
