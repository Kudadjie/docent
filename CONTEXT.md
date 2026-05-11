# CONTEXT - resume hint for next session

**Current Task:** v1.2.0 blockers fixed (Hermes session 2026-05-11). Ready to tag release.

**Key Changes (2026-05-11):**
- Bug 1 fixed: duplicate registration (relative import + registry warns/skips)
- Bug 2 fixed: DDG replaced with Tavily across 6 files + docs
- Tavily API key onboarding: interactive prompt on first use, saves to `~/.docent/config.toml`, skips in non-TTY
- WSL-native venv: `.venv-wsl` ready (Windows `.venv` deleted)
- 263/263 tests green

**Next Steps:**
1. Add Tavily API key to `~/.docent/config.toml` under `[research]` as `tavily_api_key = "tvly-..."`
2. Re-run real-life research tests 3–17 to verify
3. Tag v1.2.0 release
