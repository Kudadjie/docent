"""Contract test: every --flag in docs/cli.md and README.md must exist in some registered tool schema."""
import re
from pathlib import Path

DOCS_ROOT = Path(__file__).parent.parent

# Flags that appear in docs but are not derived from tool input schemas.
_EXTRA_VALID = {
    # Typer / app built-ins
    "help",
    "version",
    "verbose",
    "no-color",
    # README example plugin (hypothetical echo tool in plugin docs)
    "msg",
    "count",
    "flag",      # generic --flag placeholder used in plugin example text
    # Other CLI tools documented in README/docs (uv, pip, npm)
    "all-extras",   # uv sync --all-extras
    "editable",     # uv tool install --editable .
    "upgrade",      # pip install --upgrade docent-cli
    # MCP JSON config argument (not a CLI flag)
    "directory",    # "--directory" in .mcp.json args array
}


def _schema_flags() -> set[str]:
    from docent.core import all_tools, collect_actions, load_plugins

    load_plugins()
    flags: set[str] = set()
    for tool_cls in all_tools().values():
        actions = collect_actions(tool_cls)
        if actions:
            for _, (_, meta) in actions.items():
                for fname in meta.input_schema.model_fields:
                    flags.add(fname.replace("_", "-"))
        elif tool_cls.input_schema:
            for fname in tool_cls.input_schema.model_fields:
                flags.add(fname.replace("_", "-"))
    return flags


def test_doc_flags_are_valid():
    valid = _schema_flags() | _EXTRA_VALID
    stale: list[str] = []
    pattern = re.compile(r"--([a-z][a-z0-9-]+)")

    for doc in ("README.md", "docs/cli.md"):
        text = (DOCS_ROOT / doc).read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            flag = m.group(1)
            if flag not in valid:
                stale.append(f"{doc}: --{flag}")

    assert not stale, (
        "Docs reference flags not in any registered schema:\n"
        + "\n".join(f"  {s}" for s in sorted(set(stale)))
    )
