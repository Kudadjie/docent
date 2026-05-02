from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class PaperSettings(BaseModel):
    """First-party `paper` tool settings. Stored under `[paper]` in config.toml.

    Env-overridable as `DOCENT_PAPER__<FIELD>` (note the double underscore for
    nesting). `database_dir` accepts a path with `~`; expansion is the caller's
    job (`Path(...).expanduser()`).
    `mendeley_watch_subdir` is a path *relative* to `database_dir` (e.g.
    "Watch") - encodes the structural truth that the watch folder lives inside
    the database. Validated at use-time.
    """

    database_dir: Path | None = None
    mendeley_watch_subdir: str | None = None
    unpaywall_email: str | None = None
    mendeley_mcp_command: list[str] | None = None  # e.g. ["uvx", "mendeley-mcp"]; None -> default in mendeley_client.
    queue_collection: str = "Docent-Queue"  # Mendeley collection name that defines reading-queue membership (Step 11.6).


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

    paper: PaperSettings = Field(default_factory=PaperSettings)

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
