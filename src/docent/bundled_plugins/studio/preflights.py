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

def _preflight_free_backend(inputs: BaseModel, context: Context) -> None:
    """Show free-tier disclaimer, guide Tavily signup if key is missing, and confirm.

    Must be called before Rich Progress starts (it steals stdin).
    Raises typer.Exit(1) if the user declines to proceed.
    """
    if getattr(inputs, "backend", None) != "free":
        return

    import sys
    import typer
    from docent.ui.console import get_console
    from docent.config import write_setting
    from .free_research import FREE_TIER_DISCLAIMER, TAVILY_SIGNUP_GUIDE

    console = get_console()
    console.print(FREE_TIER_DISCLAIMER)

    try:
        if not typer.confirm("I understand the limitations. Proceed with the free tier?", default=False):
            raise typer.Exit(0)
    except (EOFError, KeyboardInterrupt):
        raise typer.Exit(0)

    # ── Tavily key guidance ───────────────────────────────────────────────────
    tavily_key = context.settings.research.tavily_api_key
    if not tavily_key:
        console.print(
            "\n[yellow]No Tavily API key found.[/] Web search results will be skipped.\n"
        )
        console.print(TAVILY_SIGNUP_GUIDE)

        if sys.stdin.isatty():
            try:
                raw = typer.prompt(
                    "Enter your Tavily API key to enable web search (Enter to skip)",
                    default="",
                    show_default=False,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                raw = ""

            if raw:
                write_setting("research.tavily_api_key", raw)
                context.settings.research.tavily_api_key = raw
                console.print("[green]✓[/] Tavily key saved.")
            else:
                console.print("[dim]Continuing without Tavily — only academic papers will be included.[/]")


def _preflight_guide_files(inputs: BaseModel) -> None:
    """Warn about unreadable/missing guide files and ask the user to confirm.

    Must be called before Rich Progress starts (it steals stdin).
    Raises typer.Exit(1) if the user declines to proceed.
    """
    raw_paths: list[str] = getattr(inputs, "guide_files", None) or []
    if not raw_paths:
        return

    from .helpers import _check_guide_files
    from docent.ui.console import get_console
    import typer

    _, problems = _check_guide_files(raw_paths)
    if not problems:
        return

    console = get_console()
    console.print("[yellow]Warning:[/] The following guide file(s) could not be read:")
    for p in problems:
        console.print(f"  [red]✗[/] {p}")

    try:
        if not typer.confirm("\nProceed anyway (skipping the files above)?", default=False):
            raise typer.Exit(1)
    except (EOFError, KeyboardInterrupt):
        raise typer.Exit(1)


def _preflight_docent(inputs: BaseModel, context: Context) -> None:
    """Pre-flight check for deep/lit actions (all backends).

    Runs *before* the generator is created (and therefore before Rich
    Progress takes over stdin).  Checks:
      0. Guide files are readable (all backends).
      1. Free-tier disclaimer + Tavily key guidance (backend='free').
      2. OpenCode server is running (backend='docent').
      3. The planner model is usable — credits, valid auth (backend='docent').
      4. Tavily API key is available (backend='docent').
    """
    _preflight_guide_files(inputs)
    _preflight_free_backend(inputs, context)

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
            "Start it with: [cyan]opencode serve --port 4096[/]\n"
            "Alternatives (no OpenCode required):\n"
            "  • [cyan]--backend free[/]    — Tavily + DuckDuckGo, no API key needed\n"
            "  • [cyan]--backend feynman[/] — Feynman agent (API credits required)"
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
            "Alternatives (no OpenCode required):\n"
            "  • [cyan]--backend free[/]    — Tavily + DuckDuckGo, no API key needed\n"
            "  • [cyan]--backend feynman[/] — Feynman agent (API credits required)\n"
            "Or fix the model issue above then retry."
        )
        raise typer.Exit(1)
    except OcUnavailableError as e:
        console.print(
            f"[red]✗[/] OpenCode server became unreachable during model check: {e}\n"
            "Alternatives (no OpenCode required):\n"
            "  • [cyan]--backend free[/]    — Tavily + DuckDuckGo, no API key needed\n"
            "  • [cyan]--backend feynman[/] — Feynman agent (API credits required)\n"
            "Or restart the OpenCode server and retry."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(
            f"[red]✗[/] Model check failed for [cyan]{planner}[/] ({e})\n"
            "Most likely cause: quota exhausted on the provider — many providers\n"
            "silently drop requests rather than returning an explicit error.\n"
            "Diagnose with: [cyan]opencode stats[/]\n"
            "Options:\n"
            "  • Switch to [cyan]--backend free[/] (no OpenCode or API key required)\n"
            "  • Switch to [cyan]--backend feynman[/] (no OpenCode required; AI API credits required)\n"
            "  • Change model: [cyan]docent studio config-set --key oc_model_planner --value <model>[/]\n"
            "  • Top up your OpenCode subscription and retry"
        )
        raise typer.Exit(1)

    tavily_key = _resolve_tavily_key(context)
    if not tavily_key:
        get_console().print(
            "[red]Error:[/] Tavily API key is required for the [cyan]docent[/] backend.\n"
            "Get one at https://tavily.com (free tier: 1,000 calls/month).\n"
            "Or switch to [cyan]--backend free[/] — uses DuckDuckGo when no Tavily key is set."
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
            "Use [cyan]--backend feynman[/] (AI API credits required) to run without OpenCode, or "
            "fix the model issue above then retry."
        )
        raise typer.Exit(1)
    except OcUnavailableError as e:
        console.print(
            f"[red]✗[/] OpenCode server became unreachable during model check: {e}\n"
            "Use [cyan]--backend feynman[/] (AI API credits required) or restart the OpenCode server."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(
            f"[red]✗[/] Model check failed for [cyan]{reviewer}[/] ({e})\n"
            "Most likely cause: quota exhausted on the provider — many providers\n"
            "silently drop requests rather than returning an explicit error.\n"
            "Diagnose with: [cyan]opencode stats[/]\n"
            "Options:\n"
            "  • Switch to [cyan]--backend feynman[/] (no OpenCode required; AI API credits required)\n"
            "  • Change model: [cyan]docent studio config-set --key oc_model_reviewer --value <model>[/]\n"
            "  • Top up your OpenCode subscription and retry"
        )
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# to-notebook preflight — file picker
# ---------------------------------------------------------------------------

def _suggest_rename(out_path: Path, console: Any, typer: Any) -> Path:
    """If the file heading implies a different name, offer to rename file + sources.

    Returns the (possibly renamed) path so the caller can update inputs.output_file.
    """
    from docent.bundled_plugins.studio._notebook import _derive_topic, _find_sources_path
    from docent.bundled_plugins.studio.helpers import _slugify

    # Derive topic two ways
    heading_topic = _derive_topic(out_path)               # reads heading from content
    stem = out_path.stem
    # Filename topic: strip backend/workflow suffixes the same way, ignoring content
    from docent.bundled_plugins.studio._notebook import _BACKEND_SUFFIXES, _WORKFLOW_SUFFIXES
    fname_stem = stem
    for suf in _BACKEND_SUFFIXES:
        if fname_stem.endswith(suf):
            fname_stem = fname_stem[: -len(suf)]
            break
    for suf in _WORKFLOW_SUFFIXES:
        if fname_stem.endswith(suf):
            fname_stem = fname_stem[: -len(suf)]
            break
    filename_topic = fname_stem.replace("-", " ").replace("_", " ")

    # Normalize both for comparison: lowercase, strip non-alphanumeric
    def _norm(t: str) -> str:
        import re as _re
        return _re.sub(r"[^a-z0-9]", "", t.lower())

    if _norm(heading_topic) == _norm(filename_topic):
        return out_path  # already consistent

    new_slug = _slugify(heading_topic)
    new_name = f"{new_slug}.md"
    new_path = out_path.parent / new_name

    if new_path == out_path or new_path.exists():
        return out_path  # would be a no-op or collision

    console.print(
        f"\n[yellow]File/topic mismatch:[/]\n"
        f"  File:  [dim]{out_path.name}[/]\n"
        f"  Topic: [cyan]{heading_topic}[/]\n"
        f"  Suggested name: [cyan]{new_name}[/]"
    )
    try:
        if not typer.confirm("  Rename the file to match its topic?", default=True):
            return out_path
    except (EOFError, KeyboardInterrupt):
        return out_path

    # Rename synthesis doc
    out_path.rename(new_path)
    console.print(f"  [green]Renamed:[/] {out_path.name} → {new_name}")

    # Rename sources file if found, standardising on the dash form
    old_src = _find_sources_path(out_path)
    if old_src and old_src.exists():
        new_src = out_path.parent / f"{new_slug}-sources.json"
        if new_src != old_src and not new_src.exists():
            old_src.rename(new_src)
            console.print(f"  [green]Renamed:[/] {old_src.name} → {new_src.name}")

    return new_path


def _check_synthesis_doc(out_path: Path, console: Any, typer: Any) -> None:
    """Refuse or confirm when the synthesis document is empty or suspiciously short."""
    try:
        content = out_path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return  # unreadable — caught elsewhere

    if not content:
        console.print(
            f"\n[red]Error:[/] [cyan]{out_path.name}[/] is empty. "
            "Nothing to add as a synthesis document."
        )
        raise typer.Exit(1)

    # Warn if there's a sources JSON but almost no synthesis text
    # (likely a blank template or accidental copy without content)
    if len(content) < 200:
        console.print(
            f"\n[yellow]Warning:[/] [cyan]{out_path.name}[/] has very little content "
            f"({len(content)} chars). It may not be a real synthesis document."
        )
        try:
            if not typer.confirm("Proceed anyway?", default=False):
                raise typer.Exit(1)
        except (EOFError, KeyboardInterrupt):
            raise typer.Exit(1)


def _warn_no_sources(out_path: Path, console: Any, typer: Any) -> None:
    """Warn and confirm when no matching sources JSON exists for an output file."""
    from docent.bundled_plugins.studio._notebook import _find_sources_path
    if _find_sources_path(out_path):
        return
    sources_path = out_path.parent / f"{out_path.stem}-sources.json"  # for display only
    console.print(
        f"\n[yellow]Warning:[/] No sources file found for [cyan]{out_path.name}[/] "
        f"(expected: [dim]{sources_path.name}[/]).\n"
        "Only the synthesis document itself will be added to NotebookLM — "
        "the original research sources won't be included.\n"
        "This typically happens when the file has been renamed."
    )
    try:
        if not typer.confirm("Proceed anyway?", default=False):
            raise typer.Exit(1)
    except (EOFError, KeyboardInterrupt):
        raise typer.Exit(1)


def _preflight_to_notebook(inputs: BaseModel, context: Context) -> None:
    """Interactive file picker when multiple research outputs exist in output_dir.

    If output_file is already set, just validates it exists.
    If multiple .md outputs are found and none is specified, shows a numbered
    list with an "all" option.  If topics appear different across selected files,
    warns the user before continuing.

    Mutates inputs.output_file (single pick) and inputs.output_files (extras for
    the "all" / multi case) so the generator body receives resolved paths.
    """
    import typer
    from docent.ui.console import get_console

    console = get_console()
    output_dir = context.settings.research.output_dir.expanduser()

    # ── Already specified: validate ───────────────────────────────────────
    if getattr(inputs, "output_file", None):
        p = Path(inputs.output_file)
        if not p.is_absolute():
            p = output_dir / inputs.output_file
        if not p.exists():
            console.print(f"[red]Error:[/] Research output not found: {p}")
            raise typer.Exit(1)
        if p.suffix.lower() != ".md":
            console.print(
                f"[red]Error:[/] [cyan]{p.name}[/] is not a Markdown file. "
                "--output-file must point to a synthesis document (.md), "
                "not a sources JSON or any other file type."
            )
            raise typer.Exit(1)
        p = _suggest_rename(p, console, typer)
        inputs.output_file = str(p)
        _check_synthesis_doc(p, console, typer)
        if not getattr(inputs, "sources_file", None):
            _warn_no_sources(p, console, typer)
        return

    # ── Discover candidates ───────────────────────────────────────────────
    candidates = sorted(
        [
            p for p in output_dir.glob("*.md")
            if not p.name.endswith("-review.md") and not p.name.endswith("-sources.json")
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ) if output_dir.is_dir() else []

    if not candidates:
        console.print(
            f"[red]Error:[/] No research output found in {output_dir}. "
            "Run [cyan]docent studio deep-research[/] or [cyan]docent studio lit[/] first."
        )
        raise typer.Exit(1)

    if len(candidates) == 1:
        inputs.output_file = str(candidates[0])
        return

    # ── Multi-file picker ─────────────────────────────────────────────────
    console.print(
        f"\n[bold]Found {len(candidates)} research output(s) in {output_dir}:[/]"
    )
    for i, p in enumerate(candidates, 1):
        import datetime
        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        console.print(f"  [cyan]{i}[/]) {p.stem}  [dim]({mtime})[/]")
    console.print(f"  [cyan]a[/]) All of the above")

    try:
        raw = typer.prompt(
            "\nSelect file(s) [1 / a]",
            default="1",
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        raise typer.Exit(1)

    if raw == "a" or raw == "all":
        selected = candidates
    else:
        try:
            idx = int(raw) - 1
            if not (0 <= idx < len(candidates)):
                raise ValueError
            selected = [candidates[idx]]
        except ValueError:
            console.print(f"[red]Invalid selection '{raw}'.[/]")
            raise typer.Exit(1)

    # ── Topic-diversity warning ───────────────────────────────────────────
    if len(selected) > 1:
        def _slug_prefix(p: Path) -> str:
            words = p.stem.replace("-", " ").replace("_", " ").split()
            return " ".join(words[:2]).lower()

        prefixes = {_slug_prefix(p) for p in selected}
        if len(prefixes) > 1:
            console.print(
                "\n[yellow]Warning:[/] The selected files appear to cover different topics:\n"
                + "\n".join(f"  • {p.stem}" for p in selected)
                + "\nThey will all be added as sources to the same notebook."
            )
            try:
                if not typer.confirm("Proceed anyway?", default=True):
                    raise typer.Exit(1)
            except (EOFError, KeyboardInterrupt):
                raise typer.Exit(1)

    selected = [_suggest_rename(p, console, typer) for p in selected]
    inputs.output_file = str(selected[0])
    # Extras stored in output_files; generator body handles them
    inputs.output_files = [str(p) for p in selected[1:]]
    _explicit_sources = getattr(inputs, "sources_file", None)
    for _sel in selected:
        _check_synthesis_doc(_sel, console, typer)
        if not _explicit_sources:
            _warn_no_sources(_sel, console, typer)
