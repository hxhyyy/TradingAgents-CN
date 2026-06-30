#!/usr/bin/env python3
"""Apply market data patch split per file."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATCH_PATH = Path(__file__).resolve().parent.parent.parent / "市场数据获取没有问题.patch"
REPO = Path(__file__).resolve().parent.parent
TMPDIR = REPO / "tmp_patches"


def main() -> int:
    patch_text = PATCH_PATH.read_text(encoding="utf-16")
    TMPDIR.mkdir(exist_ok=True)

    parts = re.split(r"(?=^diff --git )", patch_text, flags=re.M)
    applied = 0
    failed: list[tuple[str, str]] = []

    for i, part in enumerate(parts):
        if not part.strip().startswith("diff --git"):
            continue
        match = re.search(r"diff --git a/(.+?) b/(.+?)$", part, re.M)
        if not match:
            continue
        relpath = match.group(2)
        patch_file = TMPDIR / f"{i:03d}.patch"
        patch_file.write_text(part if part.endswith("\n") else part + "\n", encoding="utf-8", newline="\n")

        check = subprocess.run(
            ["git", "apply", "--check", str(patch_file)],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if check.returncode != 0:
            err = (check.stderr or check.stdout).strip().split("\n")[0]
            failed.append((relpath, err))
            continue

        apply = subprocess.run(["git", "apply", str(patch_file)], cwd=REPO, capture_output=True, text=True)
        if apply.returncode != 0:
            err = (apply.stderr or apply.stdout).strip().split("\n")[0]
            failed.append((relpath, err))
            continue

        applied += 1
        print(f"OK   {relpath}")

    print(f"\nApplied {applied} file(s)")
    if failed:
        print(f"Failed {len(failed)} file(s):")
        for path, err in failed:
            print(f"  FAIL {path}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
