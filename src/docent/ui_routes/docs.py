"""Serve user-facing markdown docs via /api/docs/{slug}."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter()

# Slug → path relative to the docs root directory.
_SLUG_MAP: dict[str, str] = {
    "reading": "guides/reading-user-guide.md",
    "studio":  "guides/studio-user-guide.md",
    "cli":     "cli.md",
    "ecosystem": "ecosystem.md",
    "plugins": "plugin-guide.md",
}


def _docs_root() -> Path:
    """Resolve the docs directory for both editable and packaged installs."""
    # Editable / source install: project_root/docs/
    source = Path(__file__).parent.parent.parent.parent / "docs"
    if source.is_dir():
        return source
    # Packaged wheel: src/docent/docs/ (bundled via hatch artifacts)
    bundled = Path(__file__).parent.parent / "docs"
    return bundled


@router.get("/api/docs/{slug}", response_class=PlainTextResponse)
async def get_doc(slug: str) -> PlainTextResponse:
    if slug not in _SLUG_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown doc slug '{slug}'. Valid slugs: {sorted(_SLUG_MAP)}",
        )
    path = _docs_root() / _SLUG_MAP[slug]
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Doc file not found on disk: {_SLUG_MAP[slug]}",
        )
    return PlainTextResponse(
        path.read_text(encoding="utf-8"),
        media_type="text/plain; charset=utf-8",
    )


@router.get("/api/docs")
async def list_docs() -> dict[str, bool]:
    """Return available doc slugs and whether their files exist on disk."""
    root = _docs_root()
    return {
        slug: (root / rel).is_file()
        for slug, rel in _SLUG_MAP.items()
    }
