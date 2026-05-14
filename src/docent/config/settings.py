from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class ResearchSettings(BaseModel):
    """First-party `research` tool settings. Stored under `[research]` in config.toml.

    Env-overridable as `DOCENT_RESEARCH__<FIELD>` (double underscore for nesting).
    `output_dir` is where research output files are written.
    `feynman_command` defaults to `["feynman"]`; override if feynman is not on PATH.
    """

    output_dir: Path = Field(default_factory=lambda: Path("~/Documents/Docent/research"))
    feynman_command: list[str] | None = None
    feynman_budget_usd: float = 0.0  # 0.0 = no limit (default). Set to e.g. 2.00 to cap Feynman spend at $2 per session.
    feynman_model: str | None = None  # e.g. "anthropic/claude-sonnet-4-5" — passes --model to feynman
    feynman_timeout: float = 900.0  # seconds before killing stuck feynman runs
    oc_provider: str = "opencode-go"
    oc_model_planner: str = "glm-5.1"
    oc_model_writer: str = "minimax-m2.7"
    oc_model_verifier: str = "glm-5.1"
    oc_model_reviewer: str = "deepseek-v4-pro"
    oc_model_researcher: str = "glm-5.1"
    oc_budget_usd: float = 0.0
    tavily_api_key: str | None = None
    tavily_research_timeout: float = 600.0  # seconds to wait for Tavily Research API results
    semantic_scholar_api_key: str | None = None
    notebooklm_notebook_id: str | None = None  # NotebookLM notebook ID from the URL (e.g. abc123...)
    obsidian_vault: Path | None = None  # Absolute path to Obsidian vault root (or target subfolder)
    alphaxiv_api_key: str | None = None  # API key from alphaxiv.org (env: ALPHAXIV_API_KEY)


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
    research: ResearchSettings = Field(default_factory=ResearchSettings)

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
