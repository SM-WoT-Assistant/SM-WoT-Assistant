"""Admin panels — simple embedded CTkFrame grid layout.

Panels are CTkFrame children inside the main window's center area,
arranged horizontally via grid with equal weight. No separate windows,
no drag/drop, no persistence file, no flickering.

Usage:
    dock = PanelDock(center_frame)
    dock.add_panel("status", "Status", build_fn, refresh_fn)
    dock.refresh()
"""

import logging
from typing import Any, Callable, Dict, List, Optional

import customtkinter

logger = logging.getLogger(__name__)

STATE_DOCKED_LEFT = "docked_left"
STATE_DOCKED_RIGHT = "docked_right"


class PanelDock:
    """Manages embedded CTkFrame panels in a horizontal grid layout."""

    def __init__(self, center_widget: Any) -> None:
        self.center = center_widget
        self.panels: Dict[str, Dict[str, Any]] = {}
        self._frames: Dict[str, customtkinter.CTkFrame] = {}
        self._columns: List[str] = []

    def add_panel(
        self,
        panel_id: str,
        title: str,
        icon_id: str,
        build: Callable[[Any], Any],
        refresh: Optional[Callable[[Any], None]] = None,
        default_dock: str = STATE_DOCKED_RIGHT,
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
        self.center.grid_columnconfigure(0, weight=1)
        for col_idx, panel_id in enumerate(self._columns):
            panel = self.panels[panel_id]
            self.center.grid_columnconfigure(col_idx, weight=1, minsize=200)

            wrapper = customtkinter.CTkFrame(
                self.center, fg_color="#14161F", corner_radius=6,
            )
            wrapper.grid(row=0, column=col_idx, sticky="nsew", padx=3, pady=3)

            header = customtkinter.CTkFrame(wrapper, height=30, fg_color="#181B26", corner_radius=6)
            header.pack(fill="x")
            header.pack_propagate(False)
            customtkinter.CTkLabel(
                header, text=f"  {panel['title']}",
                font=customtkinter.CTkFont(size=12, weight="bold"),
                text_color="#D4A843", anchor="w",
            ).pack(side="left", fill="y", padx=4)

            body_container = customtkinter.CTkFrame(wrapper, fg_color="transparent")
            body_container.pack(fill="both", expand=True, padx=2, pady=(2, 4))

            content = panel["build"](body_container)
            content.pack(fill="both", expand=True)
            panel["body"] = content

            self._frames[panel_id] = wrapper

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
        for frame in self._frames.values():
            try:
                frame.destroy()
            except Exception:
                pass
        self._frames.clear()
        for panel in self.panels.values():
            panel["body"] = None
