"""Platform-agnostic backend protocol for the Docent studio pipeline."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from docent.config.settings import Settings

from docent.errors import AuthError, ServiceUnavailableError

# Maps provider name → litellm config
_PROVIDER_SPECS: dict[str, dict] = {
    "groq": {
        "prefix": "groq/",
        "model_attr": "groq_model",
        "key_attr": "groq_api_key",
        "key_env": "GROQ_API_KEY",
        # llama-3.1-70b-versatile was decommissioned May 2025
    },
    "gemini": {
        "prefix": "gemini/",
        "model_attr": "gemini_model",
        "key_attr": "gemini_api_key",
        "key_env": "GEMINI_API_KEY",
    },
    "openrouter": {
        "prefix": "openrouter/",
        "model_attr": "openrouter_model",
        "key_attr": "openrouter_api_key",
        "key_env": "OPENROUTER_API_KEY",
    },
    "mistral": {
        "prefix": "mistral/",
        "model_attr": "mistral_model",
        "key_attr": "mistral_api_key",
        "key_env": "MISTRAL_API_KEY",
    },
    "cerebras": {
        "prefix": "cerebras/",
        "model_attr": "cerebras_model",
        "key_attr": "cerebras_api_key",
        "key_env": "CEREBRAS_API_KEY",
    },
    "anthropic": {
        "prefix": "anthropic/",
        "model_attr": None,
        "key_attr": None,
        "key_env": "ANTHROPIC_API_KEY",
        "top_key": "anthropic_api_key",
        "top_model": "claude-sonnet-4-6",
    },
    "openai": {
        "prefix": "openai/",
        "model_attr": None,
        "key_attr": None,
        "key_env": "OPENAI_API_KEY",
        "top_key": "openai_api_key",
        "top_model": "gpt-4o",
    },
    "ollama": {
        "prefix": "ollama/",
        "model_attr": "ollama_model",
        "key_attr": None,
        "key_env": None,
        "url_attr": "ollama_base_url",
    },
    "lm_studio": {
        "prefix": "openai/",
        "model_attr": "lm_studio_model",
        "key_attr": None,
        "key_env": None,
        "key_override": "lm-studio",
        "url_attr": "lm_studio_base_url",
    },
    "local": {
        "prefix": "openai/",
        "model_attr": "local_model",
        "key_attr": "local_api_key",
        "key_env": None,
        "url_attr": "local_base_url",
    },
}

# All valid backend names for the Docent tier
DOCENT_BACKEND_NAMES: frozenset[str] = frozenset({"docent", "opencode"} | set(_PROVIDER_SPECS))


@runtime_checkable
class StudioBackend(Protocol):
    def call(
        self,
        prompt: str,
        *,
        system: str | None = None,
        role: str = "default",
        timeout: int = 300,
    ) -> str: ...

    def is_available(self) -> bool: ...


class OcBackend:
    """Wraps OcClient — maps role hints to configured OpenCode models."""

    _ROLE_ATTRS = {
        "planner": "oc_model_planner",
        "writer": "oc_model_writer",
        "verifier": "oc_model_verifier",
        "reviewer": "oc_model_reviewer",
        "researcher": "oc_model_researcher",
    }

    def __init__(self, settings: "Settings") -> None:
        from .oc_client import OcClient
        self._oc = OcClient(
            provider=settings.research.oc_provider,
        )
        self._research = settings.research

    def call(
        self,
        prompt: str,
        *,
        system: str | None = None,
        role: str = "default",
        timeout: int = 300,
    ) -> str:
        attr = self._ROLE_ATTRS.get(role, "oc_model_planner")
        model = getattr(self._research, attr)
        if system:
            prompt = f"{system}\n\n{prompt}"
        return self._oc.call(prompt, model=model, timeout=timeout)

    def is_available(self) -> bool:
        return self._oc.is_available()


class LiteLLMBackend:
    """Calls any litellm-supported provider with one model for all roles."""

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    def call(
        self,
        prompt: str,
        *,
        system: str | None = None,
        role: str = "default",
        timeout: int = 300,
    ) -> str:
        import litellm
        litellm.suppress_debug_info = True
        litellm.set_verbose = False

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"num_retries": 2}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url

        try:
            response = litellm.completion(
                model=self._model,
                messages=messages,
                timeout=timeout,
                **kwargs,
            )
            return response.choices[0].message.content or ""
        except litellm.AuthenticationError as e:
            raise AuthError(f"Authentication failed for {self._model}: {e}") from e
        except litellm.RateLimitError as e:
            from docent.errors import UsageLimitError
            raise UsageLimitError(f"Rate limited by {self._model}: {e}") from e
        except litellm.ServiceUnavailableError as e:
            raise ServiceUnavailableError(f"Provider unavailable for {self._model}: {e}") from e

    def is_available(self) -> bool:
        try:
            self.call(".", timeout=15)
            return True
        except Exception:
            return False


def get_backend(settings: "Settings", *, override: str | None = None) -> StudioBackend:
    """Return the correct StudioBackend.

    override: a provider name ("groq", "gemini", ...) or "docent"/"opencode".
    "docent" and None both fall through to settings.research.studio_backend.
    """
    name = override if override and override != "docent" else settings.research.studio_backend

    if name in ("opencode", None, ""):
        return OcBackend(settings)

    if name not in _PROVIDER_SPECS:
        raise ValueError(
            f"Unknown studio backend {name!r}. "
            f"Valid: {', '.join(sorted(DOCENT_BACKEND_NAMES))}"
        )

    spec = _PROVIDER_SPECS[name]
    rs = settings.research

    # Resolve API key
    api_key: str | None = spec.get("key_override")
    if api_key is None:
        key_attr: str | None = spec.get("key_attr")
        key_env: str | None = spec.get("key_env")
        top_key: str | None = spec.get("top_key")

        if key_attr and hasattr(rs, key_attr):
            api_key = getattr(rs, key_attr) or None
        elif top_key:
            api_key = getattr(settings, top_key, None) or None
        if api_key is None and key_env:
            api_key = os.environ.get(key_env)
        if api_key is None and key_env:
            raise AuthError(
                f"No API key found for backend {name!r}. "
                f"Set {key_env} or run:\n"
                f"  docent studio config-set --key {name}_api_key --value YOUR_KEY"
            )

    # Resolve model
    model_attr: str | None = spec.get("model_attr")
    raw_model: str = getattr(rs, model_attr, "") if model_attr else spec.get("top_model", "")
    prefix: str = spec["prefix"]
    model = raw_model if raw_model.startswith(prefix) else f"{prefix}{raw_model}"

    # Resolve base_url
    url_attr: str | None = spec.get("url_attr")
    base_url: str | None = getattr(rs, url_attr, None) if url_attr else None

    return LiteLLMBackend(model, api_key=api_key, base_url=base_url or None)
