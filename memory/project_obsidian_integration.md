---
name: Obsidian integration design
description: Ideas and design thinking for integrating Docent with Obsidian vaults; v1.4+ work
type: project
---

Source: conversation 2026-05-11

## Core idea

Obsidian as a **third output destination** alongside "local" and "to-notebook" (NotebookLM).
Studio research outputs (`.md` files) are written directly into the Obsidian vault with enriched frontmatter and `[[wikilinks]]` so they slot into the user's knowledge graph automatically. No separate sync layer — Obsidian just reads markdown in the vault.

Config key needed: `obsidian_vault` (path to vault root or target subfolder). `docent doctor` should verify this path exists on startup when configured.

## Integration surface — by feature

### Studio / research outputs (`--output vault`)
- Add `--output vault` flag alongside `local` and `notebook`
- Write `.md` files with frontmatter: `tags`, `aliases`, `date`, `source_url`, `doi`, `backend`
- Emit `[[wikilinks]]` between related research outputs (e.g. lit review links to its sources)

### Reading queue → literature notes
- On `docent reading done <id>`, optionally generate a literature note in the vault
- Format compatible with Obsidian's **Citations plugin** and **Dataview** queries
- Fields: title, authors, DOI, abstract, user annotations, read date, tags
- If Zotero integration is live (v1.3), this gets cleaner — Zotero → BetterBibTeX → Citations; Docent adds structured annotations on top

### Dataview compatibility
- Structure frontmatter so standard Dataview queries work out of the box
  e.g. `TABLE title, date WHERE tags contains "docent/reading"`
- Document the expected schema so users can build their own queries

### Daily notes integration (opt-in)
- Append a daily reading/research summary to the Obsidian daily note
- Format: bullets of papers marked done, research tasks completed, outputs written
- Config key: `obsidian_daily_notes: true`

### Templater support
- Respect user-defined Obsidian Templater templates for note creation
- Docent reads a configured template path and fills in variables rather than hard-coding structure
- Makes output format user-customisable without code changes

### Canvas export (stretch / parked)
- Export a deep research source graph as an Obsidian `.canvas` file
- Park until core integration is stable

### Bidirectional sync (stretch / parked)
- Frontmatter edits made in Obsidian feed back into the reading queue
- Requires file watcher or explicit `docent reading sync-vault` command
- Park until core integration is stable

## Key tradeoff
Vault path coupling — if the user moves their vault things break silently. Mitigate with `docent doctor` path check.

## Roadmap placement
- v1.4: `--output vault` for Studio + literature note on `reading done`
- v1.4+: Dataview schema docs, daily notes opt-in, Templater support
- Stretch: Canvas export, bidirectional sync
