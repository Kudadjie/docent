"""Preflight checks, Tavily key resolver, and output routing helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from docent.config import write_setting
from docent.core import Context
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Tavily key resolver
# ---------------------------------------------------------------------------

def _resolve_tavily_key(context: Context) -> str | None:
    """Ensure a Tavily API key is available. Prompt interactively if missing.

    Must be called OUTSIDE any Rich Progress context — i.e. from the preflight,
    not from inside a generator action.  Rich Progress steals stdin and will
    abort typer.prompt() calls.
    """
    rs = context.settings.research
    if rs.tavily_api_key:
        return rs.tavily_api_key

    import sys
    if not sys.stdin.isatty():
        return None

    try:
        import typer
        key = typer.prompt(
            "\nTavily API key (free at https://tavily.com — 1,000 calls/month)",
            default="",
            show_default=False,
        ).strip()
    except (EOFError, KeyboardInterrupt, typer.Abort):
        return None

    if not key:
        return None

    write_setting("research.tavily_api_key", key)
    rs.tavily_api_key = key
    return key


# ---------------------------------------------------------------------------
# Output routing + Obsidian vault
# ---------------------------------------------------------------------------

def _write_to_vault(
    out_path: Path,
    topic_or_artifact: str,
    workflow: str,
    backend: str,
    vault: Path,
) -> Path:
    """Write a research output to the Obsidian vault under {vault}/Studio/.

    Adds YAML frontmatter compatible with Obsidian, Dataview, and Citations plugin.
    Returns the destination path.
    """
    import datetime
    studio_dir = vault.expanduser() / "Studio"
    studio_dir.mkdir(parents=True, exist_ok=True)

    dest = studio_dir / out_path.name
    content = out_path.read_text(encoding="utf-8")

    date_str = datetime.date.today().isoformat()
    tag = f"docent/studio/{workflow}"
    frontmatter = (
        f"---\n"
        f"tags: [docent/studio, {tag}]\n"
        f"date: {date_str}\n"
        f"topic: \"{topic_or_artifact.replace(chr(34), chr(39))}\"\n"
        f"backend: {backend}\n"
        f"source_file: {out_path.name}\n"
        f"---\n\n"
    )

    dest.write_text(frontmatter + content, encoding="utf-8")
    return dest


def _route_output(inputs: Any, out_path: Path, sources_path: Path | None, context: "Context", workflow: str):
    """Generator helper: handles --output routing after local file is written.

    Yields ProgressEvents from _nlm_push when output='notebook'.
    Returns (notebook_id, vault_path, extra_message) as a tuple.
    """
    from ._notebook import _nlm_push

    if inputs.output == "notebook":
        topic = getattr(inputs, "topic", None)
        gf_list = getattr(inputs, "guide_files", []) or []
        result = yield from _nlm_push(
            out_path, sources_path, context,
            topic=topic,
            guide_files=[Path(p).expanduser() for p in gf_list],
        )
        if result["ok"]:
            return result["notebook_id"], None, f" {result['message']}"
        return None, None, f" (NotebookLM push failed: {result['message']})"

    if inputs.output == "vault":
        vault = context.settings.research.obsidian_vault
        if not vault:
            return None, None, (
                " (vault output requested but obsidian_vault is not configured — "
                "set it with: docent studio config-set --key obsidian_vault --value <path>)"
            )
        topic = getattr(inputs, "topic", None) or getattr(inputs, "artifact", "")
        dest = _write_to_vault(out_path, topic, workflow, inputs.backend, vault)
        return None, str(dest), f" Written to Obsidian vault: {dest.name}"

    return None, None, ""


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

def _preflight_docent(inputs: BaseModel, context: Context) -> None:
    """Pre-flight check for deep/lit actions with ``backend='docent'``.

    Runs *before* the generator is created (and therefore before Rich
    Progress takes over stdin).  Checks:
      1. OpenCode server is running.
      2. The planner model is usable (has credits, valid auth).
      3. Tavily API key is available.
    """
    if getattr(inputs, "backend", None) != "docent":
        return

    import typer
    from docent.ui.console import get_console
    from docent.utils.model_health import verify_opencode_model
    from .oc_client import OcClient, OcModelError, OcUnavailableError

    oc = OcClient(
        provider=context.settings.research.oc_provider,
        budget_usd=context.settings.research.oc_budget_usd,
    )
    if not oc.is_available():
        get_console().print(
            "[red]Error:[/] OpenCode server is not running. "
            "Start it with: [cyan]opencode serve --port 4096[/]"
        )
        raise typer.Exit(1)

    planner = context.settings.research.oc_model_planner
    console = get_console()
    try:
        with console.status(f"Checking model availability: [cyan]{planner}[/]..."):
            verify_opencode_model(planner, provider=context.settings.research.oc_provider)
        console.print(f"[green]✓[/] Model [cyan]{planner}[/] is available")
    except OcModelError as e:
        console.print(
            f"[red]✗[/] Model [cyan]{planner}[/] is not usable: {e}\n"
            "Use [cyan]--backend feynman[/] to run without OpenCode, or "
            "fix the model issue above then retry."
        )
        raise typer.Exit(1)
    except OcUnavailableError as e:
        console.print(
            f"[red]✗[/] OpenCode server became unreachable during model check: {e}\n"
            "Use [cyan]--backend feynman[/] or restart the OpenCode server."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(
            f"[red]✗[/] Model check failed for [cyan]{planner}[/] ({e})\n"
            "Most likely cause: quota exhausted on the provider — many providers\n"
            "silently drop requests rather than returning an explicit error.\n"
            "Diagnose with: [cyan]opencode stats[/]\n"
            "Options:\n"
            "  • Switch to [cyan]--backend feynman[/] (no OpenCode required)\n"
            "  • Change model: [cyan]docent studio config-set --key oc_model_planner --value <model>[/]\n"
            "  • Top up your OpenCode subscription and retry"
        )
        raise typer.Exit(1)

    tavily_key = _resolve_tavily_key(context)
    if not tavily_key:
        get_console().print(
            "[red]Error:[/] Tavily API key is required for web search. "
            "Get one at https://tavily.com (free tier: 1,000 calls/month)."
        )
        raise typer.Exit(1)


def _preflight_oc_only(inputs: BaseModel, context: Context) -> None:
    """Pre-flight check for review/compare/draft/replicate/audit (needs OcClient but not Tavily)."""
    if getattr(inputs, "backend", None) != "docent":
        return

    import typer
    from docent.ui.console import get_console
    from docent.utils.model_health import verify_opencode_model
    from .oc_client import OcClient, OcModelError, OcUnavailableError

    oc = OcClient(
        provider=context.settings.research.oc_provider,
        budget_usd=context.settings.research.oc_budget_usd,
    )
    if not oc.is_available():
        get_console().print(
            "[red]Error:[/] OpenCode server is not running. "
            "Start it with: [cyan]opencode serve --port 4096[/]"
        )
        raise typer.Exit(1)

    reviewer = context.settings.research.oc_model_reviewer
    console = get_console()
    try:
        with console.status(f"Checking model availability: [cyan]{reviewer}[/]..."):
            verify_opencode_model(reviewer, provider=context.settings.research.oc_provider)
        console.print(f"[green]✓[/] Model [cyan]{reviewer}[/] is available")
    except OcModelError as e:
        console.print(
            f"[red]✗[/] Model [cyan]{reviewer}[/] is not usable: {e}\n"
            "Use [cyan]--backend feynman[/] to run without OpenCode, or "
            "fix the model issue above then retry."
        )
        raise typer.Exit(1)
    except OcUnavailableError as e:
        console.print(
            f"[red]✗[/] OpenCode server became unreachable during model check: {e}\n"
            "Use [cyan]--backend feynman[/] or restart the OpenCode server."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(
            f"[red]✗[/] Model check failed for [cyan]{reviewer}[/] ({e})\n"
            "Most likely cause: quota exhausted on the provider — many providers\n"
            "silently drop requests rather than returning an explicit error.\n"
            "Diagnose with: [cyan]opencode stats[/]\n"
            "Options:\n"
            "  • Switch to [cyan]--backend feynman[/] (no OpenCode required)\n"
            "  • Change model: [cyan]docent studio config-set --key oc_model_reviewer --value <model>[/]\n"
            "  • Top up your OpenCode subscription and retry"
        )
        raise typer.Exit(1)
