"""Constants shared across Studio action mixin modules."""
from __future__ import annotations

_PRICING_NOTE = (
    "API cost heads-up — typical cost per run by provider:\n"
    "  Free / very cheap : Groq, Mistral, Cerebras (~$0.01–$0.05)  |  Gemini (free tier available)\n"
    "  Moderate          : OpenRouter free models (~$0.00–$0.10)    |  OpenAI GPT-4o (~$0.20–$0.80)\n"
    "  Expensive         : Anthropic Claude — most expensive of all  (~$0.50–$3.00+ per run)\n"
    "Switch provider: docent studio config-set --key feynman_model --value groq/llama-3.3-70b-versatile"
)


_KNOWN_RESEARCH_KEYS = {
    "output_dir",
    "feynman_model",
    "feynman_timeout",
    "studio_backend",
    "oc_provider",
    "oc_model_planner",
    "oc_model_writer",
    "oc_model_verifier",
    "oc_model_reviewer",
    "oc_model_researcher",
    "groq_api_key",
    "groq_model",
    "gemini_api_key",
    "gemini_model",
    "openrouter_api_key",
    "openrouter_model",
    "mistral_api_key",
    "mistral_model",
    "cerebras_api_key",
    "cerebras_model",
    "ollama_model",
    "ollama_base_url",
    "lm_studio_model",
    "lm_studio_base_url",
    "local_model",
    "local_api_key",
    "local_base_url",
    "tavily_api_key",
    "tavily_research_timeout",
    "semantic_scholar_api_key",
    "notebooklm_notebook_id",
    "notebooklm_source_limit",
    "obsidian_vault",
    "alphaxiv_api_key",
}

