"""NotebookLM action mixin: to-notebook."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from docent.bundled_plugins.studio._notebook import (
    ToNotebookInputs,
    ToNotebookResult,
    _find_sources_path,
    _nlm_push,
    _rank_sources,
    notebooklm_session_lock,
)
from docent.bundled_plugins.studio.preflights import _preflight_to_notebook
from docent.core import Context, ProgressEvent, action


class NotebookMixin:
    """Mixin providing notebook actions for StudioTool."""

    @action(
        description=(
            "Populate a new or existing NotebookLM notebook with research sources, then run "
            "the full quality pipeline: NLM web research arm, source stabilisation, quality "
            "gate (validation + contradictions + gap-fill), and 3-perspective summaries "
            "(practitioner / skeptic / beginner). Mirrors the research-to-notebook skill. "
            "Falls back to local package export + browser open if NLM is unavailable."
        ),
        input_schema=ToNotebookInputs,
        name="to-notebook",
        preflight=_preflight_to_notebook,
    )
    def to_notebook(self, inputs: ToNotebookInputs, context: Context):
        output_dir = context.settings.research.output_dir.expanduser()

        # Preflight resolves output_file before the action runs. When called
        # directly (e.g. in tests, bypassing preflight) we auto-detect.
        if inputs.output_file is None:
            candidates = (
                sorted(
                    [
                        p
                        for p in output_dir.glob("*.md")
                        if not p.name.endswith("-review.md")
                        and not p.name.endswith("-sources.json")
                    ],
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if output_dir.is_dir()
                else []
            )
            if not candidates:
                return ToNotebookResult(
                    ok=False,
                    output_file=None,
                    sources_file=None,
                    package_dir=None,
                    sources_count=0,
                    message=(
                        f"No research output found in {output_dir}. "
                        "Run docent studio deep-research or docent studio lit first."
                    ),
                )
            inputs.output_file = str(candidates[0])

        out_path = Path(inputs.output_file)
        if not out_path.is_absolute():
            out_path = output_dir / inputs.output_file

        # Extra synthesis docs selected by the multi-file picker
        extra_synthesis_docs: list[Path] = []
        for extra_str in inputs.output_files or []:
            ep = Path(extra_str)
            if not ep.is_absolute():
                ep = output_dir / extra_str
            if ep.exists():
                extra_synthesis_docs.append(ep)

        stem = out_path.stem
        if inputs.sources_file:
            _explicit_src = Path(inputs.sources_file)
            if not _explicit_src.is_absolute():
                _explicit_src = output_dir / inputs.sources_file
            sources_path = _explicit_src
        else:
            sources_path = _find_sources_path(out_path) or (
                out_path.parent / f"{stem}-sources.json"
            )

        has_sources = sources_path.exists()

        # Merge sources JSON from extra files (multi-file picker "all" case)
        extra_sources_raw: list[dict] = []
        for extra_doc in extra_synthesis_docs:
            extra_src = _find_sources_path(extra_doc)
            if extra_src and extra_src.exists():
                try:
                    extra_sources_raw.extend(json.loads(extra_src.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    pass

        primary_raw = json.loads(sources_path.read_text(encoding="utf-8")) if has_sources else []
        all_raw = primary_raw + extra_sources_raw
        selected = _rank_sources(all_raw, inputs.max_sources) if all_raw else []

        # Write merged sources to a combined sources file for the package
        if extra_sources_raw and all_raw:
            merged_src_path = out_path.parent / f"{stem}-combined-sources.json"
            merged_src_path.write_text(
                json.dumps(all_raw, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            sources_path = merged_src_path
            has_sources = True

        package_dir = out_path.parent / f"{stem}-notebook"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "sources_urls.txt").write_text(
            "\n".join(s["url"] for s in selected if s.get("url")),
            encoding="utf-8",
        )
        shutil.copy2(out_path, package_dir / out_path.name)
        yield ProgressEvent(phase="package", message=f"Local package written to {package_dir}")

        if inputs.notebook_id:
            context.settings.research.notebooklm_notebook_id = inputs.notebook_id

        sources_file_str = str(sources_path) if has_sources else None

        # ── Machine-level NotebookLM session mutex ────────────────────────────
        # The shared Playwright session can't be touched by two runs at once.
        # Acquire non-blocking first; if another run (UI, CLI, or MCP) holds it,
        # surface a human "waiting" event and then block until it frees up. This
        # is what makes the client-side auto-queue *correct* rather than advisory,
        # and it also covers the CLI-vs-UI collision the client can't see.
        from filelock import Timeout as _FileLockTimeout

        lock_timeout = context.settings.research.notebooklm_lock_timeout
        session_lock = notebooklm_session_lock(timeout=lock_timeout)
        try:
            session_lock.acquire(timeout=0)
        except _FileLockTimeout:
            yield ProgressEvent(
                phase="nlm-wait",
                message=(
                    "Waiting: NotebookLM session is busy — another to-notebook run is "
                    "active. This run will start automatically when it finishes."
                ),
            )
            try:
                session_lock.acquire(timeout=lock_timeout)
            except _FileLockTimeout:
                return ToNotebookResult(
                    ok=False,
                    output_file=str(out_path),
                    sources_file=sources_file_str,
                    package_dir=str(package_dir),
                    sources_count=len(selected),
                    message=(
                        f"NotebookLM session stayed busy for over {int(lock_timeout)}s — "
                        "aborting. Run this again once the other to-notebook run finishes."
                    ),
                )

        try:
            nlm = yield from _nlm_push(
                out_path=out_path,
                sources_path=sources_path if has_sources else None,
                context=context,
                max_sources=inputs.max_sources,
                topic=inputs.topic,
                guide_files=[Path(p).expanduser() for p in inputs.guide_files],
                extra_synthesis_docs=extra_synthesis_docs or None,
                run_nlm_research=inputs.run_nlm_research,
                run_quality_gate=inputs.run_quality_gate,
                run_perspectives=inputs.run_perspectives,
            )
        finally:
            session_lock.release()

        # ── Write quality report to package dir ───────────────────────────────
        qg = nlm.get("quality_gate")
        persp = nlm.get("perspectives")
        if qg or persp:
            report_parts: list[str] = ["# Docent Studio — Quality Report\n"]
            if qg and qg.get("raw"):
                report_parts.append(qg["raw"])
            if persp:
                report_parts.append("\n## Perspectives\n")
                for key, label in (
                    ("practitioner", "Practitioner"),
                    ("skeptic", "Skeptic"),
                    ("beginner", "Beginner"),
                ):
                    if persp.get(key):
                        report_parts.append(f"### {label}\n\n{persp[key]}\n")
            report_path = package_dir / "quality-report.md"
            report_path.write_text("\n".join(report_parts), encoding="utf-8")
            yield ProgressEvent(phase="package", message=f"Quality report: {report_path}")

        if not nlm["ok"]:
            import webbrowser

            webbrowser.open("https://notebooklm.google.com")
            return ToNotebookResult(
                ok=True,
                output_file=str(out_path),
                sources_file=sources_file_str,
                package_dir=str(package_dir),
                sources_count=len(selected),
                sources_added=0,
                sources_failed=0,
                message=f"{nlm['message']} -- opened browser. Local package at {package_dir}.",
            )

        nb_id = nlm["notebook_id"]
        save_hint = ""
        if nb_id and nb_id != context.settings.research.notebooklm_notebook_id:
            save_hint = (
                f" Save with: docent studio config-set --key notebooklm_notebook_id --value {nb_id}"
            )

        return ToNotebookResult(
            ok=True,
            output_file=str(out_path),
            sources_file=sources_file_str,
            package_dir=str(package_dir),
            sources_count=len(selected),
            sources_added=nlm["sources_added"],
            sources_failed=nlm["sources_failed"],
            sources_from_feynman=nlm["sources_from_feynman"],
            sources_from_nlm=nlm["sources_from_nlm"],
            notebook_id=nb_id,
            quality_gate=nlm["quality_gate"],
            perspectives=nlm["perspectives"],
            message=nlm["message"] + save_hint,
        )
