"""Unit tests for search.py (web_search, paper_search, fetch_page, Tavily spend tracking)."""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestWebSearch:
    @patch("docent.bundled_plugins.research_to_notebook.search._read_tavily_daily_requests")
    @patch("docent.bundled_plugins.research_to_notebook.search._write_tavily_daily_requests")
    def test_web_search_returns_normalised_dicts(self, mock_write, mock_read):
        from docent.bundled_plugins.research_to_notebook.search import web_search

        mock_read.return_value = 0

        fake_response = {
            "results": [
                {"title": "Result 1", "url": "https://example.com/1", "content": "Snippet 1"},
                {"title": "Result 2", "url": "https://example.com/2", "content": "Snippet 2"},
            ]
        }

        with patch(
            "tavily.TavilyClient"
        ) as MockClient:
            mock_instance = MagicMock()
            mock_instance.search.return_value = fake_response
            MockClient.return_value = mock_instance

            results = web_search("test query", max_results=8, api_key="test-key")

        assert len(results) == 2
        assert results[0] == {
            "title": "Result 1",
            "url": "https://example.com/1",
            "snippet": "Snippet 1",
        }
        assert results[1] == {
            "title": "Result 2",
            "url": "https://example.com/2",
            "snippet": "Snippet 2",
        }

    @patch("docent.bundled_plugins.research_to_notebook.search._read_tavily_daily_requests")
    @patch("docent.bundled_plugins.research_to_notebook.search._write_tavily_daily_requests")
    def test_web_search_returns_empty_on_exception(self, mock_write, mock_read):
        from docent.bundled_plugins.research_to_notebook.search import web_search

        mock_read.return_value = 0

        with patch(
            "tavily.TavilyClient",
            side_effect=Exception("rate limited"),
        ):
            results = web_search("test query", api_key="test-key")

        assert results == []


class TestWebSearchTavily:
    """Tests for Tavily-backed web_search (v1.2.0+)."""

    def test_returns_empty_when_api_key_is_none(self):
        from docent.bundled_plugins.research_to_notebook.search import web_search

        results = web_search("test query", api_key=None)
        assert results == []

    @patch("docent.bundled_plugins.research_to_notebook.search._read_tavily_daily_requests")
    @patch("docent.bundled_plugins.research_to_notebook.search._write_tavily_daily_requests")
    def test_calls_tavily_client_and_normalises_results(self, mock_write, mock_read):
        from docent.bundled_plugins.research_to_notebook.search import web_search

        mock_read.return_value = 0

        fake_response = {
            "results": [
                {"title": "Tavily Result", "url": "https://tavily.com/1", "content": "Tavily snippet"},
                {"title": "Another", "url": "https://tavily.com/2", "content": "More content"},
            ]
        }

        with patch(
            "tavily.TavilyClient"
        ) as MockClient:
            mock_instance = MagicMock()
            mock_instance.search.return_value = fake_response
            MockClient.return_value = mock_instance

            results = web_search("test query", api_key="test-key")

        MockClient.assert_called_once_with(api_key="test-key")
        mock_instance.search.assert_called_once_with("test query", max_results=8)
        assert len(results) == 2
        assert results[0] == {
            "title": "Tavily Result",
            "url": "https://tavily.com/1",
            "snippet": "Tavily snippet",
        }
        assert results[1] == {
            "title": "Another",
            "url": "https://tavily.com/2",
            "snippet": "More content",
        }

    @patch("docent.bundled_plugins.research_to_notebook.search._read_tavily_daily_requests")
    @patch("docent.bundled_plugins.research_to_notebook.search._write_tavily_daily_requests")
    def test_increments_daily_request_counter(self, mock_write, mock_read):
        from docent.bundled_plugins.research_to_notebook.search import web_search

        mock_read.return_value = 5

        fake_response = {
            "results": [
                {"title": "T", "url": "https://x.com", "content": "S"},
            ]
        }

        with patch(
            "tavily.TavilyClient"
        ) as MockClient:
            mock_instance = MagicMock()
            mock_instance.search.return_value = fake_response
            MockClient.return_value = mock_instance

            web_search("query", api_key="key")

        mock_read.assert_called_once()
        mock_write.assert_called_once_with(6)

    @patch("docent.bundled_plugins.research_to_notebook.search._read_tavily_daily_requests")
    @patch("docent.bundled_plugins.research_to_notebook.search._write_tavily_daily_requests")
    def test_counter_error_is_silently_ignored(self, mock_write, mock_read):
        """If spend tracking fails, web_search still returns results."""
        from docent.bundled_plugins.research_to_notebook.search import web_search

        mock_read.side_effect = OSError("disk full")

        fake_response = {
            "results": [
                {"title": "T", "url": "https://x.com", "content": "S"},
            ]
        }

        with patch(
            "tavily.TavilyClient"
        ) as MockClient:
            mock_instance = MagicMock()
            mock_instance.search.return_value = fake_response
            MockClient.return_value = mock_instance

            results = web_search("query", api_key="key")

        assert len(results) == 1
        mock_write.assert_not_called()

    def test_returns_empty_on_tavily_exception(self):
        from docent.bundled_plugins.research_to_notebook.search import web_search

        with patch(
            "tavily.TavilyClient",
            side_effect=Exception("Tavily API down"),
        ):
            results = web_search("test query", api_key="test-key")

        assert results == []

    def test_import_error_returns_empty(self):
        """When tavily is not installed, web_search returns []."""
        from docent.bundled_plugins.research_to_notebook.search import web_search

        with patch.dict("sys.modules", {"tavily": None}):
            results = web_search("test query", api_key="test-key")
            assert results == []


class TestTavilySpendFile:
    """Tests for _tavily_spend_file path resolution."""

    def test_returns_path_under_cache_dir(self, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook.search import _tavily_spend_file

        path = _tavily_spend_file()
        assert isinstance(path, Path)
        assert path.name == "tavily_spend.json"
        assert "research" in path.parts


class TestReadTavilyDailyRequests:
    """Tests for _read_tavily_daily_requests."""

    def test_returns_zero_when_file_does_not_exist(self, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook.search import _read_tavily_daily_requests

        result = _read_tavily_daily_requests()
        assert result == 0

    def test_returns_zero_when_file_has_stale_date(self, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook.search import (
            _read_tavily_daily_requests,
            _tavily_spend_file,
        )

        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        _tavily_spend_file().parent.mkdir(parents=True, exist_ok=True)
        _tavily_spend_file().write_text(
            json.dumps({"date": yesterday, "requests": 10}), encoding="utf-8"
        )

        result = _read_tavily_daily_requests()
        assert result == 0

    def test_returns_count_when_file_is_for_today(self, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook.search import (
            _read_tavily_daily_requests,
            _tavily_spend_file,
        )

        today = datetime.date.today().isoformat()
        _tavily_spend_file().parent.mkdir(parents=True, exist_ok=True)
        _tavily_spend_file().write_text(
            json.dumps({"date": today, "requests": 42}), encoding="utf-8"
        )

        result = _read_tavily_daily_requests()
        assert result == 42

    def test_returns_zero_on_corrupt_file(self, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook.search import (
            _read_tavily_daily_requests,
            _tavily_spend_file,
        )

        _tavily_spend_file().parent.mkdir(parents=True, exist_ok=True)
        _tavily_spend_file().write_text("not valid json {{{", encoding="utf-8")

        result = _read_tavily_daily_requests()
        assert result == 0


class TestWriteTavilyDailyRequests:
    """Tests for _write_tavily_daily_requests."""

    def test_creates_dir_and_writes_file(self, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook.search import (
            _tavily_spend_file,
            _write_tavily_daily_requests,
        )

        assert not _tavily_spend_file().exists()
        _write_tavily_daily_requests(7)
        assert _tavily_spend_file().exists()

        data = json.loads(_tavily_spend_file().read_text("utf-8"))
        assert data["requests"] == 7
        assert data["date"] == datetime.date.today().isoformat()

    def test_overwrites_previous_value(self, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook.search import (
            _tavily_spend_file,
            _write_tavily_daily_requests,
        )

        _write_tavily_daily_requests(3)
        _write_tavily_daily_requests(99)

        data = json.loads(_tavily_spend_file().read_text("utf-8"))
        assert data["requests"] == 99
        assert data["date"] == datetime.date.today().isoformat()


class TestPaperSearch:
    def test_paper_search_returns_normalised_dicts(self):
        from docent.bundled_plugins.research_to_notebook.search import paper_search

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "data": [
                {
                    "title": "Deep Learning for NLP",
                    "abstract": "A survey of deep learning methods.",
                    "authors": [
                        {"name": "Alice Smith"},
                        {"name": "Bob Jones"},
                    ],
                    "year": 2023,
                    "externalIds": {"ArXiv": "2301.00001"},
                },
                {
                    "title": "Transformers Are All You Need",
                    "abstract": "We propose a new architecture.",
                    "authors": [{"name": "Carol Lee"}],
                    "year": 2022,
                    "externalIds": {},
                },
            ]
        }
        fake_response.raise_for_status = MagicMock()

        with patch(
            "docent.bundled_plugins.research_to_notebook.search.httpx.get",
            return_value=fake_response,
        ):
            results = paper_search("deep learning nlp", max_results=5)

        assert len(results) == 2
        assert results[0]["title"] == "Deep Learning for NLP"
        assert results[0]["url"] == "https://arxiv.org/abs/2301.00001"
        assert "Alice Smith" in results[0]["authors"]
        assert results[0]["year"] == 2023
        assert results[1]["title"] == "Transformers Are All You Need"
        assert results[1]["url"] == ""

    def test_paper_search_returns_empty_on_http_error(self):
        from docent.bundled_plugins.research_to_notebook.search import paper_search

        with patch(
            "docent.bundled_plugins.research_to_notebook.search.httpx.get",
            side_effect=Exception("connection error"),
        ):
            results = paper_search("test query")

        assert results == []

    def test_paper_search_arxiv_url_built_correctly(self):
        from docent.bundled_plugins.research_to_notebook.search import paper_search

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "data": [
                {
                    "title": "Test Paper",
                    "abstract": "Abstract text.",
                    "authors": [{"name": "Author A"}],
                    "year": 2024,
                    "externalIds": {"ArXiv": "2401.12345"},
                },
            ]
        }
        fake_response.raise_for_status = MagicMock()

        with patch(
            "docent.bundled_plugins.research_to_notebook.search.httpx.get",
            return_value=fake_response,
        ):
            results = paper_search("test", max_results=1)

        assert results[0]["url"] == "https://arxiv.org/abs/2401.12345"


class TestFetchPage:
    def test_fetch_page_strips_html(self):
        from docent.bundled_plugins.research_to_notebook.search import fetch_page

        fake_response = MagicMock()
        fake_response.text = "<html><body><p>Hello <b>world</b></p></body></html>"
        fake_response.raise_for_status = MagicMock()

        with patch(
            "docent.bundled_plugins.research_to_notebook.search.httpx.get",
            return_value=fake_response,
        ):
            result = fetch_page("https://example.com")

        assert "<" not in result
        assert "Hello world" in result

    def test_fetch_page_truncates_to_max_chars(self):
        from docent.bundled_plugins.research_to_notebook.search import fetch_page

        long_text = "word " * 2000
        fake_response = MagicMock()
        fake_response.text = long_text
        fake_response.raise_for_status = MagicMock()

        with patch(
            "docent.bundled_plugins.research_to_notebook.search.httpx.get",
            return_value=fake_response,
        ):
            result = fetch_page("https://example.com", max_chars=100)

        assert len(result) <= 100

    def test_fetch_page_returns_empty_on_error(self):
        from docent.bundled_plugins.research_to_notebook.search import fetch_page

        with patch(
            "docent.bundled_plugins.research_to_notebook.search.httpx.get",
            side_effect=Exception("timeout"),
        ):
            result = fetch_page("https://example.com")

        assert result == ""

    def test_fetch_page_returns_empty_for_empty_url(self):
        from docent.bundled_plugins.research_to_notebook.search import fetch_page

        result = fetch_page("")
        assert result == ""