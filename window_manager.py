import ctypes
import tkinter as tk
import sys
import threading
import time
try:
    import mouse
except ImportError:
    mouse = None

# Константи для Click-through та WinAPI
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20
GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_CLIPSIBLINGS = 0x04000000
WS_POPUP = 0x80000000
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_CAPTION = WS_BORDER | WS_DLGFRAME
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000

WS_EX_APPWINDOW = 0x00040000
WS_EX_WINDOWEDGE = 0x00000100
WS_EX_CLIENTEDGE = 0x00000200
WS_EX_DLGMODALFRAME = 0x00000001

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

# Обгортки для 32/64-бітних викликів Get/SetWindowLong
is_64bits = sys.maxsize > 2**32

def _get_window_long(hwnd, index):
    if is_64bits:
        func = ctypes.windll.user32.GetWindowLongPtrW
        func.restype = ctypes.c_longlong
        func.argtypes = [ctypes.c_void_p, ctypes.c_int]
    else:
        func = ctypes.windll.user32.GetWindowLongW
        func.restype = ctypes.c_long
        func.argtypes = [ctypes.c_void_p, ctypes.c_int]
    return func(hwnd, index)


def _set_window_long(hwnd, index, new_long):
    if is_64bits:
        func = ctypes.windll.user32.SetWindowLongPtrW
        func.restype = ctypes.c_longlong
        func.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
    else:
        func = ctypes.windll.user32.SetWindowLongW
        func.restype = ctypes.c_long
        func.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    return func(hwnd, index, new_long)

SetWindowPos = ctypes.windll.user32.SetWindowPos
SetWindowPos.restype = ctypes.c_bool
SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]

class WindowManager:
    def __init__(self, app):
        """
        app - це посилання на головний клас WotAssistantHQ.
        """
        self.app = app
        self.drag = None
        self.mouse_drag_active = False
        self.mouse_last_pos = None
        self.drag_thread = None
        self.drag_running = False
        self.ctrl_press_time = None  # Час першого натиску Ctrl
        self.ctrl_double_tap_active = False  # Статус подвійного натиску
        self.ctrl_arm_timeout = 2.0  # Час дії "озброєного" режиму після подвійного Ctrl
        self.ctrl_armed_until = 0.0
        self.format_mode_enabled = False  # Ручний режим форматування (вмикається в edit)
        self._last_tomato_size = None
        
        # Запуск моніторингу миші для drag
        self.start_mouse_drag_monitor()

    def initialize_window(self):
        root = self.app.root
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        cfg_max_w = int(self.app.settings.get("max_window_w", 1000))
        self.app.max_window_w = max(500, min(cfg_max_w, max(500, sw - 40)))
        
        self.app.w = self.app.settings.get("edit_w", 800)
        self.app.w = max(500, min(int(self.app.w), self.app.max_window_w))
        self.app.h = self.app.settings.get("edit_h", self.app.w + 160)
        self.app.alpha = self.app.settings.get("edit_alpha", 1.0)
        self.app.alpha = max(0.1, min(float(self.app.alpha), 1.0))
        self.app.contrast = self.app.settings.get("edit_contrast", 1.0)
        
        px = self.app.settings.get("edit_x", (sw - self.app.w) // 2)
        py = self.app.settings.get("edit_y", (sh - self.app.h) // 2)
        cx = self.app.settings.get("edit_cx", px + self.app.w // 2)
        cy = self.app.settings.get("edit_cy", py + self.app.h // 2)
        px = max(0, min(int(cx - self.app.w // 2), max(0, sw - self.app.w)))
        py = max(0, min(int(cy - self.app.h // 2), max(0, sh - self.app.h)))
        
        root.geometry(f"{self.app.w}x{self.app.h}+{px}+{py}")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg="black")
        root.attributes("-alpha", self.app.alpha)

    def start_mouse_drag_monitor(self):
        """Запуск моніторингу Ctrl+ЛКМ для drag"""
        if self.drag_running: return
        self.drag_running = True
        self.drag_thread = threading.Thread(target=self._monitor_mouse_drag, daemon=True)
        self.drag_thread.start()

    def _monitor_mouse_drag(self):
        """Моніторинг стану миші для Ctrl (подвійний натиск) + ЛКМ drag"""
        try:
            ctrl_was_pressed = False
            while self.drag_running:
                # Перевіряємо чи натиснута Ctrl + ЛКМ
                ctrl_pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)  # VK_CONTROL
                lmb_pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)  # VK_LBUTTON
                
                # Відслідковуємо подвійне натиснення Ctrl
                if ctrl_pressed and not ctrl_was_pressed:
                    current_time = time.time()
                    if self.ctrl_press_time and (current_time - self.ctrl_press_time) < 0.3:
                        self._arm_ctrl_controls()  # Подвійне натиснення в межах 300мс
                        self.ctrl_press_time = None
                    else:
                        self.ctrl_press_time = current_time  # Перше натиснення
                    ctrl_was_pressed = True
                elif not ctrl_pressed and ctrl_was_pressed:
                    ctrl_was_pressed = False

                # Авто-вимкнення "озброєного" режиму після таймауту
                if self.ctrl_double_tap_active and time.time() > self.ctrl_armed_until and not self.mouse_drag_active:
                    self._disarm_ctrl_controls()

                painter_move_active = hasattr(self.app, "painter") and getattr(self.app.painter, "move_drag_active", False)

                # У форматуванні (F8) дозволяємо перетягування ЛКМ без Ctrl (будь-який режим)
                drag_ready = lmb_pressed and not painter_move_active and (
                    self.format_mode_enabled or
                    (self._is_ctrl_armed() and ctrl_pressed)
                )

                if drag_ready:
                    if not self.mouse_drag_active:
                        # Початок drag
                        if self.app.dialog_open: 
                            time.sleep(0.1)
                            continue
                        self.mouse_drag_active = True
                        # Тимчасово вимикаємо click-through для захоплення фокуса
                        if self.app.mode == "norm":  # тільки в бойовому режимі
                            self.set_clickthrough(False)
                        # Фокусуємо вікно для захоплення подій
                        self.app.root.focus_force()
                        # Отримуємо поточну позицію курсора
                        point = ctypes.wintypes.POINT()
                        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
                        self.mouse_last_pos = (point.x, point.y)
                        print(f"[DRAG] Початок drag Ctrl(x2)+ЛКМ: {self.mouse_last_pos}")
                    
                    # Продовження drag
                    point = ctypes.wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
                    current_pos = (point.x, point.y)
                    
                    if self.mouse_last_pos and self.app.root.winfo_viewable():
                        dx, dy = current_pos[0] - self.mouse_last_pos[0], current_pos[1] - self.mouse_last_pos[1]
                        if abs(dx) > 0 or abs(dy) > 0:  # Рух тільки якщо є зміна
                            root = self.app.root
                            root.geometry(f"+{root.winfo_x()+dx}+{root.winfo_y()+dy}")
                    
                    self.mouse_last_pos = current_pos
                else:
                    if self.mouse_drag_active:
                        # Кінець drag
                        self.mouse_drag_active = False
                        self.mouse_last_pos = None
                        # Відновлюємо click-through якщо ми в бойовому режимі
                        if self.app.mode == "norm" and not self.format_mode_enabled:
                            self.set_clickthrough(True)
                        self.app.save_settings()
                        if hasattr(self.app, '_sync_po_pos'): self.app._sync_po_pos()
                        print("[DRAG] Кінець drag")
                
                time.sleep(0.016)  # ~60 FPS
                
        except Exception as e:
            print(f"[DRAG] Помилка в mouse monitor: {e}")
        finally:
            self.drag_running = False

    def stop_mouse_drag_monitor(self):
        """Зупинка моніторингу миші для drag"""
        self.drag_running = False
        if self.drag_thread and self.drag_thread.is_alive():
            self.drag_thread.join(timeout=1.0)

    def _arm_ctrl_controls(self):
        self.ctrl_double_tap_active = True
        self.ctrl_armed_until = time.time() + self.ctrl_arm_timeout

    def _disarm_ctrl_controls(self):
        self.ctrl_double_tap_active = False
        self.ctrl_armed_until = 0.0

    def set_format_mode(self, enabled):
        """Явно вмикає/вимикає режим форматування незалежно від double-Ctrl."""
        self.format_mode_enabled = bool(enabled)
        if not self.format_mode_enabled:
            self._disarm_ctrl_controls()

    def _is_ctrl_armed(self):
        return self.format_mode_enabled or (self.ctrl_double_tap_active and time.time() <= self.ctrl_armed_until)

    def bind_controls(self, top_bar, canvas):
        root = self.app.root
        root.bind("<Control-Up>", self.resize_up)
        root.bind("<Control-Down>", self.resize_down)
        root.bind("<Control-Right>", self.alpha_up)
        root.bind("<Control-Left>", self.alpha_down)
        root.bind("<Control-Shift-Up>", self.contrast_up)
        root.bind("<Control-Shift-Down>", self.contrast_down)
        top_bar.bind("<Control-Button-1>", self.start_win_move)
        top_bar.bind("<Control-B1-Motion>", self.do_win_move)
        top_bar.bind("<Control-ButtonRelease-1>", self.stop_win_move)
        canvas.bind("<Control-Button-1>", self.start_win_move)
        canvas.bind("<Control-B1-Motion>", self.do_win_move)
        canvas.bind("<Control-ButtonRelease-1>", self.stop_win_move)
        
        # Додаємо глобальну обробку Alt+ЛКМ для бойового режиму
        if mouse:
            self._setup_mouse_drag()

    def _setup_mouse_drag(self):
        """Обробка Ctrl+ЛКМ для перетягування вікна у бойовому режимі"""
        import keyboard
        
        def on_mouse_move(event):
            if not self.mouse_drag_active or not keyboard.is_pressed('alt'):
                self.mouse_drag_active = False
                return
            
            if self.mouse_last_pos:
                dx = event.x - self.mouse_last_pos[0]
                dy = event.y - self.mouse_last_pos[1]
                root = self.app.root
                root.geometry(f"+{root.winfo_x() + dx}+{root.winfo_y() + dy}")
            
            self.mouse_last_pos = (event.x, event.y)
        
        def on_mouse_click(event):
            if event.button == 'left' and keyboard.is_pressed('alt'):
                self.mouse_drag_active = True
                self.mouse_last_pos = (event.x, event.y)
        
        def on_mouse_release(event):
            if event.button == 'left':
                self.mouse_drag_active = False
                self.mouse_last_pos = None
                self.app.save_settings()
                if hasattr(self.app, '_sync_po_pos'): self.app._sync_po_pos()

        def on_any_mouse_event(event):
            et = getattr(event, "event_type", None)
            btn = getattr(event, "button", None)

            if et == "move":
                on_mouse_move(event)
            elif et in ("down", "double") and btn == "left":
                on_mouse_click(event)
            elif et == "up" and btn == "left":
                on_mouse_release(event)

        # Підписуємось з урахуванням різних версій бібліотеки mouse.
        has_on_move = hasattr(mouse, "on_move")
        has_on_click = hasattr(mouse, "on_click")
        has_on_release = hasattr(mouse, "on_release")

        if has_on_move and has_on_click and has_on_release:
            mouse.on_move(on_mouse_move)
            mouse.on_click(on_mouse_click)
            mouse.on_release(on_mouse_release)
        elif hasattr(mouse, "hook"):
            mouse.hook(on_any_mouse_event)

    def toggle_visibility(self):
        if self.app.dialog_open: return 
        if self.app.root.winfo_viewable(): 
            self.app.root.withdraw()
        else: 
            self.app.root.deiconify()

    def start_win_move(self, e): 
        if not self._is_ctrl_armed():
            return
        self.drag = {"x": e.x, "y": e.y}

    def do_win_move(self, e):
        if not self._is_ctrl_armed():
            self.drag = None
            return
        if self.drag:
            dx, dy = e.x - self.drag["x"], e.y - self.drag["y"]
            root = self.app.root
            root.geometry(f"+{root.winfo_x()+dx}+{root.winfo_y()+dy}")

    def stop_win_move(self, e):
        self.drag = None
        self.app.save_settings()
        if hasattr(self.app, '_sync_po_pos'): self.app._sync_po_pos()

    def resize_up(self, e): 
        if not self._is_ctrl_armed():
            return "break"
        self.apply_anchor_resize(1 if self.app.mode == "norm" else 20)
        return "break"
    
    def resize_up_hotkey(self):
        """Обгортка для глобального hotkey (без event)"""
        if self.app.dialog_open or not self._is_ctrl_armed(): return
        self.apply_anchor_resize(1 if self.app.mode == "norm" else 20)

    def resize_down(self, e):
        if not self._is_ctrl_armed():
            return "break"
        step = 1 if self.app.mode == "norm" else 20
        if self.app.mode == "edit":
            min_width = self.app.filters_container.winfo_reqwidth() - step
            if min_width < 500: min_width = 500
        else: min_width = 150
        if self.app.w - step >= min_width: self.apply_anchor_resize(-step)
        return "break"
    
    def resize_down_hotkey(self):
        """Обгортка для глобального hotkey (без event)"""
        if self.app.dialog_open or not self._is_ctrl_armed(): return
        step = 1 if self.app.mode == "norm" else 20
        if self.app.mode == "edit":
            min_width = self.app.filters_container.winfo_reqwidth() - step
            if min_width < 500: min_width = 500
        else: min_width = 150
        if self.app.w - step >= min_width: self.apply_anchor_resize(-step)

    def apply_anchor_resize(self, delta):
        cur_x, cur_y = self.app.root.winfo_x(), self.app.root.winfo_y()
        old_w = self.app.w
        self.app.w += delta
        min_w = 500 if self.app.mode == "edit" else 150
        max_w = getattr(self.app, "max_window_w", 1000)
        self.app.w = max(self.app.w, min_w)
        self.app.w = min(self.app.w, max_w)
        self.app.h = self.app.w + (self.app.get_edit_extra_height() if self.app.mode == "edit" else 18)
        actual_delta = self.app.w - old_w
        self.app.root.geometry(f"{self.app.w}x{self.app.h}+{cur_x - actual_delta}+{cur_y - actual_delta}")
        
        if hasattr(self.app, '_resize_timer') and self.app._resize_timer: 
            self.app.root.after_cancel(self.app._resize_timer)
        self.app._resize_timer = self.app.root.after(100, self.app.map_renderer.show_main_splash)
        self.app.save_settings()

    def alpha_up(self, e):
        if self.app.dialog_open or not self._is_ctrl_armed(): return "break"
        self.app.alpha = min(1.0, self.app.alpha + 0.05)
        self.app.root.attributes("-alpha", self.app.alpha)
        self.app.save_settings()
        return "break"
    
    def alpha_up_hotkey(self):
        """Обгортка для глобального hotkey (без event)"""
        if self.app.dialog_open or not self._is_ctrl_armed(): return
        self.app.alpha = min(1.0, self.app.alpha + 0.05)
        self.app.root.attributes("-alpha", self.app.alpha)
        self.app.save_settings()

    def alpha_down(self, e):
        if self.app.dialog_open or not self._is_ctrl_armed(): return "break"
        self.app.alpha = max(0.1, self.app.alpha - 0.05)
        self.app.root.attributes("-alpha", self.app.alpha)
        self.app.save_settings()
        return "break"
    
    def alpha_down_hotkey(self):
        """Обгортка для глобального hotkey (без event)"""
        if self.app.dialog_open or not self._is_ctrl_armed(): return
        self.app.alpha = max(0.1, self.app.alpha - 0.05)
        self.app.root.attributes("-alpha", self.app.alpha)
        self.app.save_settings()

    def contrast_up(self, e):
        if self.app.dialog_open or not self._is_ctrl_armed(): return "break"
        self.app.contrast = min(2.0, self.app.contrast + 0.1)
        self.app.save_settings()
        self.app.map_renderer.show_main_splash()
        return "break"
    
    def contrast_up_hotkey(self):
        """Обгортка для глобального hotkey (без event)"""
        if self.app.dialog_open or not self._is_ctrl_armed(): return
        self.app.contrast = min(2.0, self.app.contrast + 0.1)
        self.app.save_settings()
        self.app.map_renderer.show_main_splash()

    def contrast_down(self, e):
        if self.app.dialog_open or not self._is_ctrl_armed(): return "break"
        self.app.contrast = max(0.5, self.app.contrast - 0.1)
        self.app.save_settings()
        self.app.map_renderer.show_main_splash()
        return "break"
    
    def contrast_down_hotkey(self):
        """Обгортка для глобального hotkey (без event)"""
        if self.app.dialog_open or not self._is_ctrl_armed(): return
        self.app.contrast = max(0.5, self.app.contrast - 0.1)
        self.app.save_settings()
        self.app.map_renderer.show_main_splash()

    def set_clickthrough(self, enabled):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.app.root.winfo_id())
            style = _get_window_long(hwnd, GWL_EXSTYLE)
            if enabled:
                style |= (WS_EX_LAYERED | WS_EX_TRANSPARENT)
            else:
                style &= ~WS_EX_TRANSPARENT
            _set_window_long(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def focus_game_window(self):
        """Повертає фокус у вікно гри World of Tanks."""
        try:
            user32 = ctypes.windll.user32
            game_hwnd = user32.FindWindowW(None, "World of Tanks")
            if not game_hwnd:
                candidates = []

                @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                def enum_proc(hwnd, _):
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length <= 0:
                        return True
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = (buf.value or "").lower()
                    if "world of tanks" in title or "wot" in title:
                        candidates.append(hwnd)
                    return True

                user32.EnumWindows(enum_proc, 0)
                if candidates:
                    game_hwnd = candidates[0]
            if not game_hwnd:
                return False
            user32.ShowWindow(game_hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(game_hwnd)
            return True
        except Exception:
            return False

    def dock_tomato_window(self, attempt=0):
        app = self.app
        if not hasattr(app, 'tomato') or not app.tomato or not app.tomato.proc: 
            return
        
        if not app.tomato.proc.is_alive():
            return

        hwnd = ctypes.windll.user32.FindWindowW(None, "WoT_Tomato_Hidden_Window")
        
        if hwnd:
            frame_hwnd = app.browser_frame.winfo_id()
            ctypes.windll.user32.SetParent(hwnd, frame_hwnd)
            style = _get_window_long(hwnd, GWL_STYLE)
            style &= ~(WS_POPUP | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
            style |= (WS_CHILD | WS_CLIPSIBLINGS)
            _set_window_long(hwnd, GWL_STYLE, style)

            exstyle = _get_window_long(hwnd, GWL_EXSTYLE)
            exstyle &= ~(WS_EX_APPWINDOW | WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE | WS_EX_DLGMODALFRAME)
            _set_window_long(hwnd, GWL_EXSTYLE, exstyle)

            app.tomato_hwnd = hwnd
            self._last_tomato_size = None
            self.resize_tomato_window()
            SetWindowPos(hwnd, None, 0, 0, app.browser_frame.winfo_width(), app.browser_frame.winfo_height(), SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
            app.root.after(700, self.tomato_watcher)
        else:
            if attempt > 100:
                return
                
            app.root.after(100, lambda: self.dock_tomato_window(attempt + 1))

    def tomato_watcher(self):
        app = self.app
        if app.tomato_hwnd and app.btn_mode_stats.cget("bg") == "#d32f2f":
            self.resize_tomato_window()
            app.root.after(700, self.tomato_watcher)

    def resize_tomato_window(self, event=None):
        app = self.app
        if hasattr(app, 'tomato_hwnd') and app.tomato_hwnd:
            w = app.browser_frame.winfo_width()
            h = app.browser_frame.winfo_height()
            if w > 10 and h > 10:
                size = (w, h)
                if size != self._last_tomato_size:
                    ctypes.windll.user32.MoveWindow(app.tomato_hwnd, 0, 0, w, h, True)
                    self._last_tomato_size = size
