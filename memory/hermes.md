---
name: hermes-wsl-venv
description: Hermes WSL venv must not touch the Windows .venv; briefing and AGENTS.md notes
metadata:
  type: project
---

**Python version as of 2026-05-14: 3.13** (bumped from 3.11 to unblock `alphaxiv-py>=0.5.0`). `.python-version` file is now `3.13`. The WSL venv must also use Python 3.13 — if the WSL venv was created on 3.11, recreate it: `uv venv --python 3.13 && uv sync` from within the WSL-native project path.

Hermes runs from WSL and creates its own `.venv` inside WSL. It must **not** modify or point at the Windows `.venv` at `/mnt/c/Users/DELL/Desktop/Docent/.venv` — doing so installs Linux wheels into a Windows venv, corrupting it (seen 2026-05-13: pygments, py, dotenv all broken).

**Why:** Cross-OS wheel incompatibility. Linux-built wheels cannot run on Windows.

**How to apply:**
- Hermes briefs must use `uv run` with a WSL-native project path, not a `/mnt/c/...` path.
- If Hermes needs to run pytest, it should do so from a WSL copy of the repo or a git worktree inside the WSL filesystem.
- Add a warning to `AGENTS.md` so any agent running from WSL knows not to touch `/mnt/c/.../.venv`.
- If the Windows `.venv` gets broken again, fix with: `Remove-Item -Recurse -Force .venv` then `uv sync` in PowerShell.
- VSCode interpreter should always point to `.venv\Scripts\python.exe` (the Windows venv), not the WSL one.
