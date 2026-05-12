# Brief: Update README.md

Update `README.md` in the repo root. Make ONLY these specific changes — do not rewrite or restructure anything else.

## Change 1 — Add `docent ui` to "What works today"

After the "Plugin system" bullet, add:
- **`docent ui`** — starts a local web dashboard at `http://localhost:7432`. Browse and manage your reading queue, sync with Mendeley, edit settings, and check for updates — all from the browser. The UI is bundled inside the package; no separate install needed.

## Change 2 — Fix "Coming Soon" section

Remove the entire "Web dashboard" bullet (it shipped as `docent ui`). Keep the other bullets (`docent research` and Omnibox) unchanged.

## Change 3 — Fix project layout in Development section

Replace:
```
frontend/                # Next.js UI (dev only — bundled release TBD)
```
With:
```
src/docent/ui_server.py  # FastAPI backend for the web UI
frontend/                # Next.js source (built by scripts/build_ui.py)
```

## Change 4 — Fix "Updating the version" section

Replace the entire "Updating the version" subsection with:

```
### Updating the version

Version is driven by git tags via `hatch-vcs` — no files to edit.

```bash
git tag v1.2.0
git push --tags
```

GitHub Actions builds the wheel, publishes to PyPI, and creates a GitHub release automatically.
```

## Change 5 — Add `docent update` to Install section

After the "Updates:" block that shows `uv tool upgrade docent-cli`, add:

Or from the CLI:
```bash
docent update
```

## Rules
- Preserve all formatting, badge links, and section structure exactly
- Only touch the five locations described above
- Do not add comments or change wording elsewhere
