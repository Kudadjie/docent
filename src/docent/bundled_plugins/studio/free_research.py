"""Free-tier research pipeline using only zero-cost public APIs.

No AI synthesis is performed. Output is a structured markdown document
compiled from Tavily web search results (optional, free account) and
academic paper metadata from Semantic Scholar and CrossRef (always free,
no key required).

Web search fallback chain:
  Tavily (free account, 1k/month) → DuckDuckGo (no key, no quota) → skip
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Generator

from docent.core import ProgressEvent

try:
    from tavily.errors import UsageLimitExceededError, InvalidAPIKeyError
except ImportError:
    UsageLimitExceededError = RuntimeError  # type: ignore[misc,assignment]
    InvalidAPIKeyError = RuntimeError  # type: ignore[misc,assignment]

# ── User-facing strings ───────────────────────────────────────────────────────

FREE_TIER_DISCLAIMER = """\
[bold yellow]Free-tier research — please read before continuing:[/]

  • [bold]No AI synthesis.[/] The output is a raw compilation of web search
    results and academic paper abstracts. There is no narrative, no critical
    analysis, and no citation checking.

  • [bold]Quality depends on search coverage.[/] Semantic Scholar and CrossRef
    cover most peer-reviewed literature; Google Scholar is tried first but
    rate-limits frequently. Web results depend on Tavily or DuckDuckGo.

  • [bold]Tavily web search is optional[/] but recommended for deep_research.
    Free account: 1,000 calls/month, no credit card required.
    If your Tavily quota runs out, DuckDuckGo is used automatically
    (lower quality — broader results, less curated).

  • [bold]This is a starting point, not a finished report.[/] For AI-synthesised
    research briefs, configure any major LLM provider API key and use
    [cyan]--backend feynman[/] or [cyan]--backend docent[/]:

      Anthropic (Claude)  →  ANTHROPIC_API_KEY
      OpenAI (GPT)        →  OPENAI_API_KEY
      Google (Gemini)     →  GEMINI_API_KEY
      Mistral             →  MISTRAL_API_KEY
      Groq                →  GROQ_API_KEY
      Together AI         →  TOGETHERAI_API_KEY
      ... and 100+ more providers via litellm

      Local LLMs (Ollama, LM Studio) — coming soon.

  • [bold]Using Docent via MCP?[/] If you called this tool from an AI assistant
    (Claude, ChatGPT, etc.), ask it to synthesise the output into a research
    brief — it can do the AI step your subscription already covers.
"""

TAVILY_SIGNUP_GUIDE = """\
[bold]How to get a free Tavily API key:[/]
  1. Go to [cyan]https://tavily.com[/] and click [bold]Get started free[/]
  2. Sign up with your email — no credit card required
  3. Copy your API key from the dashboard
  4. Save it: [cyan]docent studio config-set --key tavily_api_key --value YOUR_KEY[/]
"""

# ── Document footer ───────────────────────────────────────────────────────────

_MCP_NOTE_HUMAN = (
    "\n\n---\n\n"
    "> **Tip:** Share this document with any AI assistant (Claude, ChatGPT, Gemini, etc.) "
    "and ask it to synthesise a research brief — your existing subscription covers "
    "the AI step. Docent handled the search and organisation.\n\n"
    "> **Want full AI synthesis inside Docent?** Configure any LLM provider API key "
    "and rerun with `--backend feynman` or `--backend docent`. "
    "Supported: Anthropic, OpenAI, Google Gemini, Mistral, Groq, Together AI, "
    "and 100+ more via litellm. Local LLMs (Ollama, LM Studio) — coming soon."
)

_MCP_SYNTHESIS_PROMPT = (
    "\n\n---\n\n"
    "> **[Instructions for the AI assistant reading this via MCP]**\n"
    "> You have just retrieved a free-tier Docent research document. "
    "It contains raw search results and paper abstracts — no AI synthesis has been done yet.\n"
    "> \n"
    "> Please offer the user the following immediately, before showing them the results:\n"
    "> \n"
    "> *\"I've compiled your research results using Docent's free tier "
    "(web search + academic papers, no AI synthesis yet). "
    "Would you like me to synthesise this into a structured research brief "
    "with an introduction, key findings, critical analysis, and conclusions? "
    "I can do that right now using my own capabilities.\"*\n"
    "> \n"
    "> If the user says yes, use the sections below as your source material. "
    "Do not just summarise — produce a coherent, critically engaged research brief."
)

# ── Document header ───────────────────────────────────────────────────────────

_DISCLAIMER_HEADER = (
    "> **FREE TIER OUTPUT** — No AI synthesis. This document was compiled from "
    "web search results and academic paper metadata "
    "(Semantic Scholar, CrossRef). Treat it as a literature discovery aid, "
    "not a finished report. See the footer for upgrade and MCP synthesis options.\n\n"
)

# ── Internal helpers ──────────────────────────────────────────────────────────

def _web_search_ddg(query: str, max_results: int = 10) -> list[dict]:
    """DuckDuckGo web search — no key, no quota. Returns same shape as web_search()."""
    from duckduckgo_search import DDGS
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
    return results


def _format_paper(p: dict, idx: int) -> str:
    title = p.get("title") or "Untitled"
    authors = p.get("authors", [])
    if isinstance(authors, list):
        authors_str = ", ".join(authors[:3])
        if len(authors) > 3:
            authors_str += " et al."
    else:
        authors_str = str(authors)
    year = p.get("year") or ""
    doi = p.get("doi") or ""
    url = p.get("url") or (f"https://doi.org/{doi}" if doi else "")
    abstract = (p.get("abstract") or p.get("snippet") or "").strip()
    if len(abstract) > 500:
        abstract = abstract[:500].rstrip() + "…"
    source = p.get("source", "")

    lines = [f"### {idx}. {title}"]
    meta_parts = []
    if authors_str:
        meta_parts.append(f"**Authors:** {authors_str}")
    if year:
        meta_parts.append(f"**Year:** {year}")
    if doi:
        meta_parts.append(f"**DOI:** [{doi}](https://doi.org/{doi})")
    elif url:
        meta_parts.append(f"**URL:** {url}")
    if source:
        meta_parts.append(f"**Source:** {source}")
    if meta_parts:
        lines.append(" | ".join(meta_parts))
    if abstract:
        lines.append("")
        lines.append(abstract)
    return "\n".join(lines)


def _format_web_result(r: dict, idx: int, source_label: str = "") -> str:
    title = r.get("title") or "Untitled"
    url = r.get("url") or ""
    snippet = (r.get("snippet") or "").strip()
    if len(snippet) > 400:
        snippet = snippet[:400].rstrip() + "…"
    header = f"### {idx}. [{title}]({url})"
    if source_label:
        header += f" *(via {source_label})*"
    lines = [header]
    if snippet:
        lines.append("")
        lines.append(snippet)
    return "\n".join(lines)


# ── Public pipeline functions ─────────────────────────────────────────────────

def run_free_deep(
    topic: str,
    guide_ctx: str,
    tavily_key: str | None,
    ss_key: str | None,
    output_path: Path,
    *,
    via_mcp: bool = False,
) -> Generator[ProgressEvent, None, dict]:
    """Compile a free-tier deep-research document.

    Web search fallback: Tavily → DuckDuckGo → skip.
    Yields ProgressEvents. Returns a result dict: ok, output_file, sources_file.
    """
    from .search import web_search, paper_search
    from .scholarly_client import search_scholarly

    date_str = datetime.date.today().isoformat()
    search_query = topic
    if guide_ctx:
        search_query = f"{topic} {guide_ctx[:300]}"

    # ── 1. Web search: Tavily → DuckDuckGo → skip ────────────────────────────
    web_results: list[dict] = []
    web_source = ""

    if tavily_key:
        yield ProgressEvent(phase="web_search", message="Searching the web via Tavily…")
        try:
            web_results = web_search(search_query, max_results=10, api_key=tavily_key)
            web_source = "Tavily"
        except (UsageLimitExceededError, InvalidAPIKeyError) as e:
            quota_msg = (
                "Tavily free quota exhausted (1,000 calls/month — resets on the 1st). "
                "Falling back to DuckDuckGo (lower quality: broader results, less curated)…"
                if isinstance(e, UsageLimitExceededError)
                else f"Tavily API key invalid: {e}. Falling back to DuckDuckGo…"
            )
            yield ProgressEvent(phase="web_search", message=quota_msg)
            try:
                web_results = _web_search_ddg(search_query, max_results=10)
                web_source = "DuckDuckGo (fallback — lower quality)"
                yield ProgressEvent(
                    phase="web_search",
                    message=f"DuckDuckGo returned {len(web_results)} results. "
                            "Note: results are broader and less curated than Tavily.",
                )
            except Exception as ddg_err:
                yield ProgressEvent(phase="web_search", message=f"DuckDuckGo also failed: {ddg_err}. Skipping web search.")
        except Exception as e:
            yield ProgressEvent(phase="web_search", message=f"Tavily search failed: {e}. Trying DuckDuckGo…")
            try:
                web_results = _web_search_ddg(search_query, max_results=10)
                web_source = "DuckDuckGo (fallback — lower quality)"
            except Exception:
                yield ProgressEvent(phase="web_search", message="DuckDuckGo also failed. Skipping web search.")
    else:
        yield ProgressEvent(phase="web_search", message="No Tavily key — trying DuckDuckGo…")
        try:
            web_results = _web_search_ddg(search_query, max_results=10)
            web_source = "DuckDuckGo (lower quality — no Tavily key configured)"
            yield ProgressEvent(
                phase="web_search",
                message=f"DuckDuckGo returned {len(web_results)} results "
                        "(lower quality than Tavily — consider adding a free Tavily key).",
            )
        except Exception as e:
            yield ProgressEvent(phase="web_search", message=f"DuckDuckGo failed: {e}. Skipping web search.")

    # ── 2. Academic papers ────────────────────────────────────────────────────
    yield ProgressEvent(phase="paper_search", message="Searching academic papers…")
    papers: list[dict] = []
    try:
        papers, backend_used = search_scholarly(topic, max_results=15, semantic_scholar_api_key=ss_key)
        yield ProgressEvent(phase="paper_search", message=f"Found {len(papers)} papers via {backend_used}.")
    except Exception:
        pass

    if len(papers) < 5:
        yield ProgressEvent(phase="paper_search", message="Supplementing with Semantic Scholar…")
        try:
            s2 = paper_search(topic, max_results=15, api_key=ss_key)
            seen = {p.get("title", "").lower() for p in papers}
            for p in s2:
                if p.get("title", "").lower() not in seen:
                    papers.append(p)
                    seen.add(p.get("title", "").lower())
        except Exception:
            pass

    # ── 3. Compile document ───────────────────────────────────────────────────
    yield ProgressEvent(phase="compile", message="Compiling output document…")

    web_note = f"Web results: {len(web_results)} via {web_source}" if web_results else "Web results: none"
    sections: list[str] = [
        _DISCLAIMER_HEADER,
        f"# Deep Research (Free Tier): {topic}\n",
        f"*Generated: {date_str} | {web_note} | Papers: {len(papers)}*\n",
    ]

    if guide_ctx:
        sections.append("## Guide Context\n")
        sections.append(guide_ctx[:1000] + ("\n…*(truncated)*" if len(guide_ctx) > 1000 else ""))
        sections.append("")

    if web_results:
        sections.append("## Web Search Results\n")
        for i, r in enumerate(web_results, 1):
            sections.append(_format_web_result(r, i, source_label=web_source))
            sections.append("")
    else:
        sections.append(
            "## Web Search Results\n\n"
            "*No web results available. Add a free Tavily key to enable web search: "
            "`docent studio config-set --key tavily_api_key --value YOUR_KEY`*\n"
        )

    if papers:
        sections.append("## Academic Papers\n")
        for i, p in enumerate(papers, 1):
            sections.append(_format_paper(p, i))
            sections.append("")
    else:
        sections.append("## Academic Papers\n\n*No academic papers found.*\n")

    all_sources = [
        {"title": r.get("title", ""), "url": r.get("url", ""), "source_type": "web", "web_backend": web_source}
        for r in web_results
    ] + [
        {
            "title": p.get("title", ""),
            "url": p.get("url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else ""),
            "source_type": "paper",
        }
        for p in papers
    ]

    sections.append("## Sources\n")
    for s in all_sources:
        title = s.get("title") or "Untitled"
        url = s.get("url") or ""
        label = f"[{title}]({url})" if url else title
        sections.append(f"- {label}")

    sections.append(_MCP_SYNTHESIS_PROMPT if via_mcp else _MCP_NOTE_HUMAN)

    content = "\n".join(sections)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    sources_path = output_path.with_suffix(".sources.json")
    sources_path.write_text(
        json.dumps(all_sources, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    yield ProgressEvent(phase="done", message=f"Output written to {output_path}")
    return {"ok": True, "output_file": str(output_path), "sources_file": str(sources_path)}


def run_free_lit(
    topic: str,
    guide_ctx: str,
    ss_key: str | None,
    output_path: Path,
    *,
    via_mcp: bool = False,
) -> Generator[ProgressEvent, None, dict]:
    """Compile a free-tier literature review document (academic papers only).

    Yields ProgressEvents. Returns a result dict: ok, output_file, sources_file.
    """
    from .search import paper_search
    from .scholarly_client import search_scholarly

    date_str = datetime.date.today().isoformat()

    yield ProgressEvent(phase="paper_search", message="Searching academic databases…")
    papers: list[dict] = []
    try:
        papers, backend_used = search_scholarly(topic, max_results=20, semantic_scholar_api_key=ss_key)
        yield ProgressEvent(phase="paper_search", message=f"Found {len(papers)} papers via {backend_used}.")
    except Exception as e:
        yield ProgressEvent(phase="paper_search", message=f"Primary search failed: {e}")

    yield ProgressEvent(phase="paper_search", message="Supplementing with Semantic Scholar…")
    try:
        s2 = paper_search(topic, max_results=20, api_key=ss_key)
        seen = {p.get("title", "").lower() for p in papers}
        added = 0
        for p in s2:
            if p.get("title", "").lower() not in seen:
                papers.append(p)
                seen.add(p.get("title", "").lower())
                added += 1
        if added:
            yield ProgressEvent(phase="paper_search", message=f"Added {added} more papers from Semantic Scholar.")
    except Exception:
        pass

    yield ProgressEvent(phase="compile", message="Compiling literature review document…")

    sections: list[str] = [
        _DISCLAIMER_HEADER,
        f"# Literature Review (Free Tier): {topic}\n",
        f"*Generated: {date_str} | Papers found: {len(papers)}*\n",
    ]

    if guide_ctx:
        sections.append("## Guide Context\n")
        sections.append(guide_ctx[:1000] + ("\n…*(truncated)*" if len(guide_ctx) > 1000 else ""))
        sections.append("")

    if papers:
        sections.append("## Papers\n")
        for i, p in enumerate(papers, 1):
            sections.append(_format_paper(p, i))
            sections.append("")
    else:
        sections.append(
            "## Papers\n\n"
            "*No papers found. Try a broader topic or check your network connection.*\n"
        )

    all_sources = [
        {
            "title": p.get("title", ""),
            "url": p.get("url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else ""),
            "source_type": "paper",
        }
        for p in papers
    ]

    sections.append("## Sources\n")
    for s in all_sources:
        title = s.get("title") or "Untitled"
        url = s.get("url") or ""
        label = f"[{title}]({url})" if url else title
        sections.append(f"- {label}")

    sections.append(_MCP_SYNTHESIS_PROMPT if via_mcp else _MCP_NOTE_HUMAN)

    content = "\n".join(sections)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    sources_path = output_path.with_suffix(".sources.json")
    sources_path.write_text(
        json.dumps(all_sources, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    yield ProgressEvent(phase="done", message=f"Output written to {output_path}")
    return {"ok": True, "output_file": str(output_path), "sources_file": str(sources_path)}
