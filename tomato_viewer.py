# tomato_viewer_4_09.py
try:
    import webview
    WEBVIEW_AVAILABLE = True
except ImportError:
    WEBVIEW_AVAILABLE = False

# ВАЖЛИВО: QtWebEngine backend вимкнено через стабільно високе CPU (idle).
QWEB_ENGINE_AVAILABLE = False

import webbrowser
import multiprocessing
import os
import psutil
import subprocess
import sys
import ctypes

# Мінімізуємо шум вбудованого браузера у консолі.

# --- КОНСТАНТИ WINDOWS ДЛЯ JOB OBJECTS (з версії 4.04) ---
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOBOBJECT_EXTENDED_LIMIT_INFORMATION = 9

class struct_IO_COUNTERS(ctypes.Structure):
    _fields_ = [('ReadOperationCount', ctypes.c_uint64), ('WriteOperationCount', ctypes.c_uint64), ('OtherOperationCount', ctypes.c_uint64), ('ReadTransferCount', ctypes.c_uint64), ('WriteTransferCount', ctypes.c_uint64), ('OtherTransferCount', ctypes.c_uint64)]

class struct_JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', ctypes.c_uint32), ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', ctypes.c_uint32), ('Affinity', ctypes.c_size_t), ('PriorityClass', ctypes.c_uint32), ('SchedulingClass', ctypes.c_uint32)]

class struct_JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', struct_JOBOBJECT_BASIC_LIMIT_INFORMATION), ('IoCounters', struct_IO_COUNTERS), ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t), ('PeakProcessMemoryLimit', ctypes.c_size_t), ('PeakJobMemoryLimit', ctypes.c_size_t)]

class WindowsJobManager:
    def __init__(self):
        self.job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
        info = struct_JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ctypes.windll.kernel32.SetInformationJobObject(
            self.job_handle, JOBOBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)
        )

    def add_process(self, pid):
        process_handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
        if process_handle:
            ctypes.windll.kernel32.AssignProcessToJobObject(self.job_handle, process_handle)
            ctypes.windll.kernel32.CloseHandle(process_handle)

    def terminate_all(self):
        if self.job_handle:
            ctypes.windll.kernel32.TerminateJobObject(self.job_handle, 1)

    def close(self):
        if self.job_handle:
            ctypes.windll.kernel32.CloseHandle(self.job_handle)
            self.job_handle = None


class SubprocessHandle:
    """Уніфікація API Popen під is_alive()/pid для існуючого коду."""
    def __init__(self, popen_obj):
        self._popen = popen_obj
        self.pid = popen_obj.pid

    def is_alive(self):
        return self._popen.poll() is None

# --- ЛОГІКА БРАУЗЕРА З ГЛИБОКИМ КЕШЕМ ---

def _run_webview(url, title, storage_path):
    """Запуск з фіксованою папкою для кешу або відкриття в браузері"""
    # Закриваємо stdout/stderr щоб не виводити логи Tomato у термінал.
    import sys
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

    # Пріоритет WebView2: зазвичай споживає менше CPU у тривалому idle-режимі.
    if WEBVIEW_AVAILABLE:
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--renderer-process-limit=1 --process-per-site --disable-background-networking --mute-audio"
        os.environ["WEBVIEW2_USER_DATA_FOLDER"] = storage_path

        window = webview.create_window(
            title=title, 
            url=url, 
            width=1150, 
            height=820,
            frameless=True, 
            on_top=True,
            background_color='#111111',
            easy_drag=False
        )
        try:
            webview.start(debug=False)
            return
        except Exception:
            pass

    webbrowser.open(url)

class TomatoManager:
    def __init__(self):
        self.proc = None
        self.job = WindowsJobManager()
        # Створюємо папку профілю прямо в папці з нашою програмою
        self.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile")
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def _edge_backend_available_here(self):
        """Перевіряємо, чи pywebview може працювати вбудовано у поточному інтерпретаторі."""
        if not WEBVIEW_AVAILABLE:
            return False
        try:
            import importlib
            importlib.import_module("webview.platforms.edgechromium")
            return True
        except Exception:
            return False

    def _find_worker_python(self):
        """Пошук Python 3.12 для worker-процесу pywebview (коли поточний env не має clr)."""
        env_python = os.environ.get("WOT_TOMATO_PYTHON", "").strip()
        if env_python and os.path.exists(env_python):
            return env_python

        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            candidate = os.path.join(local_app, "Programs", "Python", "Python312", "python.exe")
            if os.path.exists(candidate):
                return candidate

        return None

    def launch(self, url="https://tomato.gg/"):
        self.stop()

        if self._edge_backend_available_here():
            self.proc = multiprocessing.Process(
                target=_run_webview,
                args=(url, "WoT_Tomato_Hidden_Window", self.cache_dir),
                daemon=True
            )
            self.proc.start()
            self.job.add_process(self.proc.pid)
            return

        worker_python = self._find_worker_python()
        if worker_python:
            flags = 0
            if os.name == "nt":
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            popen_obj = subprocess.Popen(
                [worker_python, __file__, "--worker", url, self.cache_dir],
                creationflags=flags,
            )
            self.proc = SubprocessHandle(popen_obj)
            self.job.add_process(self.proc.pid)
            return

        if not WEBVIEW_AVAILABLE and not QWEB_ENGINE_AVAILABLE:
            # Для браузера просто відкриваємо URL без subprocess
            webbrowser.open(url)
            return

        webbrowser.open(url)

    def stop(self):
        # Завжди намагаємось прибрати Tomato-процеси повністю.
        if self.proc and self.proc.is_alive():
            try:
                parent = psutil.Process(self.proc.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
                self.proc.join(timeout=1.0)
            except Exception:
                pass

        # Жорстко завершуємо весь Job (включно з дочірніми Chromium/Qt процесами).
        try:
            self.job.terminate_all()
            self.job.close()
        except Exception:
            pass

        # Fallback: якщо вікно ще існує, завершуємо процес по PID вікна.
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "WoT_Tomato_Hidden_Window")
            if hwnd:
                pid = ctypes.c_ulong(0)
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value:
                    p = psutil.Process(pid.value)
                    for child in p.children(recursive=True):
                        child.kill()
                    p.kill()
        except Exception:
            pass

        # Створюємо новий Job для наступного запуску.
        self.job = WindowsJobManager()
        self.proc = None

if __name__ == "__main__":
    multiprocessing.freeze_support()

    if len(sys.argv) >= 2 and sys.argv[1] == "--worker":
        url = sys.argv[2] if len(sys.argv) >= 3 else "https://tomato.gg/"
        cache_dir = sys.argv[3] if len(sys.argv) >= 4 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile")
        _run_webview(url, "WoT_Tomato_Hidden_Window", cache_dir)
        sys.exit(0)

    manager = TomatoManager()
    manager.launch("https://tomato.gg/")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop()
# tomato_viewer_4_09.py
