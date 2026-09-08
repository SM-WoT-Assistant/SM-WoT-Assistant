"""Admin panel content controllers with real data.

Each panel is a CTkFrame subclass with refresh() and data-loading logic.
PanelDock uses build(parent) -> content and refresh(content) callbacks.
"""

import customtkinter
import threading
import time
from typing import Any, Optional, List


_STATUS_COLS = 3


def _make_divider(parent, orient="h"):
    """Create a thin grey divider line."""
    if orient == "h":
        return customtkinter.CTkFrame(parent, height=1, fg_color="#2E3240")
    else:
        return customtkinter.CTkFrame(parent, width=1, fg_color="#2E3240")


class StatusPanel(customtkinter.CTkFrame):
    """Status tiles in a single horizontal row: Raw, DB, Builds, Queue."""

    _NCOLS = 4

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._cards: dict = {}
        self._build()

    def _build(self) -> None:
        from admin_ui.widgets import card

        labels = [
            ("tanks_raw", "Raw", "0"),
            ("tanks_db", "DB", "0"),
            ("builds", "Builds", "0"),
            ("queue", "Queue", "0"),
        ]

        ncols = self._NCOLS
        grid_cols = ncols * 2 - 1

        for idx, (key, title, value) in enumerate(labels):
            col = idx % ncols
            grid_col = col * 2

            drilldown_key = key if key in ("tanks_db", "queue") else None
            c = card(
                self, title=title, value=value, width=110, height=36, center=True,
                command=lambda dk=drilldown_key: self._open_drilldown(dk) if dk else None,
            )
            c.grid(row=0, column=grid_col, sticky="nsew", padx=2, pady=2)
            self._cards[key] = c

            if col < ncols - 1:
                sep = _make_divider(self, "v")
                sep.grid(row=0, column=grid_col + 1, sticky="ns", padx=0, pady=2)

        for gc in range(grid_cols):
            if gc % 2 == 0:
                self.grid_columnconfigure(gc, weight=1)
            else:
                self.grid_columnconfigure(gc, weight=0, minsize=1)

    def refresh(self) -> None:
        if self.app is None:
            return

        try:
            from admin_backend.data import count_raw_tanks
            raw = count_raw_tanks()
            self._cards["tanks_raw"]._val_lbl.configure(text=str(raw))
        except Exception:
            pass

        try:
            from admin_backend.data import count_builds
            tank_db = getattr(self.app, 'tank_db', {})
            prompts = getattr(self.app, 'prompts', {})
            db_count = len(tank_db)
            builds_count = count_builds()
            queue_count = max(0, db_count - builds_count)
            self._cards["tanks_db"]._val_lbl.configure(text=str(db_count))
            self._cards["builds"]._val_lbl.configure(text=str(builds_count))
            q_color = "#cc6666" if queue_count > 0 else "#66cc66"
            self._cards["queue"]._val_lbl.configure(text=str(queue_count), text_color=q_color)

            # DB ≠ Prompts mismatch → report error
            prompts_count = len(prompts)
            if db_count != prompts_count:
                try:
                    import firebase_reporter as fr
                    fr.report_fallback(
                        source="admin_ui.status",
                        context="db_prompts_mismatch",
                        error_text=f"DB ({db_count}) ≠ Prompts ({prompts_count})",
                        level="warning",
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def _open_drilldown(self, card_key: str) -> None:
        if card_key == "tanks_db":
            self._drilldown_tanks_db()
        elif card_key == "queue":
            self._drilldown_queue()

    def _drilldown_tanks_db(self) -> None:
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
            url = fr._rtdb_url("error_reports.json?orderBy=%22timestamp%22&limitToLast=50")
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



class InfoPanel(customtkinter.CTkFrame):
    """Info tiles: version, game version, game status, errors, installs."""

    _NCOLS = 5

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._cards: dict = {}
        self._build()

    def _build(self) -> None:
        from admin_ui.widgets import card

        labels = [
            ("version", "Ver", "-"),
            ("wg_version", "Game", "-"),
            ("game_status", "Status", "No WoT"),
            ("errors", "Errors", "0"),
            ("installs", "Installs", "0"),
        ]

        ncols = self._NCOLS
        grid_cols = ncols * 2 - 1

        for idx, (key, title, value) in enumerate(labels):
            col = idx % ncols
            grid_col = col * 2

            drilldown_key = key if key in ("errors",) else None
            c = card(
                self, title=title, value=value, width=110, height=36, center=True,
                command=lambda dk=drilldown_key: self._open_drilldown(dk) if dk else None,
            )
            c.grid(row=0, column=grid_col, sticky="nsew", padx=2, pady=2)
            self._cards[key] = c

            if col < ncols - 1:
                sep = _make_divider(self, "v")
                sep.grid(row=0, column=grid_col + 1, sticky="ns", padx=0, pady=2)

        for gc in range(grid_cols):
            if gc % 2 == 0:
                self.grid_columnconfigure(gc, weight=1)
            else:
                self.grid_columnconfigure(gc, weight=0, minsize=1)

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
            from admin_backend.data import get_errors_count
            errs = get_errors_count()
            color = "#cc6666" if errs > 0 else "#888888"
            self._cards["errors"]._val_lbl.configure(text=str(errs), text_color=color)
        except Exception:
            pass

        try:
            from admin_backend.data import get_community_stats
            stats = get_community_stats()
            installs = stats.get("installs", 0)
            self._cards["installs"]._val_lbl.configure(text=str(installs))
        except Exception:
            pass

    def _open_drilldown(self, card_key: str) -> None:
        if card_key == "errors":
            self._drilldown_errors()

    def _drilldown_errors(self) -> None:
        dlg = customtkinter.CTkToplevel(self)
        dlg.title("Errors")
        dlg.geometry("600x500")
        dlg.transient(self.winfo_toplevel())
        dlg.configure(fg_color="#1A1D28")
        customtkinter.CTkLabel(dlg, text="Error Reports",
                               font=customtkinter.CTkFont(size=14, weight="bold"),
                               text_color="#D4A843").pack(pady=(12, 4))
        from tkinter import ttk
        style = ttk.Style()
        style.configure("ErrDrill.Treeview", background="#12141C", foreground="#DDE0EA",
                        fieldbackground="#12141C", font=("Segoe UI", 10))
        tree = ttk.Treeview(dlg, columns=("type", "stage", "text", "time"), show="headings",
                            style="ErrDrill.Treeview", height=20)
        tree.heading("type", text="Type")
        tree.heading("stage", text="Stage")
        tree.heading("text", text="Error")
        tree.heading("time", text="Time")
        tree.column("type", width=100)
        tree.column("stage", width=100)
        tree.column("text", width=300)
        tree.column("time", width=100)
        scroll = ttk.Scrollbar(dlg, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(fill="both", expand=True, padx=12)
        scroll.pack(side="right", fill="y")
        try:
            from admin_backend.data import get_error_reports
            errors = get_error_reports()
            for e in errors:
                tree.insert("", "end", values=(
                    e.get("error_type", "-"), e.get("stage", "-"),
                    e.get("error_text", "-")[:100], e.get("timestamp", "-")[:16]))
        except Exception as ex:
            customtkinter.CTkLabel(dlg, text=f"Error: {ex}", text_color="#cc6666").pack(pady=20)


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
    """Community monitoring: 6 platform tiles in a horizontal strip with dividers."""

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._tiles: dict = {}
        self._build()

    def _build(self) -> None:
        platforms = [
            ("youtube", "YouTube"),
            ("reddit", "Reddit"),
            ("github", "GitHub"),
            ("kofi", "Ko-fi"),
            ("patreon", "Patreon"),
        ]
        strip = customtkinter.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", padx=6, pady=6)
        for i, (key, label) in enumerate(platforms):
            tile = customtkinter.CTkFrame(strip, height=34, fg_color="#14161F",
                border_width=2, border_color="#2E3240", corner_radius=4)
            tile.pack_propagate(False)
            tile.pack(side="left", fill="both", expand=True, padx=0)

            spacer_top = customtkinter.CTkFrame(tile, fg_color="transparent", height=1)
            spacer_top.pack(fill="x", expand=True)

            customtkinter.CTkLabel(
                tile, text=label, font=customtkinter.CTkFont(size=11),
                text_color="#6E7284").pack(pady=(1, 0))
            val_lbl = customtkinter.CTkLabel(
                tile, text="-", font=customtkinter.CTkFont(size=15, weight="bold"),
                text_color="#DDE0EA")
            val_lbl.pack()
            hint_lbl = customtkinter.CTkLabel(
                tile, text="", font=customtkinter.CTkFont(size=10),
                text_color="#6E7284")
            hint_lbl.pack(pady=(0, 1))

            spacer_bottom = customtkinter.CTkFrame(tile, fg_color="transparent", height=1)
            spacer_bottom.pack(fill="x", expand=True)

            self._tiles[key] = {"val": val_lbl, "hint": hint_lbl}

            if i < len(platforms) - 1:
                sep = _make_divider(strip, "v")
                sep.pack(side="left", fill="y", padx=0, pady=2)

    def refresh(self) -> None:
        try:
            from admin_backend import community as comm
            results = comm.fetch_all_tiles()
            for key, tile in self._tiles.items():
                res = results.get(key, {})
                if key == "youtube":
                    if res.get("ok"):
                        views = res.get("views", 0)
                        tile["val"].configure(text=f"{views:,}")
                        tile["hint"].configure(text=f"{res.get('subscribers', 0):,} subs")
                    else:
                        tile["val"].configure(text="-")
                        tile["hint"].configure(text=res.get("error", "no data")[:20])
                elif key == "reddit":
                    if res.get("ok"):
                        count = res.get("count", 0)
                        tile["val"].configure(text=str(count))
                        tile["hint"].configure(text=f"{count} posts")
                    else:
                        tile["val"].configure(text="-")
                        tile["hint"].configure(text=res.get("error", "no data")[:20])
                elif key == "github":
                    if res.get("ok"):
                        tile["val"].configure(text=str(res.get("downloads", 0)))
                        tile["hint"].configure(text=f"{res.get('releases', []) and len(res.get('releases', [])) or 0} releases")
                    else:
                        tile["val"].configure(text="-")
                        tile["hint"].configure(text=res.get("error", "no data")[:20])
                elif key == "kofi":
                    tile["val"].configure(text="ko-fi.com")
                    tile["hint"].configure(text="link")
                elif key == "patreon":
                    if res.get("ok"):
                        tile["val"].configure(text=str(res.get("patrons", 0)))
                        tile["hint"].configure(text=f"${res.get('pledge', 0):.0f}/mo")
                    else:
                        tile["val"].configure(text="-")
                        tile["hint"].configure(text=res.get("error", "no data")[:20])
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
            url = fr._rtdb_url("error_reports.json?orderBy=%22timestamp%22&limitToLast=50")
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


def info_controller(app: Any = None):
    return _controller("Info", "info", InfoPanel, app)


def builds_controller(app: Any = None):
    return _controller("Builds", "builds", BuildsPanel, app)


def community_controller(app: Any = None):
    return _controller("Community", "community", CommunityPanel, app)


def errors_controller(app: Any = None):
    return _controller("Errors", "errors", ErrorsPanel, app)


def log_controller(app: Any = None):
    return _controller("Log", "log", LogPanel, app)
