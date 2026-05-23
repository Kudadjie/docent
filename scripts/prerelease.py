#!/usr/bin/env python3
"""Pre-release check: Python tests, ruff, frontend build + lint, docs flag validation.

Run before tagging a release:
    uv run python scripts/prerelease.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FRONTEND = ROOT / "frontend"

_CHECKS: list[tuple[str, list[str], Path | None]] = [
    ("ruff lint",        ["uv", "run", "ruff", "check", "src/"],              ROOT),
    ("pytest",           ["uv", "run", "pytest", "-q"],                        ROOT),
    ("frontend install", ["npm", "ci"],                                         FRONTEND),
    ("frontend lint",    ["npm", "run", "lint"],                                FRONTEND),
    ("frontend build",   ["python", str(ROOT / "scripts" / "build_ui.py")],    ROOT),
    ("docs flags",       ["uv", "run", "pytest", "tests/test_doc_flags.py", "-v"], ROOT),
]


def _run(label: str, cmd: list[str], cwd: Path | None) -> bool:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    result = subprocess.run(cmd, cwd=cwd)
    ok = result.returncode == 0
    status = "✓ PASS" if ok else "✗ FAIL"
    print(f"\n{status}: {label}")
    return ok


def main() -> None:
    results: list[tuple[str, bool]] = []
    for label, cmd, cwd in _CHECKS:
        ok = _run(label, cmd, cwd)
        results.append((label, ok))

    print(f"\n{'═' * 60}")
    print("  Pre-release summary")
    print(f"{'═' * 60}")
    all_pass = True
    for label, ok in results:
        mark = "✓" if ok else "✗"
        print(f"  {mark}  {label}")
        if not ok:
            all_pass = False

    if all_pass:
        print("\n  All checks passed — safe to tag.\n")
    else:
        print("\n  One or more checks failed — fix before tagging.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
