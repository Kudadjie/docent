# Plugin Builder Guide

Plugin Builder is Docent's AI-assisted tool for generating, testing, and installing plugins from a plain-language description. Instead of writing the boilerplate yourself, you describe the workflow you want and the Builder produces a ready-to-run plugin file.

---

## Prerequisites

Plugin Builder uses the OpenCode server for LLM generation. Start it before opening the Builder:

```bash
opencode serve --port 4096
```

Leave that terminal open. The Builder will not generate without it.

---

## Quick start

1. Open `http://localhost:7432` and navigate to **Plugin Builder** in the sidebar.
2. Describe the plugin in the **Generate** text area.
3. Optionally add context (data formats, file paths, related tools) in the second field.
4. Pick a model from the **LLM model** dropdown (default: GLM-5.1).
5. Click **Generate Plugin**.

The progress strip shows the three generation stages (reading spec → LLM call → extracting code) in real time. When complete, the generated code appears in the **Generated Code** panel.

---

## Models

| Model | Notes |
|-------|-------|
| `glm-5.1` | Default. Fast and capable for most plugin specs. |
| `deepseek-v4-pro` | Stronger reasoning; good for complex multi-file logic. |
| `minimax-m2.7` | Large-context; use when the spec or context is very long. |
| `qwen3.5-plus` | Lightweight; good for simple single-action plugins. |

The model choice only affects the generate and iterate steps. Validate, sandbox, and install are all local and model-free.

---

## Worthiness gate

The Plugin Builder evaluates your spec against five criteria before generating:

1. The workflow runs more than three times (repetitive work).
2. It can execute without AI present (deterministic, automatable).
3. The parameter space is well-defined (clear inputs and outputs).
4. The output suits Docent's shapes (structured data, not freeform prose).
5. It integrates with existing Docent tools.

If fewer than three criteria are true — in particular, if the workflow *requires* AI reasoning to execute — the Builder will decline and explain why. This keeps generated plugins lightweight and reliable.

---

## History

Every generation run is saved to the history panel (click **History** in the page header). Each entry shows the model used, timestamp, spec snippet, and detected action names.

**Duplicate detection:** if you click Generate with the same spec and context as a previous successful run, the Builder shows a prompt instead of re-running the LLM:

- **Restore previous** — loads the saved code instantly with no LLM call.
- **Generate anyway** — bypasses the check and runs a fresh generation.

To revisit any previous plugin, open the History panel and click the entry. This restores the spec, context, model, code, and actions exactly as they were.

---

## Iterate

After generating code, click **Iterate** to revise it. Describe what you want to change in the feedback field and click **Revise Plugin**. The same model is used. The progress strip shows the three revision stages.

Each successful iteration updates the code in place and also updates the corresponding history entry so the saved copy stays current.

---

## Validate

Click **Validate** for a fast, local static check (no LLM). The validator reports:

- **Blocking errors** — must fix before the plugin will load (syntax errors, missing `@register_tool`, no `Tool` subclass).
- **Warnings** — non-blocking suggestions (no `@action` methods, missing `name` attribute).

Fix errors by using **Iterate** with the error message as feedback.

---

## Sandbox test

Click **Sandbox Test** to run one action in an isolated tool registry.

> **Heads up:** the isolation covers Docent's tool *registry* only — it is not a security
> sandbox. The plugin code executes in-process with your full user privileges (it can
> read/write files and make network calls), exactly as it would after install. Review
> the generated code before sandbox-testing it.

1. Enter the action name in the **Action name** field. The Builder pre-fills this from the generated `@action` methods.
2. Enter any inputs as a JSON object in the **Inputs (JSON)** field (leave `{}` for no inputs).
3. Click **Run in Sandbox**.

If the action runs successfully the output JSON is shown. If it fails, the error is shown — paste it into the **Iterate** feedback field to ask the LLM to fix it.

**Note on nested Pydantic models:** Generated plugins that use `from __future__ import annotations` and reference one model class inside another (e.g. `list[UrgentEntry]`) are automatically handled by the sandbox — it rebuilds Pydantic's forward references before running.

---

## Install

Click **Install** when you are satisfied with the code and sandbox test.

1. Set the **Plugin name** (snake_case, no `.py` extension). The Builder pre-fills a slug from your spec.
2. Tick **Overwrite existing** if you want to replace a plugin with the same name.
3. Click **Install Plugin**.

The plugin is written to `~/.docent/plugins/<name>.py`. Restart `docent` or `docent ui` for it to become active.

---

## Configuring the default model

The default model (`glm-5.1`) can be changed permanently in `~/.docent/config.toml`:

```toml
[plugin_builder]
model = "deepseek-v4-pro"
```

The UI model dropdown overrides this per-session.

---

## CLI / MCP access

The Plugin Builder is also available as five MCP tools when running `docent serve`:

| MCP tool | What it does |
|----------|-------------|
| `plugin_builder__generate` | LLM generates plugin from spec (streaming progress) |
| `plugin_builder__iterate` | LLM revises code based on feedback (streaming progress) |
| `plugin_builder__validate` | Static AST check — instant, no LLM |
| `plugin_builder__sandbox_test` | Runs one action in an isolated registry (registry-only isolation; code runs with full user privileges) |
| `plugin_builder__install` | Writes to `~/.docent/plugins/<name>.py` |

From Claude Code or any MCP client, call `plugin_builder__generate` with a `spec` string. The tool description includes the worthiness gate criteria so the AI client can apply them before calling.

```bash
# From the terminal (MCP client must be running)
docent plugin_builder generate --spec "A tool that scans my queue for overdue papers"
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| "OpenCode server is not running" | OpenCode not started | `opencode serve --port 4096` |
| Sandbox: `PydanticUserError: ... not fully defined` | Should be fixed automatically | Update to latest Docent; the sandbox now calls `model_rebuild` with the sandbox namespace |
| Install: "already exists" | A plugin with that name is installed | Tick **Overwrite existing** or choose a different name |
| Plugin doesn't appear after install | Server not restarted | Run `docent ui` again |
| Generated code uses wrong tool name | LLM drift | Use **Iterate** with feedback like "set `name = 'my_tool'`" |
