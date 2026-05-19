"""CLI startup banner — pixel-art logo + pixel-font wordmark."""
from __future__ import annotations

import shutil

# ── Palette ───────────────────────────────────────────────────────────────────
_O = "#ededed"   # outer light box
_D = "#1e1e1e"   # dark inner box
_G = "#18E299"   # brand green core
_B = "#18E299"   # pixel-font fill colour
_M = "#3a3a3a"   # muted (separator / meta)

# ── Icon ──────────────────────────────────────────────────────────────────────
# 10 cells wide × 5 rows. Each cell = 2 background-coloured spaces (looks square).
# O = outer light  |  D = dark inner  |  G = green core
#
#  O O O O O O O O O O
#  O O D D D D D D O O     (2 outer, 6 dark, 2 outer)
#  O O D G G G G D O O     (2 outer, 1 dark, 4 green, 1 dark, 2 outer)
#  O O D D D D D D O O
#  O O O O O O O O O O

def _cell(color: str) -> str:
    return f"[on {color}]  [/on {color}]"

_CELLS = {"O": _cell(_O), "D": _cell(_D), "G": _cell(_G)}

_ICON = [
    "".join(_CELLS[c] for c in "OOOOOOOOOO"),
    "".join(_CELLS[c] for c in "OODDDDDDOO"),
    "".join(_CELLS[c] for c in "OODGGGGDOO"),
    "".join(_CELLS[c] for c in "OODDDDDDOO"),
    "".join(_CELLS[c] for c in "OOOOOOOOOO"),
]

# ── Pixel font — 5 chars wide × 5 rows ───────────────────────────────────────
_FONT: dict[str, list[str]] = {
    "d": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "o": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "c": [" ████", "█    ", "█    ", "█    ", " ████"],
    "e": ["████ ", "█   █", "████ ", "█    ", "████ "],
    "n": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "t": ["█████", "  █  ", "  █  ", "  █  ", "  ██ "],
}


def _render(word: str) -> list[str]:
    """Stitch glyph rows for every character in *word* into 5 full rows."""
    rows = [""] * 5
    for i, ch in enumerate(word.lower()):
        glyph = _FONT.get(ch, ["     "] * 5)
        sep = " " if i < len(word) - 1 else ""
        for r in range(5):
            rows[r] += glyph[r] + sep
    return rows


def _short_version() -> str:
    try:
        from docent._version import __version__ as v  # type: ignore[import]
        return v.split(".dev")[0].split("+")[0]
    except Exception:
        return ""


def print_banner(console: object) -> None:
    """Print the startup banner to *console* (a Rich Console instance)."""
    ver = _short_version()
    cols = shutil.get_terminal_size((80, 24)).columns

    text_rows = _render("docent")
    # Colour every filled pixel in brand green
    colored = [row.replace("█", f"[bold {_B}]█[/bold {_B}]") for row in text_rows]

    gap = "   "  # visual gap between icon and word

    _p = getattr(console, "print")

    _p("")
    for icon_row, text_row in zip(_ICON, colored):
        _p(icon_row + gap + text_row)

    # Full-width separator
    sep_width = min(cols, 80)
    _p(f"[{_M}]{'─' * sep_width}[/{_M}]")

    # Version + tagline
    ver_part = f"[{_M}]{ver}[/{_M}]  ·  " if ver else ""
    _p(f" {ver_part}[dim]a CLI-based control center for academic workflows[/dim]")
    _p("")
