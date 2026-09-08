"""Admin panel engine: floatable, tab-groupable, edge-snapping panels.

Adapted from AI Project Studio ui/panels.py — persistence via JSON file
instead of SQLAlchemy, removed tools-panel special-casing, generalized
restore() for admin panel IDs.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import customtkinter

logger = logging.getLogger(__name__)

EDGE_SNAP = 70
MIN_WIDTH = 120
MAX_WIDTH = 720
PANEL_WIDTH = 300
EDGE_MARGIN = 4
STRIP_HEIGHT = 30
TOPBAR_HEIGHT = 44
STATUSBAR_HEIGHT = 26

STATE_FLOATING = "floating"
STATE_DOCKED_LEFT = "docked_left"
STATE_DOCKED_RIGHT = "docked_right"
STATE_HIDDEN = "hidden"

LAYOUT_FILE = Path(os.environ.get("APPDATA", "")) / "SM WoT Assistant" / "admin_panels_layout.json"


def _load_layout() -> Dict[str, Any]:
    try:
        if LAYOUT_FILE.exists():
            return json.loads(LAYOUT_FILE.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to load panel layout", exc_info=True)
    return {}


def _save_layout(layout: Dict[str, Any]) -> None:
    try:
        LAYOUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAYOUT_FILE.write_text(json.dumps(layout, indent=2), encoding="utf-8")
    except Exception:
        logger.warning("Failed to save panel layout", exc_info=True)


class PanelWindow(customtkinter.CTkToplevel):
    """Borderless floating panel window with a drag strip and tabs."""

    def __init__(
        self,
        dock: "PanelDock",
        group: List[str],
        width: int = PANEL_WIDTH,
    ) -> None:
        super().__init__(dock.main_window)
        self.dock = dock
        self.group: List[str] = list(group)
        self._drag_offset = (0, 0)
        self._resize_origin = (0, 0)

        self.overrideredirect(True)
        self.transient(dock.main_window)
        self.attributes("-topmost", False)
        self.configure(fg_color="#14161F")

        self._strip = customtkinter.CTkFrame(self, height=STRIP_HEIGHT, fg_color="#181B26")
        self._strip.pack(fill="x")
        self._strip.pack_propagate(False)
        grip = customtkinter.CTkLabel(
            self._strip, text="\u2261", text_color="#6E7284",
            font=customtkinter.CTkFont(size=14), cursor="fleur",
        )
        grip.pack(side="left", padx=(8, 4))
        self._title_label = customtkinter.CTkLabel(
            self._strip, text=self._group_title(),
            font=customtkinter.CTkFont(size=12),
        )
        self._title_label.pack(side="left", padx=2)
        customtkinter.CTkButton(
            self._strip, text="\u2715", text_color="#6E7284",
            width=24, height=22, fg_color="transparent", hover_color="#1A1D28",
            corner_radius=6, font=customtkinter.CTkFont(size=12),
            command=lambda: dock.close_window(self),
        ).pack(side="right", padx=2, pady=2)

        self._tabs: Optional[customtkinter.CTkTabview] = None
        if len(self.group) > 1:
            self._tabs = customtkinter.CTkTabview(self)
            self._tabs.pack(fill="both", expand=True, padx=4, pady=(0, 4))
            for panel_id in self.group:
                self._build_tab(panel_id)
        else:
            panel = self.dock.panels[self.group[0]]
            content = panel["build"](self)
            content.pack(fill="both", expand=True, padx=0, pady=(0, 4))
            panel["body"] = content

        for widget in (self._strip, grip):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<ButtonRelease-1>", self._drag_end)

        self._resize_handle = customtkinter.CTkFrame(
            self, width=5, fg_color="#181B26", cursor="sb_h_double_arrow"
        )
        self._resize_handle.pack(side="right", fill="y")
        self._resize_handle.bind("<ButtonPress-1>", self._resize_start)
        self._resize_handle.bind("<B1-Motion>", self._resize_move)

        self.update_idletasks()
        self.geometry(f"{max(width, self.winfo_reqwidth())}x{self.winfo_reqheight()}")

    def _group_title(self) -> str:
        first = self.group[0] if self.group else ""
        panel = self.dock.panels.get(first)
        return panel["title"] if panel else "Panel"

    def _build_tab(self, panel_id: str) -> None:
        if self._tabs is None:
            return
        panel = self.dock.panels[panel_id]
        tab = self._tabs.add(panel["title"] or panel["id"])
        content = panel["build"](tab)
        content.pack(fill="both", expand=True, padx=2, pady=2)
        panel["body"] = content

    def add_tabs(self, panel_ids: List[str]) -> None:
        for panel_id in panel_ids:
            if panel_id not in self.group:
                self.group.append(panel_id)
                self._build_tab(panel_id)
        if self._title_label is not None:
            self._title_label.configure(text=self._group_title())

    def refresh_tabs(self) -> None:
        for panel_id in self.group:
            panel = self.dock.panels[panel_id]
            if panel["body"] is not None and panel["refresh"] is not None:
                try:
                    panel["refresh"](panel["body"])
                except Exception:
                    logger.warning("Panel refresh failed: %s", panel_id, exc_info=True)

    def set_width(self, width: int) -> None:
        width = min(max(width, MIN_WIDTH), MAX_WIDTH)
        self.geometry(f"{width}x{self.winfo_height()}")

    def _drag_start(self, event) -> None:
        self._drag_offset = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_move(self, event) -> None:
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.geometry(f"+{x}+{y}")
        self.dock.update_drop_preview(self, event.x_root, event.y_root)

    def _drag_end(self, event) -> None:
        self.dock.resolve_drop(self, event.x_root, event.y_root)

    def _resize_start(self, event) -> None:
        self._resize_origin = (event.x_root, self.winfo_width())

    def _resize_move(self, event) -> None:
        width = self._resize_origin[1] + (event.x_root - self._resize_origin[0])
        self.set_width(width)
        self.dock.on_width_changed(self, self.winfo_width())


class PanelDock:
    """Manages panels: floating, tab groups, edge snapping, JSON persistence."""

    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.panels: Dict[str, Dict[str, Any]] = {}
        self._layout: Dict[str, Dict[str, Any]] = _load_layout()
        self._windows: Dict[str, PanelWindow] = {}
        self._indicator: Optional[customtkinter.CTkFrame] = None
        self._indicator_side = ""
        self._dock_order: Dict[str, List[str]] = {
            "docked_left": [],
            "docked_right": [],
        }
        saved_order = self._layout.get("_order", {})
        if isinstance(saved_order, dict):
            for side in self._dock_order:
                order = saved_order.get(side, [])
                self._dock_order[side] = [pid for pid in order if pid in self.panels]
        self.main_window.bind("<Configure>", lambda _e: self._sync_docked_heights())
        self.main_window.bind("<Map>", lambda _e: self._sync_docked_heights())
        self.main_window.bind("<Map>", lambda _e: self.raise_all())
        self.main_window.bind("<FocusIn>", lambda _e: self.raise_all())

    def _register_docked(self, panel_id: str, side: str) -> None:
        order = self._dock_order.setdefault(side, [])
        if panel_id not in order:
            order.append(panel_id)

    def _unregister_docked(self, panel_id: str) -> None:
        for order in self._dock_order.values():
            if panel_id in order:
                order.remove(panel_id)

    def _root_size(self) -> int:
        root = self.main_window
        width = root.winfo_width()
        if width < 100:
            return getattr(root, "default_width", 1200) or 1200
        return width

    def _sync_docked_heights(self) -> None:
        root = self.main_window
        if not root.winfo_ismapped():
            return
        root_w = self._root_size()
        root_x0 = root.winfo_rootx()
        y = root.winfo_rooty() + TOPBAR_HEIGHT
        height = max(200, root.winfo_height() - TOPBAR_HEIGHT - STATUSBAR_HEIGHT)
        for side in (STATE_DOCKED_LEFT, STATE_DOCKED_RIGHT):
            columns = []
            seen_windows = set()
            for pid in self._dock_order.get(side, []):
                window = self._window_for(pid)
                if window is None or not window.winfo_exists():
                    continue
                if self.panels[pid]["state"] != side:
                    continue
                if id(window) in seen_windows:
                    continue
                seen_windows.add(id(window))
                panel = self.panels[pid]
                width = max(MIN_WIDTH, panel["width"])
                columns.append((window, width))
            if side == STATE_DOCKED_LEFT:
                offset = root_x0 + EDGE_MARGIN
                for window, width in columns:
                    window.geometry(f"{width}x{height}+{offset}+{y}")
                    offset += width
            else:
                offset = root_x0 + root_w - EDGE_MARGIN
                for window, width in columns:
                    x = offset - width
                    window.geometry(f"{width}x{height}+{x}+{y}")
                    offset = x

    def add_panel(
        self,
        panel_id: str,
        title: str,
        icon_id: str,
        build: Callable[[Any], Any],
        refresh: Optional[Callable[[Any], None]] = None,
        default_dock: str = STATE_DOCKED_RIGHT,
        width: int = PANEL_WIDTH,
    ) -> None:
        saved = self._layout.get(panel_id, {})
        self.panels[panel_id] = {
            "id": panel_id,
            "title": title,
            "icon": icon_id,
            "build": build,
            "refresh": refresh,
            "body": None,
            "width": int(saved.get("width", width)),
            "state": saved.get("state", default_dock),
            "x": saved.get("x"),
            "y": saved.get("y"),
            "group": saved.get("group"),
        }

    def restore(self) -> None:
        for panel in self.panels.values():
            if panel["state"] == STATE_HIDDEN:
                panel["state"] = STATE_DOCKED_RIGHT
        opened: set = set()
        group_keys: List[str] = []
        for panel in self.panels.values():
            key = panel.get("group") or ""
            if key and key not in group_keys:
                group_keys.append(key)
        for key in group_keys:
            ids = [pid for pid in key.split("|") if pid in self.panels]
            if not ids:
                continue
            if len(ids) == 1:
                self.open_panel(ids[0], save=False)
            else:
                self.open_group(ids, save=False)
            opened.update(ids)
        for panel_id, panel in self.panels.items():
            if panel_id in opened:
                continue
            if panel["state"] in (STATE_FLOATING, STATE_DOCKED_LEFT, STATE_DOCKED_RIGHT):
                self.open_panel(panel_id, save=False)
        if not any(self._dock_order.values()):
            right = []
            for pid in self.panels:
                if pid not in opened:
                    right.append(pid)
                    if len(right) >= 2:
                        break
            self._dock_order = {"docked_left": [], "docked_right": right}
        self._sync_docked_heights()
        self._save()

    def open_panel(
        self, panel_id: str, x: Optional[int] = None, y: Optional[int] = None,
        save: bool = True,
    ) -> None:
        panel = self.panels.get(panel_id)
        if panel is None:
            return
        if self._window_for(panel_id) is not None:
            return
        window = PanelWindow(self, [panel_id], width=panel["width"])
        if x is None or y is None:
            x, y = self._anchored_position(panel_id, window.winfo_width())
        window.geometry(f"+{x}+{y}")
        self._windows["|".join(window.group)] = window
        if panel["state"] not in (STATE_DOCKED_LEFT, STATE_DOCKED_RIGHT):
            panel["state"] = STATE_FLOATING
        else:
            self._register_docked(panel_id, panel["state"])
        panel["x"], panel["y"] = x, y
        panel["group"] = panel_id
        if save:
            self._save()
        self._sync_docked_heights()

    def open_group(self, panel_ids: List[str], save: bool = True) -> None:
        ids = [pid for pid in panel_ids if pid in self.panels]
        if not ids:
            return
        for panel_id in ids:
            if self._window_for(panel_id) is not None:
                return
        if len(ids) == 1:
            self.open_panel(ids[0], save=save)
            return
        widths = [self.panels[i]["width"] for i in ids]
        window = PanelWindow(self, ids, width=max(widths))
        x, y = self._anchored_position(ids[0], window.winfo_width())
        window.geometry(f"+{x}+{y}")
        self._windows["|".join(window.group)] = window
        group_key = "|".join(ids)
        for panel_id in ids:
            panel = self.panels[panel_id]
            if panel["state"] not in (STATE_DOCKED_LEFT, STATE_DOCKED_RIGHT):
                panel["state"] = STATE_FLOATING
            else:
                self._register_docked(panel_id, panel["state"])
            panel["x"], panel["y"] = x, y
            panel["group"] = group_key
        if save:
            self._save()
        self._sync_docked_heights()

    def toggle_panels(self, panel_ids: List[str]) -> None:
        visible = [
            pid for pid in panel_ids
            if pid in self.panels and self._window_for(pid) is not None
        ]
        if visible:
            for pid in visible:
                self.panels[pid]["state"] = STATE_HIDDEN
                window = self._window_for(pid)
                if window is not None:
                    self._destroy_window(window)
            self._save()
        else:
            self.open_group(panel_ids)

    def _anchored_position(self, panel_id: str, width: int) -> tuple:
        panel = self.panels[panel_id]
        saved_x = panel.get("x")
        saved_y = panel.get("y")
        state = panel.get("state")
        root = self.main_window
        root_x0 = root.winfo_rootx()
        root_y0 = root.winfo_rooty()
        root_w = self._root_size()
        if state == STATE_DOCKED_LEFT:
            x = root_x0 + EDGE_MARGIN
            y = root_y0 + TOPBAR_HEIGHT
        elif state == STATE_DOCKED_RIGHT:
            x = root_x0 + root_w - width - EDGE_MARGIN
            y = root_y0 + TOPBAR_HEIGHT
        elif saved_x is not None and saved_y is not None:
            x, y = int(saved_x), int(saved_y)
        else:
            x = root_x0 + root_w - width - EDGE_MARGIN
            y = root_y0 + 60
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = min(max(x, EDGE_MARGIN), screen_w - width - EDGE_MARGIN)
        y = min(max(y, 40), screen_h - 80)
        return x, y

    def close_window(self, window: Optional[PanelWindow] = None) -> None:
        if window is None:
            return
        for panel_id in window.group:
            self.panels[panel_id]["state"] = STATE_HIDDEN
            self._unregister_docked(panel_id)
        self._destroy_window(window)
        self._save()

    def _window_for(self, panel_id: str) -> Optional[PanelWindow]:
        for window in self._windows.values():
            if panel_id in window.group:
                return window
        return None

    def _destroy_window(self, window: PanelWindow) -> None:
        self._windows.pop("|".join(window.group), None)
        for panel_id in window.group:
            self.panels[panel_id]["body"] = None
        try:
            window.destroy()
        except Exception:
            pass

    def update_drop_preview(self, window: PanelWindow, root_x: int, root_y: int) -> None:
        root = self.main_window
        root_x0 = root.winfo_rootx()
        root_w = root.winfo_width()
        if root_x - root_x0 < EDGE_SNAP:
            side = STATE_DOCKED_LEFT
        elif root_x0 + root_w - root_x < EDGE_SNAP:
            side = STATE_DOCKED_RIGHT
        else:
            side = ""
        if side == self._indicator_side and self._indicator is not None:
            return
        self._hide_indicator()
        if side:
            self._show_indicator(side)

    def _show_indicator(self, side: str) -> None:
        root = self.main_window
        indicator = customtkinter.CTkFrame(root, width=3, fg_color="#D4A843")
        indicator.configure(
            width=3, height=max(100, root.winfo_height() - 44 - 30)
        )
        x = 0 if side == STATE_DOCKED_LEFT else max(0, root.winfo_width() - 3)
        indicator.place(x=x, y=44)
        self._indicator = indicator
        self._indicator_side = side

    def _hide_indicator(self) -> None:
        if self._indicator is not None:
            try:
                self._indicator.destroy()
            except Exception:
                pass
            self._indicator = None
        self._indicator_side = ""

    def resolve_drop(self, window: PanelWindow, root_x: int, root_y: int) -> None:
        self._hide_indicator()
        target = self._window_at(root_x, root_y, exclude=window)
        if target is not None:
            self._join_groups(window, target)
            return
        root = self.main_window
        root_x0 = root.winfo_rootx()
        root_w = root.winfo_width()
        width = window.winfo_width()
        x = root_x - width // 2
        state = STATE_FLOATING
        if root_x - root_x0 < EDGE_SNAP:
            x = root_x0 + EDGE_MARGIN
            state = STATE_DOCKED_LEFT
        elif root_x0 + root_w - root_x < EDGE_SNAP:
            x = root_x0 + root_w - width - EDGE_MARGIN
            state = STATE_DOCKED_RIGHT
        y = root_y - 15
        window.geometry(f"+{x}+{y}")
        if state == STATE_FLOATING:
            window.update_idletasks()
            window.geometry(f"{width}x{window.winfo_reqheight()}+{x}+{y}")
        for panel_id in window.group:
            panel = self.panels[panel_id]
            panel["state"] = state
            panel["x"], panel["y"] = x, y
            panel["group"] = "|".join(window.group)
            if state == STATE_FLOATING:
                self._unregister_docked(panel_id)
            else:
                self._register_docked(panel_id, state)
        self._save()
        self._sync_docked_heights()

    def _window_at(self, root_x: int, root_y: int, exclude: PanelWindow) -> Optional[PanelWindow]:
        for window in self._windows.values():
            if window is exclude or not window.winfo_exists():
                continue
            if (
                window.winfo_rootx() <= root_x <= window.winfo_rootx() + window.winfo_width()
                and window.winfo_rooty() <= root_y <= window.winfo_rooty() + 36
            ):
                return window
        return None

    def _join_groups(self, source: PanelWindow, target: PanelWindow) -> None:
        moved = [panel_id for panel_id in source.group if panel_id not in target.group]
        if not moved:
            return
        target.add_tabs(moved)
        self._windows.pop("|".join(source.group), None)
        for panel_id in moved:
            self.panels[panel_id]["body"] = None
        try:
            source.destroy()
        except Exception:
            pass
        self._save()

    def on_width_changed(self, window: PanelWindow, width: int) -> None:
        panel_id = window.group[0]
        self.panels[panel_id]["width"] = width
        self._save()

    def set_panel_width(self, panel_id: str, width: int) -> None:
        width = min(max(width, MIN_WIDTH), MAX_WIDTH)
        window = self._window_for(panel_id)
        if window is not None and window.winfo_exists():
            window.set_width(width)
        self.panels[panel_id]["width"] = width

    def _save(self) -> None:
        layout: Dict[str, Dict[str, Any]] = {}
        for panel_id, panel in self.panels.items():
            entry: Dict[str, Any] = {
                "state": panel["state"],
                "width": panel["width"],
            }
            window = self._window_for(panel_id)
            if window is not None and window.winfo_exists():
                entry["x"] = window.winfo_x()
                entry["y"] = window.winfo_y()
                entry["group"] = "|".join(window.group)
            else:
                entry["group"] = panel.get("group")
            layout[panel_id] = entry
        layout["_order"] = {
            side: list(order) for side, order in self._dock_order.items()
        }
        _save_layout(layout)

    def raise_all(self) -> None:
        for window in self._windows.values():
            try:
                if window.winfo_exists():
                    window.lift()
            except Exception:
                pass

    def refresh(self) -> None:
        for window in self._windows.values():
            if window.winfo_exists():
                window.refresh_tabs()

    def close_all(self) -> None:
        self._save()
        self._hide_indicator()
        for window in list(self._windows.values()):
            try:
                window.destroy()
            except Exception:
                pass
        self._windows = {}
