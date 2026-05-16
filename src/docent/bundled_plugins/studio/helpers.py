"""Pure utility helpers: text slugging, guide file reading, reference building."""
from __future__ import annotations

import re
from pathlib import Path


def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric with hyphens, collapse runs."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return s.strip("-")[:60]


def _artifact_slug(artifact: str) -> str:
    """Derive a slug from an artifact identifier (URL, arXiv ID, or path)."""
    s = artifact.strip()
    if "/" in s:
        s = s.rstrip("/").rsplit("/", 1)[-1]
    return s


def _read_guide_file(path: str | None) -> str:
    """Read a single guide file. Returns '' if missing/unreadable."""
    if not path:
        return ""
    p = Path(path).expanduser()
    if not p.exists():
        return ""
    try:
        if p.suffix.lower() == ".pdf":
            try:
                from pdfminer.high_level import extract_text
                return extract_text(str(p))
            except ImportError:
                return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


_GUIDE_EXTS = {".md", ".txt", ".pdf"}


def _expand_guide_paths(paths: list[str]) -> list[str]:
    """Expand any directory paths to their contained .md/.txt/.pdf files."""
    expanded: list[str] = []
    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            expanded.extend(
                str(f) for f in sorted(p.iterdir())
                if f.is_file() and f.suffix.lower() in _GUIDE_EXTS
            )
        else:
            expanded.append(raw)
    return expanded


def _check_guide_files(paths: list[str]) -> tuple[list[str], list[str]]:
    """Check guide file paths and return (readable, problems).

    A path is a problem if: it doesn't exist, is a directory with no matching
    files, or exists but cannot be read (permissions, encoding, corrupt PDF).
    Directories are expanded first.
    """
    readable: list[str] = []
    problems: list[str] = []

    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            matches = [
                f for f in sorted(p.iterdir())
                if f.is_file() and f.suffix.lower() in _GUIDE_EXTS
            ]
            if not matches:
                problems.append(f"{raw}  (folder contains no .md/.txt/.pdf files)")
            else:
                for f in matches:
                    if _is_readable(f):
                        readable.append(str(f))
                    else:
                        problems.append(str(f))
        elif not p.exists():
            problems.append(f"{raw}  (not found)")
        elif not p.suffix.lower() in _GUIDE_EXTS:
            problems.append(f"{raw}  (unsupported type — use .md, .txt, or .pdf)")
        elif _is_readable(p):
            readable.append(str(p))
        else:
            problems.append(f"{raw}  (unreadable or corrupted)")

    return readable, problems


def _is_readable(p: Path) -> bool:
    """Return True if the file can be successfully opened and read."""
    try:
        if p.suffix.lower() == ".pdf":
            try:
                from pdfminer.high_level import extract_text
                extract_text(str(p))
                return True
            except Exception:
                return False
        p.read_text(encoding="utf-8", errors="strict")
        return True
    except (OSError, UnicodeDecodeError):
        return False


def _read_guide_files(paths: list[str]) -> str:
    """Read one or more guide files (or folder) and concatenate their content.

    Directories are expanded to all .md/.txt/.pdf files inside them.
    Each file's content is prefixed with a header so the LLM can distinguish
    sources. Files that are missing or unreadable are silently skipped.
    """
    if not paths:
        return ""
    resolved = _expand_guide_paths(paths)
    if not resolved:
        return ""
    if len(resolved) == 1:
        return _read_guide_file(resolved[0])
    parts: list[str] = []
    for path in resolved:
        text = _read_guide_file(path)
        if text:
            name = Path(path).name
            parts.append(f"### {name}\n\n{text}")
    return "\n\n".join(parts)


def _build_references_section(sources: list[dict]) -> str:
    """Build a markdown References section from source dicts."""
    lines = ["\n\n## References\n"]
    idx = 0
    for s in sources:
        url = s.get("url", "")
        if not url:
            continue
        idx += 1
        title = s.get("title", "Untitled")
        stype = s.get("source_type", "web")
        authors = s.get("authors", "")
        author_tag = f" — {authors}" if authors else ""
        lines.append(f"{idx}. **{title}**{author_tag} — {url} [{stype}]")
    if idx == 0:
        return ""
    return "\n".join(lines) + "\n"


def _strip_references_section(draft: str) -> str:
    """Remove any existing ## References section from the end of a draft."""
    stripped = re.sub(r"\n## References\s*[\r\n].*$", "", draft, flags=re.DOTALL)
    return stripped.rstrip()


def _append_references(draft: str, sources: list[dict]) -> str:
    """Strip any existing References section, then append our own."""
    cleaned = _strip_references_section(draft)
    return cleaned + _build_references_section(sources)
