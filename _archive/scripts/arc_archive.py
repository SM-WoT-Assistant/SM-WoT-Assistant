#!/usr/bin/env python3
"""
Архівація поточних модулів у ARC/ з наступним номером версії у імені файлу.

  python arc_archive.py                 показати план
  python arc_archive.py --apply         записати копії в ARC
  python arc_archive.py --apply --only main,painter
  python arc_archive.py --apply --bump-header   оновити перший рядок (# main.py M_m)

Номер версії: max усіх main_*.py у ARC + 1 по другому компоненту (4_44 -> 4_45).
Якщо в ARC ще немає файлів — береться з першого рядка джерела (# main.py 4_43).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from arc_sync import ARC_PREFIX_TO_TARGET, pick_best, version_from_name

# logical name у першому рядку коментаря
TARGET_HEADER: dict[str, str] = {
    "main.py": "main.py",
    "painter.py": "painter.py",
    "config.py": "config.py",
    "map_extractor.py": "map_extractor.py",
    "wot_decoder.py": "wot_decoder.py",
    "tomato_viewer.py": "tomato_viewer.py",
}

def version_from_source_header(path: Path, logical: str) -> tuple[int, int] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    first = text.splitlines()[0] if text else ""
    m = re.match(
        r"^#\s*(?P<name>\S+\.py)\s+(?P<maj>\d+)_(?P<min>\d+)\s*$",
        first,
    )
    if not m or m.group("name") != logical:
        return None
    return int(m.group("maj")), int(m.group("min"))


def next_version_tuple(
    arc_dir: Path,
    prefix: str,
    root_file: Path,
    logical: str,
) -> tuple[int, int]:
    latest = pick_best(arc_dir, prefix, by_mtime=False)
    if latest is not None:
        v = version_from_name(latest.name, prefix)
        if v:
            return v[0], v[1] + 1
    hv = version_from_source_header(root_file, logical)
    if hv:
        return hv[0], hv[1] + 1
    return 1, 0


def bump_first_version_line(content: str, logical: str, maj: int, min_: int) -> str:
    lines = content.splitlines(keepends=True)
    if not lines:
        return content
    pat = re.compile(rf"^#\s*{re.escape(logical)}\s+\d+_\d+\s*$")
    raw0 = lines[0]
    if pat.match(raw0.rstrip("\r\n")):
        nl = "\r\n" if raw0.endswith("\r\n") else ("\n" if raw0.endswith("\n") else "\n")
        lines[0] = f"# {logical} {maj}_{min_}{nl}"
        return "".join(lines)
    return content


def main() -> int:
    p = argparse.ArgumentParser(description="Archive project modules into ARC with bumped version.")
    p.add_argument("--apply", action="store_true", help="Write files to ARC")
    p.add_argument(
        "--only",
        type=str,
        default="",
        help="Comma-separated: main,painter,config,map_extractor,wot_decoder,tomato_viewer",
    )
    p.add_argument(
        "--bump-header",
        action="store_true",
        help="If first line is '# name.py M_m', replace with new version",
    )
    args = p.parse_args()

    root = Path(__file__).resolve().parent
    arc_dir = root / "ARC"
    if not arc_dir.is_dir():
        print("ARC folder missing:", arc_dir, file=sys.stderr)
        return 1

    only_set = {x.strip().lower() for x in args.only.split(",") if x.strip()}

    plan: list[tuple[Path, Path, int, int]] = []
    for prefix, target_name in ARC_PREFIX_TO_TARGET:
        key = target_name.replace(".py", "")
        if only_set and key.lower() not in only_set:
            continue
        src = root / target_name
        if not src.is_file():
            print("skip (missing):", target_name, file=sys.stderr)
            continue
        logical = TARGET_HEADER.get(target_name, target_name)
        maj, min_ = next_version_tuple(arc_dir, prefix, src, logical)
        # Другий компонент з мінімум 2 цифрами (як painter_2_01, tomato_viewer_4_09)
        dest_name = f"{prefix}{maj}_{min_:02d}.py"
        dest = arc_dir / dest_name
        plan.append((src, dest, maj, min_))

    if not plan:
        print("Nothing to archive.")
        return 0

    mode = "APPLY" if args.apply else "PLAN"
    for src, dest, maj, min_ in plan:
        print(f"{mode}: {src.name} -> ARC/{dest.name}  [v{maj}.{min_}]")

    if not args.apply:
        print("\nRun: python arc_archive.py --apply")
        return 0

    for src, dest, maj, min_ in plan:
        text = src.read_text(encoding="utf-8")
        if args.bump_header:
            logical = TARGET_HEADER.get(src.name, src.name)
            text = bump_first_version_line(text, logical, maj, min_)
        dest.write_text(text, encoding="utf-8", newline="\n")
        print("ok", dest.name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
