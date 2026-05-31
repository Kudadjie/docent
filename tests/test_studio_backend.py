"""Unit tests for the platform-agnostic studio backend (backend.py)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from docent.bundled_plugins.studio.backend import (
    DOCENT_BACKEND_NAMES,
    LiteLLMBackend,
    OcBackend,
    _PROVIDER_SPECS,
    get_backend,
)
from docent.config.settings import ResearchSettings, Settings
from docent.errors import AuthError, ServiceUnavailableError, UsageLimitError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(**research_kwargs) -> Settings:
    rs = ResearchSettings(**research_kwargs)
    return Settings(research=rs)


def _mock_litellm_response(text: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = text
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# DOCENT_BACKEND_NAMES completeness
# ---------------------------------------------------------------------------

class TestBackendNames:
    def test_all_provider_specs_in_names(self):
        assert set(_PROVIDER_SPECS).issubset(DOCENT_BACKEND_NAMES)

    def test_docent_and_opencode_in_names(self):
        assert "docent" in DOCENT_BACKEND_NAMES
        assert "opencode" in DOCENT_BACKEND_NAMES

    def test_free_and_feynman_not_in_names(self):
        # Those are separate tiers, not Docent-tier backends
        assert "free" not in DOCENT_BACKEND_NAMES
        assert "feynman" not in DOCENT_BACKEND_NAMES


# ---------------------------------------------------------------------------
# get_backend factory routing
# ---------------------------------------------------------------------------

class TestGetBackendRouting:
    def test_no_override_opencode_default(self):
        s = _settings(studio_backend="opencode")
        assert isinstance(get_backend(s), OcBackend)

    def test_override_docent_resolves_opencode(self):
        s = _settings(studio_backend="opencode")
        assert isinstance(get_backend(s, override="docent"), OcBackend)

    def test_override_opencode_returns_oc_backend(self):
        s = _settings()
        assert isinstance(get_backend(s, override="opencode"), OcBackend)

    def test_studio_backend_groq_returns_litellm(self):
        s = _settings(studio_backend="groq", groq_api_key="gsk_test")
        assert isinstance(get_backend(s), LiteLLMBackend)

    def test_override_groq_returns_litellm(self):
        s = _settings(groq_api_key="gsk_test")
        assert isinstance(get_backend(s, override="groq"), LiteLLMBackend)

    def test_override_gemini_raises_value_error(self):
        # gemini was archived in commit 286607e; expect ValueError until restored
        s = _settings(gemini_api_key="AIzatest")
        with pytest.raises(ValueError, match="Unknown studio backend"):
            get_backend(s, override="gemini")

    def test_override_openrouter_raises_value_error(self):
        # openrouter was archived in commit 286607e; expect ValueError until restored
        s = _settings(openrouter_api_key="sk-or-test")
        with pytest.raises(ValueError, match="Unknown studio backend"):
            get_backend(s, override="openrouter")

    def test_unknown_backend_raises_value_error(self):
        s = _settings()
        with pytest.raises(ValueError, match="Unknown studio backend"):
            get_backend(s, override="notabackend")

    def test_missing_key_raises_auth_error(self):
        s = _settings(groq_api_key=None)
        with pytest.raises(AuthError, match="No API key found"):
            get_backend(s, override="groq")

    def test_missing_key_error_mentions_env_var(self):
        s = _settings(groq_api_key=None)
        with pytest.raises(AuthError, match="GROQ_API_KEY"):
            get_backend(s, override="groq")

    def test_env_var_key_fallback(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_from_env")
        s = _settings(groq_api_key=None)
        b = get_backend(s, override="groq")
        assert isinstance(b, LiteLLMBackend)
        assert b._api_key == "gsk_from_env"

    def test_settings_key_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_from_env")
        s = _settings(groq_api_key="gsk_from_settings")
        b = get_backend(s, override="groq")
        assert b._api_key == "gsk_from_settings"

    def test_anthropic_raises_value_error(self):
        # anthropic was archived in commit 286607e; expect ValueError until restored
        s = Settings(anthropic_api_key="sk-ant-test", research=ResearchSettings())
        with pytest.raises(ValueError, match="Unknown studio backend"):
            get_backend(s, override="anthropic")

    def test_openai_raises_value_error(self):
        # openai was archived in commit 286607e; expect ValueError until restored
        s = Settings(openai_api_key="sk-openai-test", research=ResearchSettings())
        with pytest.raises(ValueError, match="Unknown studio backend"):
            get_backend(s, override="openai")


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------

class TestModelResolution:
    def test_groq_model_gets_prefix(self):
        s = _settings(groq_api_key="key", groq_model="llama-3.3-70b-versatile")
        b = get_backend(s, override="groq")
        assert b._model == "groq/llama-3.3-70b-versatile"

    def test_model_not_double_prefixed(self):
        s = _settings(groq_api_key="key", groq_model="groq/mixtral-8x7b")
        b = get_backend(s, override="groq")
        assert b._model == "groq/mixtral-8x7b"

    def test_gemini_raises_value_error(self):
        # gemini was archived in commit 286607e; expect ValueError until restored
        s = _settings(gemini_api_key="key", gemini_model="gemini-2.0-flash")
        with pytest.raises(ValueError, match="Unknown studio backend"):
            get_backend(s, override="gemini")

    def test_custom_groq_model_reflected(self):
        s = _settings(groq_api_key="key", groq_model="llama-3.3-70b-versatile")
        b = get_backend(s, override="groq")
        assert "llama-3.3-70b-versatile" in b._model


# ---------------------------------------------------------------------------
# Local backends (no key required)
# ---------------------------------------------------------------------------

class TestLocalBackends:
    """Local backends (ollama, lm_studio, local) were archived in commit 286607e.
    These tests verify that they raise ValueError until they are restored.
    To restore: add the provider spec back to _PROVIDER_SPECS in backend.py.
    """

    def test_ollama_raises_value_error(self):
        s = _settings()
        with pytest.raises(ValueError, match="Unknown studio backend"):
            get_backend(s, override="ollama")

    def test_lm_studio_raises_value_error(self):
        s = _settings()
        with pytest.raises(ValueError, match="Unknown studio backend"):
            get_backend(s, override="lm_studio")

    def test_local_raises_value_error(self):
        s = _settings(local_api_key=None, local_base_url="http://localhost:8080/v1")
        with pytest.raises(ValueError, match="Unknown studio backend"):
            get_backend(s, override="local")


# ---------------------------------------------------------------------------
# LiteLLMBackend.call
# ---------------------------------------------------------------------------

class TestLiteLLMBackendCall:
    def test_call_returns_content(self):
        b = LiteLLMBackend("groq/llama3", api_key="key")
        with patch("litellm.completion", return_value=_mock_litellm_response("hello world")):
            result = b.call("test prompt")
        assert result == "hello world"

    def test_system_prompt_added_to_messages(self):
        b = LiteLLMBackend("groq/llama3", api_key="key")
        captured: list = []

        def fake_completion(**kwargs):
            captured.append(kwargs["messages"])
            return _mock_litellm_response("ok")

        with patch("litellm.completion", side_effect=fake_completion):
            b.call("user msg", system="be helpful")

        msgs = captured[0]
        assert msgs[0] == {"role": "system", "content": "be helpful"}
        assert msgs[1] == {"role": "user", "content": "user msg"}

    def test_role_ignored_for_model_selection(self):
        """LiteLLMBackend uses the same model regardless of role."""
        b = LiteLLMBackend("groq/llama3", api_key="key")
        calls: list = []

        def fake_completion(**kwargs):
            calls.append(kwargs["model"])
            return _mock_litellm_response("ok")

        with patch("litellm.completion", side_effect=fake_completion):
            b.call("p1", role="planner")
            b.call("p2", role="reviewer")

        assert calls == ["groq/llama3", "groq/llama3"]

    def test_auth_error_mapped_to_docent_auth_error(self, monkeypatch):
        import litellm

        class _FakeAuthError(Exception):
            pass

        monkeypatch.setattr(litellm, "AuthenticationError", _FakeAuthError)
        b = LiteLLMBackend("groq/llama3", api_key="badkey")
        with patch("litellm.completion", side_effect=_FakeAuthError("bad key")):
            with pytest.raises(AuthError):
                b.call("test")

    def test_rate_limit_mapped_to_usage_limit_error(self, monkeypatch):
        import litellm

        class _FakeRateLimitError(Exception):
            pass

        monkeypatch.setattr(litellm, "RateLimitError", _FakeRateLimitError)
        b = LiteLLMBackend("groq/llama3", api_key="key")
        with patch("litellm.completion", side_effect=_FakeRateLimitError("slow down")):
            with pytest.raises(UsageLimitError):
                b.call("test")

    def test_service_unavailable_mapped(self, monkeypatch):
        import litellm

        class _FakeServiceError(Exception):
            pass

        monkeypatch.setattr(litellm, "ServiceUnavailableError", _FakeServiceError)
        b = LiteLLMBackend("groq/llama3", api_key="key")
        with patch("litellm.completion", side_effect=_FakeServiceError("down")):
            with pytest.raises(ServiceUnavailableError):
                b.call("test")

    def test_base_url_passed_to_litellm(self):
        b = LiteLLMBackend("openai/local", api_key="lm-studio", base_url="http://localhost:1234/v1")
        captured: list = []

        def fake_completion(**kwargs):
            captured.append(kwargs)
            return _mock_litellm_response("ok")

        with patch("litellm.completion", side_effect=fake_completion):
            b.call("test")

        assert captured[0]["base_url"] == "http://localhost:1234/v1"

    def test_empty_content_returns_empty_string(self):
        b = LiteLLMBackend("groq/llama3", api_key="key")
        with patch("litellm.completion", return_value=_mock_litellm_response("")):
            result = b.call("test")
        assert result == ""


# ---------------------------------------------------------------------------
# OcBackend role mapping
# ---------------------------------------------------------------------------

class TestOcBackendRoleMapping:
    @pytest.fixture
    def mock_oc(self, monkeypatch):
        mock = MagicMock()
        mock.call.return_value = "response"
        mock.is_available.return_value = True
        import docent.bundled_plugins.studio.backend as bmod
        monkeypatch.setattr(
            bmod,
            "OcBackend.__init__",
            lambda self, settings: (
                setattr(self, "_oc", mock) or
                setattr(self, "_research", settings.research)
            ),
        )
        return mock

    def test_planner_role_uses_planner_model(self):
        s = _settings(oc_model_planner="glm-5.1")
        b = OcBackend.__new__(OcBackend)
        mock_oc = MagicMock()
        mock_oc.call.return_value = "ok"
        b._oc = mock_oc
        b._research = s.research

        b.call("prompt", role="planner")
        mock_oc.call.assert_called_once_with("prompt", model="glm-5.1", timeout=300)

    def test_writer_role_uses_writer_model(self):
        s = _settings(oc_model_writer="minimax-m2.7")
        b = OcBackend.__new__(OcBackend)
        mock_oc = MagicMock()
        mock_oc.call.return_value = "ok"
        b._oc = mock_oc
        b._research = s.research

        b.call("prompt", role="writer")
        mock_oc.call.assert_called_once_with("prompt", model="minimax-m2.7", timeout=300)

    def test_reviewer_role_uses_reviewer_model(self):
        s = _settings(oc_model_reviewer="deepseek-v4-pro")
        b = OcBackend.__new__(OcBackend)
        mock_oc = MagicMock()
        mock_oc.call.return_value = "ok"
        b._oc = mock_oc
        b._research = s.research

        b.call("prompt", role="reviewer")
        mock_oc.call.assert_called_once_with("prompt", model="deepseek-v4-pro", timeout=300)

    def test_unknown_role_falls_back_to_planner(self):
        s = _settings(oc_model_planner="glm-5.1")
        b = OcBackend.__new__(OcBackend)
        mock_oc = MagicMock()
        mock_oc.call.return_value = "ok"
        b._oc = mock_oc
        b._research = s.research

        b.call("prompt", role="somefuturerole")
        mock_oc.call.assert_called_once_with("prompt", model="glm-5.1", timeout=300)

    def test_system_prompt_prepended_to_user_prompt(self):
        s = _settings()
        b = OcBackend.__new__(OcBackend)
        mock_oc = MagicMock()
        mock_oc.call.return_value = "ok"
        b._oc = mock_oc
        b._research = s.research

        b.call("user content", system="you are helpful")
        call_args = mock_oc.call.call_args[0][0]
        assert "you are helpful" in call_args
        assert "user content" in call_args

    def test_timeout_forwarded(self):
        s = _settings()
        b = OcBackend.__new__(OcBackend)
        mock_oc = MagicMock()
        mock_oc.call.return_value = "ok"
        b._oc = mock_oc
        b._research = s.research

        b.call("prompt", timeout=600)
        mock_oc.call.assert_called_once_with("prompt", model=s.research.oc_model_planner, timeout=600)
