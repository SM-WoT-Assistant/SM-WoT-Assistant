"""Admin panels — vertical stack layout with drag-to-reorder and collapse/expand.

Panels are CTkFrame children packed side='top' inside the main window's
scrollable center area. Each panel spans the full width (horizontal rows).
Headers support drag-to-reorder with a gold indicator line and collapse/expand
toggle (click chevron or header). Order persists in admin_panels_layout.json.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import customtkinter

logger = logging.getLogger(__name__)

_LAYOUT_FILE = (
    Path(os.environ.get("APPDATA", ""))
    / "SM WoT Assistant"
    / "admin_panels_layout.json"
)

_DIVIDER_COLOR = "#2E3240"


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


def divider_h(parent: Any, **kw: Any) -> customtkinter.CTkFrame:
    """Create a thin horizontal grey divider line."""
    f = customtkinter.CTkFrame(parent, height=1, fg_color=_DIVIDER_COLOR, **kw)
    return f


def divider_v(parent: Any, **kw: Any) -> customtkinter.CTkFrame:
    """Create a thin vertical grey divider line."""
    f = customtkinter.CTkFrame(parent, width=1, fg_color=_DIVIDER_COLOR, **kw)
    return f


class PanelDock:
    """Manages embedded CTkFrame panels in a vertical stack layout
    with drag-to-reorder headers and collapse/expand."""

    def __init__(self, center_widget: Any) -> None:
        self.center = center_widget
        self.panels: Dict[str, Dict[str, Any]] = {}
        self._frames: Dict[str, customtkinter.CTkFrame] = {}
        self._headers: Dict[str, customtkinter.CTkFrame] = {}
        self._bodies: Dict[str, customtkinter.CTkFrame] = {}
        self._chevrons: Dict[str, customtkinter.CTkLabel] = {}
        self._collapsed: Dict[str, bool] = {}
        self._columns: List[str] = []

        # Drag state
        self._drag_panel_id: Optional[str] = None
        self._drag_start_y: int = 0
        self._drag_indicator: Optional[customtkinter.CTkFrame] = None

    def add_panel(
        self,
        panel_id: str,
        title: str,
        icon_id: str,
        build: Callable[[Any], Any],
        refresh: Optional[Callable[[Any], None]] = None,
        width: int = 300,
        collapsed: bool = False,
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
        self._collapsed[panel_id] = collapsed

    def restore(self) -> None:
        """Load saved order, create all panel frames, pack vertically."""
        saved = _load_order()
        if saved:
            ordered = [pid for pid in saved if pid in self.panels]
            rest = [pid for pid in self._columns if pid not in ordered]
            self._columns = ordered + rest

        for panel_id in self._columns:
            self._create_panel_frame(panel_id)

        self._repack_all()

    def _create_panel_frame(self, panel_id: str) -> None:
        panel = self.panels[panel_id]

        wrapper = customtkinter.CTkFrame(
            self.center, fg_color="#14161F", border_width=2, border_color="#2E3240", corner_radius=6,
        )

        header = customtkinter.CTkFrame(wrapper, height=30, fg_color="#181B26", corner_radius=6)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_lbl = customtkinter.CTkLabel(
            header, text=f"  \u2261 {panel['title']}",
            font=customtkinter.CTkFont(size=12, weight="bold"),
            text_color="#D4A843", anchor="w",
        )
        title_lbl.pack(side="left", fill="y", padx=4)

        is_collapsed = self._collapsed.get(panel_id, False)
        chevron_char = "\u25b8" if is_collapsed else "\u25be"
        chevron = customtkinter.CTkLabel(
            header, text=chevron_char,
            font=customtkinter.CTkFont(size=12),
            text_color="#6E7284", width=24,
        )
        chevron.pack(side="right", padx=4)
        self._chevrons[panel_id] = chevron

        body_container = customtkinter.CTkFrame(wrapper, fg_color="transparent")
        self._bodies[panel_id] = body_container

        if is_collapsed:
            pass
        else:
            body_container.pack(fill="both", expand=True, padx=2, pady=(2, 4))

        content = panel["build"](body_container)
        content.pack(fill="both", expand=True)
        panel["body"] = content

        self._frames[panel_id] = wrapper
        self._headers[panel_id] = header

        for widget in (header, title_lbl):
            widget.bind("<Button-1>", lambda e, pid=panel_id: self._drag_start(e, pid))
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<ButtonRelease-1>", self._drag_end)
            widget.configure(cursor="fleur")

        chevron.bind("<Button-1>", lambda e, pid=panel_id: self._toggle_collapse(pid))
        chevron.configure(cursor="hand2")

    def _toggle_collapse(self, panel_id: str) -> None:
        collapsed = self._collapsed.get(panel_id, False)
        new_state = not collapsed
        self._collapsed[panel_id] = new_state

        chevron = self._chevrons.get(panel_id)
        body = self._bodies.get(panel_id)
        if chevron:
            chevron.configure(text="\u25b8" if new_state else "\u25be")
        if body:
            if new_state:
                body.pack_forget()
            else:
                body.pack(fill="both", expand=True, padx=2, pady=(2, 4))

    def _repack_all(self) -> None:
        """Unpack all wrappers, then pack in current _columns order (top to bottom)."""
        for wrapper in self._frames.values():
            try:
                wrapper.pack_forget()
            except Exception:
                pass

        for panel_id in self._columns:
            if panel_id in self._frames:
                self._frames[panel_id].pack(
                    side="top", fill="x", padx=3, pady=3,
                )

    def _drag_start(self, event, panel_id: str) -> None:
        self._drag_panel_id = panel_id
        self._drag_start_y = event.y_root

    def _drag_move(self, event) -> None:
        if self._drag_panel_id is None:
            return
        target_idx = self._resolve_target_idx(event.y_root)
        self._show_indicator(target_idx)

    def _drag_end(self, event) -> None:
        if self._drag_panel_id is None:
            return

        target_idx = self._resolve_target_idx(event.y_root)
        self._hide_indicator()

        src_idx = self._columns.index(self._drag_panel_id)
        if target_idx != src_idx:
            pid = self._drag_panel_id
            self._columns.remove(pid)
            self._columns.insert(target_idx, pid)
            self._repack_all()
            _save_order(self._columns)
        else:
            self._toggle_collapse(self._drag_panel_id)

        self._drag_panel_id = None

    def _resolve_target_idx(self, root_y: int) -> int:
        """Determine insertion index from mouse y_root coordinate."""
        for i, pid in enumerate(self._columns):
            if pid not in self._frames:
                continue
            wrapper = self._frames[pid]
            y0 = wrapper.winfo_rooty()
            y1 = y0 + wrapper.winfo_height()
            mid = (y0 + y1) // 2
            if root_y < mid:
                return i
        return len(self._columns)

    def _show_indicator(self, target_idx: int) -> None:
        """Show a gold horizontal line at the target drop position."""
        self._hide_indicator()
        try:
            if 0 <= target_idx < len(self._columns):
                pid = self._columns[target_idx]
                if pid in self._frames:
                    wrapper = self._frames[pid]
                    y = wrapper.winfo_rooty() - self.center.winfo_rooty() - 2
                else:
                    return
            elif target_idx >= len(self._columns) and self._columns:
                last_pid = self._columns[-1]
                if last_pid in self._frames:
                    wrapper = self._frames[last_pid]
                    y = (wrapper.winfo_rooty() - self.center.winfo_rooty()
                         + wrapper.winfo_height() + 2)
                else:
                    return
            else:
                return

            w = max(100, self.center.winfo_width() - 10)
            indicator = customtkinter.CTkFrame(
                self.center, width=w, height=3, fg_color="#D4A843",
            )
            indicator.place(x=5, y=max(0, y))
            self._drag_indicator = indicator
        except Exception:
            pass

    def _hide_indicator(self) -> None:
        if self._drag_indicator is not None:
            try:
                self._drag_indicator.destroy()
            except Exception:
                pass
            self._drag_indicator = None

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
        self._bodies.clear()
        self._chevrons.clear()
        for panel in self.panels.values():
            panel["body"] = None
