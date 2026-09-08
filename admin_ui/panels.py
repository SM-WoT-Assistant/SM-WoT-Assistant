"""Admin panels — horizontal grid with drag-to-reorder.

Panels are CTkFrame children inside the main window's center area,
arranged horizontally via grid with equal weight. Headers support
drag-to-reorder: grab a header, drag to a new position, drop to
reorder. Order persists in admin_panels_layout.json.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import customtkinter

logger = logging.getLogger(__name__)

_STATE_DOCKED_LEFT = "docked_left"
_STATE_DOCKED_RIGHT = "docked_right"

_LAYOUT_FILE = (
    Path(os.environ.get("APPDATA", ""))
    / "SM WoT Assistant"
    / "admin_panels_layout.json"
)


def _load_order() -> List[str]:
    try:
        if _LAYOUT_FILE.exists():
            data = json.loads(_LAYOUT_FILE.read_text(encoding="utf-8"))
            cols = data.get("_columns", [])
            if isinstance(cols, list) and cols:
                return cols
    except Exception:
        pass
    return []


def _save_order(columns: List[str]) -> None:
    try:
        _LAYOUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAYOUT_FILE.write_text(
            json.dumps({"_columns": columns}, indent=2), encoding="utf-8"
        )
    except Exception:
        logger.warning("Failed to save panel order", exc_info=True)


class PanelDock:
    """Manages embedded CTkFrame panels in a horizontal grid layout
    with drag-to-reorder headers."""

    def __init__(self, center_widget: Any) -> None:
        self.center = center_widget
        self.panels: Dict[str, Dict[str, Any]] = {}
        self._frames: Dict[str, customtkinter.CTkFrame] = {}
        self._headers: Dict[str, customtkinter.CTkFrame] = {}
        self._columns: List[str] = []

        # Drag state
        self._drag_panel_id: Optional[str] = None
        self._drag_start_x: int = 0
        self._drag_start_col: int = 0
        self._indicator: Optional[customtkinter.CTkFrame] = None

    def add_panel(
        self,
        panel_id: str,
        title: str,
        icon_id: str,
        build: Callable[[Any], Any],
        refresh: Optional[Callable[[Any], None]] = None,
        default_dock: str = _STATE_DOCKED_RIGHT,
        width: int = 300,
    ) -> None:
        self.panels[panel_id] = {
            "id": panel_id,
            "title": title,
            "icon": icon_id,
            "build": build,
            "refresh": refresh,
            "body": None,
            "width": width,
        }
        self._columns.append(panel_id)

    def restore(self) -> None:
        """Create all panel frames and pack them into the grid."""
        saved = _load_order()
        if saved:
            ordered = [pid for pid in saved if pid in self.panels]
            rest = [pid for pid in self._columns if pid not in ordered]
            self._columns = ordered + rest

        for col_idx, panel_id in enumerate(self._columns):
            self._create_panel_frame(panel_id, col_idx)

        self._regrid_all()

    def _create_panel_frame(self, panel_id: str, col_idx: int) -> None:
        panel = self.panels[panel_id]

        wrapper = customtkinter.CTkFrame(
            self.center, fg_color="#14161F", corner_radius=6,
        )

        header = customtkinter.CTkFrame(wrapper, height=30, fg_color="#181B26", corner_radius=6)
        header.pack(fill="x")
        header.pack_propagate(False)
        customtkinter.CTkLabel(
            header, text=f"  \u2261 {panel['title']}",
            font=customtkinter.CTkFont(size=12, weight="bold"),
            text_color="#D4A843", anchor="w",
        ).pack(side="left", fill="y", padx=4)

        body_container = customtkinter.CTkFrame(wrapper, fg_color="transparent")
        body_container.pack(fill="both", expand=True, padx=2, pady=(2, 4))

        content = panel["build"](body_container)
        content.pack(fill="both", expand=True)
        panel["body"] = content

        self._frames[panel_id] = wrapper
        self._headers[panel_id] = header

        for widget in (header,):
            widget.bind("<Button-1>", lambda e, pid=panel_id: self._drag_start(e, pid))
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<ButtonRelease-1>", self._drag_end)
            widget.configure(cursor="fleur")

    def _regrid_all(self) -> None:
        """Remove all wrappers from grid, then regrid in current _columns order."""
        for panel_id, wrapper in self._frames.items():
            try:
                wrapper.grid_forget()
            except Exception:
                pass

        for col_idx, panel_id in enumerate(self._columns):
            if panel_id not in self._frames:
                continue
            self.center.grid_columnconfigure(col_idx, weight=1)
            self._frames[panel_id].grid(
                row=0, column=col_idx, sticky="nsew", padx=3, pady=3,
            )

    def _drag_start(self, event, panel_id: str) -> None:
        self._drag_panel_id = panel_id
        self._drag_start_x = event.x_root
        self._drag_start_col = self._columns.index(panel_id)

    def _drag_move(self, event) -> None:
        if self._drag_panel_id is None:
            return

        # Determine target column from mouse position relative to panels
        target_col = self._drag_start_col
        for i, pid in enumerate(self._columns):
            if pid not in self._frames:
                continue
            wrapper = self._frames[pid]
            x0 = wrapper.winfo_rootx()
            x1 = x0 + wrapper.winfo_width()
            mid = (x0 + x1) // 2
            if event.x_root < mid:
                target_col = i
                break
            else:
                target_col = i + 1

        target_col = max(0, min(target_col, len(self._columns)))

        # Show gold indicator line at target position
        self._show_indicator(target_col)

    def _drag_end(self, event) -> None:
        if self._drag_panel_id is None:
            return

        target_col = self._drag_start_col
        for i, pid in enumerate(self._columns):
            if pid not in self._frames:
                continue
            wrapper = self._frames[pid]
            x0 = wrapper.winfo_rootx()
            x1 = x0 + wrapper.winfo_width()
            mid = (x0 + x1) // 2
            if event.x_root < mid:
                target_col = i
                break
            else:
                target_col = i + 1

        target_col = max(0, min(target_col, len(self._columns)))

        self._hide_indicator()

        # Reorder
        if target_col != self._drag_start_col:
            pid = self._drag_panel_id
            self._columns.remove(pid)
            self._columns.insert(target_col, pid)
            self._regrid_all()
            _save_order(self._columns)

        self._drag_panel_id = None

    def _show_indicator(self, col_idx: int) -> None:
        """Show a gold vertical line at the target column boundary."""
        self._hide_indicator()
        try:
            if col_idx < len(self._columns) and col_idx >= 0:
                pid = self._columns[col_idx]
                if pid in self._frames:
                    wrapper = self._frames[pid]
                    x = wrapper.winfo_rootx() - self.center.winfo_rootx() - 2
                else:
                    return
            elif col_idx >= len(self._columns) and self._columns:
                last_pid = self._columns[-1]
                if last_pid in self._frames:
                    wrapper = self._frames[last_pid]
                    x = (wrapper.winfo_rootx() - self.center.winfo_rootx()
                         + wrapper.winfo_width() + 2)
                else:
                    return
            else:
                return

            h = max(100, self.center.winfo_height() - 10)
            indicator = customtkinter.CTkFrame(
                self.center, width=3, height=h, fg_color="#D4A843",
            )
            indicator.place(x=max(0, x), y=5)
            self._indicator = indicator
        except Exception:
            pass

    def _hide_indicator(self) -> None:
        if self._indicator is not None:
            try:
                self._indicator.destroy()
            except Exception:
                pass
            self._indicator = None

    def refresh(self) -> None:
        """Refresh all panel bodies."""
        for panel_id, panel in self.panels.items():
            if panel["body"] is not None and panel["refresh"] is not None:
                try:
                    panel["refresh"](panel["body"])
                except Exception:
                    logger.warning("Panel refresh failed: %s", panel_id, exc_info=True)

    def close_all(self) -> None:
        """Destroy all panel frames."""
        self._hide_indicator()
        for frame in self._frames.values():
            try:
                frame.destroy()
            except Exception:
                pass
        self._frames.clear()
        self._headers.clear()
        for panel in self.panels.values():
            panel["body"] = None
