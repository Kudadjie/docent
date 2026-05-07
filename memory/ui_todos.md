---
name: Reading UI — open todos
description: Tracked list of remaining work on the Reading page frontend (frontend/). Read when picking up UI work.
type: project
---

UI is live at http://localhost:3000. Dev server: `node frontend/node_modules/next/dist/bin/next dev` from repo root (or `npm run dev` inside `frontend/`).

## Must do (broken or missing)

- [x] **Export button** — client-side download from `/api/queue` data; JSON.stringify + Blob + `<a>` click; toast on success/fail.
- [x] **Edit row action** — `EditModal.tsx` with status/order/deadline/notes/tags fields; `edit` case in API route uses spawn (safe arg passing); wired through PaperTable + page.tsx.
- [x] **Scan/Sync feedback** — toast shown after each action (success + error) via `toastSuccess`/`toastError` helpers.
- [x] **Error handling** — API errors surfaced as error toast with cleaned CLI output.

## Should do (UX gaps)

- [x] **Dark mode persistence** — reads `localStorage('docent:dark')` on mount; saves on every toggle.
- [ ] **Real-time refresh** — if the CLI mutates the queue externally (e.g. `docent reading sync-from-mendeley` run in terminal), the UI doesn't know. Add a polling interval (e.g. 30s) or a manual "Refresh" button.
- [ ] **User footer** — hardcoded to "John" / "Graduate student". Read from a config endpoint or env var.
- [ ] **Modal a11y** — HowToAddModal: add Escape key close handler + focus trap (focus first focusable element on open, trap Tab, return focus on close).
- [x] **Delete confirm** — inline confirm state in PaperRow; first click shows "Delete? / ✕", second click fires delete. No `window.confirm`.

## Nice to have

- [ ] **Filter/search in URL** — filter and search state doesn't survive page refresh. Encode as `?filter=queued&q=storm` search params.
- [ ] **Per-filter empty state** — generic "No papers found" regardless of context. Contextualise: "No queued papers — sync Mendeley to pull new ones."
- [ ] **TypeScript build** — `npm run build` still fails on `.next/dev/types/routes.d.ts` (Next.js 16 generated-file bug). `tsconfig.json` already excludes `.next/dev/types` but Next.js may re-add it. Investigate when shipping production build.
- [x] **"Start reading" action** — Play icon for `queued` entries; CheckCircle for `reading` entries only. Wired to `handleStart` → `runAction('start', id)`.

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
