"""Studio form → in-process action kwargs.

``build_studio_request`` is the single source of truth that turns a
``StudioRunBody`` into the kwargs fed to ``run_action`` when the form is
submitted as a background job (``POST /api/studio/submit``). Historically it
also rendered a subprocess argv for the WebSocket path and fed an SSE stream —
both transports were deleted in the v2.3 rewire (jobs polling is the only
studio transport now).
"""

from __future__ import annotations

import re as _re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

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
    """A resolved Studio form: the action name plus the kwargs fed to
    ``run_action`` when the form is submitted as a background job."""

    action: str
    kwargs: dict[str, Any] = field(default_factory=dict)


def build_studio_request(body: StudioRunBody) -> StudioRequest | None:
    """Single source of truth: StudioRunBody → in-process action kwargs.

    Returns None if the action_id is unknown.
    """
    action = _STUDIO_ACTION_MAP.get(body.action_id)
    if not action:
        return None
    backend = _BACKEND_NORM.get(body.backend.lower().replace(" ", "_"), "free")
    dest = body.dest.lower().replace(" →", "").strip()
    req = StudioRequest(action=action)
    k = req.kwargs

    if action in ("deep-research", "lit", "draft"):
        k.update({"topic": body.topic, "backend": backend, "output": dest})
        # deep-research/lit gate the free backend behind a disclaimer; pre-confirm
        # it so the UI doesn't need a second prompt. draft is AI-backend-only and
        # its DraftInputs model has no `confirmed`/`expand_citations` field, so
        # passing either kwarg would fail input validation.
        if action in ("deep-research", "lit"):
            k["confirmed"] = True
            if body.expand_citations:
                k["expand_citations"] = True
        k["guide_files"] = body.guides
    elif action in ("review", "replicate", "audit"):
        k.update({"artifact": body.artifact, "backend": backend, "output": dest})
        k["guide_files"] = body.guides
    elif action == "compare":
        k.update(
            {
                "artifact_a": body.artifact_a,
                "artifact_b": body.artifact_b,
                "backend": backend,
                "output": dest,
            }
        )
        k["guide_files"] = body.guides
    elif action in ("search-papers", "scholarly-search"):
        k.update({"query": body.query, "max_results": body.max_results})
    elif action == "get-paper":
        k["arxiv_id"] = body.arxiv_id
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
    elif action == "to-notebook":
        # Derive output-file from the sources path when not set explicitly. This
        # keeps the (non-interactive) job off the file-picker preflight, which
        # raises a structured error when multiple outputs exist.
        out_file = body.out_path or _re.sub(r"-sources\.json$", ".md", body.src_path)
        if out_file == body.src_path:
            out_file = ""
        k.update(
            {
                "output_file": out_file or None,
                "sources_file": body.src_path or None,
                "max_sources": body.max_sources,
                "run_nlm_research": body.nlm,
                "run_quality_gate": body.gate,
                "run_perspectives": body.persp,
            }
        )
    elif action == "config-set":
        k.update({"key": body.cfg_key, "value": body.cfg_val})
    # config-show: no args.
    return req


def _parse_studio_body(body: StudioRunBody) -> tuple[str, dict[str, Any]] | None:
    """(action, kwargs) view of a StudioRunBody. Thin wrapper over
    :func:`build_studio_request`."""
    req = build_studio_request(body)
    return None if req is None else (req.action, req.kwargs)
