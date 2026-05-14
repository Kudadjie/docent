"""Tests for OcClient spend tracking."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import docent.bundled_plugins.studio.oc_client as oc_mod
from docent.bundled_plugins.studio.oc_client import (
    OcBudgetExceededError,
    OcClient,
    _read_oc_daily_spend,
    _write_oc_daily_spend,
)


@pytest.fixture(autouse=True)
def redirect_spend_file(tmp_path, monkeypatch):
    monkeypatch.setattr(oc_mod, "_oc_spend_file", lambda: tmp_path / "oc_spend.json")


def test_spend_starts_at_zero():
    assert _read_oc_daily_spend() == 0.0


def test_write_and_read_spend():
    _write_oc_daily_spend(0.42)
    assert _read_oc_daily_spend() == 0.42


def test_spend_resets_for_new_day():
    import datetime
    import json

    spend_file = oc_mod._oc_spend_file()
    spend_file.parent.mkdir(parents=True, exist_ok=True)
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    spend_file.write_text(
        json.dumps({"date": yesterday, "spend_usd": 1.23}),
        encoding="utf-8",
    )
    assert _read_oc_daily_spend() == 0.0


def test_call_accumulates_cost():
    client = OcClient()
    mock_response = {
        "parts": [{"type": "text", "text": "ok"}],
        "info": {"cost": 0.05},
    }
    with patch.object(client, "_api") as mock_api:
        mock_api.side_effect = [
            {"id": "sess1"},
            mock_response,
        ]
        result = client.call("test prompt", model="glm-5.1")
    assert result == "ok"
    assert _read_oc_daily_spend() == pytest.approx(0.05)


def test_call_silent_on_missing_cost():
    client = OcClient()
    mock_response = {
        "parts": [{"type": "text", "text": "hello"}],
    }
    with patch.object(client, "_api") as mock_api:
        mock_api.side_effect = [
            {"id": "sess1"},
            mock_response,
        ]
        result = client.call("test prompt", model="glm-5.1")
    assert result == "hello"
    assert _read_oc_daily_spend() == 0.0


def test_budget_zero_never_blocks():
    """budget_usd=0.0 means no limit — even with huge spend, no error raised."""
    _write_oc_daily_spend(9999.0)
    client = OcClient(budget_usd=0.0)
    mock_response = {"parts": [{"type": "text", "text": "ok"}]}
    with patch.object(client, "_api") as mock_api:
        mock_api.side_effect = [{"id": "s"}, mock_response]
        result = client.call("hi")
    assert result == "ok"


def test_budget_90_percent_blocks():
    """Spend at 90% of budget raises OcBudgetExceededError before making the API call."""
    _write_oc_daily_spend(0.90)  # 90% of $1.00
    client = OcClient(budget_usd=1.0)
    with pytest.raises(OcBudgetExceededError, match="daily budget nearly exhausted"):
        client.call("test")


def test_budget_under_90_proceeds():
    """Spend under 90% proceeds normally."""
    _write_oc_daily_spend(0.50)  # 50% of $2.00 — under threshold
    client = OcClient(budget_usd=2.0)
    mock_response = {"parts": [{"type": "text", "text": "ok"}]}
    with patch.object(client, "_api") as mock_api:
        mock_api.side_effect = [{"id": "s"}, mock_response]
        result = client.call("hi")
    assert result == "ok"