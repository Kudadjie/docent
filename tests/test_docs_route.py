"""Tests for /api/docs/{slug} — ensures docs files are reachable and valid.

These tests catch two failure modes:
  1. A docs file was deleted or moved (route returns 404).
  2. A docs file was accidentally emptied or is missing expected headings.
"""

import pytest
from fastapi.testclient import TestClient

from docent.ui_routes.docs import _SLUG_MAP, _docs_root
from docent.ui_server import app

client = TestClient(app)

VALID_SLUGS = list(_SLUG_MAP)

# Required H2 headings per doc — ensures the file wasn't accidentally gutted.
# Update these if you intentionally rename a top-level section.
REQUIRED_HEADINGS: dict[str, list[str]] = {
    "reading": ["## Prerequisites", "## The workflow", "## Syncing with your reference manager"],
    "studio": ["## "],  # at least one H2
    "cli": ["## 3. The Reading Queue", "## 4. Configuration"],
    "ecosystem": ["## "],  # at least one H2
    "plugins": ["## "],  # at least one H2
}


# ── Availability ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("slug", VALID_SLUGS)
def test_valid_slug_returns_200(slug: str):
    r = client.get(f"/api/docs/{slug}")
    assert r.status_code == 200, f"/api/docs/{slug} returned {r.status_code}: {r.text[:200]}"


def test_invalid_slug_returns_404():
    r = client.get("/api/docs/nonexistent-slug")
    assert r.status_code == 404


def test_list_endpoint_returns_all_slugs():
    r = client.get("/api/docs")
    assert r.status_code == 200
    data = r.json()
    for slug in VALID_SLUGS:
        assert slug in data, f"Slug '{slug}' missing from /api/docs listing"
        assert data[slug] is True, f"Doc file for slug '{slug}' is missing on disk"


# ── Content validity ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("slug", VALID_SLUGS)
def test_doc_is_non_empty(slug: str):
    r = client.get(f"/api/docs/{slug}")
    assert len(r.text.strip()) > 100, f"/api/docs/{slug} content is suspiciously short"


@pytest.mark.parametrize("slug", VALID_SLUGS)
def test_doc_is_valid_utf8(slug: str):
    path = _docs_root() / _SLUG_MAP[slug]
    text = path.read_text(encoding="utf-8")  # raises if not valid UTF-8
    assert text  # non-empty


@pytest.mark.parametrize("slug,headings", REQUIRED_HEADINGS.items())
def test_doc_contains_required_headings(slug: str, headings: list[str]):
    r = client.get(f"/api/docs/{slug}")
    content = r.text
    for heading in headings:
        assert heading in content, (
            f"/api/docs/{slug} is missing expected heading: {heading!r}\n"
            "If you renamed this section, update REQUIRED_HEADINGS in test_docs_route.py."
        )


# ── No Mendeley-only framing in user docs ────────────────────────────────────
# Catches accidental reintroduction of Mendeley-only language in user-facing docs.

_BANNED_PHRASES: list[str] = [
    "syncs with Mendeley",
    "sync-from-mendeley\n",  # bare command (not the alias-mention line)
    "Mendeley is the source of truth",
    "Mendeley Desktop\n",  # bare prereq line (OK inside "Mendeley Desktop (or…)")
    "mendeley_id",  # old field name, replaced by reference_id
    "SyncFromMendeleyResult",  # old result type name
]


@pytest.mark.parametrize("slug", ["reading", "cli"])
def test_doc_has_no_banned_mendeley_phrases(slug: str):
    r = client.get(f"/api/docs/{slug}")
    content = r.text
    for phrase in _BANNED_PHRASES:
        assert phrase not in content, (
            f"/api/docs/{slug} contains banned Mendeley-only phrase: {phrase!r}\n"
            "Update the docs to use reference-manager-agnostic language."
        )
