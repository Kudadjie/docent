---
name: Reading UI — open todos
description: Tracked list of remaining work on the Reading page frontend (frontend/). Read when picking up UI work.
type: project
---

UI is live at http://localhost:3000. Dev server: `node frontend/node_modules/next/dist/bin/next dev` from repo root (or `npm run dev` inside `frontend/`).

## Must do (broken or missing)

- [ ] **Export button** — stub. Wire `docent reading export --format json` via POST /api/actions, then trigger a file download with the response body.
- [ ] **Edit row action** — currently no-ops. Needs an edit modal pre-populated with status / order / deadline / notes / tags (all user-settable fields per the spec). Calls `docent reading edit --id <id> ...` on save.
- [ ] **Scan/Sync feedback** — busy text shows ("Scanning…") but no success/error toast. User can't tell if it worked. Add a simple status notification after the action resolves.
- [ ] **Error handling** — API errors are silently swallowed. If the CLI call fails, surface the error.message to the user.

## Should do (UX gaps)

- [ ] **Dark mode persistence** — resets to light on every page reload. Persist the preference to `localStorage` and read it on mount.
- [ ] **Real-time refresh** — if the CLI mutates the queue externally (e.g. `docent reading sync-from-mendeley` run in terminal), the UI doesn't know. Add a polling interval (e.g. 30s) or a manual "Refresh" button.
- [ ] **User footer** — hardcoded to "John" / "Graduate student". Read from a config endpoint or env var.
- [ ] **Modal a11y** — HowToAddModal: add Escape key close handler + focus trap (focus first focusable element on open, trap Tab, return focus on close).
- [ ] **Delete confirm** — currently `window.confirm()` which is blocked in some environments. Replace with an inline confirm state (e.g. a "Really delete?" tooltip-button).

## Nice to have

- [ ] **Filter/search in URL** — filter and search state doesn't survive page refresh. Encode as `?filter=queued&q=storm` search params.
- [ ] **Per-filter empty state** — generic "No papers found" regardless of context. Contextualise: "No queued papers — sync Mendeley to pull new ones."
- [ ] **TypeScript build** — `npm run build` still fails on `.next/dev/types/routes.d.ts` (Next.js 16 generated-file bug). `tsconfig.json` already excludes `.next/dev/types` but Next.js may re-add it. Investigate when shipping production build.
- [ ] **"Start reading" action** — row action to mark a queued paper as "reading" (`docent reading start --id <id>`). Currently only "Mark done" is shown. Add a play icon for queued entries.

## Done

- [x] App shell: sidebar + main pane
- [x] Status banner with real data from queue.json + state.json
- [x] Filter tabs (All / Reading / Queued / Done) with live counts
- [x] Search (matches title, authors, notes, category, id, tags)
- [x] Paper table with status badge, order indicator, deadline pill, type tag
- [x] Mark done → `docent reading done`
- [x] Delete → `docent reading remove`
- [x] Scan folder → `docent reading scan`
- [x] Sync Mendeley → `docent reading sync-from-mendeley`
- [x] How to add? modal (replaces Add Paper button)
- [x] Dark mode toggle (CSS variable swap)
- [x] Design tokens: Inter + Geist Mono, brand green #18E299
- [x] Animations: row fade-in, pulse-high, logo dot states
- [x] Database PDF count from config.toml + filesystem walk
- [x] Dashboard stub route
