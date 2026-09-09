"""Queue popup window — shows tanks in build queue with live status dots.

Opened from BuildsPanel or StatusPanel queue tile. Contains Scan + Generate
controls and a scrollable list of tanks with colored status indicators:
  - Grey = waiting in queue
  - Yellow = currently generating
  - Green = successfully built (fades from list after 3s)
  - Red = failed (stays with reason)
"""

import customtkinter
import threading
import time
from typing import Any, Optional


class QueuePopup(customtkinter.CTkToplevel):
    """Build queue popup with live generation status."""

    _instance: Optional["QueuePopup"] = None

    def __init__(self, parent: Any, app: Any) -> None:
        if QueuePopup._instance is not None:
            try:
                QueuePopup._instance.lift()
                QueuePopup._instance.focus_force()
                return
            except Exception:
                QueuePopup._instance = None

        super().__init__(parent)
        QueuePopup._instance = self

        self.app = app
        self.title("Build Queue")
        self.geometry("560x520")
        self.minsize(400, 350)
        self.configure(fg_color="#1A1D28")
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._tank_widgets: dict = {}
        self._running = True

        self._build_ui()
        self._refresh_list()
        self._poll_progress()

    def _build_ui(self) -> None:
        header = customtkinter.CTkFrame(self, fg_color="#14161F", height=36)
        header.pack(fill="x")
        header.pack_propagate(False)

        self._title_lbl = customtkinter.CTkLabel(
            header, text="Build Queue",
            font=customtkinter.CTkFont(size=13, weight="bold"),
            text_color="#D4A843",
        )
        self._title_lbl.pack(side="left", padx=10)

        self._progress_bar = customtkinter.CTkProgressBar(
            header, width=120, height=6,
            progress_color="#D4A843", fg_color="#2E3240",
        )
        self._progress_bar.pack(side="left", padx=(8, 0))
        self._progress_bar.set(0)

        self._progress_lbl = customtkinter.CTkLabel(
            header, text="",
            font=customtkinter.CTkFont(size=10),
            text_color="#6E7284",
        )
        self._progress_lbl.pack(side="left", padx=6)

        controls = customtkinter.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=8, pady=(6, 4))

        self._scan_btn = customtkinter.CTkButton(
            controls, text="Scan", width=60, height=28,
            fg_color="transparent", hover_color="#1A1D28",
            text_color="#DDE0EA", border_width=1, border_color="#2E3240",
            command=self._on_scan,
        )
        self._scan_btn.pack(side="left", padx=2)

        self._gen_btn = customtkinter.CTkButton(
            controls, text="Generate", width=80, height=28,
            fg_color="#D4A843", hover_color="#B8922E", text_color="#12141C",
            command=self._on_generate,
        )
        self._gen_btn.pack(side="left", padx=2)

        self._status_lbl = customtkinter.CTkLabel(
            controls, text="",
            font=customtkinter.CTkFont(size=10),
            text_color="#6E7284",
        )
        self._status_lbl.pack(side="right", padx=4)

        sep = customtkinter.CTkFrame(self, height=1, fg_color="#2E3240")
        sep.pack(fill="x", padx=8)

        self._list_frame = customtkinter.CTkScrollableFrame(
            self, fg_color="#12141C",
            scrollbar_fg_color="#12141C",
            scrollbar_button_color="#2E3240",
            scrollbar_button_hover_color="#3E4250",
        )
        self._list_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def _on_scan(self) -> None:
        if hasattr(self.app, "_scan_now"):
            self.app._scan_now()

    def _on_generate(self) -> None:
        if hasattr(self.app, "_generate_now"):
            self.app._generate_now()

    def _refresh_list(self) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._tank_widgets.clear()

        gen_progress = getattr(self.app, "_gen_progress", {})
        current_tag = gen_progress.get("current_tag")
        results = gen_progress.get("results", {})
        queue = getattr(self.app, "_queue", [])

        tank_db = getattr(self.app, "tank_db", {})
        items = []
        if current_tag and current_tag in queue:
            items.append(current_tag)
        for tag in queue:
            if tag != current_tag:
                items.append(tag)

        for tag in items:
            row = customtkinter.CTkFrame(self._list_frame, fg_color="#181B26", height=28)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            canvas = customtkinter.CTkCanvas(row, width=10, height=10,
                                              bg="#181B26", highlightthickness=0)
            canvas.pack(side="left", padx=(8, 6), pady=9)

            if tag in results:
                color = "#66cc66" if results[tag] == "ok" else "#cc6666"
            elif tag == current_tag:
                color = "#ffaa00"
            else:
                color = "#6E7284"
            canvas.create_oval(1, 1, 9, 9, fill=color, outline="")

            name = tank_db.get(tag, {}).get("name", tag)
            tag_text = f"{tag}"
            name_text = f"  {name}" if name != tag else ""

            lbl = customtkinter.CTkLabel(
                row, text=tag_text,
                font=customtkinter.CTkFont(size=11, weight="bold"),
                text_color="#DDE0EA", width=140, anchor="w",
            )
            lbl.pack(side="left", padx=(0, 4))

            name_lbl = customtkinter.CTkLabel(
                row, text=name_text,
                font=customtkinter.CTkFont(size=11),
                text_color="#6E7284", anchor="w",
            )
            name_lbl.pack(side="left", fill="x", expand=True)

            status = ""
            status_color = "#6E7284"
            if tag in results:
                if results[tag] == "ok":
                    status = "OK"
                    status_color = "#66cc66"
                else:
                    reason = results[tag]
                    if reason.startswith("fail:"):
                        reason = reason[5:]
                    status = reason[:40]
                    status_color = "#cc6666"
            elif tag == current_tag:
                status = "generating..."
                status_color = "#ffaa00"
            else:
                status = "waiting"
                status_color = "#6E7284"

            st_lbl = customtkinter.CTkLabel(
                row, text=status,
                font=customtkinter.CTkFont(size=10),
                text_color=status_color, width=120, anchor="e",
            )
            st_lbl.pack(side="right", padx=8)

            self._tank_widgets[tag] = {"row": row, "canvas": canvas, "dot_color": color}

        if not items:
            lbl = customtkinter.CTkLabel(
                self._list_frame, text="Queue is empty",
                font=customtkinter.CTkFont(size=12),
                text_color="#6E7284",
            )
            lbl.pack(pady=20)

    def _poll_progress(self) -> None:
        if not self._running:
            return
        gen_progress = getattr(self.app, "_gen_progress", {})
        running = gen_progress.get("running", False)
        queue = getattr(self.app, "_queue", [])

        self._title_lbl.configure(text=f"Build Queue — {len(queue)} tanks")

        if running:
            cur, total = gen_progress.get("progress", (0, 0))
            if total > 0:
                self._progress_bar.set(cur / total)
                self._progress_lbl.configure(text=f"{cur}/{total}")
            self._gen_btn.configure(state="disabled")
            self._scan_btn.configure(state="disabled")
            current_tag = gen_progress.get("current_tag", "")
            tank_db = getattr(self.app, "tank_db", {})
            tank_name = tank_db.get(current_tag, {}).get("name", current_tag)
            self._status_lbl.configure(text=f"Building: {tank_name}", text_color="#ffaa00")
        else:
            self._progress_bar.set(0)
            self._progress_lbl.configure(text="")
            self._gen_btn.configure(state="normal")
            self._scan_btn.configure(state="normal")
            results = gen_progress.get("results", {})
            if results:
                ok = sum(1 for v in results.values() if v == "ok")
                fail = sum(1 for v in results.values() if v != "ok")
                self._status_lbl.configure(
                    text=f"Done: {ok} ok, {fail} fail", text_color="#66cc66")
            elif queue:
                self._status_lbl.configure(
                    text=f"{len(queue)} tanks in queue", text_color="#6E7284")
            else:
                self._status_lbl.configure(text="", text_color="#6E7284")

        self._refresh_list()
        self.after(500, self._poll_progress)

    def _on_close(self) -> None:
        self._running = False
        QueuePopup._instance = None
        self.destroy()
