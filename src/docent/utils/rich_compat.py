"""Compatibility shim for Rich 15.x on Python 3.13.

Rich 15.0.0 ships unicode data files named ``unicode17-0-0.py`` (hyphens),
but ``importlib.import_module`` cannot resolve module names that contain
hyphens.  This module replaces ``rich._unicode_data.load`` with a version
that uses ``spec_from_file_location`` instead, which works fine with
hyphenated filenames.

Call ``patch_rich_unicode_loader()`` before the first Rich import that
would trigger the broken load path.  Patching is idempotent and
failure-safe — if anything goes wrong the original behaviour is left intact.
"""

from __future__ import annotations

import functools


def patch_rich_unicode_loader() -> None:
    """Apply the Rich unicode-data loader fix if needed.  Safe to call multiple times."""
    try:
        import bisect
        import importlib.util
        import os
        import unicodedata

        import rich._unicode_data as _rd
        from rich._unicode_data._versions import VERSIONS

        _data_dir = os.path.dirname(os.path.abspath(_rd.__file__))
        _version_set = set(VERSIONS)
        _version_order = [[int(x) for x in v.split(".")] for v in VERSIONS]

        @functools.cache
        def _fixed_load(unicode_version: str = "auto"):
            if unicode_version in ("auto", "latest"):
                detected = unicodedata.unidata_version
            else:
                detected = unicode_version
            try:
                parts = [int(x) for x in detected.split(".")]
                ver = f"{parts[0]}.{parts[1]}.{parts[2]}"
                if ver not in _version_set:
                    idx = bisect.bisect_right(_version_order, parts) - 1
                    ver = VERSIONS[max(0, idx)]
            except (ValueError, IndexError):
                ver = VERSIONS[-1]
            ver_comp = ver.replace(".", "-")
            fname = os.path.join(_data_dir, f"unicode{ver_comp}.py")
            spec = importlib.util.spec_from_file_location(
                f"_rich_ud_{ver_comp.replace('-', '_')}", fname
            )
            module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            return module.cell_table

        _rd.load = _fixed_load
    except Exception:
        pass
