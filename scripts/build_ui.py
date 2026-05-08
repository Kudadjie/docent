#!/usr/bin/env python3
"""Build the Next.js frontend and copy the static export to src/docent/ui_dist/.

Run from the repo root:
    python scripts/build_ui.py

The Next.js API routes (frontend/src/app/api/) are replaced by FastAPI at runtime
and cannot be included in a static export. This script temporarily moves them aside
during the build, then restores them so local dev (npm run dev) keeps working.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
API_DIR = FRONTEND / "src" / "app" / "api"
API_TEMP = FRONTEND / "src" / "app" / "_api_disabled"
OUT = FRONTEND / "out"
DIST = ROOT / "src" / "docent" / "ui_dist"


def main() -> None:
    # Temporarily hide API routes — they're not compatible with output: 'export'
    # and are replaced by FastAPI at runtime.
    api_hidden = False
    # Clean stale Next.js build cache so type generation reflects the hidden API routes.
    next_cache = FRONTEND / ".next"
    if next_cache.exists():
        shutil.rmtree(next_cache, ignore_errors=True)

    if API_DIR.exists():
        shutil.move(str(API_DIR), str(API_TEMP))
        api_hidden = True

    try:
        print("Building Next.js frontend...")
        result = subprocess.run("npm run build", cwd=FRONTEND, shell=True)
        if result.returncode != 0:
            print("Build failed.", file=sys.stderr)
            sys.exit(1)
    finally:
        if api_hidden and API_TEMP.exists():
            shutil.move(str(API_TEMP), str(API_DIR))

    if not OUT.is_dir():
        print(f"Expected {OUT} after build but it doesn't exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Copying frontend/out -> src/docent/ui_dist")
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(OUT, DIST)
    print("Done. Run `docent ui` to launch.")


if __name__ == "__main__":
    main()
