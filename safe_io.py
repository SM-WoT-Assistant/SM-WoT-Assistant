# safe_io.py
"""Захист користувацьких JSON від раптового вимкнення ПК / обриву живлення.

Корінь інциденту (22.10.2026): звичайний open(path, "w") без fsync — живе
вимкнення посеред запису лишає файл повного РОЗМІРУ, але вмістом НУЛІ
(map_drawings.json = 1 017 517 байт, 100% нулів). Далі load_json мовчки
повертав default → малюнки «зникали» безслідно, наступний save добивав
файл остаточно.

Три рівні захисту:
 1. write_json: атомарний запис — *.tmp → flush+fsync → os.replace. Обрив
    живлення б'є по *.tmp, оригінал лишається цілим.
 2. read_json: самозагоєння — пошкоджений файл не знищується мовчки:
    перейменовується у *.corrupt-<ts> (доказ), вміст відновлюється з
    *.bak, втрата фіксується через report_fallback (admin.html Errors).
 3. Ротація *.bak: один раз на сесію на файл, ТІЛЬКИ з валідного стану —
    завжди є джерело для відновлення.

Self-heal застосовується ТІЛЬКИ до файлів у config.USER_DATA_DIR —
бандлові файли (читання через data_manager) лишаються недоторканими.
"""
import json
import os
import time

import config

# Сесійний набір файлів, для яких вже зроблена ротація .bak
_rotated = set()

# Сентинел: прочитано, але вміст не є валідним JSON
_INVALID = object()


def _try_read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _INVALID


def _is_user_data(path):
    try:
        return os.path.normcase(os.path.abspath(path)).startswith(
            os.path.normcase(os.path.abspath(config.USER_DATA_DIR)))
    except Exception:
        return False


def _report(level, name, text):
    """Консоль (джерело істини) + Firebase error_reports (admin.html Errors)."""
    print(f"[SAFE_IO] {name}: {text}")
    try:
        import firebase_reporter
        firebase_reporter.report_fallback("safe_io.read_json", name, text, level)
    except Exception:
        pass


def write_json(path, data, indent=4):
    """Атомарний запис JSON: *.tmp → flush+fsync → os.replace. True/False."""
    tmp = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f"[SAFE_IO] write failed {path}: {e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def _preserve_evidence(path):
    """Перейменувати пошкоджений файл у *.corrupt-<ts> (доказ не знищувати)."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    target = f"{path}.corrupt-{ts}"
    n = 1
    while os.path.exists(target):
        target = f"{path}.corrupt-{ts}-{n}"
        n += 1
        if n > 99:
            return None
    try:
        os.replace(path, target)
        return target
    except Exception:
        return None


def _rotate_bak(path, data):
    """Один раз на сесію: зберегти валідний стан як *.bak (останній робочий)."""
    if path in _rotated:
        return
    _rotated.add(path)
    if not _is_user_data(path):
        return  # бандлові файли не ротуємо
    write_json(path + ".bak", data)


def read_json(path, default=None):
    """Читання JSON з ротацією .bak та самозагоєнням при пошкодженні.

    Повертає дані: валідні / відновлені з .bak / default (немає файлу
    або пошкодження без валідного бекапу)."""
    if default is None:
        default = {}
    if not os.path.isfile(path):
        return default
    data = _try_read(path)
    if data is not _INVALID:
        _rotate_bak(path, data)
        return data

    # Пошкодження: JSONDecodeError / порожній / нульовий файл (power-loss)
    if not _is_user_data(path):
        # Бандловий файл: поведінка як раніше (мовчки default, без чужини)
        return default
    name = os.path.basename(path)
    evidence = _preserve_evidence(path)
    bak_path = path + ".bak"
    bak = _try_read(bak_path)
    if bak is not _INVALID:
        if write_json(path, bak):
            _report("warning", name,
                    f"corrupt (evidence: {os.path.basename(evidence) if evidence else 'rename failed'})"
                    " — restored from .bak")
        else:
            _report("warning", name,
                    "corrupt — .bak loaded to memory, rewrite failed (will retry on save)")
        return bak
    _report("error", name,
            f"corrupt (evidence: {os.path.basename(evidence) if evidence else 'rename failed'}),"
            " no valid .bak — data lost until next save")
    return default
