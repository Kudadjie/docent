"""Pydantic input/result models for all StudioTool actions."""
from __future__ import annotations

from pydantic import BaseModel, Field

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

_BACKEND_DEEP_DESC = (
    "Research backend: 'feynman' (default, requires Feynman CLI), "
    "'docent' (requires OpenCode + API credits), or "
    "'free' (no AI — Tavily + Semantic Scholar + CrossRef only; "
    "output is a raw literature dump, not a synthesised report)."
)

class DeepInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description=_BACKEND_DEEP_DESC)
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class LitInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description=_BACKEND_DEEP_DESC)
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class ReviewInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, local PDF path, or URL to review.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class ConfigShowInputs(BaseModel):
    pass


class ConfigSetInputs(BaseModel):
    key: str = Field(..., description="Setting key under [research]: 'output_dir'.")
    value: str = Field(..., description="New value.")


class ToLocalInputs(BaseModel):
    output_file: str | None = Field(
        None,
        description=(
            "Path to a research output .md file. "
            "If omitted, the most recent output in research.output_dir is used."
        ),
    )
    guide_files: list[str] = _GUIDE_FILES_FIELD
    to_vault: bool = Field(
        False,
        description="Also copy to Obsidian vault if research.obsidian_vault is configured.",
    )


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
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD

    @property
    def topic(self) -> str:
        return f"{self.artifact_a} vs {self.artifact_b}"


class DraftInputs(BaseModel):
    topic: str = Field(..., description="Topic or section title to draft.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class ReplicateInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, PDF path, or URL of the paper to replicate.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class AuditInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, PDF path, or URL of the paper to audit.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class UsageInputs(BaseModel):
    pass


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
    oc_budget_usd: float
    tavily_api_key: str | None = None
    tavily_research_timeout: float = 600.0
    semantic_scholar_api_key: str | None = None
    feynman_model: str | None = None
    feynman_timeout: float = 900.0
    notebooklm_notebook_id: str | None = None
    notebooklm_source_limit: int = 50
    obsidian_vault: str | None = None
    alphaxiv_api_key: str | None = None

    def to_shapes(self) -> list[Shape]:
        def _mask(key: str | None) -> str:
            if not key:
                return "(not set)"
            if len(key) <= 8:
                return "***"
            return key[:4] + "..." + key[-4:]

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
            MetricShape(label="oc_budget_usd", value=str(self.oc_budget_usd)),
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


class ToLocalResult(BaseModel):
    ok: bool
    output_file: str | None
    sources_file: str | None
    package_dir: str | None
    sources_count: int
    vault_path: str | None = None
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.package_dir:
            shapes.append(LinkShape(url=self.package_dir, label="Local package"))
        if self.vault_path:
            shapes.append(LinkShape(url=self.vault_path, label="Obsidian note"))
        if self.sources_count:
            shapes.append(MetricShape(label="Sources in package", value=str(self.sources_count)))
        return shapes


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
    overview: str
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
        preview = self.overview[:600] + ("…" if len(self.overview) > 600 else "")
        shapes.append(MessageShape(text=preview, level="info"))
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


class UsageResult(BaseModel):
    feynman_spend_usd: float
    oc_spend_usd: float
    feynman_budget_usd: float
    oc_budget_usd: float
    date: str
    message: str

    def to_shapes(self) -> list[Shape]:
        return [
            MetricShape(label="Date", value=self.date),
            MetricShape(label="Feynman spend today", value=f"${self.feynman_spend_usd:.4f}",
                       unit=f"/ ${self.feynman_budget_usd:.2f} budget" if self.feynman_budget_usd > 0 else "(no limit)"),
            MetricShape(label="OpenCode spend today", value=f"${self.oc_spend_usd:.4f}",
                       unit=f"/ ${self.oc_budget_usd:.2f} budget" if self.oc_budget_usd > 0 else "(no limit)"),
        ]
