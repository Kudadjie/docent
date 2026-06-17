"""Tests for docent.whatsnew — changelog parsing + post-update banner state machine."""

from __future__ import annotations

import docent.whatsnew as wn

_CHANGELOG = """# Changelog

## [Unreleased]

### What's New
- Dev highlight A

## [2.1.0] - 2026-06-01

### What's New
- Faster UI
- SSRF hardening
### Changed
- Some internal refactor (should NOT be a highlight)

## [2.0.4] - 2026-05-01
- Bare bullet one
- Bare bullet two
"""


def _write_changelog(tmp_path, monkeypatch, text=_CHANGELOG):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(wn, "changelog_path", lambda: path)
    return path


# ── Parsing ─────────────────────────────────────────────────────────────────


def test_parse_extracts_versions_dates_and_whatsnew_highlights():
    releases = wn.parse_changelog(_CHANGELOG)
    by_ver = {r.version: r for r in releases}
    assert set(by_ver) == {"Unreleased", "2.1.0", "2.0.4"}
    assert by_ver["2.1.0"].date == "2026-06-01"
    # only the "### What's New" bullets, not the "### Changed" ones
    assert by_ver["2.1.0"].highlights == ["Faster UI", "SSRF hardening"]


def test_parse_falls_back_to_bare_bullets_when_no_whatsnew_section():
    by_ver = {r.version: r for r in wn.parse_changelog(_CHANGELOG)}
    assert by_ver["2.0.4"].highlights == ["Bare bullet one", "Bare bullet two"]


# ── get_latest_release ───────────────────────────────────────────────────────


def test_get_latest_release_returns_first_tagged(tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    rel = wn.get_latest_release()
    assert rel is not None and rel.version == "2.1.0"


def test_get_latest_release_skips_unreleased(tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    rel = wn.get_latest_release()
    assert rel is not None and rel.version != "Unreleased"


def test_get_latest_release_none_when_no_changelog(monkeypatch):
    monkeypatch.setattr(wn, "changelog_path", lambda: None)
    assert wn.get_latest_release() is None


# ── get_release matching ──────────────────────────────────────────────────────


def test_get_release_exact_match(tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    rel = wn.get_release("2.1.0")
    assert rel is not None and rel.highlights == ["Faster UI", "SSRF hardening"]


def test_get_release_normalizes_dev_version_then_falls_back_to_unreleased(tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    # 1.1.2.dev219+g047 has no exact or base ("1.1.2") entry → Unreleased
    rel = wn.get_release("1.1.2.dev219+g047043c71")
    assert rel is not None and rel.version == "Unreleased"


def test_get_release_none_when_no_changelog(monkeypatch):
    monkeypatch.setattr(wn, "changelog_path", lambda: None)
    assert wn.get_release("2.1.0") is None


# ── CLI banner state machine ──────────────────────────────────────────────────


def test_first_run_is_quiet_then_baseline_recorded(tmp_docent_home, tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    # No prior state → first run establishes baseline, shows nothing.
    assert wn.pop_banner_release("2.1.0") is None
    # Subsequent runs at the same version stay quiet.
    assert wn.pop_banner_release("2.1.0") is None


def test_version_change_shows_banner_then_goes_quiet(tmp_docent_home, tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    # Establish baseline at 2.0.4.
    assert wn.pop_banner_release("2.0.4") is None
    # Update to 2.1.0 → banner shows for MAX_BANNER_SHOWS invocations.
    shown = [wn.pop_banner_release("2.1.0") for _ in range(wn.MAX_BANNER_SHOWS)]
    assert all(r is not None and r.version == "2.1.0" for r in shown)
    # Then quiet until the next version bump.
    assert wn.pop_banner_release("2.1.0") is None


def test_no_banner_when_version_has_no_changelog_entry(tmp_docent_home, tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    assert wn.pop_banner_release("2.0.4") is None  # baseline
    # Update to a version with no entry → no banner, baseline silently advances.
    assert wn.pop_banner_release("9.9.9") is None


# ── UI payload ────────────────────────────────────────────────────────────────


def test_ui_payload_new_until_seen(tmp_docent_home, tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    payload = wn.ui_payload("2.1.0")
    assert payload["new"] is True
    assert payload["release"]["highlights"] == ["Faster UI", "SSRF hardening"]

    wn.mark_ui_seen("2.1.0")
    assert wn.ui_payload("2.1.0")["new"] is False
    # A newer version is "new" again.
    assert wn.ui_payload("2.2.0")["new"] is True


# ── _ui_seen_key ─────────────────────────────────────────────────────────────


def test_ui_seen_key_production_version_unchanged(tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    assert wn._ui_seen_key("2.1.0") == "2.1.0"


def test_ui_seen_key_dev_build_uses_latest_tagged(tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    # Latest tagged release in _CHANGELOG is "2.1.0"
    assert wn._ui_seen_key("2.0.5.dev60+gabc") == "2.1.0"


# ── UI route (/api/whatsnew) ──────────────────────────────────────────────────


def test_ui_route_get_then_seen(tmp_docent_home, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from docent import ui_server

    _write_changelog(tmp_path, monkeypatch)
    client = TestClient(ui_server.app)

    # Dev build: toast fires once (keyed on latest tagged release "2.1.0").
    data = client.get("/api/whatsnew").json()
    assert data["new"] is True
    assert data["release"]["highlights"]

    # After dismiss the seen key is "2.1.0"; next load is quiet.
    assert client.post("/api/whatsnew/seen").status_code == 200
    assert client.get("/api/whatsnew").json()["new"] is False


def test_ui_payload_dev_build_falls_back_to_latest_when_unreleased_empty(
    tmp_docent_home, tmp_path, monkeypatch
):
    empty_unreleased = "## [Unreleased]\n\n## [2.1.0] - 2026-06-01\n\n### What's New\n- Faster UI\n"
    _write_changelog(tmp_path, monkeypatch, text=empty_unreleased)
    payload = wn.ui_payload("1.0.0.dev5+gabcdef")
    # Falls back to latest tagged release and fires the toast.
    assert payload["new"] is True
    assert payload["release"] is not None
    assert payload["release"]["version"] == "2.1.0"


def test_ui_payload_dev_build_quiet_after_dismiss(tmp_docent_home, tmp_path, monkeypatch):
    _write_changelog(tmp_path, monkeypatch)
    # First load on dev: new=True (keyed on latest release "2.1.0")
    assert wn.ui_payload("1.0.0.dev5+gabcdef")["new"] is True
    # Dismiss (stored as "2.1.0", not the dev string)
    wn.mark_ui_seen("1.0.0.dev5+gabcdef")
    # Subsequent dev commits: same seen key → quiet
    assert wn.ui_payload("1.0.0.dev6+gffffff")["new"] is False
    # New tagged release: seen key changes → fires again
    assert wn.ui_payload("1.0.0.dev6+gffffff")["new"] is False  # still on 2.1.0 latest


# ── CLI command + banner ──────────────────────────────────────────────────────


def test_whatsnew_command_prints_highlights(tmp_path, monkeypatch):
    from rich.console import Console

    import docent.cli as cli

    _write_changelog(tmp_path, monkeypatch)
    rec = Console(record=True, width=100)
    monkeypatch.setattr(cli, "get_console", lambda: rec)
    cli.whatsnew_command()
    out = rec.export_text()
    assert "What's New" in out
    assert "Dev highlight A" in out  # the [Unreleased] highlight


def test_whatsnew_command_dev_build_shows_latest_when_unreleased_empty(tmp_path, monkeypatch):
    """On dev builds with an empty [Unreleased], show latest tagged release notes."""
    from rich.console import Console

    import docent.cli as cli

    empty_unreleased = "## [Unreleased]\n\n## [2.1.0] - 2026-06-01\n\n### What's New\n- Faster UI\n"
    _write_changelog(tmp_path, monkeypatch, text=empty_unreleased)
    # Simulate a dev-build version string.
    monkeypatch.setattr(cli, "__version__", "1.0.0.dev5+gabcdef")
    rec = Console(record=True, width=100)
    monkeypatch.setattr(cli, "get_console", lambda: rec)
    cli.whatsnew_command()
    out = rec.export_text()
    assert "2.1.0" in out
    assert "Faster UI" in out
    assert "Dev build" in out


def test_cli_banner_renders_when_interactive(tmp_path, monkeypatch):
    from rich.console import Console

    import docent.cli as cli

    _write_changelog(tmp_path, monkeypatch)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    monkeypatch.delenv("DOCENT_UI_SUBPROCESS", raising=False)
    monkeypatch.setattr(
        wn, "pop_banner_release", lambda: wn.Release(version="9.9.9", highlights=["Shiny thing"])
    )
    rec = Console(record=True, width=100)
    monkeypatch.setattr(cli, "get_console", lambda: rec)
    cli._maybe_show_whatsnew()
    out = rec.export_text()
    assert "9.9.9" in out and "Shiny thing" in out


def test_cli_banner_quiet_when_not_a_tty(monkeypatch):
    """Non-interactive callers (pipes, MCP, UI subprocess) never see the banner."""
    import docent.cli as cli

    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False)
    called = {"n": 0}
    monkeypatch.setattr(wn, "pop_banner_release", lambda: called.__setitem__("n", 1))
    cli._maybe_show_whatsnew()  # must return before touching state
    assert called["n"] == 0
