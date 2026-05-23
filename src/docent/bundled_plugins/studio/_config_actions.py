"""Config action mixins: config-show, config-set."""
from __future__ import annotations


from docent.core import Context, action

from docent.config import write_setting
from docent.bundled_plugins.studio._studio_shared import _KNOWN_RESEARCH_KEYS
from docent.bundled_plugins.studio.models import (
    ConfigSetInputs, ConfigSetResult, ConfigShowInputs, ConfigShowResult,
)


class ConfigMixin:
    """Mixin providing config actions for StudioTool."""

    @action(
        description="Show research settings.",
        input_schema=ConfigShowInputs,
        name="config-show",
    )
    def config_show(self, inputs: ConfigShowInputs, context: Context) -> ConfigShowResult:
        from docent.utils.paths import config_file
        rs = context.settings.research
        return ConfigShowResult(
            config_path=str(config_file()),
            output_dir=str(rs.output_dir),
            feynman_command=rs.feynman_command or ["feynman"],
            oc_provider=rs.oc_provider,
            oc_model_planner=rs.oc_model_planner,
            oc_model_writer=rs.oc_model_writer,
            oc_model_verifier=rs.oc_model_verifier,
            oc_model_reviewer=rs.oc_model_reviewer,
            oc_model_researcher=rs.oc_model_researcher,
            tavily_api_key=rs.tavily_api_key,
            tavily_research_timeout=rs.tavily_research_timeout,
            semantic_scholar_api_key=rs.semantic_scholar_api_key,
            feynman_model=rs.feynman_model,
            feynman_timeout=rs.feynman_timeout,
            notebooklm_notebook_id=rs.notebooklm_notebook_id,
            obsidian_vault=str(rs.obsidian_vault) if rs.obsidian_vault else None,
            alphaxiv_api_key=rs.alphaxiv_api_key,
        )

    @action(
        description="Set a research setting (output_dir).",
        input_schema=ConfigSetInputs,
        name="config-set",
    )
    def config_set(self, inputs: ConfigSetInputs, context: Context) -> ConfigSetResult:
        from docent.utils.paths import config_file
        if inputs.key not in _KNOWN_RESEARCH_KEYS:
            return ConfigSetResult(
                ok=False,
                key=inputs.key,
                value=inputs.value,
                config_path=str(config_file()),
                message=f"Unknown key {inputs.key!r}. Known: {sorted(_KNOWN_RESEARCH_KEYS)}.",
            )
        path = write_setting(f"research.{inputs.key}", inputs.value)
        return ConfigSetResult(
            ok=True,
            key=inputs.key,
            value=inputs.value,
            config_path=str(path),
            message=f"Set research.{inputs.key} = {inputs.value!r} in {path}.",
        )

