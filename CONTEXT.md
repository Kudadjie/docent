# CONTEXT — resume hint for next session

**Current Task:** UI polish + versioning session complete (commit ae0eda9 on dev). Next milestone is bundled release (docent-ui inside docent-cli).

**Key Decisions:**
- hatch-vcs replaces uv_build; release = `git tag vX.Y.Z && git push --tags`, no files to edit
- Sidebar split into PLUGIN_NAV (tools) and UTILITY_NAV (Docs, Settings) pinned at bottom
- Version check in UI is check-only — shows `docent update` command, no self-upgrade

**Next Steps:**
1. Bundled release: FastAPI server + `output: 'export'` + `docent ui` command (see memory/project_ui_bundling.md)
2. Phase 1.5-C research-to-notebook plugin (plan in memory/project_feynman_port.md)
