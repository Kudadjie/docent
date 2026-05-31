"""Citation graph action mixin: cite-graph."""
from __future__ import annotations

from docent.core import Context, action
from docent.bundled_plugins.studio.models import (
    CiteGraphInputs,
    CiteGraphResult,
    CitedPaperItem,
)


class CiteMixin:
    @action(
        description=(
            "Explore the citation graph around an anchor paper via Semantic Scholar. "
            "Returns a discovery list — titles, authors, DOIs, and open-access links. "
            "Use 'cited-by' to find papers that built on this work (default); "
            "'citing' to explore its bibliography. "
            "Open-access papers are listed first. "
            "Add interesting ones to your reference manager to queue them in Docent."
        ),
        input_schema=CiteGraphInputs,
        name="cite-graph",
    )
    def cite_graph(self, inputs: CiteGraphInputs, context: Context) -> CiteGraphResult:
        from .citation_client import fetch_anchor, fetch_citation_graph, resolve_s2_id

        try:
            s2_id = resolve_s2_id(inputs.doi, inputs.arxiv_id)
        except ValueError as e:
            return CiteGraphResult(
                ok=False, anchor_title="", anchor_doi=None,
                direction=inputs.direction, total_found=0, oa_count=0,
                papers=[], message=str(e),
            )

        api_key = context.settings.research.semantic_scholar_api_key

        try:
            anchor = fetch_anchor(s2_id, api_key)
        except LookupError as e:
            return CiteGraphResult(
                ok=False, anchor_title="", anchor_doi=None,
                direction=inputs.direction, total_found=0, oa_count=0,
                papers=[], message=str(e),
            )
        except RuntimeError as e:
            return CiteGraphResult(
                ok=False, anchor_title="", anchor_doi=None,
                direction=inputs.direction, total_found=0, oa_count=0,
                papers=[], message=str(e),
            )

        # Fetch more than max_results so OA filtering has room to work.
        fetch_limit = min(max(inputs.max_results * 2, 50), 100)

        try:
            all_papers = fetch_citation_graph(s2_id, inputs.direction, fetch_limit, api_key)
        except RuntimeError as e:
            return CiteGraphResult(
                ok=False, anchor_title=anchor["title"], anchor_doi=anchor["doi"],
                direction=inputs.direction, total_found=0, oa_count=0,
                papers=[], message=str(e),
            )

        oa = [p for p in all_papers if p["oa_url"]]
        non_oa = [p for p in all_papers if not p["oa_url"]]
        selected = (oa + non_oa)[:inputs.max_results]

        papers = [
            CitedPaperItem(
                title=p["title"],
                authors=p["authors"],
                year=p["year"],
                doi=p["doi"],
                arxiv_id=p["arxiv_id"],
                oa_url=p["oa_url"],
                s2_url=p["s2_url"],
                abstract=p.get("abstract", ""),
            )
            for p in selected
        ]

        _dir_label = {
            "cited-by": "citing this paper",
            "citing": "cited by this paper",
            "both": "in the citation graph",
        }.get(inputs.direction, inputs.direction)

        oa_note = f"{len(oa)} open access" if oa else "none open access"

        return CiteGraphResult(
            ok=True,
            anchor_title=anchor["title"],
            anchor_doi=anchor["doi"],
            direction=inputs.direction,
            total_found=len(all_papers),
            oa_count=len(oa),
            papers=papers,
            message=(
                f"Found {len(all_papers)} papers {_dir_label} — {oa_note}. "
                f"Showing top {len(selected)}. "
                "Add interesting ones to your reference manager to queue them in Docent."
            ),
        )
