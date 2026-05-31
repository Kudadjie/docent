"""Search and output action mixins: search-papers, get-paper, scholarly-search, read-output, save-synthesis."""

from __future__ import annotations

from docent.bundled_plugins.studio._init_helpers import _path_under
from docent.bundled_plugins.studio.models import (
    GetPaperInputs,
    GetPaperResult,
    ReadOutputInputs,
    ReadOutputResult,
    SaveSynthesisInputs,
    SaveSynthesisResult,
    ScholarlySearchInputs,
    ScholarlySearchResult,
    SearchPapersInputs,
    SearchPapersResult,
)
from docent.core import Context, action


class SearchMixin:
    """Mixin providing search actions for StudioTool."""

    @action(
        description=(
            "Read the full content of a Docent research output file for AI synthesis. "
            "Call this after studio__deep_research or studio__lit returns a synthesis_hint, "
            "then use the content to write a synthesised research brief."
        ),
        input_schema=ReadOutputInputs,
        name="read-output",
    )
    def read_output(self, inputs: ReadOutputInputs, context: Context) -> ReadOutputResult:  # noqa: ARG002
        from pathlib import Path

        from docent.config import load_settings
        from docent.utils.paths import root_dir

        p = Path(inputs.output_file).expanduser()

        # Path must be under research.output_dir or the Docent home directory
        try:
            settings = load_settings()
            output_dir = settings.research.output_dir.expanduser().resolve()
        except Exception:
            output_dir = None
        docent_home = root_dir().resolve()
        resolved = p.resolve()
        approved = [r for r in [output_dir, docent_home] if r is not None]
        if not any(_path_under(resolved, root) for root in approved):
            return ReadOutputResult(
                ok=False,
                output_file=inputs.output_file,
                content="",
                word_count=0,
                message=f"Access denied: {inputs.output_file} is outside approved Docent output directories.",
            )

        if not p.exists():
            return ReadOutputResult(
                ok=False,
                output_file=inputs.output_file,
                content="",
                word_count=0,
                message=f"File not found: {inputs.output_file}",
            )
        content = p.read_text(encoding="utf-8")
        words = len(content.split())
        return ReadOutputResult(
            ok=True,
            output_file=inputs.output_file,
            content=content,
            word_count=words,
            message=(
                f"Document saved at: {inputs.output_file} — "
                f"{words} words. Tell the user this path so they can open it. "
                "Now synthesise the content field into a research brief."
            ),
        )

    @action(
        description=(
            "Save an AI-synthesised research brief to the same folder as the Docent source "
            "compilation. Returns the saved file path and the summary for display in chat. "
            "Always call this after synthesising free-tier research — never paste the full "
            "synthesis into chat directly."
        ),
        input_schema=SaveSynthesisInputs,
        name="save-synthesis",
    )
    def save_synthesis(self, inputs: SaveSynthesisInputs, context: Context) -> SaveSynthesisResult:  # noqa: ARG002
        import datetime
        from pathlib import Path

        from docent.config import load_settings
        from docent.utils.paths import root_dir

        source = Path(inputs.source_output_file).expanduser()

        # The source file must be under an approved root — deny traversal attempts
        try:
            settings = load_settings()
            output_dir = settings.research.output_dir.expanduser().resolve()
        except Exception:
            output_dir = None
        docent_home = root_dir().resolve()
        approved = [r for r in [output_dir, docent_home] if r is not None]
        source_resolved = source.resolve() if source.exists() else source.parent.resolve()
        if not any(_path_under(source_resolved, root) for root in approved):
            return SaveSynthesisResult(
                ok=False,
                saved_file="",
                summary="",
                word_count=0,
                message=f"Access denied: {inputs.source_output_file} is outside approved Docent output directories.",
            )

        folder = source.parent if source.parent.exists() else Path.cwd()
        stem = source.stem.removesuffix("-free") if source.stem.endswith("-free") else source.stem
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        save_path = folder / f"{stem}-synthesis-{timestamp}.md"

        save_path.write_text(inputs.content, encoding="utf-8")
        words = len(inputs.content.split())

        return SaveSynthesisResult(
            ok=True,
            saved_file=str(save_path),
            summary=inputs.summary,
            word_count=words,
            message=(
                f"Synthesis saved to: {save_path} ({words} words). "
                "Display only the summary field to the user, then mention the saved path."
            ),
        )

    @action(
        description="Search academic papers on alphaXiv by topic or keyword.",
        input_schema=SearchPapersInputs,
        name="search-papers",
    )
    def search_papers(self, inputs: SearchPapersInputs, context: Context) -> SearchPapersResult:
        from .alphaxiv_client import AlphaXivAuthError
        from .alphaxiv_client import search_papers as _search

        try:
            papers = _search(
                inputs.query,
                api_key=context.settings.research.alphaxiv_api_key,
                max_results=inputs.max_results,
            )
        except AlphaXivAuthError as e:
            return SearchPapersResult(
                ok=False, query=inputs.query, papers=[], count=0, message=str(e)
            )
        except Exception as e:
            return SearchPapersResult(
                ok=False, query=inputs.query, papers=[], count=0, message=f"Search failed: {e}"
            )
        return SearchPapersResult(
            ok=True,
            query=inputs.query,
            papers=papers,
            count=len(papers),
            message=f"Found {len(papers)} paper(s) for '{inputs.query}'.",
        )

    @action(
        description="Get abstract and metadata for an arXiv paper. Returns an AI overview too if an alphaXiv key is configured.",
        input_schema=GetPaperInputs,
        name="get-paper",
    )
    def get_paper(self, inputs: GetPaperInputs, context: Context) -> GetPaperResult:
        from .alphaxiv_client import get_paper_overview

        raw = inputs.arxiv_id.strip().rstrip("/")

        # Detect non-arXiv URLs early and give a clear error rather than
        # submitting a filename like "paper.pdf" to the arXiv API.
        if raw.startswith("http") and "arxiv.org" not in raw:
            return GetPaperResult(
                ok=False,
                arxiv_id=raw,
                title=None,
                abstract="",
                overview=None,
                message=(
                    "Get paper only works with arXiv IDs or arxiv.org links "
                    "(e.g. 2301.12345 or https://arxiv.org/abs/2301.12345). "
                    "To analyse a PDF from another source, use the Peer review action instead."
                ),
            )

        # Extract bare ID from arxiv.org URLs: https://arxiv.org/abs/2301.12345 → 2301.12345
        arxiv_id = raw
        if "/" in arxiv_id:
            arxiv_id = arxiv_id.rsplit("/", 1)[-1]
        # Strip version suffix: 2301.12345v2 → 2301.12345
        arxiv_id = (
            arxiv_id.split("v")[0]
            if arxiv_id and arxiv_id[-1].isdigit() and "v" in arxiv_id
            else arxiv_id
        )

        try:
            data = get_paper_overview(
                arxiv_id,
                api_key=context.settings.research.alphaxiv_api_key,
            )
        except Exception as e:
            return GetPaperResult(
                ok=False,
                arxiv_id=arxiv_id,
                title=None,
                abstract="",
                overview=None,
                message=f"Failed to fetch paper: {e}",
            )
        has_overview = bool(data.get("overview"))
        msg = f"Retrieved {'overview + abstract' if has_overview else 'abstract'} for {arxiv_id}."
        return GetPaperResult(
            ok=True,
            arxiv_id=arxiv_id,
            title=data["title"],
            abstract=data["abstract"],
            overview=data.get("overview"),
            message=msg,
        )

    @action(
        description="Search academic papers via Google Scholar (with Semantic Scholar and CrossRef as fallbacks).",
        input_schema=ScholarlySearchInputs,
        name="scholarly-search",
    )
    def scholarly_search(
        self, inputs: ScholarlySearchInputs, context: Context
    ) -> ScholarlySearchResult:
        from .scholarly_client import search_scholarly

        try:
            papers, backend = search_scholarly(
                inputs.query,
                inputs.max_results,
                semantic_scholar_api_key=context.settings.research.semantic_scholar_api_key,
            )
        except RuntimeError as e:
            return ScholarlySearchResult(
                ok=False,
                query=inputs.query,
                papers=[],
                count=0,
                backend_used="none",
                message=str(e),
            )
        except Exception as e:
            return ScholarlySearchResult(
                ok=False,
                query=inputs.query,
                papers=[],
                count=0,
                backend_used="none",
                message=f"Search failed: {e}",
            )
        if not papers:
            return ScholarlySearchResult(
                ok=False,
                query=inputs.query,
                papers=[],
                count=0,
                backend_used=backend,
                message=f"No results found for '{inputs.query}' (via {backend}).",
            )
        return ScholarlySearchResult(
            ok=True,
            query=inputs.query,
            papers=papers,
            count=len(papers),
            backend_used=backend,
            message=f"Found {len(papers)} paper(s) for '{inputs.query}' (via {backend}).",
        )
