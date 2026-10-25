"""Admin panel content controllers with real data.

Each panel is a CTkFrame subclass with refresh() and data-loading logic.
PanelDock uses build(parent) -> content and refresh(content) callbacks.
"""

import customtkinter
import tkinter as tk
import threading
import time
from typing import Any, Optional, List


_STATUS_COLS = 3


def _err_ts_sort(val):
    """Sort key for error timestamp: handle both ISO strings and epoch ms."""
    ts = val.get("timestamp", "")
    if isinstance(ts, (int, float)):
        return str(ts)
    return str(ts or "")


def _err_text(val):
    """Get error text from RTDB record: handle both firebase_reporter and admin_backend schemas."""
    return val.get("error") or val.get("error_text") or val.get("message") or ""


def _make_divider(parent, orient="h"):
    """Create a thin grey divider line."""
    if orient == "h":
        return customtkinter.CTkFrame(parent, height=1, fg_color="#2E3240")
    else:
        return customtkinter.CTkFrame(parent, width=1, fg_color="#2E3240")


def _admin_tree_style(style, name: str) -> None:
    """Єдиний темний стиль ttk.Treeview для всієї адмінки (одне джерело правди).

    Тіло: #12141C/#DDE0EA; шапка: #181B26/#D4A843 bold, relief flat —
    без білого дефолтного clam-заголовка (#dcdad5) та його 3D-обводки.
    """
    style.theme_use("clam")
    style.configure(f"{name}.Treeview", background="#12141C", foreground="#DDE0EA",
                    fieldbackground="#12141C", borderwidth=0, font=("Segoe UI", 10))
    style.configure(f"{name}.Treeview.Heading", background="#181B26", foreground="#D4A843",
                    borderwidth=0, relief="flat", font=("Segoe UI", 10, "bold"))
    # Treeview.field малює 2px світло-сіру 3D-обводку НАВІТЬ при borderwidth=0
    # (relief/lightcolor/layout-border не допомагають — перевірено піксельними
    # зондами 25.10.2026); без field фон дає style background, рядки — fieldbackground.
    style.layout(f"{name}.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])


def _bind_copy(dlg):
    """Bind Ctrl+C / right-click Copy on all widgets in a popup dialog.

    - Treeview: Ctrl+C copies selected rows; right-click copies focused row
    - CTkLabel: right-click → Copy menu
    - CTkTextbox: already supports Ctrl+C natively
    """
    from tkinter import ttk

    def _copy_text(widget, text):
        widget.clipboard_clear()
        widget.clipboard_append(text)

    def _copy_treeview(tree, event=None):
        sel = tree.selection()
        if not sel:
            return
        rows = []
        for iid in sel:
            vals = tree.item(iid, "values")
            rows.append("\t".join(str(v) for v in vals))
        _copy_text(tree, "\n".join(rows))

    def _tree_context_menu(tree, event):
        menu = tk.Menu(tree, tearoff=0, bg="#1A1D28", fg="#DDE0EA",
                       activebackground="#D4A843", activeforeground="#12141C")
        menu.add_command(label="Copy",
                         command=lambda: _copy_treeview(tree))
        menu.add_command(label="Copy All",
                         command=lambda: _copy_text(
                             tree,
                             "\n".join(
                                 "\t".join(str(v) for v in tree.item(iid, "values"))
                                 for iid in tree.get_children()
                             )))
        menu.add_separator()
        menu.add_command(label="Select All",
                         command=lambda: tree.selection_set(tree.get_children()))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _label_context_menu(lbl, event):
        text = lbl.cget("text")
        if not text:
            return
        menu = tk.Menu(lbl, tearoff=0, bg="#1A1D28", fg="#DDE0EA",
                       activebackground="#D4A843", activeforeground="#12141C")
        menu.add_command(label="Copy",
                         command=lambda: _copy_text(lbl, text))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    for widget in dlg.winfo_children():
        if isinstance(widget, ttk.Treeview):
            widget.bind("<Control-c>", lambda e, t=widget: _copy_treeview(t, e))
            widget.bind("<Control-C>", lambda e, t=widget: _copy_treeview(t, e))
            widget.bind("<Control-a>",
                        lambda e, t=widget: t.selection_set(t.get_children()))
            widget.bind("<Control-A>",
                        lambda e, t=widget: t.selection_set(t.get_children()))
            widget.bind("<Button-3>",
                        lambda e, t=widget: _tree_context_menu(t, e))
        elif isinstance(widget, customtkinter.CTkLabel):
            widget.bind("<Button-3>",
                        lambda e, l=widget: _label_context_menu(l, e))
        elif isinstance(widget, customtkinter.CTkFrame):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Treeview):
                    child.bind("<Control-c>",
                               lambda e, t=child: _copy_treeview(t, e))
                    child.bind("<Control-C>",
                               lambda e, t=child: _copy_treeview(t, e))
                    child.bind("<Control-a>",
                               lambda e, t=child: t.selection_set(t.get_children()))
                    child.bind("<Control-A>",
                               lambda e, t=child: t.selection_set(t.get_children()))
                    child.bind("<Button-3>",
                               lambda e, t=child: _tree_context_menu(t, e))
                elif isinstance(child, customtkinter.CTkLabel):
                    child.bind("<Button-3>",
                               lambda e, l=child: _label_context_menu(l, e))


class StatusPanel(customtkinter.CTkFrame):
    """Status tiles in a single horizontal row: Raw, DB, Builds, Prompts, Queue."""

    _NCOLS = 5

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._cards: dict = {}
        self._pending_lbl: Optional[customtkinter.CTkLabel] = None
        self._pending_bar: Optional[customtkinter.CTkProgressBar] = None
        self._pending_poll_id: Optional[str] = None
        self._build()

    def _build(self) -> None:
        from admin_ui.widgets import card

        labels = [
            ("tanks_raw", "Raw", "0"),
            ("tanks_db", "DB", "0"),
            ("builds", "Builds", "0"),
            ("prompts", "Prompts", "0"),
            ("queue", "Queue", "0"),
        ]

        ncols = self._NCOLS
        grid_cols = ncols * 2 - 1

        for idx, (key, title, value) in enumerate(labels):
            col = idx % ncols
            grid_col = col * 2

            drilldown_key = key if key in ("tanks_db", "queue") else None
            c = card(
                self, title=title, value=value, width=110, height=30, center=True,
                fg_color="#14161F",
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

        # Pending progress row (below tiles)
        pending_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        pending_frame.grid(row=1, column=0, columnspan=grid_cols, sticky="ew", padx=4, pady=(4, 0))
        self._pending_lbl = customtkinter.CTkLabel(
            pending_frame, text="", text_color="#6E7284",
            font=customtkinter.CTkFont(size=11))
        self._pending_lbl.pack(side="left", padx=(0, 8))
        self._pending_bar = customtkinter.CTkProgressBar(
            pending_frame, width=200, height=6,
            progress_color="#D4A843", fg_color="#2E3240")
        self._pending_bar.pack(side="left", padx=(0, 4))
        self._pending_bar.set(0)

    def apply_cache(self, cached: dict) -> None:
        """Apply cached stats for instant display at startup."""
        if "db_count" in cached:
            self._cards["tanks_db"]._val_lbl.configure(text=str(cached["db_count"]))
        if "builds_count" in cached:
            self._cards["builds"]._val_lbl.configure(text=str(cached["builds_count"]))
        if "db_count" in cached and "builds_count" in cached:
            q = max(0, cached["db_count"] - cached["builds_count"])
            q_color = "#cc6666" if q > 0 else "#66cc66"
            self._cards["queue"]._val_lbl.configure(text=str(q), text_color=q_color)

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
            from admin_backend.data import count_builds, count_prompts, get_build_tags, get_pending_status, write_pending_queue
            tank_db = getattr(self.app, 'tank_db', {})
            prompts = getattr(self.app, 'prompts', {})
            db_count = len(tank_db)
            builds_count = count_builds()
            prompts_count = count_prompts()
            self._cards["tanks_db"]._val_lbl.configure(text=str(db_count))
            self._cards["builds"]._val_lbl.configure(text=str(builds_count))
            self._cards["prompts"]._val_lbl.configure(text=str(prompts_count))

            # Build/Prompt guard: color builds tile if mismatch
            if builds_count > 0 and prompts_count > 0 and builds_count != prompts_count:
                self._cards["builds"]._val_lbl.configure(text_color="#cc6666")
                self._cards["prompts"]._val_lbl.configure(text_color="#cc6666")
            elif builds_count > 0:
                self._cards["builds"]._val_lbl.configure(text_color="#66cc66")
                self._cards["prompts"]._val_lbl.configure(text_color="#66cc66" if prompts_count == builds_count else "#888888")
            else:
                self._cards["builds"]._val_lbl.configure(text_color="#888888")
                self._cards["prompts"]._val_lbl.configure(text_color="#888888")

            db_tags = set(tank_db.keys())
            build_tags = get_build_tags()
            self._missing_builds = sorted(db_tags - build_tags)
            self._extra_builds = sorted(build_tags - db_tags)
            queue_count = len(self._missing_builds)

            q_color = "#cc6666" if queue_count > 0 else "#66cc66"
            self._cards["queue"]._val_lbl.configure(text=str(queue_count), text_color=q_color)

            # Publish queue to RTDB with full tank info for website synchronization
            tanks_list = []
            for tag in self._missing_builds:
                td = tank_db.get(tag, {})
                tanks_list.append({
                    "tag": tag,
                    "name": td.get("name", tag),
                    "tier": str(td.get("tier", "?")),
                    "status": "waiting",
                })
            write_pending_queue(tanks_list)

            arith_queue = max(0, db_count - builds_count)
            if queue_count != arith_queue:
                try:
                    import firebase_reporter as fr
                    fr.report_fallback(
                        source="admin_ui.status",
                        context="queue_mismatch",
                        error_text=(f"Arithmetic queue ({arith_queue}) != factual ({queue_count}). "
                                    f"Extra builds in RTDB: {len(self._extra_builds)}"),
                        level="warning",
                    )
                except Exception:
                    pass

            # Report builds vs prompts mismatch
            if builds_count > 0 and prompts_count > 0 and builds_count != prompts_count:
                try:
                    import firebase_reporter as fr
                    fr.report_fallback(
                        source="admin_ui.status",
                        context="builds_prompts_mismatch",
                        error_text=f"Builds ({builds_count}) ≠ Prompts ({prompts_count})",
                        level="warning",
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # Pending updates polling
        self._poll_pending()

    def _poll_pending(self) -> None:
        """Read pending_updates/builds from RTDB and update progress bar."""
        if self.app is None:
            return
        try:
            from admin_backend.data import get_pending_status
            data = get_pending_status("builds")
            status = data.get("status")
            if not status or status == "idle":
                self._pending_lbl.configure(text="", text_color="#6E7284")
                self._pending_bar.set(0)
                return

            progress = data.get("progress", {})
            msg = data.get("message", "")
            done = progress.get("done", 0)
            total = progress.get("total", 0)

            if status == "generating":
                pct = done / total if total > 0 else 0
                self._pending_bar.set(pct)
                self._pending_lbl.configure(
                    text=f"Generating: {done}/{total} {'— ' + msg if msg else ''}",
                    text_color="#ffaa00")
            elif status == "done":
                self._pending_bar.set(1.0)
                self._pending_lbl.configure(
                    text=f"Done: {msg or 'generation complete'}",
                    text_color="#66cc66")
            elif status == "error":
                self._pending_bar.set(0)
                self._pending_lbl.configure(
                    text=f"Error: {msg or 'unknown'}",
                    text_color="#cc6666")
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
        _admin_tree_style(style, "Drill")
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
        dlg.title("Queue \u2014 Builds Validation")
        dlg.geometry("560x550")
        dlg.transient(self.winfo_toplevel())
        dlg.configure(fg_color="#1A1D28")
        from tkinter import ttk

        missing = list(getattr(self, '_missing_builds', []))
        extra = list(getattr(self, '_extra_builds', []))
        tank_db = self.app.tank_db if self.app else {}

        # --- Controls ---
        ctrl_frame = customtkinter.CTkFrame(dlg, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=12, pady=(10, 4))

        gen_btn = customtkinter.CTkButton(
            ctrl_frame, text="Generate", width=90, height=28,
            fg_color="#D4A843", hover_color="#B8922E", text_color="#12141C",
            command=lambda: self.app._generate_now(queue=list(missing)) if self.app and missing else None,
        )
        gen_btn.pack(side="left", padx=2)

        auto_var = customtkinter.BooleanVar(value=getattr(self.app, '_auto_generate', False) if self.app else False)
        auto_btn = customtkinter.CTkButton(
            ctrl_frame, text=f"Auto: {'ON' if auto_var.get() else 'OFF'}", width=80, height=28,
            fg_color="transparent", text_color="#6E7284", border_width=1, border_color="#2E3240",
            command=lambda: self._toggle_auto_in_queue(auto_var, auto_btn),
        )
        auto_btn.pack(side="left", padx=2)

        chrome_vis = getattr(self.app, '_chrome_visible', False) if self.app else False
        chrome_btn = customtkinter.CTkButton(
            ctrl_frame, text=f"Chrome: {'Visible' if chrome_vis else 'Hidden'}", width=110, height=28,
            fg_color="#D4A843" if chrome_vis else "transparent",
            text_color="#12141C" if chrome_vis else "#6E7284",
            border_width=1, border_color="#D4A843" if chrome_vis else "#2E3240",
            command=lambda: self._toggle_chrome_in_queue(chrome_btn),
        )
        chrome_btn.pack(side="left", padx=2)

        status_lbl = customtkinter.CTkLabel(
            ctrl_frame, text="", text_color="#6E7284",
            font=customtkinter.CTkFont(size=11))
        status_lbl.pack(side="left", padx=(8, 0))

        # --- Progress bar ---
        pbar = customtkinter.CTkProgressBar(dlg, width=520, height=6,
            progress_color="#D4A843", fg_color="#2E3240")
        pbar.pack(fill="x", padx=12, pady=(0, 6))
        pbar.set(0)

        # --- Missing builds treeview ---
        customtkinter.CTkLabel(dlg, text=f"Tanks Without Builds ({len(missing)})",
                               font=customtkinter.CTkFont(size=14, weight="bold"),
                               text_color="#D4A843").pack(pady=(0, 4), anchor="w", padx=12)

        style = ttk.Style()
        _admin_tree_style(style, "Queue")

        tree = ttk.Treeview(dlg, columns=("tag", "name", "tier", "status"), show="headings",
                            style="Queue.Treeview", height=14)
        tree.heading("tag", text="Tag")
        tree.heading("name", text="Name")
        tree.heading("tier", text="Tier")
        tree.heading("status", text="\u25cf")
        tree.column("tag", width=170)
        tree.column("name", width=200)
        tree.column("tier", width=40)
        tree.column("status", width=30)
        tree.tag_configure("generating", background="#3d3a00")
        tree.tag_configure("ok", background="#0a2e0a")
        tree.tag_configure("fail", background="#2e0a0a")
        tree.pack(fill="x", padx=12, pady=(0, 4))

        for tag in missing:
            name = tank_db.get(tag, {}).get("name", tag)
            tier = tank_db.get(tag, {}).get("tier", "?")
            tree.insert("", "end", values=(tag, name, tier, ""), tags=(), iid=f"m_{tag}")

        # --- Extra builds ---
        if extra:
            customtkinter.CTkLabel(
                dlg, text=f"Extra Builds in RTDB ({len(extra)}) \u2014 not in DB",
                font=customtkinter.CTkFont(size=12, weight="bold"),
                text_color="#cc6666").pack(pady=(8, 2), anchor="w", padx=12)
            extra_tree = ttk.Treeview(dlg, columns=("tag",), show="headings",
                                      style="Queue.Treeview", height=6)
            extra_tree.heading("tag", text="Tag")
            extra_tree.column("tag", width=500)
            extra_tree.pack(fill="x", padx=12, pady=(0, 8))
            for tag in extra:
                extra_tree.insert("", "end", values=(tag,))

        # --- Live progress polling ---
        def _poll():
            if not dlg.winfo_exists():
                return
            gp = getattr(self.app, '_gen_progress', {}) if self.app else {}
            running = gp.get("running", False)
            current_tag = gp.get("current_tag")
            results = gp.get("results", {})
            progress = gp.get("progress", (0, 0))

            if running:
                gen_btn.configure(state="disabled")
                auto_btn.configure(state="disabled")
                cur, total = progress
                pct = cur / total if total > 0 else 0
                pbar.set(pct)
                status_lbl.configure(text=f"{cur}/{total}", text_color="#ffaa00")

                for iid in tree.get_children():
                    vals = tree.item(iid, "values")
                    tag = vals[0]
                    name_val = vals[1]
                    tier_val = vals[2]
                    if tag == current_tag:
                        tree.item(iid, values=(tag, name_val, tier_val, "\u25cf"),
                                  tags=("generating",))
                    elif tag in results:
                        st = results[tag]
                        sym = "\u2714" if st == "ok" else "\u2716"
                        tree.item(iid, values=(tag, name_val, tier_val, sym),
                                  tags=(st,))
            else:
                gen_btn.configure(state="normal")
                auto_btn.configure(state="normal")
                if results:
                    ok = sum(1 for v in results.values() if v == "ok")
                    fail = sum(1 for v in results.values() if v == "fail")
                    status_lbl.configure(text=f"Done: {ok} ok, {fail} fail",
                                         text_color="#66cc66" if fail == 0 else "#ffaa00")
                    pbar.set(1.0)
                elif not missing:
                    status_lbl.configure(text="All builds complete", text_color="#66cc66")

            dlg.after(500, _poll)

        dlg.after(500, _poll)
        _bind_copy(dlg)

    def _toggle_auto_in_queue(self, var, btn):
        if self.app and hasattr(self.app, '_auto_generate_toggle'):
            self.app._auto_generate_toggle()
            active = getattr(self.app, '_auto_generate', False)
            var.set(active)
            btn.configure(text=f"Auto: {'ON' if active else 'OFF'}")

    def _toggle_chrome_in_queue(self, btn) -> None:
        current = getattr(self.app, '_chrome_visible', False) if self.app else False
        new_val = not current
        if self.app:
            self.app._chrome_visible = new_val
        btn.configure(
            text=f"Chrome: {'Visible' if new_val else 'Hidden'}",
            fg_color="#D4A843" if new_val else "transparent",
            text_color="#12141C" if new_val else "#6E7284",
            border_color="#D4A843" if new_val else "#2E3240",
        )

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
        style = ttk.Style()
        _admin_tree_style(style, "ErrDrill")
        tree = ttk.Treeview(dlg, columns=("time", "type", "stage", "text"), show="headings",
                            style="ErrDrill.Treeview", height=18)
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
            url = fr._rtdb_url("error_reports?orderBy=%22timestamp%22&limitToLast=50")
            import requests
            resp = requests.get(url, timeout=10)
            if resp.ok:
                data = resp.json()
                if data:
                    for key, val in sorted(data.items(), key=lambda x: _err_ts_sort(x[1]), reverse=True)[:50]:
                        ts = val.get("timestamp", "")
                        if isinstance(ts, (int, float)):
                            ts = time.strftime("%m-%d %H:%M", time.localtime(ts / 1000 if ts > 1e12 else ts))
                        tree.insert("", "end", values=(
                            str(ts)[:16], val.get("type", "-"), val.get("stage", "-"),
                            _err_text(val)[:100]))
        except Exception:
            pass
        _bind_copy(dlg)



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
                self, title=title, value=value, width=110, height=30, center=True,
                fg_color="#14161F",
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
        _admin_tree_style(style, "ErrDrill")
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
            errors.reverse()
            for e in errors:
                tree.insert("", "end", values=(
                    e.get("type", "-"), e.get("stage", "-"),
                    _err_text(e)[:100], str(e.get("timestamp", "-"))[:16]))
        except Exception as ex:
            customtkinter.CTkLabel(dlg, text=f"Error: {ex}", text_color="#cc6666").pack(pady=20)
        _bind_copy(dlg)


class BuildsPanel(customtkinter.CTkFrame):
    """Builds summary: clickable queue count + tank treeview."""

    def __init__(self, parent: Any, app: Any = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._tree = None
        self._queue_label = None
        self._build()

    def _build(self) -> None:
        summary = customtkinter.CTkFrame(self, fg_color="transparent")
        summary.pack(fill="x", padx=6, pady=(6, 2))

        self._queue_btn = customtkinter.CTkButton(
            summary, text="Queue:", width=50, height=28,
            fg_color="transparent", text_color="#6E7284",
            border_width=1, border_color="#2E3240",
            command=self._open_queue,
        )
        self._queue_btn.pack(side="left", padx=2)

        self._queue_label = customtkinter.CTkLabel(
            summary, text="", text_color="#6E7284",
            font=customtkinter.CTkFont(size=11))
        self._queue_label.pack(side="left", padx=(4, 0))

        self._search = customtkinter.CTkEntry(self, placeholder_text="Search tanks...")
        self._search.pack(fill="x", padx=6, pady=(0, 4))
        self._search.bind("<KeyRelease>", self._on_search)

        self._tree_frame = customtkinter.CTkFrame(self, fg_color="#12141C")
        self._tree_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    def _open_queue(self) -> None:
        if self.app:
            self.app._open_queue()

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
        queue = getattr(self.app, '_queue', [])
        if queue:
            self._queue_label.configure(text=f"{len(queue)} in queue", text_color="#ffaa00")
        else:
            self._queue_label.configure(text="queue empty", text_color="#6E7284")
        if self._tree is None:
            try:
                from tkinter import ttk
                style = ttk.Style()
                _admin_tree_style(style, "Admin")
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
        import webbrowser
        platforms = [
            ("youtube", "YouTube", "https://youtube.com/@SMWoTAssistant"),
            ("reddit", "Reddit", "https://reddit.com/user/SM-WoT-Assistant"),
            ("github", "GitHub", "https://github.com/SM-WoT-Assistant"),
            ("kofi", "Ko-fi", "https://ko-fi.com/smwotassistant"),
            ("patreon", "Patreon", "https://patreon.com/cw/SMWoTAssistant"),
        ]
        strip = customtkinter.CTkFrame(self, fg_color="transparent")
        strip.pack(fill="x", padx=6, pady=6)
        for i, (key, label, url) in enumerate(platforms):
            tile = customtkinter.CTkFrame(strip, height=30, fg_color="#14161F",
                border_width=2, border_color="#2E3240", corner_radius=4)
            tile.pack_propagate(False)
            tile.pack(side="left", fill="both", expand=True, padx=0)
            tile.configure(cursor="hand2")

            spacer_top = customtkinter.CTkFrame(tile, fg_color="transparent", height=1)
            spacer_top.pack(fill="x", expand=True)

            customtkinter.CTkLabel(
                tile, text=label, font=customtkinter.CTkFont(size=12),
                text_color="#6E7284").pack(pady=(1, 0))
            val_lbl = customtkinter.CTkLabel(
                tile, text="-", font=customtkinter.CTkFont(size=16, weight="bold"),
                text_color="#DDE0EA")
            val_lbl.pack()
            hint_lbl = customtkinter.CTkLabel(
                tile, text="", font=customtkinter.CTkFont(size=12),
                text_color="#6E7284")
            hint_lbl.pack(pady=(0, 1))

            spacer_bottom = customtkinter.CTkFrame(tile, fg_color="transparent", height=1)
            spacer_bottom.pack(fill="x", expand=True)

            for w in (tile, spacer_top, spacer_top.winfo_children()[0] if spacer_top.winfo_children() else spacer_top):
                pass
            tile.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            for child in tile.winfo_children():
                child.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

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
                _admin_tree_style(style, "Err")
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
            url = fr._rtdb_url("error_reports?orderBy=%22timestamp%22&limitToLast=50")
            import requests
            resp = requests.get(url, timeout=10)
            if resp.ok:
                data = resp.json()
                if data:
                    for key, val in sorted(data.items(), key=lambda x: _err_ts_sort(x[1]), reverse=True)[:50]:
                        ts = val.get("timestamp", "")
                        if isinstance(ts, (int, float)):
                            ts = time.strftime("%m-%d %H:%M", time.localtime(ts / 1000 if ts > 1e12 else ts))
                        self._tree.insert("", "end", values=(
                            str(ts)[:16], val.get("type", "-"), val.get("stage", "-"),
                            str(val.get("error") or val.get("error_text") or "-")[:100]))
        except Exception:
            pass


class SiteMapsPanel(customtkinter.CTkFrame):
    """Tactic Map Updates: історія подій service_events (category=site_maps).

    Рендерить КЕШ app._site_events_list (оновлює добовий воркер через ping
    у _bg_poll) — без власних мережевих запитів на головному потоці (#1598).
    Дедуп балонів (site_events_last_seen) на секцію НЕ впливає: показується
    вся історія з RTDB."""

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
                _admin_tree_style(style, "SiteMap")
                self._tree = ttk.Treeview(
                    self._tree_frame,
                    columns=("time", "event"),
                    show="headings",
                    style="SiteMap.Treeview",
                    height=12,
                )
                self._tree.heading("time", text="Time")
                self._tree.heading("event", text="Event")
                self._tree.column("time", width=120, stretch=False)
                self._tree.column("event", width=380)
                scroll = customtkinter.CTkScrollbar(
                    self._tree_frame, command=self._tree.yview)
                self._tree.configure(yscrollcommand=scroll.set)
                self._tree.pack(side="left", fill="both", expand=True)
                scroll.pack(side="right", fill="y")
            except Exception:
                return
        for item in self._tree.get_children():
            self._tree.delete(item)
        events = list(getattr(self.app, "_site_events_list", []) or []) if self.app else []
        # Найновіші зверху: timestamp у подіях — ISO-рядок (рядкове desc ок)
        events.sort(key=lambda e: str(e.get("timestamp", "")), reverse=True)
        if not events:
            self._tree.insert("", "end", values=("", "No site map updates yet"))
            return
        for e in events[:50]:
            ts = str(e.get("timestamp", ""))[:19].replace("T", " ")
            msg = str(e.get("message", "-"))
            self._tree.insert("", "end", values=(ts, msg[:160]))


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


def site_maps_controller(app: Any = None):
    return _controller("Tactic Map Updates", "sitemaps", SiteMapsPanel, app)
