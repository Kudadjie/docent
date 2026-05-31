#!/usr/bin/env python3
"""One-shot script to split studio/__init__.py into focused mixin files.

Run from the repo root:
    uv run python scripts/split_studio.py
"""
from __future__ import annotations

import re
from pathlib import Path

STUDIO = Path("src/docent/bundled_plugins/studio")
INIT = STUDIO / "__init__.py"

content = INIT.read_text(encoding="utf-8")
lines = content.splitlines(keepends=True)

# ---------------------------------------------------------------------------
# Step 1: Locate method boundaries
# ---------------------------------------------------------------------------
# Each action is: @action(...)\n    def method_name(self, inputs, context):
# We find the START of each @action block and the end (= start of the next one,
# or end of the class, whichever comes first).

# Line-numbers where @action appears (1-based in the original file):
action_lines = [i for i, ln in enumerate(lines) if ln.strip().startswith("@action(")]
# Also locate the class declaration and on_startup
class_line = next(i for i, ln in enumerate(lines) if "class StudioTool" in ln)
on_startup_line = next(i for i, ln in enumerate(lines) if ln.startswith("def on_startup"))

# Build blocks: (start_line, method_name)
blocks: list[tuple[int, int, str]] = []  # (start, end, method_name)
for idx, start in enumerate(action_lines):
    # Find the def line just after this @action block
    def_line = next(
        i for i in range(start + 1, start + 20)
        if lines[i].strip().startswith("def ")
    )
    method_name = re.match(r'\s+def (\w+)\(', lines[def_line]).group(1)  # type: ignore[union-attr]
    end = action_lines[idx + 1] if idx + 1 < len(action_lines) else on_startup_line
    blocks.append((start, end, method_name))

print(f"Found {len(blocks)} actions:")
for s, e, n in blocks:
    print(f"  {n}: lines {s+1}-{e}")

# ---------------------------------------------------------------------------
# Step 2: Assign each method to a group
# ---------------------------------------------------------------------------
RESEARCH_METHODS = {
    "deep_research", "lit", "review", "compare", "draft", "replicate", "audit",
}
NOTEBOOK_METHODS = {"to_notebook"}
SEARCH_METHODS = {
    "search_papers", "get_paper", "scholarly_search", "read_output", "save_synthesis",
}
CONFIG_METHODS = {"config_show", "config_set"}

def get_group(name: str) -> str:
    if name in RESEARCH_METHODS:
        return "research"
    if name in NOTEBOOK_METHODS:
        return "notebook"
    if name in SEARCH_METHODS:
        return "search"
    if name in CONFIG_METHODS:
        return "config"
    raise ValueError(f"Unknown action: {name}")

grouped: dict[str, list[tuple[int, int, str]]] = {
    "research": [], "notebook": [], "search": [], "config": [],
}
for block in blocks:
    grouped[get_group(block[2])].append(block)

# ---------------------------------------------------------------------------
# Step 3: Extract the module header (everything before the class declaration)
# ---------------------------------------------------------------------------
# Between the class decl and first @action:
header_lines = lines[:class_line]  # everything before "class StudioTool"

# Extract JUST the class body attributes (name, description, category)
# These go into the thin __init__.py shell
class_header_end = action_lines[0]
class_attrs = "".join(lines[class_line:class_header_end]).rstrip()

# ---------------------------------------------------------------------------
# Step 4: Build the _studio_shared.py file
# ---------------------------------------------------------------------------
# Extract _PRICING_NOTE and _KNOWN_RESEARCH_KEYS from the header region
pricing_start = next(i for i, ln in enumerate(lines) if "_PRICING_NOTE = " in ln)
pricing_end = next(i for i in range(pricing_start + 1, pricing_start + 10) if lines[i].strip() == ")")
known_start = next(i for i, ln in enumerate(lines) if "_KNOWN_RESEARCH_KEYS = {" in ln)
known_end = next(i for i in range(known_start + 1, known_start + 50) if lines[i].strip() == "}")

shared_content = "".join([
    '"""Constants shared across Studio action mixin modules."""\n',
    "from __future__ import annotations\n\n",
    *lines[pricing_start:pricing_end + 1],
    "\n\n",
    *lines[known_start:known_end + 1],
    "\n",
])
(STUDIO / "_studio_shared.py").write_text(shared_content, encoding="utf-8")
print(f"\nWrote _studio_shared.py ({len(shared_content.splitlines())} lines)")

# ---------------------------------------------------------------------------
# Step 5: Write each mixin file
# ---------------------------------------------------------------------------
COMMON_IMPORTS = """\
from __future__ import annotations

import json
import shutil
from pathlib import Path

from docent.core import Context, ProgressEvent, action
from docent.core.shapes import ErrorShape, MessageShape
"""

def extract_methods(method_blocks: list[tuple[int, int, str]]) -> str:
    parts = []
    for start, end, name in method_blocks:
        parts.append("".join(lines[start:end]))
    return "".join(parts)

FILE_CONFIGS: dict[str, dict] = {
    "research": {
        "filename": "_research.py",
        "docstring": '"""Research workflow action mixins: deep-research, lit, review, compare, draft, replicate, audit."""',
        "extra_imports": """\
from docent.bundled_plugins.studio._studio_shared import _PRICING_NOTE
from docent.bundled_plugins.studio.feynman import (
    FeynmanNotFoundError, _find_feynman, _run_feynman, _summarize_feynman_error,
)
from docent.bundled_plugins.studio.helpers import (
    _append_references, _artifact_slug, _read_guide_files, _slugify,
    _strip_references_section,
)
from docent.bundled_plugins.studio.models import (
    AuditInputs, CompareInputs, DeepInputs, DraftInputs, LitInputs,
    ReplicateInputs, ResearchResult, ReviewInputs,
)
from docent.bundled_plugins.studio.preflights import (
    _preflight_docent, _preflight_oc_only, _route_output,
)
from docent.bundled_plugins.studio._init_helpers import _path_under
""",
    },
    "notebook": {
        "filename": "_notebook_actions.py",
        "docstring": '"""NotebookLM action mixin: to-notebook."""',
        "extra_imports": """\
from docent.bundled_plugins.studio._notebook import (
    ToNotebookInputs, ToNotebookResult, _find_sources_path, _nlm_push, _rank_sources,
)
from docent.bundled_plugins.studio.preflights import _preflight_to_notebook
""",
    },
    "search": {
        "filename": "_search_actions.py",
        "docstring": '"""Search and output action mixins: search-papers, get-paper, scholarly-search, read-output, save-synthesis."""',
        "extra_imports": """\
from docent.bundled_plugins.studio._init_helpers import _path_under
from docent.bundled_plugins.studio.models import (
    GetPaperInputs, GetPaperResult, ReadOutputInputs, ReadOutputResult,
    SaveSynthesisInputs, SaveSynthesisResult, ScholarlySearchInputs,
    ScholarlySearchResult, SearchPapersInputs, SearchPapersResult,
)
""",
    },
    "config": {
        "filename": "_config_actions.py",
        "docstring": '"""Config action mixins: config-show, config-set."""',
        "extra_imports": """\
from docent.config import write_setting
from docent.bundled_plugins.studio._studio_shared import _KNOWN_RESEARCH_KEYS
from docent.bundled_plugins.studio.models import (
    ConfigSetInputs, ConfigSetResult, ConfigShowInputs, ConfigShowResult,
)
""",
    },
}

for group, cfg in FILE_CONFIGS.items():
    method_blocks = grouped[group]
    methods_text = extract_methods(method_blocks)

    # De-indent by 4 spaces (methods are at class level, need to be at module level)
    # but they should stay at class level inside a mixin class
    mixin_class_name = group.title().replace("_", "") + "Mixin"
    file_text = f"""{cfg['docstring']}
{COMMON_IMPORTS}
{cfg['extra_imports']}

class {mixin_class_name}:
    \"\"\"Mixin providing {group} actions for StudioTool.\"\"\"

{methods_text}"""

    out_path = STUDIO / cfg["filename"]
    out_path.write_text(file_text, encoding="utf-8")
    print(f"Wrote {cfg['filename']} ({len(file_text.splitlines())} lines, {len(method_blocks)} actions)")

# ---------------------------------------------------------------------------
# Step 6: Create _init_helpers.py for small helpers used by multiple mixins
# ---------------------------------------------------------------------------
helpers_content = """\
\"\"\"Small helpers shared between action mixin modules.\"\"\"
from __future__ import annotations

from pathlib import Path


def _path_under(path: Path, root: Path) -> bool:
    \"\"\"Return True if *path* is equal to or under *root* (both must be resolved).\"\"\"
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
"""
(STUDIO / "_init_helpers.py").write_text(helpers_content, encoding="utf-8")
print("\nWrote _init_helpers.py")

# ---------------------------------------------------------------------------
# Step 7: Rewrite __init__.py (thin class shell + mixin imports)
# ---------------------------------------------------------------------------
# Keep everything before class_line (imports, constants)
# Remove _PRICING_NOTE and _KNOWN_RESEARCH_KEYS (moved to _studio_shared.py)
# Remove _path_under (moved to _init_helpers.py)
# Keep the class, importing from mixins

# Extract the on_startup and everything after the class
after_class = "".join(lines[on_startup_line:])

# Build the new __init__.py header (imports etc., minus moved constants)
new_header_lines = []
skip_until = None
i = 0
while i < class_line:
    line = lines[i]
    # Skip _path_under function (moved to _init_helpers.py)
    if line.strip().startswith("def _path_under("):
        j = i + 1
        while j < class_line and (lines[j].startswith("    ") or lines[j].strip() == ""):
            j += 1
        i = j
        continue
    # Skip _PRICING_NOTE block
    if "_PRICING_NOTE = " in line:
        j = i + 1
        while j < class_line and (not lines[j].strip().startswith("_") or "_PRICING_NOTE" in lines[j]):
            j += 1
        i = j
        continue
    # Skip _KNOWN_RESEARCH_KEYS block
    if "_KNOWN_RESEARCH_KEYS = {" in line:
        j = i + 1
        while j < class_line and lines[j].strip() != "}":
            j += 1
        i = j + 1
        continue
    new_header_lines.append(line)
    i += 1

# Clean up trailing blank lines in header
header_text = "".join(new_header_lines).rstrip() + "\n\n"

# The new thin class
thin_class = """\
from docent.bundled_plugins.studio._research import ResearchMixin
from docent.bundled_plugins.studio._notebook_actions import NotebookMixin
from docent.bundled_plugins.studio._search_actions import SearchMixin
from docent.bundled_plugins.studio._config_actions import ConfigMixin
from docent.bundled_plugins.studio._studio_shared import _KNOWN_RESEARCH_KEYS, _PRICING_NOTE  # noqa: F401
from docent.bundled_plugins.studio._init_helpers import _path_under  # noqa: F401


@register_tool
class StudioTool(ResearchMixin, NotebookMixin, SearchMixin, ConfigMixin, Tool):
    \"\"\"Run research workflows (deep research, literature review, peer review) via Feynman.\"\"\"

    name = "studio"
    description = "Run research workflows (deep research, literature review, peer review) via Feynman."
    category = "studio"

"""

new_init = header_text + thin_class + after_class
INIT.write_text(new_init, encoding="utf-8")
print(f"\nRewritten __init__.py ({len(new_init.splitlines())} lines, down from {len(lines)})")
print("\nDone! Run: uv run pytest -x -q")
