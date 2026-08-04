#!/usr/bin/env python3
"""
Синхронізація ARC/ -> корінь: для кожного модуля береться файл з найвищим
номером у імені (main_4_44 новіший за main_4_43). Альтернатива: --by-mtime.

  python arc_sync.py              перегляд
  python arc_sync.py --apply      копіювання
  python arc_sync.py --apply --by-mtime   за датою файлу

Зворотна операція (корінь -> ARC): python arc_archive.py
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ARC_PREFIX_TO_TARGET: tuple[tuple[str, str], ...] = (
    ("main_", "main.py"),
    ("painter_", "painter.py"),
    ("config_", "config.py"),
    ("map_extractor_", "map_extractor.py"),
    ("wot_decoder_", "wot_decoder.py"),
    ("tomato_viewer_", "tomato_viewer.py"),
)

# Ключ у sync_override.txt -> префікс (без .py)
TARGET_KEY_TO_PREFIX: dict[str, str] = {
    "main": "main_",
    "painter": "painter_",
    "config": "config_",
    "map_extractor": "map_extractor_",
    "wot_decoder": "wot_decoder_",
    "tomato_viewer": "tomato_viewer_",
}


def load_overrides(arc_dir: Path) -> dict[str, str]:
    """ARC/sync_override.txt: рядки key=filename.py (наприклад main=main_4_43.py)."""
    path = arc_dir / "sync_override.txt"
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip().lower(), v.strip()
        if k in TARGET_KEY_TO_PREFIX and v.endswith(".py"):
            out[k] = v
    return out


def version_from_name(filename: str, prefix: str) -> tuple[int, int] | None:
    pat = "^" + re.escape(prefix) + r"(\d+)_(\d+)\.py$"
    m = re.match(pat, filename, re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def pick_best(arc_dir: Path, prefix: str, by_mtime: bool) -> Path | None:
    paths = [p for p in arc_dir.glob(f"{prefix}*.py") if p.is_file()]
    if not paths:
        return None
    if by_mtime:
        return max(paths, key=lambda p: p.stat().st_mtime)

    def sort_key(p: Path) -> tuple:
        v = version_from_name(p.name, prefix)
        mt = p.stat().st_mtime
        if v:
            return (1, v[0], v[1], mt)
        return (0, 0, 0, mt)

    return max(paths, key=sort_key)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy newest ARC module snapshots into project root."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually copy files (default is plan only)",
    )
    parser.add_argument(
        "--by-mtime",
        action="store_true",
        help="Pick by file mtime instead of version in filename",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    arc_dir = root / "ARC"
    if not arc_dir.is_dir():
        print("ARC folder missing:", arc_dir, file=sys.stderr)
        return 1

    overrides = load_overrides(arc_dir)
    prefix_to_key = {pr: k for k, pr in TARGET_KEY_TO_PREFIX.items()}

    plan: list[tuple[Path, Path]] = []
    for prefix, target_name in ARC_PREFIX_TO_TARGET:
        key = prefix_to_key.get(prefix)
        if key and key in overrides:
            forced = arc_dir / overrides[key]
            if not forced.is_file():
                print(f"override missing: {forced}", file=sys.stderr)
                return 1
            src = forced
        else:
            src = pick_best(arc_dir, prefix, args.by_mtime)
        if src is None:
            continue
        plan.append((src, root / target_name))

    if not plan:
        print("No matching modules in ARC.")
        return 0

    if overrides:
        print("Overrides from ARC/sync_override.txt:", overrides)

    mode = "APPLY" if args.apply else "PLAN"
    for src, dst in plan:
        extra = ""
        for pr, _ in ARC_PREFIX_TO_TARGET:
            if src.name.lower().startswith(pr.lower()):
                v = version_from_name(src.name, pr)
                if v:
                    extra = f"  [v{v[0]}.{v[1]}]"
                break
        print(f"{mode}: {src.name} -> {dst.name}{extra}")

    if not args.apply:
        print("\nRun: python arc_sync.py --apply")
        return 0

    for src, dst in plan:
        shutil.copy2(src, dst)
        print("ok", dst.name)

    print("\nTip: python -m py_compile main.py painter.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
