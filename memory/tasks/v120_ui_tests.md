# v1.2.0 UI Test Checklist

Run these before tagging v1.2.0. Start with `docent ui` and open http://localhost:7432.

---

## Reading Page

- [/] Queue loads and displays paper entries
- [/] Filter tabs (All / Reading / Queued / Done) filter correctly and counts update
- [/] Search box filters by title, author, tags in real time
- [/] Scroll through the paper list (should NOT be clipped — list must scroll)
- [/] "How to add?" button opens the modal (purple button)
- [/] "Sync Mendeley" button shows spinner ≥ 1.5s, then shows success/error toast (green button) - Just says syncing... (thats fine - docent pill status shows)
- [/] "Refresh" button shows "Refreshing…" for at least 1.5 seconds before resolving
- [/] "Export Documents" opens a print dialog
- [/] "Next" highlights and scrolls to the top queued entry
- [/] "Stats" modal opens and shows queue breakdown
- [/] Row action: mark entry as Done → entry moves to Done filter
- [/] Row action: Edit modal opens, saves successfully
- [/] Row action: Detail modal opens with full paper info
- [/] Row action: Move up / Move down reorders correctly
- [/] Server error banner appears if server is unavailable
- [/] Filter + search state persists in URL (navigate away and back) — fixed: now also persists in sessionStorage so nav-link-back works
- [/] Filter dropdown (right-side) shows item counts and selects correctly

---

## Studio Page

- [/] Action list loads and shows Research + Utility groups with colored dots
- [/] Selecting an action changes the form fields on the right
- [/] Ctrl+K opens the quick-action palette; selecting navigates to that action
- [/] "Run AI-powered academic actions" subtitle visible under Studio heading
- [/] Empty state shows "Run a studio action" (not "Run a research action")
- [/] Output destination only shows "Local" and "Notebook" (no "Pipe →")
- [/] Backend selector dropdown lists available backends
- [/] Guide files: Browse button opens file picker; files appear in list
- [/] Run disabled when required field is empty (topic/artifact/query)
- [/] Ctrl+Enter triggers run when fields are valid
- [/] Running: phase strip appears and updates live as logs stream in
- [/] Running: activity log shows new entries in real time (not all at once at end)
- [/] Running: Stop run button shows "Stopped" status (amber dot in history)
- [/] Success: result panel shows output file path
- [/] Success (Local dest): "Send to NotebookLM" button appears
- [/] Success (Notebook dest): "Open in NotebookLM" link appears (no Send button)
- [/] Success (with notebook_id from server): shows notebook link correctly
- [/] "Preview document" expands and renders markdown (not raw text)
- [/] "Open output folder" button calls `/api/fs/open`
- [/] History drawer opens, shows past runs with status dots
- [/] History: clicking a run loads its state and logs
- [/] History: per-item delete (trash icon on hover) removes that run
- [/] History: "Clear all" wipes all runs
- [/] Outputs panel opens and lists research files; clicking a file shows markdown preview
- [/] Form state persists across tab navigation (sessionStorage)
- [/] History persists across page reload (localStorage)
- [/] Column resize: drag divider between left form and right output; width snaps between 260–600px; persists after reload
- [/] Save as preset: saves and appears in action list; can be loaded and deleted

---

## Ecosystem Page

- [/] Page loads with tool cards (Feynman, Tavily, Mendeley, NotebookLM, etc.)
- [/] Install instructions expand/copy correctly for each tool
- [/] "Inside Docent" table visible
- [/] Gradient bleed covers the full page (not just the top)

---

## Docs Page

- [/] TOC sidebar lists all sections including "Ecosystem" and "Plugin Guide"
- [/] Clicking a TOC item scrolls to that section
- [/] Overview section shows quick-start table and updated description
- [/] Studio section: output destinations only list Local and Notebook
- [/] Ecosystem section is present and readable
- [/] Plugin Guide section is present with code examples
- [/] CLI Reference includes `docent ui` and `docent doctor`
- [/] Docs content fills the full width (no empty right column)
- [/] Gradient bleed covers the full page

---

## Settings Page

- [/] Page shows 2-column layout (Reading config + API keys side by side)
- [/] Gradient bleeds into the settings page background
- [/] Reading config: database_dir and queue_collection can be edited and saved
- [/] API keys: each key shows "set" badge if configured; Replace/Set key works
- [/] System health: runs automatically on load; shows OK/WARN/FAIL for each check
- [/] System health: Refresh button reruns checks
- [/] OpenCode server: status dot shows running/stopped; Start/Stop button works
- [/] Danger zone: "Clear queue" shows confirm dialog before clearing
- [/] Toast appears on save/error

---

## Notification Inbox (Bell icon — all pages)

- [/] Bell badge shows unread count
- [] Opening bell dropdown marks all as read
- [/] No duplicate notifications for same title+body (dedup check)
- [/] Clicking a notification with a route hint navigates to the relevant page
- [/] Dismiss (×) on individual notification removes it
- [/] "Clear all" empties the inbox
- [/] Version update notification appears if not up-to-date (test with older version)

---

## Sidebar (all pages)

- [/] Logo visible and correctly sized in top bar
- [/] Sidebar top bar and StatusBanner form one continuous horizontal strip (48px each, same border-bottom)
- [/] Active nav item highlights in green
- [/] Dashboard item is always first (pinned)
- [/] Drag-and-drop reorders Reading / Studio tabs; order persists after page reload
- [/] Studio nav shows running pill (amber) during an active run
- [/] Reading nav shows queue count badge when active
- [/] User footer shows name and role; clicking opens Edit profile modal
- [/] Utility nav (Ecosystem, Docs, Settings) visible at bottom

---

## User Footer / Welcome Modal

- [/] Clicking user footer opens profile modal
- [/] Name, program, and level save correctly
- [/] Database directory field saves correctly
- [/] "Set up your profile" prompt shows when no profile set

---

## Cross-cutting

- [/] No console errors on any page
- [/] No 404s for API calls during normal use
- [/] Dark/light mode toggle works and persists across page navigations (toggle in StatusBanner)
- [/] All pages load without white flash
