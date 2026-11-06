# -*- coding: UTF-8 -*-
"""Fail when tracked text files contain a BOM or are not valid UTF-8."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "logs", "profiles"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".apk", ".jar"}


def main() -> int:
    problems = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        data = path.read_bytes()
        if data.startswith(b"\xef\xbb\xbf"):
            problems.append((path, "UTF-8 BOM"))
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            problems.append((path, "not UTF-8"))

    if not problems:
        print("OK: all text files are UTF-8 without BOM")
        return 0
    for path, reason in problems:
        print(f"{path.relative_to(ROOT)}: {reason}")
    print(f"FAIL: {len(problems)} file(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
