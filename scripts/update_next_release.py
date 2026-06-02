"""
update_next_release.py — Auto-update memory/next_release.md from git commits.

Designed to be called from the Claude Code Stop hook (session close).
Uses conventional-commit heuristics only; no AI involved — runs in <1s.

Usage:
    python scripts/update_next_release.py [--since <ref>] [--dry-run]

Exit codes: 0 always (hook must not break session close on failure).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NEXT_RELEASE = REPO_ROOT / "memory" / "next_release.md"

# Conventional commit types → category
_TYPE_MAP: dict[str, str] = {
    "feat": "new",
    "fix": "detail",
    "perf": "detail",
    "refactor": "detail",
    "chore": "skip",
    "docs": "skip",
    "test": "skip",
    "ci": "skip",
    "build": "skip",
    "style": "skip",
    "revert": "skip",
}

# Patterns in the commit description that are always skipped (infrastructure noise)
_SKIP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bruff\b", re.I),
    re.compile(r"\bmypy\b", re.I),
    re.compile(r"\blint\b", re.I),
    re.compile(r"\bformat\b.*\bcheck\b", re.I),
    re.compile(r"\bui[-_]?dist\b", re.I),
    re.compile(r"\brebuild\b", re.I),
    re.compile(r"\bbump\b.*\bversion\b", re.I),
    re.compile(r"\bpre[-_]?commit\b", re.I),
]


def _run(args: list[str]) -> str:
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, cwd=REPO_ROOT, timeout=10
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _last_tag() -> str:
    return _run(["git", "describe", "--tags", "--abbrev=0"])


def _commits_since(ref: str) -> list[tuple[str, str]]:
    """Return list of (short_hash, message) since ref (exclusive)."""
    if ref:
        raw = _run(["git", "log", f"{ref}..HEAD", "--oneline", "--no-merges"])
    else:
        raw = _run(["git", "log", "--oneline", "--no-merges", "-80"])
    if not raw:
        return []
    pairs = []
    for line in raw.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            pairs.append((parts[0], parts[1].strip()))
    return pairs


def _parse(msg: str) -> tuple[str, str, str]:
    """Return (ctype, scope, description) from a conventional commit message."""
    m = re.match(r"^(\w+)(?:\(([^)]+)\))?!?: (.+)$", msg)
    if m:
        return m.group(1).lower(), m.group(2) or "", m.group(3).strip()
    return "", "", msg.strip()


def _categorize(ctype: str, desc: str) -> str:
    for pat in _SKIP_PATTERNS:
        if pat.search(desc):
            return "skip"
    if ctype in _TYPE_MAP:
        return _TYPE_MAP[ctype]
    # Non-conventional message: treat as detail so it doesn't get silently dropped
    return "detail"


def _already_captured(desc: str, content: str) -> bool:
    """
    Rough dedup: if the first 35 chars of the description appear anywhere
    in the file (case-insensitive), assume it's already recorded.
    """
    needle = desc[:35].lower().strip()
    return bool(needle) and needle in content.lower()


def _pending_version(content: str) -> str:
    m = re.search(r"## Pending for (v[\d.]+)", content)
    return m.group(1) if m else "vNext"


def _make_bullet(ctype: str, scope: str, desc: str) -> str:
    if scope:
        return f"- `{scope}`: {desc}"
    return f"- {desc}"


def _insert_after_heading(content: str, heading: str, bullets: list[str]) -> str:
    """Insert bullets on the line immediately after the heading line."""
    idx = content.find(heading)
    if idx == -1:
        return content
    line_end = content.find("\n", idx)
    if line_end == -1:
        return content + "\n" + "\n".join(bullets)
    block = "\n".join(bullets) + "\n"
    return content[: line_end + 1] + block + content[line_end + 1 :]


def main(argv: list[str] | None = None) -> None:
    argv = argv or sys.argv[1:]
    dry_run = "--dry-run" in argv
    since_ref: str = ""
    if "--since" in argv:
        idx = argv.index("--since")
        if idx + 1 < len(argv):
            since_ref = argv[idx + 1]

    if not since_ref:
        since_ref = _last_tag()

    commits = _commits_since(since_ref)
    if not commits:
        print("[update-next-release] No new commits to process.")
        return

    content = NEXT_RELEASE.read_text(encoding="utf-8") if NEXT_RELEASE.exists() else ""

    new_bullets: list[str] = []
    detail_bullets: list[str] = []
    skipped = 0

    for _, msg in commits:
        ctype, scope, desc = _parse(msg)
        cat = _categorize(ctype, desc)
        if cat == "skip":
            skipped += 1
            continue
        if _already_captured(desc, content):
            skipped += 1
            continue
        bullet = _make_bullet(ctype, scope, desc)
        if cat == "new":
            new_bullets.append(bullet)
        else:
            detail_bullets.append(bullet)

    if not new_bullets and not detail_bullets:
        print(f"[update-next-release] Nothing new to add ({skipped} commits skipped).")
        return

    if dry_run:
        version = _pending_version(content)
        print(f"[update-next-release] Dry run — proposed additions for {version}:")
        if new_bullets:
            print("  ### What's New")
            for b in new_bullets:
                print(f"    {b}")
        if detail_bullets:
            print("  ### Details")
            for b in detail_bullets:
                print(f"    {b}")
        print(f"  Skipped: {skipped} commits")
        return

    # Ensure the file has the required structure
    if not content:
        version = "vNext"
        content = (
            "---\n"
            "name: next-release-notes\n"
            "description: Scratchpad for changes accumulating toward the next release; promote to CHANGELOG.md [Unreleased] before tagging.\n"
            "type: project\n"
            "---\n\n"
            "# Next Release Notes\n\n"
            "**Two tiers:**\n"
            "- `### What's New` — 2–5 bullets, strictly user-facing.\n"
            "- `### Details` — fixes, internal improvements, error message tweaks.\n\n"
            "---\n\n"
            f"## Pending for {version}\n\n"
            "### What's New\n\n"
            "### Details\n"
        )

    # Insert bullets (newest first — prepend after the heading)
    if new_bullets and "### What's New" in content:
        content = _insert_after_heading(content, "### What's New", new_bullets)
    if detail_bullets and "### Details" in content:
        content = _insert_after_heading(content, "### Details", detail_bullets)

    NEXT_RELEASE.write_text(content, encoding="utf-8")
    print(
        f"[update-next-release] Added {len(new_bullets)} What's New "
        f"+ {len(detail_bullets)} Detail items ({skipped} skipped)."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        # Hook must never crash the session close
        print(f"[update-next-release] Error (non-fatal): {exc}", file=sys.stderr)
        sys.exit(0)
