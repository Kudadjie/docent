"""CLI startup banner — dynamic pixel-art logo + pixel-font wordmark.

The logo is a 5-row × N-col grid of tiny coloured squares (2 chars wide each
so they look square in a fixed-width terminal font). N scales with terminal
width, so the banner always fills the available horizontal space.
"""
from __future__ import annotations

import shutil

# ── Palette ───────────────────────────────────────────────────────────────────
_O  = "#ededed"  # outer light box
_D  = "#1a1a1a"  # dark inner ring
_G  = "#18E299"  # brand green core
_M  = "#3a3a3a"  # muted  (separator / meta line)
_FG = "#18E299"  # pixel-font glyph colour


# ── Logo — pixel grid ─────────────────────────────────────────────────────────

def _zone(x: int, y: int, w: int, h: int) -> str:
    """Return 'O' (outer), 'D' (dark ring), or 'G' (green core) for pixel (x,y).

    Proportions match the SVG logo:
      outer border ≈ 22 % on each side (clamped to ≥ 1 px)
      dark ring    ≈ 12 % on each side (clamped to ≥ 1 px)
    """
    o_h = max(1, round(w * 0.22))
    d_h = max(1, round(w * 0.12))
    o_v = max(1, round(h * 0.22))
    d_v = max(1, round(h * 0.12))

    x_outer = x < o_h or x >= w - o_h
    y_outer = y < o_v or y >= h - o_v

    if x_outer or y_outer:
        return "O"

    x_dark = x < o_h + d_h or x >= w - o_h - d_h
    y_dark = y < o_v + d_v or y >= h - o_v - d_v

    if x_dark or y_dark:
        return "D"

    return "G"


def _build_logo(pixel_cols: int, pixel_rows: int = 5) -> list[str]:
    """Return *pixel_rows* Rich-markup strings for the pixel-art logo.

    Each pixel is two background-coloured spaces wide (so the cell appears
    square in most fixed-width fonts where char height ≈ 2 × char width).
    """
    color = {"O": _O, "D": _D, "G": _G}
    rows: list[str] = []
    for y in range(pixel_rows):
        parts: list[str] = []
        for x in range(pixel_cols):
            c = color[_zone(x, y, pixel_cols, pixel_rows)]
            parts.append(f"[on {c}]  [/on {c}]")
        rows.append("".join(parts))
    return rows


# ── Pixel font — 5 chars wide × 5 rows ───────────────────────────────────────

_FONT: dict[str, list[str]] = {
    "d": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "o": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "c": [" ████", "█    ", "█    ", "█    ", " ████"],
    "e": ["████ ", "█   █", "████ ", "█    ", "████ "],
    "n": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "t": [" ███ ", "  █  ", "  █  ", "  █  ", "  ██ "],
}


def _build_text(word: str) -> list[str]:
    """Return 5 Rich-markup strings for *word* in the pixel font."""
    rows = [""] * 5
    for i, ch in enumerate(word.lower()):
        glyph = _FONT.get(ch, ["     "] * 5)
        sep = " " if i < len(word) - 1 else ""
        for r in range(5):
            coloured = glyph[r].replace("█", f"[bold {_FG}]█[/bold {_FG}]")
            rows[r] += coloured + sep
    return rows


# ── Version ───────────────────────────────────────────────────────────────────

def _short_version() -> str:
    try:
        from docent._version import __version__ as v  # type: ignore[import]
        return v.split(".dev")[0].split("+")[0]
    except Exception:
        return ""


# ── Entry point ───────────────────────────────────────────────────────────────

def print_banner(console: object) -> None:
    """Print the startup banner to *console* (a ``rich.console.Console``)."""
    ver       = _short_version()
    term_cols = shutil.get_terminal_size((80, 24)).columns

    # "docent" in the 5-px font: 6 glyphs × 5 chars + 5 × 1-char gap = 35 chars
    text_width = 35
    gap_width  = 4
    # Each pixel renders as 2 chars, so pixel_cols = available_chars / 2
    pixel_cols = max(14, (term_cols - gap_width - text_width) // 2)

    logo_rows = _build_logo(pixel_cols)
    text_rows = _build_text("docent")
    gap       = " " * gap_width

    _p = getattr(console, "print")

    _p("")
    for logo_row, text_row in zip(logo_rows, text_rows):
        _p(logo_row + gap + text_row)

    _p(f"[{_M}]{'─' * term_cols}[/{_M}]")

    ver_tag = f"[{_M}]{ver}[/{_M}]  ·  " if ver else ""
    _p(f" {ver_tag}[dim]a CLI-based control center for academic workflows[/dim]")
    _p("")
