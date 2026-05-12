---
name: Reading UI v1.0 — completed todos
description: Archived completed todo list for the Reading page frontend; all items shipped 2026-05-06. Reference for what the v1.0 UI surface includes.
type: project
---

All items complete as of 2026-05-06. Archived from `memory/ui_todos.md`.

UI is live at http://localhost:3000. Dev server: `node frontend/node_modules/next/dist/bin/next dev` from repo root (or `npm run dev` inside `frontend/`).

## Must do (broken or missing)

- [x] **Export button** — client-side download from `/api/queue` data; JSON.stringify + Blob + `<a>` click; toast on success/fail.
- [x] **Edit row action** — `EditModal.tsx` with status/order/deadline/notes/tags fields; `edit` case in API route uses spawn (safe arg passing); wired through PaperTable + page.tsx.
- [x] **Scan/Sync feedback** — toast shown after each action (success + error) via `toastSuccess`/`toastError` helpers.
- [x] **Error handling** — API errors surfaced as error toast with cleaned CLI output.

## Should do (UX gaps)

- [x] **Dark mode persistence** — reads `localStorage('docent:dark')` on mount; saves on every toggle.
- [x] **Real-time refresh** — 30s polling interval calls `refresh()` (disk read, no CLI). Auto-sync on load if `last_updated` > 30 min stale; success toast shown, errors swallowed.
- [x] **User footer** — onboarding modal (`WelcomeModal.tsx`) on first load; saves to `~/.docent/user.json` via `/api/user`; Sidebar reads and displays live.
- [x] **Modal a11y** — HowToAddModal: Escape closes, focus trap on Tab/Shift+Tab, first focusable element auto-focused on open.
- [x] **Delete confirm** — inline confirm state in PaperRow; first click shows "Delete? / ✕", second click fires delete. No `window.confirm`.

## Nice to have

- [x] **Filter/search in URL** — reads `?filter=&q=` on mount via `URLSearchParams`; writes back on change via `history.replaceState`. Survives page refresh.
- [x] **Per-filter empty state** — contextual messages per filter; "No papers match your search." when search is active.
- [x] **TypeScript build** — `npm run build` passes clean (was already resolved).
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
