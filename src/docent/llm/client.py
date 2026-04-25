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
        # Propagate config-provided API keys into env if the env var is unset.
        # Env vars set by the user always win.
        if settings.anthropic_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

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

        kwargs: dict[str, object] = {}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = litellm.completion(
            model=model or self.settings.default_model,
            messages=messages,
            temperature=temperature,
            num_retries=2,
            **kwargs,
        )

        text = response.choices[0].message.content or ""
        return LLMResponse(text=text, model=response.model)
