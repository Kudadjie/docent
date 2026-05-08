"""Unit tests for search.py (web_search, paper_search, fetch_page)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestWebSearch:
    def test_web_search_returns_normalised_dicts(self):
        from docent.bundled_plugins.research_to_notebook.search import web_search

        fake_results = [
            {"title": "Result 1", "href": "https://example.com/1", "body": "Snippet 1"},
            {"title": "Result 2", "href": "https://example.com/2", "body": "Snippet 2"},
        ]
        with patch(
            "docent.bundled_plugins.research_to_notebook.search.DDGS"
        ) as MockDDGS:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.text.return_value = iter(fake_results)
            MockDDGS.return_value = mock_instance

            results = web_search("test query", max_results=8)

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

    def test_web_search_returns_empty_on_exception(self):
        from docent.bundled_plugins.research_to_notebook.search import web_search

        with patch(
            "docent.bundled_plugins.research_to_notebook.search.DDGS",
            side_effect=Exception("rate limited"),
        ):
            results = web_search("test query")

        assert results == []


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