"""External plugin discovery.

Search order:
  1. src/docent/bundled_plugins/  (shipped plugins — may not exist yet, skip gracefully)
  2. ~/.docent/plugins/           (user-installed plugins, via plugins_dir() from paths.py)

Each directory is added to sys.path before importing, so plugin packages can use
relative imports internally. Both flat *.py files and packages (dir + __init__.py)
are supported. Names starting with _ are skipped.

Broken plugins: print one-line warning to stderr, continue loading others.
Name conflicts (plugin registers a name already taken): the registry raises ValueError,
which is caught and printed as a warning — same skip behaviour.

Startup hooks: plugins may define on_startup(context: Context) at module level.
The loader collects them; run_startup_hooks(context) calls them all after the CLI
creates its Context object.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Callable

from docent.core.context import Context
from docent.utils.paths import plugins_dir

_STARTUP_HOOKS: list[Callable[[Context], None]] = []


def _bundled_plugins_dir() -> Path:
    import docent

    return Path(docent.__file__).parent / "bundled_plugins"


def _ensure_in_sys_path(directory: Path) -> None:
    str_path = str(directory)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)


def _load_plugin_module(module_name: str) -> bool:
    """Import a plugin module and collect its startup hook if present.

    Returns True if loaded successfully, False if there was a recoverable error.
    """
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        print(f"Warning: failed to load plugin '{module_name}': {exc}", file=sys.stderr)
        return False

    module = sys.modules.get(module_name)
    if module is not None and hasattr(module, "on_startup"):
        hook = getattr(module, "on_startup")
        if callable(hook):
            _STARTUP_HOOKS.append(hook)

    return True


def _scan_plugin_dir(directory: Path, *, qualified_prefix: str | None = None) -> None:
    """Scan a directory for plugin modules/packages and load them.

    ``qualified_prefix`` — if given (e.g. ``"docent.bundled_plugins"``), import
    modules as ``<prefix>.<name>`` so they share the same sys.modules slot as any
    other absolute import of that path.  This prevents the double-import problem
    that occurs when the same file is imported twice under different module names.

    Without a prefix (external user plugins) the directory is added to sys.path
    and modules are imported by their bare name, as before.
    """
    if not directory.exists():
        return

    if qualified_prefix is None:
        _ensure_in_sys_path(directory)

    for entry in directory.iterdir():
        name = entry.name

        if name.startswith("_"):
            continue

        if entry.is_file() and name.endswith(".py"):
            base = name[:-3]
        elif entry.is_dir() and (entry / "__init__.py").exists():
            base = name
        else:
            continue

        module_name = f"{qualified_prefix}.{base}" if qualified_prefix else base
        _load_plugin_module(module_name)


def load_plugins() -> None:
    """Discover and load all external plugins."""
    _STARTUP_HOOKS.clear()
    _scan_plugin_dir(_bundled_plugins_dir(), qualified_prefix="docent.bundled_plugins")
    _scan_plugin_dir(plugins_dir())


def run_startup_hooks(context: Context) -> None:
    """Call all collected startup hooks."""
    for hook in _STARTUP_HOOKS:
        try:
            hook(context)
        except Exception as exc:
            print(f"Warning: startup hook failed: {exc}", file=sys.stderr)
