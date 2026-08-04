# ORION_DECODER.md - Як декодувати XML через PjOrion (з прихованим вікном)

## Швидка команда для одного файлу

```powershell
$orionPath = "tools\orion\PjOrion.exe"
$absPath = (Resolve-Path "ПОТРІБНИЙ_ШЛЯХ").Path
$proc = Start-Process -FilePath $orionPath -ArgumentList "--unpack-file=""$absPath""" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 10
if (!$proc.HasExited) { Stop-Process -Id $proc.Id -Force }
```

## Python метод (_ctypes + tkinter для приховування вікна)

```python
import subprocess
import ctypes
import tkinter as tk
import time
import os

ORION_PATH = r"tools\orion\PjOrion.exe"
FILE_PATH = r"шлях\до\файлу.xml"

root = tk.Tk()
root.withdraw()
parent_hwnd = root.winfo_id()

abs_path = os.path.abspath(FILE_PATH)
proc = subprocess.Popen(
    [ORION_PATH, "--unpack-file", abs_path],
    creationflags=0x08000000,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

start_time = time.time()
while time.time() - start_time < 3.0:
    if proc.poll() is not None:
        break
    def enum_callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                if "pjorion" in buff.value.lower():
                    user32.ShowWindow(hwnd, 0)
        return True
    user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
    time.sleep(0.05)

if proc.poll() is None:
    proc.kill()
root.destroy()
```

## Опції PjOrion

```
--unpack-file=<file>     Один файл (потрібен абсолютний шлях!)
--unpack-folder=<path>  Папка з XML для декодування
--exit                  Вихід після завершення
```

## Як перевірити чи файл закодований

Перші байти файлу повинні бути:
- Закодований: `ENb` (69, 78, 161, 98)
- Розкодований: `<` (60, 63, 120, 109 = "<?xm")

## Перевірка в Python

```python
def is_encoded(file_path):
    with open(file_path, 'rb') as f:
        first = f.read(4)
    return first[0] == 69 and first[1] == 78 and first[2] == 161
```