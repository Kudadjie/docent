"""Pydantic input/result models for all StudioTool actions."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from docent.core.shapes import (
    ErrorShape,
    LinkShape,
    MessageShape,
    MetricShape,
    Shape,
)

# Re-export notebook models so callers can import from .models
from ._notebook import ToNotebookInputs as ToNotebookInputs, ToNotebookResult as ToNotebookResult  # noqa: F401

_OUTPUT_CHOICES = "'local' (default), 'notebook' (push to NotebookLM), 'vault' (write to Obsidian vault)."

_GUIDE_FILES_FIELD = Field(
    default_factory=list,
    description=(
        "Optional path(s) to files (.md, .txt, PDF) or a folder that guide the research — "
        "their content is injected into the research brief to focus the output. "
        "Pass the flag multiple times for individual files "
        "(e.g. --guide-files notes.md --guide-files outline.txt), "
        "or pass a folder path once to include all .md/.txt/.pdf files inside it "
        "(e.g. --guide-files my_notes/)."
    ),
)


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

# Active backend values exposed in the UI and MCP tool descriptions.
# Archived backends (gemini, openrouter, mistral, cerebras, anthropic, openai,
# ollama, lm_studio, local) still work from the CLI with --backend <name>.
_BACKEND_ENUM = ["free", "feynman", "docent", "groq"]

_AI_ONLY_FREE_ERROR = (
    "The 'free' backend only aggregates sources — it cannot generate or rewrite "
    "text, so it is not available for this action. Choose an AI backend: "
    "'docent', 'feynman', or 'groq'."
)


def _reject_free_backend(v: str) -> str:
    """Validator helper for the text-generating actions (draft/review/compare/
    replicate/audit). These have no free-tier path, so 'free' must fail loudly
    here instead of silently falling through to the Feynman branch."""
    if isinstance(v, str) and v.strip().lower() == "free":
        raise ValueError(_AI_ONLY_FREE_ERROR)
    return v

_BACKEND_DEEP_DESC = (
    "Research backend.\n\n"
    "MCP TIMEOUT WARNING: all AI backends run a multi-minute pipeline that WILL time out "
    "through the MCP connection. Via MCP, ONLY 'free' is reliable — it completes in seconds "
    "and you synthesise here. For any AI backend, tell the user to run the command in their "
    "terminal instead and provide the exact command. Do NOT attempt AI backends via MCP.\n\n"
    "  'free' — RECOMMENDED VIA MCP. Docent aggregates sources (Tavily + Semantic Scholar "
    "+ CrossRef) then YOU synthesise both streams here. No extra API cost. "
    "MODEL: Sonnet for everyday research; Opus for thesis-quality output.\n\n"
    "  'docent' — 6-stage AI pipeline via OpenCode. "
    "TERMINAL ONLY — times out via MCP. Requires OpenCode server + Tavily key.\n\n"
    "  'feynman' — full AI deep research via Feynman CLI (10–30 min). "
    "TERMINAL ONLY — always times out via MCP.\n\n"
    "  'groq' — fast Groq inference. TERMINAL ONLY. Requires GROQ_API_KEY.\n\n"
    "Valid values: free, feynman, docent, groq."
)

_TO_NOTEBOOK_FIELD = Field(
    False,
    description=(
        "Push the finished output directly to NotebookLM after research completes. "
        "Shorthand for --output notebook. "
        "Requires notebooklm-py and a configured notebook."
    ),
)

class DeepInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description=_BACKEND_DEEP_DESC, json_schema_extra={"enum": _BACKEND_ENUM})

    @field_validator('topic')
    @classmethod
    def _topic_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Topic is required and cannot be empty.')
        return v.strip()

    @field_validator('backend')
    @classmethod
    def _backend_valid(cls, v: str) -> str:
        if v not in _BACKEND_ENUM:
            raise ValueError(f"backend must be one of {_BACKEND_ENUM}; got {v!r}")
        return v

    output: Literal["local", "notebook", "vault"] = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    to_notebook: bool = _TO_NOTEBOOK_FIELD
    guide_files: list[str] = _GUIDE_FILES_FIELD
    confirmed: bool = Field(
        False,
        description=(
            "Set to true on a retry after the user has acknowledged the disclaimer "
            "and any warnings returned in a previous confirmation_required response. "
            "Only relevant for the 'free' backend via MCP."
        ),
    )


class LitInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description=_BACKEND_DEEP_DESC, json_schema_extra={"enum": _BACKEND_ENUM})

    @field_validator('topic')
    @classmethod
    def _topic_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Topic is required and cannot be empty.')
        return v.strip()

    @field_validator('backend')
    @classmethod
    def _backend_valid(cls, v: str) -> str:
        if v not in _BACKEND_ENUM:
            raise ValueError(f"backend must be one of {_BACKEND_ENUM}; got {v!r}")
        return v

    output: Literal["local", "notebook", "vault"] = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    to_notebook: bool = _TO_NOTEBOOK_FIELD
    guide_files: list[str] = _GUIDE_FILES_FIELD
    confirmed: bool = Field(
        False,
        description=(
            "Set to true on a retry after the user has acknowledged the disclaimer "
            "and any warnings returned in a previous confirmation_required response. "
            "Only relevant for the 'free' backend via MCP."
        ),
    )


class ReviewInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, local PDF path, or URL to review.")
    backend: str = Field("feynman", description="Research backend — ask the user which to use. Options: 'feynman' (requires Feynman CLI; slow via MCP — suggest terminal instead), 'docent' (requires OpenCode server + API credits).")
    output: Literal["local", "notebook", "vault"] = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD

    @field_validator('backend')
    @classmethod
    def _reject_free(cls, v: str) -> str:
        return _reject_free_backend(v)


class ReadOutputInputs(BaseModel):
    output_file: str = Field(
        ...,
        description=(
            "Absolute path to a Docent research output file (.md). "
            "Returns the full content for AI synthesis. "
            "Use the output_file path returned by studio__deep_research or studio__lit."
        ),
    )


class ReadOutputResult(BaseModel):
    ok: bool
    output_file: str
    content: str
    word_count: int
    message: str


class SaveSynthesisInputs(BaseModel):
    source_output_file: str = Field(
        ...,
        description=(
            "Absolute path to the Docent research output file this synthesis is based on. "
            "Used to determine the save folder and derive the synthesis filename."
        ),
    )
    content: str = Field(
        ...,
        description="The full synthesised research brief to save.",
    )
    summary: str = Field(
        ...,
        description=(
            "A concise summary (3–5 paragraphs) to display in chat. "
            "The full content is saved to file; only this summary is shown to the user."
        ),
    )


class SaveSynthesisResult(BaseModel):
    ok: bool
    saved_file: str
    summary: str
    word_count: int
    message: str


class ConfigShowInputs(BaseModel):
    pass


class ConfigSetInputs(BaseModel):
    key: str = Field(..., description="Setting key under [research]: 'output_dir'.")
    value: str = Field(..., description="New value.")


class SearchPapersInputs(BaseModel):
    query: str = Field(..., description="Search query for academic papers on alphaXiv.")
    max_results: int = Field(10, description="Maximum number of results to return (default 10).")


class GetPaperInputs(BaseModel):
    arxiv_id: str = Field(..., description="arXiv paper ID (e.g. '2401.12345') or arXiv URL.")


class ScholarlySearchInputs(BaseModel):
    query: str = Field(..., description="Search query for academic papers (Google Scholar / Semantic Scholar / CrossRef).")
    max_results: int = Field(10, description="Maximum results to return (default 10).")


class CompareInputs(BaseModel):
    artifact_a: str = Field(..., description="First artifact: arXiv ID, PDF path, or URL.")
    artifact_b: str = Field(..., description="Second artifact: arXiv ID, PDF path, or URL.")
    backend: str = Field("feynman", description="Research backend — ask the user which to use. Options: 'feynman' (requires Feynman CLI; slow via MCP — suggest terminal instead), 'docent' (requires OpenCode server + API credits).")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD

    @field_validator('backend')
    @classmethod
    def _reject_free(cls, v: str) -> str:
        return _reject_free_backend(v)

    @property
    def topic(self) -> str:
        return f"{self.artifact_a} vs {self.artifact_b}"


class DraftInputs(BaseModel):
    topic: str = Field(..., description="Topic or section title to draft.")
    backend: str = Field("feynman", description="Research backend — ask the user which to use. Options: 'feynman' (requires Feynman CLI; slow via MCP — suggest terminal instead), 'docent' (requires OpenCode server + API credits).")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD

    @field_validator('topic')
    @classmethod
    def _topic_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Topic is required and cannot be empty.')
        return v.strip()

    @field_validator('backend')
    @classmethod
    def _reject_free(cls, v: str) -> str:
        return _reject_free_backend(v)


class ReplicateInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, PDF path, or URL of the paper to replicate.")
    backend: str = Field("feynman", description="Research backend — ask the user which to use. Options: 'feynman' (requires Feynman CLI; slow via MCP — suggest terminal instead), 'docent' (requires OpenCode server + API credits).")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD

    @field_validator('backend')
    @classmethod
    def _reject_free(cls, v: str) -> str:
        return _reject_free_backend(v)


class AuditInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, PDF path, or URL of the paper to audit.")
    backend: str = Field("feynman", description="Research backend — ask the user which to use. Options: 'feynman' (requires Feynman CLI; slow via MCP — suggest terminal instead), 'docent' (requires OpenCode server + API credits).")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD

    @field_validator('backend')
    @classmethod
    def _reject_free(cls, v: str) -> str:
        return _reject_free_backend(v)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

class ResearchResult(BaseModel):
    ok: bool
    backend: str
    workflow: str
    topic_or_artifact: str
    output_file: str | None
    returncode: int | None
    message: str
    notebook_id: str | None = None
    vault_path: str | None = None

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.output_file is not None:
            shapes.append(LinkShape(url=self.output_file, label="Output file"))
        if self.notebook_id is not None:
            shapes.append(MetricShape(label="NotebookLM notebook", value=self.notebook_id))
        if self.vault_path is not None:
            shapes.append(LinkShape(url=self.vault_path, label="Obsidian vault note"))
        return shapes


class ConfigShowResult(BaseModel):
    config_path: str
    output_dir: str
    feynman_command: list[str]
    oc_provider: str
    oc_model_planner: str
    oc_model_writer: str
    oc_model_verifier: str
    oc_model_reviewer: str
    oc_model_researcher: str
    tavily_api_key: str | None = None
    tavily_research_timeout: float = 600.0
    semantic_scholar_api_key: str | None = None
    feynman_model: str | None = None
    feynman_timeout: float = 900.0
    notebooklm_notebook_id: str | None = None
    notebooklm_source_limit: int = 50
    obsidian_vault: str | None = None
    alphaxiv_api_key: str | None = None

    # Field names that hold secrets and must be masked before leaving the process.
    _SECRET_FIELDS = (
        "tavily_api_key",
        "semantic_scholar_api_key",
        "alphaxiv_api_key",
    )

    @staticmethod
    def _mask_secret(key: str | None) -> str:
        if not key:
            return "(not set)"
        if len(key) <= 8:
            return "***"
        return key[:4] + "..." + key[-4:]

    def to_ui(self) -> dict:
        """JSON-safe dict for the UI config panel, with API keys masked.

        Used by the CLI's UI-subprocess result emitter so raw secrets never
        cross the WebSocket to the browser.
        """
        data = self.model_dump(mode="json")
        for field in self._SECRET_FIELDS:
            if field in data:
                data[field] = self._mask_secret(data.get(field))
        return data

    def to_shapes(self) -> list[Shape]:
        def _mask(key: str | None) -> str:
            return self._mask_secret(key)

        return [
            MetricShape(label="Config", value=self.config_path),
            MetricShape(label="output_dir", value=self.output_dir),
            MetricShape(label="feynman_command", value=" ".join(self.feynman_command)),
            MetricShape(label="oc_provider", value=self.oc_provider),
            MetricShape(label="oc_model_planner", value=self.oc_model_planner),
            MetricShape(label="oc_model_writer", value=self.oc_model_writer),
            MetricShape(label="oc_model_verifier", value=self.oc_model_verifier),
            MetricShape(label="oc_model_reviewer", value=self.oc_model_reviewer),
            MetricShape(label="oc_model_researcher", value=self.oc_model_researcher),
            MetricShape(label="tavily_api_key", value=_mask(self.tavily_api_key)),
            MetricShape(label="tavily_research_timeout", value=f"{self.tavily_research_timeout:.0f}s"),
            MetricShape(label="semantic_scholar_api_key", value=_mask(self.semantic_scholar_api_key)),
            MetricShape(label="feynman_model", value=self.feynman_model or "(feynman default)"),
            MetricShape(label="feynman_timeout", value=f"{self.feynman_timeout:.0f}s"),
            MetricShape(label="notebooklm_notebook_id", value=self.notebooklm_notebook_id or "(not set)"),
            MetricShape(label="notebooklm_source_limit", value=str(self.notebooklm_source_limit)),
            MetricShape(label="obsidian_vault", value=self.obsidian_vault or "(not set)"),
            MetricShape(label="alphaxiv_api_key", value=_mask(self.alphaxiv_api_key)),
        ]


class ConfigSetResult(BaseModel):
    ok: bool
    key: str
    value: str
    config_path: str
    message: str

    def to_shapes(self) -> list[Shape]:
        return [
            MessageShape(text=self.message, level="success" if self.ok else "error"),
        ]


class SearchPapersResult(BaseModel):
    ok: bool
    query: str
    papers: list[dict]
    count: int
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        for p in self.papers:
            authors = ", ".join(p.get("authors", [])[:3])
            if len(p.get("authors", [])) > 3:
                authors += " et al."
            year = (p.get("published") or "")[:4] or "?"
            shapes.append(MetricShape(
                label=f"{p['title']} ({year})",
                value=authors or "Unknown authors",
            ))
            if p.get("arxiv_url"):
                shapes.append(LinkShape(url=p["arxiv_url"], label=p["arxiv_id"]))
        return shapes


class GetPaperResult(BaseModel):
    ok: bool
    arxiv_id: str
    title: str | None
    abstract: str
    overview: str | None = None  # None when no alphaXiv key — arXiv fallback omits the AI overview
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.title:
            shapes.append(MetricShape(label="Title", value=self.title))
        shapes.append(LinkShape(
            url=f"https://arxiv.org/abs/{self.arxiv_id}",
            label=self.arxiv_id,
        ))
        body = self.overview or self.abstract
        if body:
            preview = body[:600] + ("…" if len(body) > 600 else "")
            shapes.append(MessageShape(text=preview, level="info"))
        return shapes


class TavilyUsageInputs(BaseModel):
    pass


class TavilyUsageResult(BaseModel):
    ok: bool
    plan: str | None = None
    plan_usage: int | None = None
    plan_limit: int | None = None
    key_search_usage: int | None = None
    pct_used: float | None = None
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = []
        if self.plan_usage is not None and self.plan_limit is not None:
            pct = f"{self.pct_used:.0f}%" if self.pct_used is not None else "?"
            shapes.append(MetricShape(
                label="Tavily credits used",
                value=f"{self.plan_usage} / {self.plan_limit} ({pct})",
            ))
        if self.plan:
            shapes.append(MetricShape(label="Plan", value=self.plan))
        if self.key_search_usage is not None:
            shapes.append(MetricShape(label="Search calls (this key)", value=str(self.key_search_usage)))
        return shapes


class ScholarlySearchResult(BaseModel):
    ok: bool
    query: str
    papers: list[dict]
    count: int
    backend_used: str
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [
            MessageShape(text=self.message, level="success"),
            MetricShape(label="Backend", value=self.backend_used),
        ]
        for p in self.papers:
            authors = ", ".join(p.get("authors", [])[:3])
            if len(p.get("authors", [])) > 3:
                authors += " et al."
            year = p.get("year") or "?"
            shapes.append(MetricShape(
                label=f"{p['title']} ({year})",
                value=authors or "Unknown authors",
            ))
            url = p.get("url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else None)
            if url:
                label = p.get("doi") or url[:60]
                shapes.append(LinkShape(url=url, label=label))
        return shapes


# ---------------------------------------------------------------------------
# cite-graph
# ---------------------------------------------------------------------------

class CiteGraphInputs(BaseModel):
    doi: str | None = Field(
        None,
        description=(
            "DOI of the anchor paper — bare (10.1234/example) or as a URL "
            "(https://doi.org/10.1234/example). Provide this OR arxiv_id."
        ),
    )
    arxiv_id: str | None = Field(
        None,
        description=(
            "arXiv ID of the anchor paper — bare (2301.12345) or as a URL "
            "(https://arxiv.org/abs/2301.12345). Provide this OR doi."
        ),
    )
    direction: str = Field(
        "cited-by",
        description=(
            "Which direction of the citation graph to explore.\n"
            "  'cited-by' (default) — papers that cite this one (who built on it).\n"
            "  'citing' — papers this one cites (its bibliography).\n"
            "  'both' — both directions merged and deduplicated."
        ),
    )
    max_results: int = Field(25, description="Maximum number of papers to return. Default 25.")

    @model_validator(mode="after")
    def _require_identifier(self) -> "CiteGraphInputs":
        if not self.doi and not self.arxiv_id:
            raise ValueError("Provide either doi or arxiv_id.")
        if self.direction not in ("cited-by", "citing", "both"):
            raise ValueError("direction must be 'cited-by', 'citing', or 'both'.")
        return self


class CitedPaperItem(BaseModel):
    title: str
    authors: str
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    oa_url: str | None = None
    s2_url: str = ""


class CiteGraphResult(BaseModel):
    ok: bool
    anchor_title: str
    anchor_doi: str | None
    direction: str
    total_found: int
    oa_count: int
    papers: list[CitedPaperItem]
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(text=self.message)]
        shapes: list[Shape] = [
            MessageShape(text=self.message, level="success"),
            MetricShape(label="Anchor", value=self.anchor_title or "Unknown"),
            MetricShape(label="Direction", value=self.direction),
            MetricShape(label="Found", value=str(self.total_found)),
            MetricShape(label="Open access", value=str(self.oa_count)),
        ]
        for p in self.papers:
            year = str(p.year) if p.year else "?"
            oa_tag = " [OA]" if p.oa_url else ""
            shapes.append(MetricShape(
                label=f"{p.title[:80]} ({year}){oa_tag}",
                value=p.authors or "Unknown authors",
            ))
            url = p.oa_url or (f"https://doi.org/{p.doi}" if p.doi else p.s2_url)
            if url:
                shapes.append(LinkShape(url=url, label=p.doi or url[:60]))
        return shapes


