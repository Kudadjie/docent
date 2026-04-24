from __future__ import annotations

from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCENT_",
        extra="ignore",
    )

    default_model: str = "anthropic/claude-sonnet-4-6"
    verbose: bool = False
    no_color: bool = False

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    tools: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (env_settings, init_settings, file_secret_settings)
