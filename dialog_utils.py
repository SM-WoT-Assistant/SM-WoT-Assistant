import tkinter as tk
import ctypes
from ctypes import wintypes

def _set_dark_title_bar(window):
    try:
        window.update_idletasks()
        dwm = ctypes.windll.dwmapi
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark = ctypes.c_int(1)
        hWnd = wintypes.HWND(int(window.winfo_id()))
        dwm.DwmSetWindowAttribute(hWnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), ctypes.sizeof(dark))
    except Exception:
        pass

class _DragHelper:
    def __init__(self, toplevel, frame):
        self.tl = toplevel; self.x = 0; self.y = 0
        frame.bind("<Button-1>", self.start)
        frame.bind("<B1-Motion>", self.drag)
    def start(self, e):
        self.x = e.x_root - self.tl.winfo_rootx()
        self.y = e.y_root - self.tl.winfo_rooty()
    def drag(self, e):
        self.tl.geometry(f"+{e.x_root - self.x}+{e.y_root - self.y}")

def _center_on_root(dlg, parent):
    dlg.update_idletasks()
    try:
        rx = parent.winfo_x()
        ry = parent.winfo_y()
        rw = parent.winfo_width()
        rh = parent.winfo_height()
        dw = dlg.winfo_reqwidth()
        dh = dlg.winfo_reqheight()
        x = rx + max(0, (rw - dw) // 2)
        y = ry + max(0, (rh - dh) // 2)
        dlg.geometry(f"+{x}+{y}")
    except Exception:
        pass

def dark_messagebox(parent, title, message, is_error=False):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg="#222")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.attributes("-topmost", True)
    _set_dark_title_bar(dlg)
    dlg.grab_set()
    dlg.lift()
    dlg.focus_force()

    tk.Label(dlg, text=title, bg="#222", fg="#ffaa00",
             font=("Arial", 10, "bold")).pack(padx=20, pady=(14, 6))
    tk.Label(dlg, text=message, bg="#222",
             fg="#ff6666" if is_error else "#cccccc",
             font=("Arial", 9), wraplength=360, justify="left").pack(padx=20, pady=(4, 12))
    bf = tk.Frame(dlg, bg="#222")
    bf.pack(pady=(0, 12))
    btn_bg = "#664444" if is_error else "#446644"
    btn_fg = "#fcc" if is_error else "#cfc"
    tk.Button(bf, text="OK", bg=btn_bg, fg=btn_fg, bd=0,
              font=("Arial", 9, "bold"), padx=20, pady=4,
              command=dlg.destroy).pack()

    _center_on_root(dlg, parent)
    parent.wait_window(dlg)

def dark_confirmbox(parent, title, message, yes_text="Yes", no_text="No"):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg="#222")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.attributes("-topmost", True)
    _set_dark_title_bar(dlg)
    dlg.grab_set()
    dlg.lift()
    dlg.focus_force()

    result = [False]
    def on_yes():
        result[0] = True
        dlg.destroy()
    def on_no():
        dlg.destroy()

    tk.Label(dlg, text=title, bg="#222", fg="#ffaa00",
             font=("Arial", 10, "bold")).pack(padx=20, pady=(14, 6))
    tk.Label(dlg, text=message, bg="#222", fg="#cccccc",
             font=("Arial", 9), wraplength=360, justify="left").pack(padx=20, pady=(4, 12))

    bf = tk.Frame(dlg, bg="#222")
    bf.pack(pady=(0, 12))
    tk.Button(bf, text=yes_text, bg="#553333", fg="#ff6666", bd=0,
              font=("Arial", 9, "bold"), padx=15, pady=4,
              command=on_yes).pack(side="left", padx=6)
    tk.Button(bf, text=no_text, bg="#444", fg="#aaa", bd=0,
              font=("Arial", 9), padx=15, pady=4,
              command=on_no).pack(side="left", padx=6)

    _center_on_root(dlg, parent)
    parent.wait_window(dlg)
    return result[0]

def dark_promptbox(parent, title, prompt, initialvalue=""):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg="#222")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.attributes("-topmost", True)
    _set_dark_title_bar(dlg)
    dlg.grab_set()
    dlg.lift()
    dlg.focus_force()

    tk.Label(dlg, text=title, bg="#222", fg="#ffaa00",
             font=("Arial", 10, "bold")).pack(padx=20, pady=(14, 4))
    tk.Label(dlg, text=prompt, bg="#222", fg="#ccc",
             font=("Arial", 9)).pack(padx=20, pady=(0, 8))

    var = tk.StringVar(value=initialvalue)
    entry = tk.Entry(dlg, textvariable=var, font=("Arial", 11),
                     bg="#333", fg="white", insertbackground="white",
                     width=30, relief="flat", bd=4)
    entry.pack(padx=20, pady=(0, 10))
    entry.select_range(0, "end")
    entry.focus_set()

    result = [None]
    def on_ok():
        result[0] = var.get()
        dlg.destroy()
    def on_cancel():
        result[0] = None
        dlg.destroy()
    entry.bind("<Return>", lambda e: on_ok())
    entry.bind("<Escape>", lambda e: on_cancel())

    bf = tk.Frame(dlg, bg="#222")
    bf.pack(pady=(0, 12))
    tk.Button(bf, text="OK", bg="#446644", fg="#cfc", bd=0,
              font=("Arial", 9, "bold"), padx=20, pady=4,
              command=on_ok).pack(side="left", padx=6)
    tk.Button(bf, text="Cancel", bg="#444", fg="#aaa", bd=0,
              font=("Arial", 9), padx=12, pady=4,
              command=on_cancel).pack(side="left", padx=6)

    _center_on_root(dlg, parent)
    parent.wait_window(dlg)
    return result[0]
