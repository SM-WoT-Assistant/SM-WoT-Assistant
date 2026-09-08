"""Admin UI design tokens, button factories, and reusable widgets.

Adapted from AI Project Studio ui/widgets.py — admin-specific color tokens
(orange accent matching existing admin_app.py), button factories, StatusPill,
card widget, and empty_state placeholder.
"""

import customtkinter
from typing import Any, Dict, Optional, Tuple

# --- design tokens ---

DARK_BG = "#1a1a1a"
DARK_BG2 = "#222222"
DARK_FG = "#cccccc"

CANVAS_BG: Dict[str, str] = {"dark": "#0E0E13", "light": "#E6E6EB"}
SURFACE_BG: Dict[str, str] = {"dark": "#14161F", "light": "#DFDFE4"}
SURFACE_HOVER: Dict[str, str] = {"dark": "#1A1D28", "light": "#D0D0D8"}
PRIMARY: Dict[str, str] = {"dark": "#D4A843", "light": "#B08830"}
PRIMARY_HOVER: Dict[str, str] = {"dark": "#C09832", "light": "#9A7828"}
NAV_PILL_ACTIVE: Dict[str, str] = {"dark": "#D4A843", "light": "#B08830"}
NAV_PILL_HOVER: Dict[str, str] = {"dark": "#2A2536", "light": "#C8C8D0"}
TEXT: Dict[str, str] = {"dark": "#DDE0EA", "light": "#1C1E26"}
TEXT_MUTED: Dict[str, str] = {"dark": "#6E7284", "light": "#8A8E9C"}
TEXT_ON_ACCENT: Dict[str, str] = {"dark": "#1C1E26", "light": "#FFFFFF"}
ACCENT: Dict[str, str] = {"dark": "#D4A843", "light": "#B08830"}
OUTLINE: Dict[str, str] = {"dark": "#2E3240", "light": "#AEB2C0"}

STATUS_COLORS: Dict[str, str] = {
    "idle": "#66cc66",
    "generating": "#ffaa00",
    "error": "#cc6666",
    "online": "#66cc66",
    "offline": "#cc6666",
    "warning": "#ffaa00",
}

ICONS = {
    "status": "\u25cf",
    "builds": "\u2699",
    "community": "\u2605",
    "errors": "\u2716",
    "log": "\u2630",
    "scan": "\u21bb",
    "generate": "\u25b6",
    "settings": "\u2699",
    "close": "\u2715",
    "refresh": "\u21bb",
    "grip": "\u2261",
}


def _mode() -> str:
    return customtkinter.get_appearance_mode().lower()


def _token(d: Dict[str, str]) -> str:
    return d[_mode()]


# --- button factories ---


def primary_button(
    parent: Any,
    text: str,
    command: Optional[Any] = None,
    width: int = 120,
    height: int = 32,
    **kw: Any,
) -> customtkinter.CTkButton:
    btn = customtkinter.CTkButton(
        parent,
        text=text,
        command=command,
        width=width,
        height=height,
        fg_color=_token(PRIMARY),
        hover_color=_token(PRIMARY_HOVER),
        text_color=_token(TEXT_ON_ACCENT),
        corner_radius=6,
        **kw,
    )
    return btn


def ghost_button(
    parent: Any,
    text: str,
    command: Optional[Any] = None,
    width: int = 100,
    height: int = 28,
    **kw: Any,
) -> customtkinter.CTkButton:
    btn = customtkinter.CTkButton(
        parent,
        text=text,
        command=command,
        width=width,
        height=height,
        fg_color="transparent",
        hover_color=_token(SURFACE_HOVER),
        text_color=_token(TEXT),
        corner_radius=6,
        border_width=1,
        border_color=_token(OUTLINE),
        **kw,
    )
    return btn


def nav_button(
    parent: Any,
    text: str,
    command: Optional[Any] = None,
    width: int = 100,
    height: int = 28,
) -> customtkinter.CTkButton:
    btn = customtkinter.CTkButton(
        parent,
        text=text,
        command=command,
        width=width,
        height=height,
        fg_color="transparent",
        hover_color=_token(NAV_PILL_HOVER),
        text_color=_token(TEXT_MUTED),
        corner_radius=1000,
    )
    return btn


def set_nav_active(button: customtkinter.CTkButton, active: bool) -> None:
    if active:
        button.configure(
            fg_color=_token(NAV_PILL_ACTIVE),
            text_color=_token(TEXT_ON_ACCENT),
        )
    else:
        button.configure(
            fg_color="transparent",
            text_color=_token(TEXT_MUTED),
        )


# --- widgets ---


class StatusPill(customtkinter.CTkFrame):
    def __init__(
        self,
        parent: Any,
        text: str = "",
        status: str = "idle",
        **kw: Any,
    ) -> None:
        super().__init__(parent, fg_color="transparent", **kw)
        color = STATUS_COLORS.get(status, TEXT_MUTED[_mode()])
        self._dot = customtkinter.CTkLabel(
            self, text="\u25cf", text_color=color, font=customtkinter.CTkFont(size=10),
            width=12,
        )
        self._dot.pack(side="left", padx=(0, 4))
        self._label = customtkinter.CTkLabel(
            self, text=text, font=customtkinter.CTkFont(size=11),
            text_color=_token(TEXT_MUTED),
        )
        self._label.pack(side="left")

    def set_status(self, text: str, status: str) -> None:
        color = STATUS_COLORS.get(status, TEXT_MUTED[_mode()])
        self._label.configure(text=text)
        self._dot.configure(text_color=color)


def status_pill(parent: Any, text: str, status: str = "idle") -> StatusPill:
    return StatusPill(parent, text=text, status=status)


def card(
    parent: Any,
    title: str,
    value: str = "",
    subtitle: str = "",
    width: int = 200,
    height: int = 80,
    command: Any = None,
    **kw: Any,
) -> customtkinter.CTkFrame:
    frame = customtkinter.CTkFrame(parent, width=width, height=height, **kw)
    frame.pack_propagate(False)
    title_lbl = customtkinter.CTkLabel(
        frame, text=title, font=customtkinter.CTkFont(size=11),
        text_color=_token(TEXT_MUTED), anchor="w",
    )
    title_lbl.pack(fill="x", padx=10, pady=(8, 0))
    val_lbl = customtkinter.CTkLabel(
        frame, text=value, font=customtkinter.CTkFont(size=18, weight="bold"),
        text_color=_token(TEXT), anchor="w",
    )
    val_lbl.pack(fill="x", padx=10)
    sub_lbl = None
    if subtitle:
        sub_lbl = customtkinter.CTkLabel(
            frame, text=subtitle, font=customtkinter.CTkFont(size=10),
            text_color=_token(TEXT_MUTED), anchor="w",
        )
        sub_lbl.pack(fill="x", padx=10, pady=(0, 6))
    frame._val_lbl = val_lbl  # type: ignore[attr-defined]
    frame._sub_lbl = sub_lbl  # type: ignore[attr-defined]
    if command:
        for widget in (frame, title_lbl, val_lbl):
            widget.bind("<Button-1>", lambda e, cmd=command: cmd())
        frame.configure(cursor="hand2")
    return frame


def empty_state(
    parent: Any,
    text: str = "No data",
    hint: str = "",
    button_text: str = "",
    command: Optional[Any] = None,
) -> customtkinter.CTkFrame:
    frame = customtkinter.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="both", expand=True)
    lbl = customtkinter.CTkLabel(
        frame, text=text, font=customtkinter.CTkFont(size=14),
        text_color=_token(TEXT_MUTED),
    )
    lbl.pack(pady=(60, 8))
    if hint:
        hlbl = customtkinter.CTkLabel(
            frame, text=hint, font=customtkinter.CTkFont(size=11),
            text_color=_token(TEXT_MUTED),
        )
        hlbl.pack(pady=(0, 8))
    if button_text and command:
        primary_button(frame, button_text, command=command).pack(pady=8)
    return frame
