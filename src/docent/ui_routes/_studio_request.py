"""Studio form → execution-surface rendering, shared by SSE and WebSocket paths.

``build_studio_request`` is the single source of truth that turns a
``StudioRunBody`` into BOTH the in-process kwargs (SSE path, ``studio.py``)
and the subprocess argv (WebSocket path, ``opencode.py``) at once, so the two
surfaces can never drift.
"""

from __future__ import annotations

import asyncio
import json
import re as _re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from docent.core.invoke import serialize_result as _serialize

_STUDIO_ACTION_MAP: dict[str, str] = {
    "deep": "deep-research",
    "lit": "lit",
    "peer": "review",
    "compare": "compare",
    "draft": "draft",
    "replicate": "replicate",
    "audit": "audit",
    "search": "search-papers",
    "scholarly": "scholarly-search",
    "getpaper": "get-paper",
    "citegraph": "cite-graph",
    "notebook": "to-notebook",
    "cfgshow": "config-show",
    "cfgset": "config-set",
}

_BACKEND_NORM: dict[str, str] = {
    "free": "free",
    "feynman": "feynman",
    "docent": "docent",
    "groq": "groq",
    # Archived: gemini, openrouter, anthropic, openai, ollama, lm_studio, mistral, cerebras
    # (still work from the CLI with --backend <name>; restore here to re-enable in the UI)
}


class StudioRunBody(BaseModel):
    action_id: str
    topic: str = ""
    backend: str = "free"
    dest: str = "local"
    guides: list[str] = []
    artifact: str = ""
    artifact_a: str = ""
    artifact_b: str = ""
    query: str = ""
    max_results: int = 10
    arxiv_id: str = ""
    out_path: str = ""
    src_path: str = ""
    max_sources: int = 20
    nlm: bool = True
    gate: bool = True
    persp: bool = True
    cfg_key: str = ""
    cfg_val: str = ""
    cite_identifier: str = ""
    cite_direction: str = "cited-by"
    cite_max: int = 25
    expand_citations: bool = False


@dataclass
class StudioRequest:
    """A resolved Studio form, rendered for BOTH execution surfaces at once.

    - ``kwargs`` — the dict fed to ``run_action`` on the in-process SSE path.
    - ``argv``   — the CLI flags following ``docent studio <action>`` on the
                   subprocess WebSocket path.

    Both are produced together in :func:`build_studio_request`, so the in-process
    and subprocess builders can no longer drift (the bug class that previously
    required editing two separate functions by hand).
    """

    action: str
    kwargs: dict[str, Any] = field(default_factory=dict)
    argv: list[str] = field(default_factory=list)


def build_studio_request(body: StudioRunBody) -> StudioRequest | None:
    """Single source of truth: StudioRunBody → (in-process kwargs, CLI argv).

    Returns None if the action_id is unknown. Each action branch appends to
    ``kwargs`` and ``argv`` side by side so the two representations stay in
    lockstep. The thin wrappers ``_parse_studio_body`` (SSE/in-process) and
    ``_build_studio_cmd`` (subprocess) both render from this.
    """
    action = _STUDIO_ACTION_MAP.get(body.action_id)
    if not action:
        return None
    backend = _BACKEND_NORM.get(body.backend.lower().replace(" ", "_"), "free")
    dest = body.dest.lower().replace(" →", "").strip()
    req = StudioRequest(action=action)
    k, a = req.kwargs, req.argv

    def _guides() -> None:
        k["guide_files"] = body.guides
        for g in body.guides or []:
            a.extend(["--guide-files", g])

    if action in ("deep-research", "lit", "draft"):
        k.update({"topic": body.topic, "backend": backend, "output": dest})
        a.extend(["--topic", body.topic, "--backend", backend, "--output", dest])
        # deep-research/lit gate the free backend behind a disclaimer; pre-confirm
        # it so the UI doesn't need a second prompt. draft is AI-backend-only and
        # its DraftInputs model has no `confirmed`/`expand_citations` field, so
        # passing either flag would make Click reject the command.
        if action in ("deep-research", "lit"):
            k["confirmed"] = True
            a.append("--confirmed")
            if body.expand_citations:
                k["expand_citations"] = True
                a.append("--expand-citations")
        _guides()
    elif action in ("review", "replicate", "audit"):
        k.update({"artifact": body.artifact, "backend": backend, "output": dest})
        a.extend(["--artifact", body.artifact, "--backend", backend, "--output", dest])
        _guides()
    elif action == "compare":
        k.update(
            {
                "artifact_a": body.artifact_a,
                "artifact_b": body.artifact_b,
                "backend": backend,
                "output": dest,
            }
        )
        a.extend(
            [
                "--artifact-a",
                body.artifact_a,
                "--artifact-b",
                body.artifact_b,
                "--backend",
                backend,
                "--output",
                dest,
            ]
        )
        _guides()
    elif action in ("search-papers", "scholarly-search"):
        k.update({"query": body.query, "max_results": body.max_results})
        a.extend(["--query", body.query, "--max-results", str(body.max_results)])
    elif action == "get-paper":
        k["arxiv_id"] = body.arxiv_id
        a.extend(["--arxiv-id", body.arxiv_id])
    elif action == "cite-graph":
        ident = body.cite_identifier.strip()
        is_arxiv = bool("arxiv" in ident.lower() or _re.match(r"^\d{4}\.\d{4,5}", ident))
        k.update(
            {
                "doi": None if is_arxiv else ident,
                "arxiv_id": ident if is_arxiv else None,
                "direction": body.cite_direction,
                "max_results": body.cite_max,
            }
        )
        a.extend(["--arxiv-id", ident] if is_arxiv else ["--doi", ident])
        a.extend(["--direction", body.cite_direction, "--max-results", str(body.cite_max)])
    elif action == "to-notebook":
        k.update(
            {
                "output_file": body.out_path or None,
                "sources_file": body.src_path or None,
                "max_sources": body.max_sources,
                "run_nlm_research": body.nlm,
                "run_quality_gate": body.gate,
                "run_perspectives": body.persp,
            }
        )
        if body.src_path:
            a.extend(["--sources-file", body.src_path])
        # Derive output-file from the sources path when not set explicitly. This
        # keeps the subprocess off the interactive file-picker preflight, which
        # hangs in a non-TTY child when multiple outputs exist.
        out_file = body.out_path or _re.sub(r"-sources\.json$", ".md", body.src_path)
        if out_file and out_file != body.src_path:
            a.extend(["--output-file", out_file])
        a.extend(["--max-sources", str(body.max_sources)])
        if not body.nlm:
            a.append("--no-run-nlm-research")
        if not body.gate:
            a.append("--no-run-quality-gate")
        if not body.persp:
            a.append("--no-run-perspectives")
    elif action == "config-set":
        k.update({"key": body.cfg_key, "value": body.cfg_val})
        a.extend(["--key", body.cfg_key, "--value", body.cfg_val])
    # config-show: no args on either surface.
    return req


def _parse_studio_body(body: StudioRunBody) -> tuple[str, dict[str, Any]] | None:
    """In-process (SSE) view of a StudioRunBody. Thin wrapper over
    :func:`build_studio_request` — the single source of truth shared with the
    subprocess CLI builder."""
    req = build_studio_request(body)
    return None if req is None else (req.action, req.kwargs)


def _form_to_studio_args(action_id: str, body: StudioRunBody) -> dict[str, Any]:
    parsed = _parse_studio_body(body)
    if parsed is None:
        return {}
    return parsed[1]


async def _stream_studio_run(studio_action: str, args: dict[str, Any]):
    """Async generator — yields SSE `data:` lines for a studio run."""
    import inspect as _inspect

    from pydantic import BaseModel as _BM

    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def _run_in_thread() -> None:
        from docent.core import ProgressEvent, run_action
        from docent.core.invoke import make_context

        # non_interactive=True: all preflights take the structured path (_bail raises
        # RuntimeError instead of print+typer.Exit so errors reach the SSE stream with
        # real messages) and skip console spinners. auto_confirm=True handles the
        # free-tier gate without a second prompt (confirmed=True in args reinforces it).
        # via_mcp stays False — this is a human UI user, so research output uses the
        # human-facing framing, not the MCP-agent synthesis prompt.
        ctx = make_context(non_interactive=True, auto_confirm=True)
        try:
            raw = run_action("studio", studio_action, args, context=ctx)
        except BaseException as exc:
            msg = str(exc).strip() or type(exc).__name__
            loop.call_soon_threadsafe(q.put_nowait, ("error", msg))
            return

        if not _inspect.isgenerator(raw):
            loop.call_soon_threadsafe(q.put_nowait, ("done", raw))
            return

        try:
            while True:
                try:
                    evt = next(raw)
                    if isinstance(evt, ProgressEvent):
                        loop.call_soon_threadsafe(q.put_nowait, ("event", evt))
                except StopIteration as stop:
                    loop.call_soon_threadsafe(q.put_nowait, ("done", stop.value))
                    return
        except BaseException as exc:
            msg = str(exc).strip() or type(exc).__name__
            loop.call_soon_threadsafe(q.put_nowait, ("error", msg))

    def _sse(data: dict) -> bytes:
        # SSE comment line + the data event. The comment acts as a keepalive marker
        # and adds bytes so chunks aren't coalesced by TCP Nagle on Windows.
        # We yield bytes directly (not str) to avoid an extra encoding step in Starlette
        # and to ensure each chunk goes through `transport.write()` as a single syscall.
        return (f": ping\ndata: {json.dumps(data)}\n\n").encode()

    # Prime the response with a 2KB SSE comment. Chrome and other browsers may
    # delay exposing chunks to JavaScript until the response body exceeds a small
    # threshold; this padding forces the stream to start flowing immediately.
    yield (": " + ("-" * 2048) + "\n\n").encode("utf-8")
    await asyncio.sleep(0.01)

    thread = loop.run_in_executor(None, _run_in_thread)
    try:
        while True:
            kind, payload = await q.get()
            if kind == "event":
                evt = payload
                if evt.message:
                    yield _sse(
                        {"type": "log", "phase": evt.phase, "text": evt.message, "level": evt.level}
                    )
                    # asyncio.sleep with a small non-zero delay forces the event loop to
                    # poll I/O and flush the transport's write buffer. sleep(0) alone is
                    # not enough on Windows ProactorEventLoop — it schedules a callback
                    # but doesn't guarantee an I/O flush cycle.
                    await asyncio.sleep(0.01)
            elif kind == "done":
                result = payload
                ok = not isinstance(result, _BM) or bool(getattr(result, "ok", True))
                yield _sse(
                    {
                        "type": "done",
                        "status": "success" if ok else "failure",
                        "raw": _serialize(result),
                    }
                )
                break
            elif kind == "error":
                yield _sse({"type": "error", "message": str(payload)})
                break
    finally:
        await thread
