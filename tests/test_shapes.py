"""Tests for docent.core.shapes, docent.ui.renderers, and result.to_shapes()."""
from __future__ import annotations

import io

import pytest
from pydantic import TypeAdapter

from docent.core.shapes import (
    DataTableShape,
    ErrorShape,
    LinkShape,
    MarkdownShape,
    MessageShape,
    MetricShape,
    ProgressShape,
    Shape,
)
from docent.ui.renderers import render_shapes
from reading import (
    AddResult,
    ConfigSetResult,
    ConfigShowResult,
    ExportResult,
    MutationResult,
    QueueClearResult,
    SearchResult,
    StatsResult,
    SyncFromMendeleyResult,
    SyncStatusResult,
    QueueEntry,
)
from reading.reading_store import BannerCounts

from rich.console import Console


# ---------------------------------------------------------------------------
# 1. Shape construction
# ---------------------------------------------------------------------------

def test_markdown_shape():
    s = MarkdownShape(content="hello")
    assert s.type == "markdown"
    assert s.content == "hello"
    assert s.model_dump()["type"] == "markdown"


def test_data_table_shape():
    s = DataTableShape(columns=["a", "b"], rows=[["1", "2"]])
    assert s.type == "data_table"
    assert s.model_dump()["type"] == "data_table"


def test_metric_shape():
    s = MetricShape(label="Total", value=42, unit="entries")
    assert s.type == "metric"
    assert s.model_dump()["type"] == "metric"


def test_link_shape():
    s = LinkShape(label="Paper", url="https://example.com")
    assert s.type == "link"
    assert s.model_dump()["type"] == "link"


def test_message_shape():
    s = MessageShape(text="Done", level="success")
    assert s.type == "message"
    assert s.model_dump()["type"] == "message"


def test_error_shape():
    s = ErrorShape(reason="bad input", hint="try again")
    assert s.type == "error"
    assert s.model_dump()["type"] == "error"


def test_progress_shape():
    s = ProgressShape(phase="discover", current=1, total=10)
    assert s.type == "progress"
    assert s.model_dump()["type"] == "progress"


# ---------------------------------------------------------------------------
# 2. Shape discriminated union round-trip
# ---------------------------------------------------------------------------

_SHAPE_ADAPTER = TypeAdapter(Shape)

_ALL_SHAPES = [
    MarkdownShape(content="hi"),
    DataTableShape(columns=["x"], rows=[["1"]]),
    MetricShape(label="L", value=1),
    LinkShape(label="L", url="https://example.com"),
    MessageShape(text="msg", level="info"),
    ErrorShape(reason="fail"),
    ProgressShape(phase="p"),
]


@pytest.mark.parametrize("shape", _ALL_SHAPES, ids=lambda s: s.type)
def test_shape_union_round_trip(shape):
    dumped = shape.model_dump()
    restored = _SHAPE_ADAPTER.validate_python(dumped)
    assert type(restored) is type(shape)
    assert restored.model_dump() == dumped


# ---------------------------------------------------------------------------
# 3. to_shapes() on result types
# ---------------------------------------------------------------------------

def _shape_types(shapes: list[Shape]) -> list[str]:
    return [s.type for s in shapes]


def test_add_result_to_shapes():
    r = AddResult(added=False, queue_size=2, banner=BannerCounts(), message="Drop PDF")
    shapes = r.to_shapes()
    assert len(shapes) > 0
    assert all(hasattr(s, "type") for s in shapes)
    assert _shape_types(shapes) == ["markdown", "message"]


def test_mutation_result_ok_to_shapes():
    entry = QueueEntry(id="smith-2024-foo", mendeley_id="abc123", added="2024-01-01")
    r = MutationResult(
        ok=True, id="smith-2024-foo", entry=entry,
        queue_size=3, banner=BannerCounts(), message="Updated.",
    )
    shapes = r.to_shapes()
    assert len(shapes) >= 1
    assert all(hasattr(s, "type") for s in shapes)


def test_mutation_result_fail_to_shapes():
    r = MutationResult(
        ok=False, id="x", entry=None,
        queue_size=0, banner=BannerCounts(), message="Not found.",
    )
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["error"]


def test_search_result_no_matches_to_shapes():
    r = SearchResult(query="foo", matches=[], total=0, queue_size=0)
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["message"]


def test_search_result_with_matches_to_shapes():
    entry = QueueEntry(id="smith-2024-foo", mendeley_id="abc123", added="2024-01-01")
    r = SearchResult(query="foo", matches=[entry], total=1, queue_size=1)
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["message", "data_table"]


def test_stats_result_to_shapes():
    r = StatsResult(
        total=10, by_status={"queued": 6, "done": 4},
        by_category={"CES701": 5, "(root)": 5}, banner=BannerCounts(),
    )
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["metric", "data_table", "data_table"]


def test_export_result_to_shapes():
    r = ExportResult(format="json", count=3, content='[{"id":"a"}]')
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["message", "markdown"]


def test_queue_clear_result_cleared_to_shapes():
    r = QueueClearResult(cleared=True, removed_count=5, queue_size=0, banner=BannerCounts(), message="Cleared 5 entries.")
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["message"]
    assert shapes[0].level == "success"


def test_queue_clear_result_not_cleared_to_shapes():
    r = QueueClearResult(cleared=False, removed_count=0, queue_size=5, banner=BannerCounts(), message="5 entries.")
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["message"]
    assert shapes[0].level == "warning"


def test_config_show_result_to_shapes():
    r = ConfigShowResult(config_path="/tmp/config.toml", database_dir="/papers", queue_collection="Docent-Queue")
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["metric", "metric", "metric"]


def test_config_set_result_ok_to_shapes():
    r = ConfigSetResult(ok=True, key="database_dir", value="/papers", config_path="/tmp/config.toml", message="Set.")
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["message"]
    assert shapes[0].level == "success"


def test_config_set_result_fail_to_shapes():
    r = ConfigSetResult(ok=False, key="bad_key", value="x", config_path="/tmp/config.toml", message="Unknown key.")
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["message"]
    assert shapes[0].level == "error"


def test_sync_from_mendeley_result_with_message_to_shapes():
    r = SyncFromMendeleyResult(
        queue_collection="Q", folder_id=None,
        added=[], unchanged=[], removed=[], failed=[],
        dry_run_added=[], dry_run_removed=[], summary="",
        message="Collection not found.",
    )
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["message"]
    assert shapes[0].level == "warning"


def test_sync_from_mendeley_result_normal_to_shapes():
    r = SyncFromMendeleyResult(
        queue_collection="Q", folder_id="f1",
        added=[{"id": "a", "mendeley_id": "m1", "title": "T"}],
        unchanged=["b"], removed=[], failed=[],
        dry_run_added=[], dry_run_removed=[], summary="1 added.",
    )
    shapes = r.to_shapes()
    assert len(shapes) > 0
    assert any(isinstance(s, MetricShape) for s in shapes)


def test_sync_status_result_without_message_to_shapes():
    r = SyncStatusResult(
        database_dir="/papers", queue_size=5,
        database_pdfs=["a.pdf"], summary="5 entries.",
    )
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["metric", "metric", "metric"]


def test_sync_status_result_with_message_to_shapes():
    r = SyncStatusResult(
        database_dir=None, queue_size=0,
        database_pdfs=[], summary="",
        message="Not configured.",
    )
    shapes = r.to_shapes()
    assert _shape_types(shapes) == ["metric", "metric", "metric", "message"]


# ---------------------------------------------------------------------------
# 4. render_shapes smoke test
# ---------------------------------------------------------------------------

def test_render_shapes_smoke():
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=80)
    shapes = [
        MarkdownShape(content="# Hello"),
        MessageShape(text="Done", level="success"),
    ]
    render_shapes(shapes, console)
    output = buf.getvalue()
    assert "Hello" in output
    assert "Done" in output
