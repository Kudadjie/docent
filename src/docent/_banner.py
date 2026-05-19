"""CLI startup banner — scalable pixel-font wordmark using Unicode block chars.

Half-block characters (▄ ▀ ▐ ▌) at corners and curves give letters like
D, O, C, E, N rounded edges instead of sharp rectangular corners.
Each "pixel" is repeated px_w times horizontally, so the text scales to
fill the terminal width at any size.
"""
from __future__ import annotations

import shutil

_FG = "#18E299"  # brand green  (pixel fills)
_M  = "#3a3a3a"  # muted        (separator / meta)

# ── Pixel font — 5 × 5 grid per glyph ────────────────────────────────────────
#
# Filled pixels:
#   █  full block          ▄  lower-half (curve: arc dips into lower half)
#   ▀  upper-half          ▐  right-half (left-side arc: only right part visible)
#   ▌  left-half
#
# Each glyph row is exactly 5 chars wide.

_FONT: dict[str, list[str]] = {
    # D — flat left side, right side curves outward
    "d": [
        "████▄",   # top bar → right-top corner curves down (▄)
        "█   ▐",   # left solid │  right side = thin curve (▐)
        "█   ▐",
        "█   ▐",
        "████▀",   # bottom bar → right-bottom corner curves up (▀)
    ],
    # O — oval, all four corners curved
    "o": [
        "▄███▄",   # top:    left-top & right-top curve inward
        "▐   ▐",   # sides:  thin left & right strokes
        "▐   ▐",
        "▐   ▐",
        "▀███▀",   # bottom: left-bottom & right-bottom curve inward
    ],
    # C — left arc, open on the right
    "c": [
        "▄████",   # top-left corner curves (▄), bar extends right
        "▐    ",   # left side = thin arc stroke (▐)
        "▐    ",
        "▐    ",
        "▀████",   # bottom-left corner curves (▀), bar extends right
    ],
    # E — closed top (like O), middle crossbar, open bottom (like C)
    "e": [
        "▄███▄",   # top closed — same as O top
        "▐   ▐",   # right side closes the top loop
        "▐████",   # midbar: left arc continues + bar closes right
        "▐    ",   # bottom left arc, open right
        "▀████",   # bottom curve + arm, same as C bottom
    ],
    # N — arch at top, two legs going straight down
    "n": [
        "▄███▄",   # arch (identical shape to O top)
        "▐   ▐",   # two legs begin
        "▐   ▐",
        "▐   ▐",
        "▐   ▐",   # legs reach the bottom (no bottom arc = open = 'n' not 'o')
    ],
    # T — plain solid crossbar (no curves, distinguishes it from N's arch)
    "t": [
        "█████",   # solid crossbar
        "  █  ",   # stem (2 spaces + pixel + 2 spaces)
        "  █  ",
        "  █  ",
        "  ██ ",   # slight right foot
    ],
}

_BLANK = ["     "] * 5
_FILLED = frozenset("█▄▀▐▌")


def _render(word: str, px_w: int) -> list[str]:
    """Render *word* in the pixel font at *px_w* chars per pixel.

    Every filled character (█ ▄ ▀ ▐ ▌) is repeated *px_w* times and
    coloured brand green; spaces are repeated *px_w* times without colour.
    Returns 5 Rich-markup strings (one per display row).
    """
    rows = [""] * 5
    for i, ch in enumerate(word.lower()):
        glyph = _FONT.get(ch, _BLANK)
        sep = " " * px_w if i < len(word) - 1 else ""
        for r in range(5):
            parts = ""
            for pixel in glyph[r]:
                if pixel in _FILLED:
                    parts += f"[bold {_FG}]{pixel * px_w}[/bold {_FG}]"
                else:
                    parts += " " * px_w
            rows[r] += parts + sep
    return rows


def _px_scale(word: str, term_cols: int, margin: int = 2) -> int:
    """Largest integer pixel width such that the word fits within *term_cols*."""
    glyphs = len(word)
    # At scale s: glyph = 5s, gap between glyphs = s  →  total = s*(6g - 1)
    base = 6 * glyphs - 1
    return max(1, (term_cols - margin) // base)


def _short_version() -> str:
    try:
        from docent._version import __version__ as v  # type: ignore[import]
        return v.split(".dev")[0].split("+")[0]
    except Exception:
        return ""


def print_banner(console: object) -> None:
    ver       = _short_version()
    term_cols = shutil.get_terminal_size((80, 24)).columns

    px   = 2  # fixed size — looks good without filling the whole terminal
    rows = _render("docent", px)

    _p = getattr(console, "print")
    _p("")
    for row in rows:
        _p(" " + row)
    _p(f"[{_M}]{'─' * term_cols}[/{_M}]")
    ver_tag = f"[{_M}]{ver}[/{_M}]  ·  " if ver else ""
    _p(f" {ver_tag}[dim]a CLI-based control center for academic workflows[/dim]")
    _p("")
