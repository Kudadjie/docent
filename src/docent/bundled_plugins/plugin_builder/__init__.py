"""Plugin Builder — generate, validate, sandbox-test, and install Docent plugins on demand.

Five MCP-exposed actions:
  generate     — Docent LLM generates a plugin from a natural-language spec
  iterate      — Docent LLM revises an existing draft based on feedback
  validate     — static AST checks (no LLM); returns errors + warnings
  sandbox_test — load plugin in an isolated registry, run one action, restore registry
  install      — write approved code to ~/.docent/plugins/{name}.py

The orchestrating AI (any MCP client) applies the worthiness gate before calling
generate — the gate criteria live in the generate action's description.

Model is configurable via plugin_builder.model in config.toml (LiteLLM string).
Default: deepseek/deepseek-chat.
"""

from __future__ import annotations

import ast
import json
import re
import types as _types
import uuid
from collections.abc import Generator
from pathlib import Path

from pydantic import BaseModel, Field

from docent.core.context import Context
from docent.core.events import ProgressEvent
from docent.core.registry import _REGISTRY, register_tool
from docent.core.tool import Tool, action

# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

_AGENTS_DIR = Path(__file__).parent / "agents"


def _system_prompt() -> str:
    return (_AGENTS_DIR / "system.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Input / output models
# ---------------------------------------------------------------------------

_WORTHINESS_GATE = (
    "WORTHINESS GATE — only call this tool when ≥3 of 5 criteria are true: "
    "(1) workflow runs >3 times, "
    "(2) makes sense without an AI present (autonomous execution), "
    "(3) parameter space is well-defined, "
    "(4) produces structured output suited to Docent shapes, "
    "(5) integrates with existing Docent tools. "
    "The sharpest filter is criterion 2: if the workflow requires AI reasoning to execute, "
    "it is an AI task — not a plugin. "
    "When skipping, tell the user explicitly why a plugin is not appropriate."
)


class GenerateInputs(BaseModel):
    spec: str = Field(description="Natural-language description of the plugin to build.")
    context: str | None = Field(
        None,
        description="Additional workflow context the AI client has gathered about the user's needs.",
    )
    model: str | None = Field(
        None,
        description="OpenCode model override (e.g. 'deepseek-v4-pro'). Defaults to plugin_builder.model in config.",
    )


class GenerateResult(BaseModel):
    ok: bool
    plugin_id: str = Field(description="Session identifier — pass to iterate/sandbox_test.")
    code: str = Field(default="")
    explanation: str = Field(default="")
    actions: list[str] = Field(default_factory=list)
    error: str | None = None


class IterateInputs(BaseModel):
    plugin_id: str = Field(description="plugin_id from the generate step (for traceability).")
    code: str = Field(description="Current plugin code to revise.")
    feedback: str = Field(description="What to change, fix, or improve in the plugin.")
    model: str | None = Field(
        None,
        description="OpenCode model override. Defaults to plugin_builder.model in config.",
    )


class IterateResult(BaseModel):
    ok: bool
    plugin_id: str
    code: str = Field(default="")
    changes: str = Field(default="", description="Plain-English summary of what changed.")
    error: str | None = None


class ValidateInputs(BaseModel):
    code: str = Field(description="Plugin source code to validate.")


class ValidateResult(BaseModel):
    ok: bool
    valid: bool
    errors: list[str] = Field(default_factory=list, description="Blocking issues.")
    warnings: list[str] = Field(default_factory=list, description="Non-blocking issues.")


class SandboxTestInputs(BaseModel):
    code: str = Field(description="Plugin source code to test.")
    action: str = Field(description="Action name to invoke (e.g. 'hello', 'scan').")
    inputs: str = Field(
        default="{}",
        description='JSON-encoded inputs to pass to the action, e.g. \'{"message": "hello"}\'.',
    )


class SandboxTestResult(BaseModel):
    ok: bool
    success: bool = False
    output: str = Field(default="", description="Serialised result from the action.")
    errors: list[str] = Field(default_factory=list)
    shapes: list[str] = Field(default_factory=list, description="OutputShape type names returned.")


class InstallInputs(BaseModel):
    code: str = Field(description="Plugin source code to install.")
    name: str = Field(description="Plugin filename in snake_case (no .py extension).")
    force: bool = Field(False, description="Overwrite if a plugin with this name already exists.")


class InstallResult(BaseModel):
    ok: bool
    path: str = Field(default="")
    actions_registered: list[str] = Field(default_factory=list)
    message: str = Field(default="")
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_code_block(text: str) -> str:
    """Pull the first ```python ... ``` block from the LLM response."""
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: strip any leading/trailing fence markers and return raw text.
    return text.strip().strip("`").strip()


def _extract_actions_from_ast(tree: ast.AST) -> list[str]:
    """Return names of @action-decorated methods in the AST.

    Handles both bare ``@action`` (Name) and called ``@action(...)`` (Call).
    """

    def _is_action_decorator(d: ast.expr) -> bool:
        if isinstance(d, ast.Name):
            return d.id == "action"
        if isinstance(d, ast.Attribute):
            return d.attr == "action"
        if isinstance(d, ast.Call):
            return _is_action_decorator(d.func)
        return False

    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(_is_action_decorator(d) for d in node.decorator_list)
    ]


def _extract_tool_name_from_ast(tree: ast.AST) -> str | None:
    """Return the value of `name = '...'` inside a Tool subclass, or None."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(
            (isinstance(b, ast.Name) and b.id == "Tool")
            or (isinstance(b, ast.Attribute) and b.attr == "Tool")
            for b in node.bases
        ):
            continue
        for stmt in node.body:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == "name"
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                return stmt.value.value
    return None


def _static_validate(code: str) -> tuple[bool, list[str], list[str]]:
    """Return (valid, errors, warnings) from a static AST analysis."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, [f"Syntax error at line {exc.lineno}: {exc.msg}"], []

    # Must have a Tool subclass.
    tool_classes = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef)
        and any(
            (isinstance(b, ast.Name) and b.id == "Tool")
            or (isinstance(b, ast.Attribute) and b.attr == "Tool")
            for b in n.bases
        )
    ]
    if not tool_classes:
        errors.append("No class inheriting from Tool found — add @register_tool class MyTool(Tool)")

    # Must have @register_tool.
    has_register = any(
        any(
            (isinstance(d, ast.Name) and d.id == "register_tool")
            or (isinstance(d, ast.Attribute) and d.attr == "register_tool")
            for d in n.decorator_list
        )
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef)
    )
    if not has_register:
        errors.append("Missing @register_tool decorator on the Tool subclass")

    # Must have at least one @action (bare or called form).
    action_methods = _extract_actions_from_ast(tree)
    if not action_methods:
        warnings.append("No @action decorated methods found")

    # Should have a name attribute.
    tool_name = _extract_tool_name_from_ast(tree)
    if tool_name is None:
        warnings.append("Tool class is missing a name = '...' attribute")

    return len(errors) == 0, errors, warnings


def _llm_generate(prompt: str, model: str) -> str:
    """Call the Docent LLM (via OpenCode) with the plugin builder system prompt."""
    from docent.bundled_plugins.studio.oc_client import OcClient, OcUnavailableError

    client = OcClient()
    if not client.is_available():
        raise OcUnavailableError(
            "OpenCode server is not running. Start it with: opencode serve --port 4096"
        )
    # OcClient.call() takes a single prompt; prepend the system prompt.
    full_prompt = f"{_system_prompt()}\n\n---\n\nUser request:\n{prompt}"
    return client.call(full_prompt, model=model)


def _run_in_sandbox(code: str, action_name: str, inputs: dict) -> tuple[bool, str, list[str]]:
    """Execute code in an isolated registry, invoke action_name, restore registry.

    Returns (success, output_json, error_list).
    """
    from docent.core.invoke import run_action

    saved = dict(_REGISTRY)
    _REGISTRY.clear()

    try:
        module = _types.ModuleType("docent._sandbox_plugin")
        module.__file__ = "<sandbox>"
        exec(compile(code, "<sandbox>", "exec"), vars(module))  # noqa: S102

        # Resolve Pydantic v2 forward references that stay unresolved when
        # models are defined inside exec() with a custom namespace.
        # `from __future__ import annotations` turns all annotations into
        # strings; model_rebuild() must receive _types_namespace so it can
        # resolve e.g. `list[UrgentEntry]` back to the actual class.
        ns = vars(module)
        for _obj in list(ns.values()):
            if isinstance(_obj, type) and issubclass(_obj, BaseModel) and _obj is not BaseModel:
                try:
                    _obj.model_rebuild(
                        force=True,
                        _parent_namespace_depth=0,
                        _types_namespace=ns,
                    )
                except Exception:
                    pass

        # Identify tool name registered by exec() side-effect.
        new_names = set(_REGISTRY.keys()) - set(saved.keys())
        if not new_names:
            return False, "", ["Plugin exec() did not register any tool"]
        if len(new_names) > 1:
            return False, "", [f"Plugin registered multiple tools: {sorted(new_names)}"]
        tool_name = next(iter(new_names))

        raw = run_action(tool_name, action_name, inputs)

        # Collect generator output.
        if hasattr(raw, "__next__"):
            lines = []
            result_value = None
            try:
                while True:
                    evt = next(raw)
                    lines.append(str(evt))
            except StopIteration as stop:
                result_value = stop.value
            output = json.dumps(
                result_value.model_dump() if hasattr(result_value, "model_dump") else result_value,
                indent=2,
            )
        else:
            output = json.dumps(raw.model_dump() if hasattr(raw, "model_dump") else raw, indent=2)

        return True, output, []

    except Exception as exc:
        return False, "", [f"{type(exc).__name__}: {exc}"]
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(saved)


def _plugins_dir() -> Path:
    from docent.utils.paths import plugins_dir

    return plugins_dir()


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@register_tool
class PluginBuilderTool(Tool):
    name = "plugin_builder"
    description = (
        "Generate, iterate, validate, sandbox-test, and install Docent plugins on demand. "
        "Uses a specialised Docent LLM (configurable via plugin_builder.model) to produce "
        "idiomatic plugin code from a natural-language spec. "
        "Requires an AI client to apply the worthiness gate before calling generate."
    )

    @action(
        description=("Generate a Docent plugin from a natural-language spec. " + _WORTHINESS_GATE),
        input_schema=GenerateInputs,
    )
    def generate(
        self, inputs: GenerateInputs, context: Context
    ) -> Generator[ProgressEvent, None, GenerateResult]:
        model = inputs.model or context.settings.plugin_builder.model
        plugin_id = str(uuid.uuid4())

        yield ProgressEvent(phase="init", message="Reading spec…")

        user_msg = f"Build a Docent plugin that does the following:\n\n{inputs.spec}"
        if inputs.context:
            user_msg += f"\n\nAdditional context:\n{inputs.context}"

        yield ProgressEvent(phase="llm", message=f"Calling OpenCode LLM ({model})…")

        try:
            raw_response = _llm_generate(user_msg, model)
        except Exception as exc:
            return GenerateResult(ok=False, plugin_id=plugin_id, error=str(exc))

        yield ProgressEvent(phase="parse", message="Extracting code…")

        code = _extract_code_block(raw_response)

        # Split explanation from code: anything before the first ``` is explanation.
        parts = raw_response.split("```python", 1)
        explanation = parts[0].strip() if len(parts) > 1 else ""

        # Parse action names from AST.
        try:
            tree = ast.parse(code)
            actions = _extract_actions_from_ast(tree)
        except SyntaxError:
            actions = []

        return GenerateResult(
            ok=True,
            plugin_id=plugin_id,
            code=code,
            explanation=explanation,
            actions=actions,
        )

    @action(
        description=(
            "Revise a previously generated plugin based on feedback. "
            "Pass the plugin_id and current code from generate, plus feedback describing what to change."
        ),
        input_schema=IterateInputs,
    )
    def iterate(
        self, inputs: IterateInputs, context: Context
    ) -> Generator[ProgressEvent, None, IterateResult]:
        model = inputs.model or context.settings.plugin_builder.model

        yield ProgressEvent(phase="process", message="Processing feedback…")

        user_msg = (
            f"Here is the current Docent plugin code:\n\n"
            f"```python\n{inputs.code}\n```\n\n"
            f"Feedback: {inputs.feedback}\n\n"
            f"Revise the plugin to address this feedback. "
            f"Return only the complete revised Python code block."
        )

        yield ProgressEvent(phase="llm", message=f"Calling OpenCode LLM ({model})…")

        try:
            raw_response = _llm_generate(user_msg, model)
        except Exception as exc:
            return IterateResult(ok=False, plugin_id=inputs.plugin_id, error=str(exc))

        yield ProgressEvent(phase="parse", message="Applying changes…")

        new_code = _extract_code_block(raw_response)
        parts = raw_response.split("```python", 1)
        changes = parts[0].strip() if len(parts) > 1 else "Code revised."

        return IterateResult(
            ok=True,
            plugin_id=inputs.plugin_id,
            code=new_code,
            changes=changes,
        )

    @action(
        description=(
            "Validate plugin source code with static AST analysis — no LLM call. "
            "Returns blocking errors (must fix before install) and non-blocking warnings."
        ),
        input_schema=ValidateInputs,
    )
    def validate(self, inputs: ValidateInputs, context: Context) -> ValidateResult:
        valid, errors, warnings = _static_validate(inputs.code)
        return ValidateResult(ok=True, valid=valid, errors=errors, warnings=warnings)

    @action(
        description=(
            "Load the plugin in an isolated registry, invoke one action with test inputs, "
            "then restore the registry. No disk writes. "
            "Use this to verify the plugin runs correctly before installing."
        ),
        input_schema=SandboxTestInputs,
    )
    def sandbox_test(self, inputs: SandboxTestInputs, context: Context) -> SandboxTestResult:
        try:
            parsed_inputs: dict = json.loads(inputs.inputs)
        except json.JSONDecodeError as exc:
            return SandboxTestResult(ok=False, errors=[f"Invalid JSON in inputs: {exc}"])

        success, output, errors = _run_in_sandbox(inputs.code, inputs.action, parsed_inputs)

        shapes: list[str] = []
        if success and output:
            try:
                result_dict = json.loads(output)
                if isinstance(result_dict, dict) and "shapes" in result_dict:
                    shapes = [
                        s.get("type", "") for s in result_dict["shapes"] if isinstance(s, dict)
                    ]
            except (json.JSONDecodeError, AttributeError):
                pass

        return SandboxTestResult(
            ok=True,
            success=success,
            output=output,
            errors=errors,
            shapes=shapes,
        )

    @action(
        description=(
            "Write approved plugin code to ~/.docent/plugins/{name}.py. "
            "The plugin becomes active after the next `docent` invocation. "
            "Only call after the user has reviewed the code and sandbox test passed."
        ),
        input_schema=InstallInputs,
    )
    def install(self, inputs: InstallInputs, context: Context) -> InstallResult:
        # Validate name.
        if not re.match(r"^[a-z][a-z0-9_]*$", inputs.name):
            return InstallResult(
                ok=False,
                error=f"Invalid name {inputs.name!r} — must be snake_case (letters, digits, underscore).",
            )

        target = _plugins_dir() / f"{inputs.name}.py"

        if target.exists() and not inputs.force:
            return InstallResult(
                ok=False,
                error=(
                    f"{target} already exists. "
                    "Pass force=true to overwrite, or choose a different name."
                ),
            )

        # Parse action names for the confirmation message.
        try:
            tree = ast.parse(inputs.code)
            action_names = _extract_actions_from_ast(tree)
        except SyntaxError as exc:
            return InstallResult(
                ok=False, error=f"Syntax error in code — run validate first: {exc}"
            )

        _plugins_dir().mkdir(parents=True, exist_ok=True)
        target.write_text(inputs.code, encoding="utf-8")

        return InstallResult(
            ok=True,
            path=str(target),
            actions_registered=action_names,
            message=(
                f"Plugin written to {target}. "
                f"Actions: {', '.join(action_names) if action_names else '(none detected)'}. "
                "Restart `docent` or `docent ui` for the plugin to become active."
            ),
        )
