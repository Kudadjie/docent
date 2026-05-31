"""Config action mixins: config-show, config-set."""

from __future__ import annotations

from docent.bundled_plugins.studio._studio_shared import _KNOWN_RESEARCH_KEYS
from docent.bundled_plugins.studio.models import (
    ConfigSetInputs,
    ConfigSetResult,
    ConfigShowInputs,
    ConfigShowResult,
    TavilyUsageInputs,
    TavilyUsageResult,
)
from docent.config import write_setting
from docent.core import Context, action


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
        description="Show live Tavily API credit usage for the configured key.",
        input_schema=TavilyUsageInputs,
        name="tavily-usage",
    )
    def tavily_usage(self, inputs: TavilyUsageInputs, context: Context) -> TavilyUsageResult:
        from .tavily_usage import fetch_tavily_usage

        key = context.settings.research.tavily_api_key
        if not key:
            return TavilyUsageResult(
                ok=False,
                message="No Tavily API key configured. Run `docent studio config-set --key tavily_api_key --value <key>`.",
            )
        try:
            data = fetch_tavily_usage(key)
        except Exception as e:
            return TavilyUsageResult(ok=False, message=f"Tavily usage check failed: {e}")

        key_data = data.get("key", {})
        account = data.get("account", {})
        plan_usage = account.get("plan_usage")
        plan_limit = account.get("plan_limit")
        plan = account.get("current_plan")
        key_search_usage = key_data.get("search_usage")

        pct: float | None = None
        if plan_usage is not None and plan_limit:
            pct = round(plan_usage / plan_limit * 100, 1)

        parts = []
        if plan_usage is not None and plan_limit is not None:
            parts.append(f"{plan_usage}/{plan_limit} credits used")
        if pct is not None:
            parts.append(f"{pct:.0f}%")
        if plan:
            parts.append(f"plan: {plan}")

        return TavilyUsageResult(
            ok=True,
            plan=plan,
            plan_usage=plan_usage,
            plan_limit=plan_limit,
            key_search_usage=key_search_usage,
            pct_used=pct,
            message=", ".join(parts) if parts else "Usage fetched.",
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
