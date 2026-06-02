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
    feynman_model: str | None = (
        None  # e.g. "anthropic/claude-sonnet-4-5" — passes --model to feynman
    )
    feynman_timeout: float = 1800.0  # seconds before killing stuck feynman runs (/review with code repo access needs ~20-25 min)
    studio_backend: str = "opencode"  # active Docent-tier backend
    oc_provider: str = "opencode-go"
    oc_model_planner: str = "glm-5.1"
    oc_model_writer: str = "minimax-m2.7"
    oc_model_verifier: str = "glm-5.1"
    oc_model_reviewer: str = "deepseek-v4-pro"
    oc_model_researcher: str = "glm-5.1"

    # LiteLLM provider API keys
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    mistral_api_key: str | None = None
    cerebras_api_key: str | None = None

    # LiteLLM provider models (defaults shown)
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_model: str = "gemini-2.0-flash"
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    mistral_model: str = "mistral-small-latest"
    cerebras_model: str = "llama-3.3-70b"
    ollama_model: str = "llama3"
    lm_studio_model: str = "local-model"
    local_model: str = "local-model"

    # Local provider base URLs
    ollama_base_url: str = "http://localhost:11434"
    lm_studio_base_url: str = "http://localhost:1234/v1"
    local_base_url: str | None = None
    local_api_key: str | None = None

    tavily_api_key: str | None = None
    tavily_research_timeout: float = 600.0  # seconds to wait for Tavily Research API results
    semantic_scholar_api_key: str | None = None
    notebooklm_notebook_id: str | None = (
        None  # NotebookLM notebook ID from the URL (e.g. abc123...)
    )
    notebooklm_source_limit: int = 50  # 50 = free tier; set to 100 for NotebookLM Plus
    notebooklm_ask_timeout: float = 300.0  # seconds to wait for a NotebookLM chat answer (quality gate / perspectives); heavy notebooks need >180s
    notebooklm_lock_timeout: float = 1800.0  # seconds a queued to-notebook run waits for the shared NotebookLM session before aborting
    obsidian_vault: Path | None = None  # Absolute path to Obsidian vault root (or target subfolder)
    alphaxiv_api_key: str | None = None  # API key from alphaxiv.org (env: ALPHAXIV_API_KEY)
    max_parallel_studio_runs: int = 3  # client-enforced cap on concurrent Studio runs in one UI tab


class ReadingSettings(BaseModel):
    """First-party `reading` tool settings. Stored under `[reading]` in config.toml.

    Env-overridable as `DOCENT_READING__<FIELD>` (double underscore for nesting).
    `database_dir` accepts a path with `~`; expansion is the caller's job.
    `database_dir` IS the Mendeley watch folder — Mendeley auto-imports anything
    dropped here.
    """

    database_dir: Path | None = None
    mendeley_mcp_command: list[str] | None = (
        None  # e.g. ["uvx", "mendeley-mcp"]; None -> default in mendeley_client.
    )
    queue_collection: str = "Docent-Queue"  # Collection name that defines reading-queue membership.
    reference_manager: str = "mendeley"  # Active backend: "mendeley" | "zotero".

    # Zotero backend (used when reference_manager == "zotero"). API key + library
    # id come from zotero.org/settings/keys — no OAuth browser flow.
    zotero_api_key: str | None = None
    zotero_library_id: str | None = None  # numeric user id, or group id for a group library
    zotero_library_type: str = "user"  # "user" | "group"


class PluginBuilderSettings(BaseModel):
    """Plugin Builder settings. Stored under [plugin_builder] in config.toml.

    `model` is an OpenCode Go model ID — the same models Studio uses.
    The default `glm-5.1` requires the OpenCode server running on port 4096
    (start with: opencode serve --port 4096).
    Override with any OpenCode-Go model: deepseek-v4-pro, minimax-m2.7, etc.
    """

    model: str = "glm-5.1"


class ServeSettings(BaseModel):
    """HTTP server settings. Stored under [serve] in config.toml.

    `api_key` is auto-generated on first `docent ui` start and used as the
    Bearer token for the MCP HTTP endpoint at /mcp/sse.
    `host` controls the bind address — 127.0.0.1 (default) restricts to
    localhost; set to 0.0.0.0 to expose on all interfaces.
    """

    api_key: str | None = None
    host: str = "127.0.0.1"
    http_mcp_enabled: bool = True


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
    serve: ServeSettings = Field(default_factory=ServeSettings)
    plugin_builder: PluginBuilderSettings = Field(default_factory=PluginBuilderSettings)

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
