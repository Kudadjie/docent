"""CLI startup banner — pixel-art logo + wordmark."""
from __future__ import annotations

_O = "#ededed"   # outer light box
_I = "#1e1e1e"   # inner dark box
_G = "#18E299"   # green core

# 6-wide × 5-tall pixel art of the docent logo (three nested rounded rects)
_ICON = [
    f"[{_O}]██████[/]",
    f"[{_O}]█[/][{_I}]████[/][{_O}]█[/]",
    f"[{_O}]█[/][{_I}]█[/][{_G}]██[/][{_I}]█[/][{_O}]█[/]",
    f"[{_O}]█[/][{_I}]████[/][{_O}]█[/]",
    f"[{_O}]██████[/]",
]


def _short_version() -> str:
    try:
        from docent._version import __version__ as v
        # "1.2.0.dev3+gabcdef.d20260519" → "1.2.0"
        return v.split(".dev")[0].split("+")[0]
    except Exception:
        return ""


def print_banner(console: object) -> None:  # console: rich.console.Console
    ver = _short_version()
    ver_str = f"  [dim]v{ver}[/]" if ver else ""

    right = [
        "",
        f"  [bold {_O}]docent[/]{ver_str}",
        f"  [dim]grad-school AI[/]",
        "",
        "",
    ]

    try:
        getattr(console, "print")("")
        for icon_line, r in zip(_ICON, right):
            getattr(console, "print")(icon_line + r)
        getattr(console, "print")("")
    except Exception:
        pass
