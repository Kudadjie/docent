"""Tests for the Zotero reference-manager backend.

Uses a fake pyzotero client (no network) — the field mapping was separately
verified against the live Zotero API during development. Shapes here mirror
real Zotero v3 API responses: collections expose data.name/data.parentCollection
(False for top-level), items expose data.itemType/title/creators/date/DOI.
"""
from __future__ import annotations

import pytest

from reading.zotero_backend import ZoteroBackend
from reading.mendeley_sync import build_entry_from_mendeley, extract_mendeley_id


class FakeZot:
    """Minimal stand-in for a pyzotero Zotero client.

    ``everything()`` is identity here because the fakes already return full
    lists (real pyzotero uses it to paginate past the per-request cap).
    """

    def __init__(self, collections, items_by_key, raises=None):
        self._collections = collections
        self._items = items_by_key
        self._raises = raises

    def collections(self):
        if self._raises:
            raise self._raises
        return self._collections

    def collection_items_top(self, key):
        if self._raises:
            raise self._raises
        return self._items.get(key, [])

    def everything(self, query):
        return query


def _coll(key, name, parent=False):
    return {"key": key, "data": {"key": key, "name": name, "parentCollection": parent}}


def _item(key, item_type, title, creators=None, date=None, doi=None):
    data = {"key": key, "itemType": item_type, "title": title}
    if creators is not None:
        data["creators"] = creators
    if date is not None:
        data["date"] = date
    if doi is not None:
        data["DOI"] = doi
    return {"key": key, "data": data}


def _backend(collections=None, items_by_key=None, raises=None):
    client = FakeZot(collections or [], items_by_key or {}, raises=raises)
    return ZoteroBackend(api_key="k", library_id="123", library_type="user", client=client)


# ── folders ───────────────────────────────────────────────────────────────────

def test_list_folders_maps_canonical_shape():
    be = _backend(collections=[
        _coll("AAA", "Docent-Queue", parent=False),
        _coll("BBB", "Sub", parent="AAA"),
    ])
    resp = be.list_folders()
    assert resp["error"] is None
    items = {f["id"]: f for f in resp["items"]}
    assert items["AAA"] == {"id": "AAA", "name": "Docent-Queue", "parent_id": None}
    assert items["BBB"]["parent_id"] == "AAA"  # child points at parent key


# ── documents ─────────────────────────────────────────────────────────────────

def test_list_documents_maps_fields():
    be = _backend(items_by_key={"AAA": [
        _item("X1", "journalArticle", "A Study",
              creators=[{"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}],
              date="September 29, 2010", doi="10.1/abc"),
    ]})
    resp = be.list_documents("AAA")
    assert resp["error"] is None
    d = resp["items"][0]
    assert d["id"] == "X1"
    assert d["title"] == "A Study"
    assert d["authors"] == [{"first_name": "Jane", "last_name": "Doe"}]
    assert d["year"] == 2010
    assert d["identifiers"] == {"doi": "10.1/abc"}
    assert d["type"] == "paper"


@pytest.mark.parametrize("item_type,expected", [
    ("book", "book"),
    ("bookSection", "book_section"),
    ("journalArticle", "paper"),
    ("webpage", "paper"),
])
def test_item_type_mapping(item_type, expected):
    be = _backend(items_by_key={"C": [_item("k", item_type, "T")]})
    assert be.list_documents("C")["items"][0]["type"] == expected


def test_skips_non_document_item_types():
    be = _backend(items_by_key={"C": [
        _item("a", "attachment", "PDF"),
        _item("n", "note", "a note"),
        _item("r", "journalArticle", "real"),
    ]})
    docs = be.list_documents("C")["items"]
    assert [d["id"] for d in docs] == ["r"]


def test_institutional_creator_becomes_string():
    be = _backend(items_by_key={"C": [
        _item("k", "report", "Gov Report",
              creators=[{"creatorType": "author", "name": "World Bank"}]),
    ]})
    assert be.list_documents("C")["items"][0]["authors"] == ["World Bank"]


@pytest.mark.parametrize("date,year", [
    ("September 29, 2010", 2010),
    ("2021-03", 2021),
    ("2019", 2019),
    ("", None),
    (None, None),
    ("no year here", None),
])
def test_year_parsing(date, year):
    be = _backend(items_by_key={"C": [_item("k", "journalArticle", "T", date=date)]})
    assert be.list_documents("C")["items"][0]["year"] == year


def test_missing_doi_yields_empty_identifiers():
    be = _backend(items_by_key={"C": [_item("k", "journalArticle", "T")]})
    assert be.list_documents("C")["items"][0]["identifiers"] == {}


# ── error paths ───────────────────────────────────────────────────────────────

def test_not_configured_returns_auth_error():
    be = ZoteroBackend(api_key=None, library_id=None)  # no client, no creds
    resp = be.list_folders()
    assert resp["items"] == []
    assert resp["error"].startswith("auth:")


def test_client_403_classified_as_auth():
    be = _backend(raises=RuntimeError("403 Forbidden — invalid key"))
    resp = be.list_folders()
    assert resp["error"].startswith("auth:")


def test_client_network_error_classified_as_transport():
    be = _backend(raises=RuntimeError("Connection timed out"))
    resp = be.list_folders()
    assert resp["error"].startswith("transport:")


# ── integration with the shared mapper ────────────────────────────────────────

def test_mapped_doc_builds_valid_queue_entry():
    be = _backend(items_by_key={"C": [
        _item("ZK99", "book", "Coastal Dynamics",
              creators=[{"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"}],
              date="2018", doi="10.5/xyz"),
    ]})
    doc = be.list_documents("C")["items"][0]
    entry = build_entry_from_mendeley(doc, extract_mendeley_id(doc), set(), 1, category="thesis")
    assert entry.title == "Coastal Dynamics"
    assert entry.authors == "Ada Lovelace"
    assert entry.year == 2018
    assert entry.type == "book"
    assert entry.doi == "10.5/xyz"
    assert entry.mendeley_id == "ZK99"  # external ref id stored here regardless of source


# ── client construction (arg order) ───────────────────────────────────────────

def test_make_zotero_passes_args_in_correct_order():
    """make_zotero(api_key, library_id, library_type) must map onto pyzotero's
    Zotero(library_id, library_type, api_key) — a silent swap would send the
    API key as the library id. Construction is offline (no API call)."""
    pytest.importorskip("pyzotero")
    from reading.zotero_client import make_zotero
    z = make_zotero(api_key="SECRET", library_id="9999", library_type="user")
    assert z.library_id == "9999"
    assert z.api_key == "SECRET"
    assert z.library_type == "users"  # pyzotero normalises "user" -> "users"


# ── backend selection ─────────────────────────────────────────────────────────

def test_select_backend_picks_zotero_vs_mendeley():
    from types import SimpleNamespace
    from reading import ReadingQueue

    def ctx(manager):
        rs = SimpleNamespace(
            reference_manager=manager, zotero_api_key="k",
            zotero_library_id="1", zotero_library_type="user",
            mendeley_mcp_command=None,
        )
        return SimpleNamespace(settings=SimpleNamespace(reading=rs))

    assert ReadingQueue._select_backend(ctx("zotero")).get_name() == "Zotero"
    assert ReadingQueue._select_backend(ctx("mendeley")).get_name() == "Mendeley"
