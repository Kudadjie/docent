# CONTEXT - resume hint for next session

**Current Task:** Docs single-source-of-truth + reference manager onboarding card shipped.

**Key Decisions:**
- `/api/docs/{slug}` route serves 5 user-facing markdown files; `docs/page.tsx` now fetches
  and renders via react-markdown + remark-gfm — edit a doc, reload the UI, done.
- New users (empty queue, localStorage flag not set) see a Mendeley/Zotero choice card
  instead of an empty table; existing users are silently marked chosen on load.
- All three docs files (reading-user-guide, reading-ui-spec, cli.md) de-Mendeley'd:
  sync-from-library, reference_id, SyncFromLibraryResult throughout.

**Next Steps:**
- PR `dev` → `main` (WSL green: 657 passed).
- Citation scavenger (#42) — anchor paper → Semantic Scholar/Crossref citation tree →
  OA filter → download + queue. First consumer for Tier-4 B fan-out primitive.
- Settings page: after user picks reference manager from setup card, deep-link them
  to the correct Settings section (Mendeley vs Zotero) to complete connection setup.
