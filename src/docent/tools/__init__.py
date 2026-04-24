from __future__ import annotations

import importlib
import pkgutil


def discover_tools() -> None:
    """Import every module in `docent.tools` so `@register_tool` fires.

    Each `.py` in this package is treated as a tool module. Names beginning
    with `_` are skipped so tests and scratch modules can coexist without
    being auto-loaded.
    """
    for _, name, _ in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{name}")
