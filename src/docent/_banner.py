"""CLI startup banner — scalable pixel-font wordmark, full terminal width."""
from __future__ import annotations

import shutil

_G = "#18E299"   # brand green  (pixel fills)
_M = "#3a3a3a"   # muted        (separator / meta)

# ── Pixel font — 5 × 5 grid per glyph ────────────────────────────────────────
# '█' = filled pixel (brand green)  ' ' = empty pixel (transparent)

_FONT: dict[str, list[str]] = {
    "d": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "o": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "c": [" ████", "█    ", "█    ", "█    ", " ████"],
    "e": ["████ ", "█   █", "████ ", "█    ", "████ "],
    "n": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "t": [" ███ ", "  █  ", "  █  ", "  █  ", "  ██ "],
}
_BLANK = ["     "] * 5

# ── Text renderer (scales horizontally to fill terminal) ──────────────────────

def _render(word: str, px_w: int) -> list[str]:
    """Render *word* in the pixel font at *px_w* chars per pixel (≥ 1).

    Returns 5 Rich-markup strings, one per display row.
    """
    rows = [""] * 5
    for i, ch in enumerate(word.lower()):
        glyph = _FONT.get(ch, _BLANK)
        sep_chars = px_w              # gap between letters = 1 "pixel" wide
        sep = " " * sep_chars if i < len(word) - 1 else ""
        for r in range(5):
            parts = ""
            for pixel in glyph[r]:
                if pixel == "█":
                    parts += f"[bold {_G}]{'█' * px_w}[/bold {_G}]"
                else:
                    parts += " " * px_w
            rows[r] += parts + sep
    return rows


def _px_scale(word: str, term_cols: int, margin: int = 2) -> int:
    """Choose the largest integer pixel width that fits in *term_cols*."""
    glyphs    = len(word)
    # At scale s: glyph = 5s chars wide, gap = s chars, last glyph has no gap
    # total = glyphs * 5s + (glyphs - 1) * s = s * (5g + g - 1) = s * (6g - 1)
    base = 6 * glyphs - 1          # total pixel-columns needed
    return max(1, (term_cols - margin) // base)


# ── Version ───────────────────────────────────────────────────────────────────

def _short_version() -> str:
    try:
        from docent._version import __version__ as v  # type: ignore[import]
        return v.split(".dev")[0].split("+")[0]
    except Exception:
        return ""


# ── Entry point ───────────────────────────────────────────────────────────────

def print_banner(console: object) -> None:
    ver       = _short_version()
    term_cols = shutil.get_terminal_size((80, 24)).columns

    px = _px_scale("docent", term_cols)
    rows = _render("docent", px)

    _p = getattr(console, "print")
    _p("")
    for row in rows:
        _p(" " + row)
    _p(f"[{_M}]{'─' * term_cols}[/{_M}]")
    ver_tag = f"[{_M}]{ver}[/{_M}]  ·  " if ver else ""
    _p(f" {ver_tag}[dim]a CLI-based control center for academic workflows[/dim]")
    _p("")
