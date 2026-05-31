"""External plugin discovery.

Search order:
  1. src/docent/bundled_plugins/  (shipped plugins — may not exist yet, skip gracefully)
  2. ~/.docent/plugins/           (user-installed plugins, via plugins_dir() from paths.py)

Bundled plugins are imported under their full qualified path
(``docent.bundled_plugins.<name>``) so they share the same sys.modules slot as any
other absolute import of that module — no double-import risk.

External plugins are imported via ``importlib.util.spec_from_file_location`` with a
unique synthetic module name (``docent._ext_plugin_<stem>``) so two external plugins
that happen to have the same filename can coexist without sys.path contamination.

Broken plugins: log a warning at WARNING level, continue loading others.

Name conflicts (plugin registers a tool name already taken by another plugin):
  → WARN-AND-SKIP. The registry raises ``ValueError``; the loader catches it, logs a
    structured warning, and continues. Hard-failing on conflict would break the user's
    whole CLI just because a new Docent update added a tool whose name collides with an
    old external plugin. Warn-and-skip gives the user a clear diagnostic without a crash.

Startup hooks: plugins may define on_startup(context: Context) at module level.
The loader collects them; run_startup_hooks(context) calls them all after the CLI
creates its Context object.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Callable

from docent.core.context import Context
from docent.utils.paths import plugins_dir

_STARTUP_HOOKS: list[Callable[[Context], None]] = []
_LOADED_PLUGINS: list[dict] = []  # [{name, source, module_path, has_hook}]

_logger = logging.getLogger("docent.plugins")


def _bundled_plugins_dir() -> Path:
    import docent

    return Path(docent.__file__).parent / "bundled_plugins"


def _load_plugin_module(
    module_name: str,
    source: str = "external",
    file_path: Path | None = None,
) -> bool:
    """Import a plugin module and collect its startup hook if present.

    For external plugins, use ``file_path`` + ``spec_from_file_location`` so the
    plugin's module name is unique and sys.path is not modified.

    Returns True if loaded successfully, False on any recoverable error.
    """
    if file_path is not None:
        # External plugin: use spec_from_file_location to avoid sys.path pollution.
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            _logger.warning("Could not create import spec for external plugin '%s'", file_path)
            return False
        try:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except (Exception, SystemExit) as exc:
            sys.modules.pop(module_name, None)
            _logger.warning("Failed to load plugin '%s': %s", module_name, exc)
            return False
    else:
        # Bundled plugin: use standard import (qualified name already unique).
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            _logger.warning("Failed to load plugin '%s': %s", module_name, exc)
            return False

    module = sys.modules.get(module_name)
    has_hook = False
    if module is not None and hasattr(module, "on_startup"):
        hook = getattr(module, "on_startup")
        if callable(hook):
            _STARTUP_HOOKS.append(hook)
            has_hook = True

    module_path = str(file_path) if file_path else getattr(
        sys.modules.get(module_name), "__file__", None
    )
    _LOADED_PLUGINS.append({
        "name": module_name,
        "source": source,
        "module_path": module_path,
        "has_hook": has_hook,
    })
    return True


def _scan_plugin_dir(directory: Path, *, qualified_prefix: str | None = None) -> None:
    """Scan a directory for plugin modules/packages and load them.

    ``qualified_prefix`` — if given (e.g. ``"docent.bundled_plugins"``), modules are
    imported by their full qualified name.  Bundled plugins go through the normal import
    system.

    External plugins (no prefix) use ``spec_from_file_location`` with a synthetic unique
    module name ``docent._ext_plugin_<stem>`` — no sys.path modification needed.
    """
    if not directory.exists():
        return

    for entry in directory.iterdir():
        name = entry.name

        if name.startswith("_"):
            continue

        if entry.is_file() and name.endswith(".py"):
            base = name[:-3]
            file_path = entry
        elif entry.is_dir() and (entry / "__init__.py").exists():
            base = name
            file_path = entry / "__init__.py"
        else:
            continue

        if qualified_prefix:
            module_name = f"{qualified_prefix}.{base}"
            _load_plugin_module(module_name, source="bundled")
        else:
            # Unique synthetic name prevents collisions between external plugins
            # with the same filename from different directories.
            module_name = f"docent._ext_plugin_{base}"
            _load_plugin_module(module_name, source="external", file_path=file_path)


def load_plugins() -> None:
    """Discover and load all external plugins."""
    _STARTUP_HOOKS.clear()
    _LOADED_PLUGINS.clear()
    _scan_plugin_dir(_bundled_plugins_dir(), qualified_prefix="docent.bundled_plugins")
    _scan_plugin_dir(plugins_dir())


def list_plugins() -> list[dict]:
    """Return metadata for all currently loaded plugins."""
    return list(_LOADED_PLUGINS)


def run_startup_hooks(context: Context) -> None:
    """Call all collected startup hooks."""
    for hook in _STARTUP_HOOKS:
        try:
            hook(context)
        except Exception as exc:
            _logger.warning(
                "Startup hook '%s' failed: %s",
                getattr(hook, "__module__", "unknown"),
                exc,
            )
