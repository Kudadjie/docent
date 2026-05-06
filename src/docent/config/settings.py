from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class ReadingSettings(BaseModel):
    """First-party `reading` tool settings. Stored under `[reading]` in config.toml.

    Env-overridable as `DOCENT_READING__<FIELD>` (double underscore for nesting).
    `database_dir` accepts a path with `~`; expansion is the caller's job.
    `database_dir` IS the Mendeley watch folder — Mendeley auto-imports anything
    dropped here.
    """

    database_dir: Path | None = None
    mendeley_mcp_command: list[str] | None = None  # e.g. ["uvx", "mendeley-mcp"]; None -> default in mendeley_client.
    queue_collection: str = "Docent-Queue"  # Mendeley collection name that defines reading-queue membership.


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCENT_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    default_model: str = "anthropic/claude-sonnet-4-6"
    verbose: bool = False
    no_color: bool = False

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    reading: ReadingSettings = Field(default_factory=ReadingSettings)

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
