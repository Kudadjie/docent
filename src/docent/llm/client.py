from __future__ import annotations

import os
from dataclasses import dataclass

from docent.config import Settings


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str


class LLMClient:
    """Thin wrapper around litellm. The single entry point for model calls.

    litellm is imported lazily inside `complete()` so meta-commands
    (`--version`, `list`, `info`) never pay the ~1s import cost.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _resolve_api_key(self, model: str) -> str | None:
        """Resolve the API key for *model*'s provider without mutating the
        process environment.

        Env vars set by the user always win over config-file values (preserves
        the original precedence). Returns None for providers Docent doesn't hold
        a top-level key for — litellm then falls back to its own env lookup,
        exactly as before.
        """
        provider = model.split("/", 1)[0].lower() if "/" in model else ""
        if provider == "anthropic" or model.startswith("claude"):
            return os.environ.get("ANTHROPIC_API_KEY") or self.settings.anthropic_api_key
        if provider == "openai" or model.startswith("gpt"):
            return os.environ.get("OPENAI_API_KEY") or self.settings.openai_api_key
        return None

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        import litellm

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resolved_model = model or self.settings.default_model
        kwargs: dict[str, object] = {}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        api_key = self._resolve_api_key(resolved_model)
        if api_key:
            kwargs["api_key"] = api_key

        response = litellm.completion(
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            num_retries=2,
            **kwargs,
        )

        text = response.choices[0].message.content or ""
        return LLMResponse(text=text, model=response.model)
