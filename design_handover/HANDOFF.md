# Handoff: Docent — Reading (Papers) Page

## Overview

This handoff covers the **Reading** screen of Docent — a personal AI assistant for graduate students. Reading is the user's local paper queue: a single-table view that shows every paper they have uploaded or imported, grouped by reading status (All / Reading / Queued / Done), with priority, tags, and quick actions to mark done, edit, or delete.

The page lives in a 2-pane app shell:
- **Sidebar (left, fixed):** brand logo + 2 nav tabs (Dashboard, Reading) + user footer
- **Main pane (right, flexible):** status banner → page header → action bar → filter tabs → paper table

The Dashboard tab in the sidebar is **a placeholder** — its design will follow once the other tools (Feynman, Database, etc.) settle. Keep the route wired but the page itself can be a stub.

---

## About the Design Files

The files in this bundle are **design references created in HTML/JSX** — interactive prototypes showing intended look and behavior. They are **not** production code to copy verbatim. Your task is to **recreate these designs in the target codebase's existing environment** (React/Next.js with TypeScript, given the `.tsx` requirement) using its established patterns, component library, and conventions.

If the codebase already has primitives (`<Button>`, `<Badge>`, `<Input>`, table primitives, etc.), use them and adapt the styling to match the spec below. Do not paste the inline-style JSX from the prototype into production — convert to your styling system (Tailwind, CSS modules, styled-components, vanilla-extract, etc.).

---

## Fidelity

**High-fidelity (hifi).** Colors, typography, spacing, radii, and interactions are all final. Recreate pixel-perfectly.

The only intentional departure: the prototype uses inline React styles + a runtime "Tweaks" panel for design exploration (dark mode toggle, accent color picker, compact rows, etc.). Do **not** ship the Tweaks panel — it is a designer tool, not a user feature. Dark mode **should** be supported but driven by the app's existing theme system (e.g. `prefers-color-scheme`, a theme context, a user setting), not the in-design panel.

---

## Files in this bundle

```
design_handoff_reading/
├── HANDOFF.md                              ← this file
├── screenshots/                            ← static reference renders
│   ├── 01-reading-light.png                ← page in light mode
│   ├── 02-reading-dark.png                 ← page in dark mode
│   └── 03-add-paper-modal.png              ← Add Paper modal open
├── designs/
│   ├── Reading.html                        ← the Reading page prototype (PRIMARY)
│   └── tweaks-panel.jsx                    ← designer-only tweaks UI (do NOT ship)
├── design_system/
│   ├── DESIGN_SYSTEM.md                    ← full Docent design system spec
│   ├── colors_and_type.css                 ← CSS custom properties (tokens)
│   └── components/
│       ├── Sidebar.jsx                     ← reference sidebar (older 4-tab version)
│       ├── ChatThread.jsx                  ← reference chat component
│       ├── DocumentPanel.jsx               ← reference doc panel
│       └── app-index.html                  ← reference app shell
└── assets/
    ├── logo.svg                            ← dark mark/wordmark, for light backgrounds
    ├── logo-light.svg                      ← white mark/wordmark, for dark backgrounds
    └── favicon.svg
```

**Logo usage:** the green accent square (`#18E299`) is preserved across both versions so brand recognition stays consistent — only the mark container and wordmark color flip. Pick `logo.svg` on light surfaces and `logo-light.svg` on dark surfaces; do not invert with CSS filters.

**Open `designs/Reading.html` in a browser** to see the working prototype. Toggle the Tweaks panel (top-right toolbar in the host environment) to explore variants — these are exploratory only.

---

## Screens / Views

### 1. Reading page (`designs/Reading.html`)

**Purpose:** Manage the user's local reading queue. List, filter, search, add, mark done, edit, delete papers.

**Layout — top level:**
- Full-viewport flex row, no scroll on the body itself.
- **Sidebar:** fixed width 220px (range 160–280px is acceptable; 220 is the design default). Full height. `border-right: 1px solid rgba(0,0,0,0.06)`.
- **Main:** `flex: 1`, vertical column, `min-width: 0`, `overflow: hidden`. Scrolling lives inside the table area only.

#### 1a. Sidebar

Vertical column, `background: #ffffff` (light) / `#0d0d0d` (dark).

Three stacked sections separated by 1px borders:

1. **Logo header** — height **56px**, padding `0 18px`.
   - Pill-shaped logo: 28px tall, `border: 1.5px solid #0d0d0d` (light) / `rgba(255,255,255,0.22)` (dark), `border-radius: 9999px`, padding `0 11px`, gap 7px.
   - Inside: 7px status dot (default `#18E299`) + the wordmark `docent` (Inter 600, 13.5px, letter-spacing -0.2px).
   - Status dot has 4 states (`idle` / `working` / `error` / `done`) — see the Logo Dot section in the design system. Drive from real app state (`idle` when at rest, `working` while syncing, etc.).

2. **Nav** — `flex: 1`, padding `10px 8px`, `gap: 2px`, vertical column.
   - Two items, in this order:
     1. **Dashboard** (id: `dashboard`) — grid icon (4-cell layout SVG)
     2. **Reading** (id: `reading`) — open-book icon
   - Each nav button:
     - Width 100%, padding `7px 10px`, border-radius 8px, no border, text-align left.
     - Inactive: color `#666666` (light) / `#a0a0a0` (dark), font-weight 400, background transparent.
     - Active: color `#0fa76e` (brand-deep), font-weight 500, background `rgba(24,226,153,0.13)` (i.e. `${accent}22` where accent is `#18E299`).
     - Icon (16×16, stroke 1.5) sits to the left with 9px gap. Icon color matches text.
     - Active item shows a count pill on the right: `margin-left: auto`, mono font, font-size 9px, padding `1px 6px`, radius 9999px, background `${accent}33`, color `#0fa76e`, uppercase, letter-spacing 0.3px. The number is the count of papers (use `papers.length`).

3. **User footer** — padding `12px 18px`, `border-top: 1px solid border-subtle`, flex row, gap 8px.
   - 28px circular avatar: background `${accent}22`, color `#0fa76e`, Inter 600, 12px, centered initial.
   - Name (Inter 500, 12px, primary fg) over email (Inter 400, 11px, muted fg).

#### 1b. Status banner

Height **40px**, full-width, `background: #fafafa` (light) / `#111` (dark), `border-bottom: 1px solid border-subtle`. Padding `0 24px`. Flex row, gap 24px, align center.

Three stat pills (left), one synced indicator (right), with a dark-mode toggle in between:

- **Stats** — `QUEUE 12 · DATABASE 45 · MENDELEY 40`. Each is a flex pair:
  - Label: Geist Mono 500, 10px, color muted (`#888` / `#606060`), letter-spacing 0.7px, uppercase.
  - Value: Geist Mono 600, 11px, color primary fg, letter-spacing 0.4px.
  - 7px gap between label and value.
- `flex: 1` spacer pushes the rest right.
- **Dark-mode toggle** (only if your app exposes it here; otherwise omit and put it in user settings): pill button, padding `3px 10px`, `border: 1px solid border-medium`, border-radius 9999, transparent background. Sun/moon icon (12px, stroke 2) + label `Light` / `Dark` (Geist Mono 10px, uppercase, letter-spacing 0.5px, color tertiary fg). Gap 5px.
- **Synced indicator:** 6px brand-green dot + `SYNCED 2M AGO` (Geist Mono 10px, uppercase, color muted, letter-spacing 0.5px).

#### 1c. Page header

Padding `20px 24px 0`, `border-bottom: 1px solid border-subtle`.

- **Title row** (flex row, justify between, align flex-start, margin-bottom 16):
  - Left: book-open icon (16×16, stroke 1.5, color `#0fa76e`) + `<h1>Reading</h1>` (Inter 600, 18px, letter-spacing -0.3px, primary fg). 10px gap.
  - Below the heading (margin-top 4): subtitle `Local reading queue · {N} papers` (Inter 400, 13px, tertiary fg).
  - Right: **Add Paper** primary button — pill, padding `7px 18px`, background `#18E299`, color `#0d0d0d`, Inter 600, 13px, no border. Plus icon (15×15, stroke 2) + label, gap 6px.

- **Action bar** (flex row, justify between, no padding bottom):
  - Left cluster (gap 6): 3 ghost buttons in a row:
    - `Scan folder` (folder-open icon)
    - `Sync Mendeley` (refresh icon)
    - `Export` (upload icon)
    Ghost button spec: padding `5px 12px`, border-radius 9999, `border: 1px solid border-medium`, transparent background, secondary fg, Inter 500 13px, icon-left (14×14 stroke 1.5, muted fg), gap 6px. Hover: background `gray-100`.
  - Right cluster (gap 8): search input + Filter ghost button.
    - Search: width 180px, padding `5px 12px 5px 32px`, border-radius 9999, border `1px solid border-medium`, Inter 12px, primary fg, transparent/page bg, with a 14px search icon absolutely positioned at left 10px (color muted fg, `pointer-events: none`). Placeholder: `Search papers…`.

- **Filter tabs** (flex row, no gap, margin-top 12): `All`, `Reading`, `Queued`, `Done`.
  - Each tab is a button: padding `8px 14px`, no border, transparent background, Inter 13px, gap 6px, flex align center.
  - Inactive: color `#888` / `#606060`, font-weight 400, `border-bottom: 2px solid transparent`.
  - Active: color primary fg, font-weight 500, `border-bottom: 2px solid #18E299`.
  - Each tab has a count chip after the label: Geist Mono 10px, padding `1px 6px`, border-radius 9999. Active: background `gray-100`, color `gray-700`. Inactive: transparent background, color muted.

#### 1d. Paper table

Container: `flex: 1`, `overflow-y: auto`. The table itself is `width: 100%`, `border-collapse: collapse`.

**Header row** (`<thead>`, sticky `top: 0`, `z-index: 1`, `background: page bg`):
Columns: `Paper` (left, padding-left 20) · `Status` · `Priority` · `Added` · `''` (right-aligned actions).
Header cell: padding `9px 16px`, Geist Mono 500 10px, muted fg, letter-spacing 0.6px, uppercase, `border-bottom: 1px solid border-subtle`.

**Body rows** (`<tbody>`):
Each row has `border-bottom: 1px solid border-subtle`, `transition: background 0.1s`. Hover: background `#fafafa` (light) / `#1a1a1a` (dark). Action buttons fade in on row hover (`opacity 0 → 1`, transition 0.12s).

Per-cell content (top vertical-align):

- **Paper cell** (padding `14px 20px`, or `8px 20px` if compact):
  - Title: Inter 500, 14px, primary fg, line-height 1.4, `text-wrap: pretty`. Followed by a tiny external-link icon (12×12, stroke 1.5, muted fg, opacity 0.5, 6px gap).
  - Sub-line (margin-top 3): authors (Inter 12px, tertiary fg) · `·` separator (gray-200) · venue+year (Geist Mono 10px, muted fg, uppercase, letter-spacing 0.4px). 6px flex gap, wrap allowed.
  - Optional tag row (margin-top 6) when `showTags` is on: each tag is a pill — padding `1px 8px`, radius 9999, background `gray-100`, color muted fg, Geist Mono 10px, uppercase, letter-spacing 0.3px.

- **Status cell** (padding `14px 16px`, vertical-align middle, no-wrap): a `<StatusBadge>`.
  - Pill, padding `3px 10px`, radius 9999, Geist Mono 600 11px, uppercase, letter-spacing 0.5px.
  - 5px dot inside, 5px gap, then label.
  - Light mode:
    - Reading: bg `#FFF7ED`, text `#B45309`, dot `#F59E0B`
    - Queued: bg `#EFF6FF`, text `#1D4ED8`, dot `#3B82F6`
    - Done: bg `#d4fae8`, text `#0fa76e`, dot `#18E299`
  - Dark mode (12% alpha tints over black):
    - Reading: bg `rgba(245,158,11,0.12)`, text `#F5A623`, dot `#F59E0B`
    - Queued: bg `rgba(59,130,246,0.12)`, text `#60A5FA`, dot `#3B82F6`
    - Done: bg `rgba(24,226,153,0.12)`, text `#18E299`, dot `#18E299`

- **Priority cell**: a 7px dot (color from priority map below) + label (Inter 500, 13px, tertiary fg). 7px gap.
  - High: `#D45656`, with pulsing animation `pulse-high 2s ease infinite` (`box-shadow: 0 0 0 0 → 0 0 0 4px` at 0.4 → 0 alpha).
  - Medium: `#C37D0D`, no animation.
  - Low: `#18E299`, no animation.

- **Added cell**: Geist Mono 11px, muted fg, letter-spacing 0.3px. Format: `Apr 18, 2026` (`{ month: 'short', day: 'numeric', year: 'numeric' }`).

- **Actions cell** (text-align right): inline-flex of three 28×28 icon buttons (border-radius 6, no border, transparent background, hover: `gray-100`):
  - **Mark done** — check-circle icon, color `#0fa76e`. Sets `status: 'Done'`.
  - **Edit** — pencil icon, color muted fg. Opens edit modal (placeholder for now).
  - **Delete** — trash icon, color `#D45656`. Removes the paper.

**Empty state** (when filter+search yields 0 rows):
Centered column, height ~200px, color muted fg, gap 10. Book-open icon at 0.4 opacity, then `No papers found` (Inter 13).

**Row enter animation:** newly added rows get class `row-fade` for 600ms — `@keyframes fadeInUp { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }`, 0.18s ease.

#### 1e. Add Paper modal

Triggered by the primary button. Centered modal over a `rgba(0,0,0,0.2)` backdrop (click to dismiss).

Card: width 480, border-radius 16, `border: 1px solid border-subtle`, `box-shadow: rgba(0,0,0,0.12) 0px 8px 32px`, background card.

- **Header** (padding `20px 24px 16px`, border-bottom): title `Add Paper` (Inter 600 15) + subtitle `Add a paper to your reading queue` (Inter 13, tertiary fg, margin-top 2).
- **Body** (padding `20px 24px`, vertical column, gap 14):
  - Field: `Title` (text input)
  - Field: `Authors` (text input, placeholder `Last, F. · Last, F.`)
  - 2-col grid (gap 12): `Year` / `Venue`
  - 2-col grid (gap 12): `Status` (select: Queued / Reading / Done) / `Priority` (select: Low / Medium / High)
  - Field: `Tags` (text input, helper `(comma separated)`, placeholder `NLP, transformers`)
- Each label: Inter 500, 12px, tertiary fg, margin-bottom 5.
- Each input/select: width 100%, padding `8px 12px`, `border: 1px solid border-medium`, border-radius 8, Inter 13px, primary fg, page bg, no outline. Focus: brand border (you can drive this via your existing input primitive).
- **Footer** (padding `12px 24px 20px`, flex row, justify-end, gap 8): ghost `Cancel` button + primary `Add Paper` button (same spec as the page header's primary).
- Submit logic: trim title (required), set defaults for missing fields, generate `id: Date.now()`, set `addedDate` to today formatted as above, prepend to list.

---

## Interactions & Behavior

| Element | Behavior |
|---|---|
| Sidebar nav | Sets active route. Reading is implemented; Dashboard is a stub (TBD design). |
| Add Paper button | Opens modal. |
| Modal backdrop click / Cancel | Dismisses modal. |
| Modal Add Paper | Validates `title.trim()`. Prepends paper. Closes modal. New row plays `row-fade` for 600ms. |
| Filter tabs | Filter table by `status`. `All` shows everything. Counts update live. |
| Search input | Case-insensitive substring match against `title` AND `authors`. Combines with active filter (AND). |
| Row hover | Row gets background tint, action buttons fade in. |
| Row Mark Done | Sets `status: 'Done'`. (No undo for now.) |
| Row Edit | Stub for now — open the same modal pre-populated when implemented. |
| Row Delete | Removes paper. (Add a confirm step in production.) |
| Status banner Sync | Driven by app state; format `Synced {n}m ago`. |

**Animation notes:**
- Row hover transition: `background 0.1s`.
- Action button reveal: `opacity 0.12s`.
- Row enter: `fadeInUp 0.18s ease`.
- High priority dot: `pulse-high 2s ease infinite`.
- Logo dot working: `logo-dot-blink 1s step-end infinite`.
- Logo dot done: `logo-dot-done 0.5s ease-in-out 3` (then back to idle).

No springs, no scroll-triggered effects. Keep it restrained.

---

## State Management

Local component state for this page:

```ts
type Status = 'Reading' | 'Queued' | 'Done';
type Priority = 'High' | 'Medium' | 'Low';

interface Paper {
  id: number | string;
  title: string;
  authors: string;       // formatted: "Last, F. · Last, F."
  year: number;
  venue: string;
  status: Status;
  priority: Priority;
  tags: string[];
  addedDate: string;     // "Apr 18, 2026"
}

// Page state
const [papers, setPapers] = useState<Paper[]>([]);
const [filter, setFilter] = useState<'All' | Status>('All');
const [search, setSearch] = useState('');
const [showAddModal, setShowAddModal] = useState(false);
const [newIds, setNewIds] = useState<Set<Paper['id']>>(new Set());  // for fade-in animation
```

Data source: replace the prototype's `SAMPLE_PAPERS` constant with whatever the codebase uses (REST endpoint, GraphQL query, local DB, etc.). The shape is what matters.

Stats in the banner:
- `QUEUE` = `papers.filter(p => p.status !== 'Done').length`
- `DATABASE`, `MENDELEY` = come from external integrations; show real counts when available.

---

## Design Tokens

All tokens are defined in `design_system/colors_and_type.css` as CSS custom properties. Key ones used by this page:

### Color
| Token | Light | Dark |
|---|---|---|
| `--color-bg-page` | `#ffffff` | `#0d0d0d` |
| `--color-bg-subtle` | `#fafafa` | `#111111` |
| `--color-bg-card` | `#ffffff` | `#141414` |
| `--color-fg-primary` | `#0d0d0d` | `#ededed` |
| `--color-fg-secondary` | `#333333` | `#c0c0c0` |
| `--color-fg-tertiary` | `#666666` | `#a0a0a0` |
| `--color-fg-muted` | `#888888` | `#606060` |
| `--color-gray-100` | `#f5f5f5` | `#1e1e1e` |
| `--color-gray-200` | `#e5e5e5` | `#2a2a2a` |
| `--color-border-subtle` | `rgba(0,0,0,0.05)` | `rgba(255,255,255,0.06)` |
| `--color-border-medium` | `rgba(0,0,0,0.08)` | `rgba(255,255,255,0.10)` |
| `--color-brand` | `#18E299` | `#18E299` |
| `--color-brand-light` | `#d4fae8` | unchanged |
| `--color-brand-deep` | `#0fa76e` | `#0fa76e` |
| `--color-error` | `#D45656` | `#D45656` |
| `--color-warning` | `#C37D0D` | `#C37D0D` |

Status badge palette (light mode literals): see the Status cell section above.

### Typography
- `--font-sans: 'Inter', system-ui, sans-serif`
- `--font-mono: 'Geist Mono', ui-monospace, monospace`
- Weights: 400 / 500 / 600 only.
- Sizes used on this page: 18 (h1), 14 (row title), 13 (body / nav / buttons), 12 (sub-line / inputs), 11 (mono small / footer email), 10 (mono micro / column headers / count chips), 9 (active nav count pill).

### Spacing
8px grid. Page-specific spacings called out inline above.

### Radii
- `--radius-xs: 4px` — none here
- `--radius-sm: 8px` — nav buttons, input/select fields, modal field rounding
- `--radius-md: 16px` — modal card, composer (n/a here)
- `--radius-lg: 24px` — n/a
- `--radius-pill: 9999px` — buttons, badges, search input, status pills, count chips. The signature shape.

### Shadows
- Cards: `rgba(0,0,0,0.03) 0px 2px 4px`
- Modal: `rgba(0,0,0,0.12) 0px 8px 32px`
- Active sidebar item (subtle): `rgba(0,0,0,0.04) 0px 1px 3px`

---

## Iconography

All icons in this page are inline stroked SVGs at 1.5px stroke (2px for the Plus and Send glyphs). They map 1:1 to **Lucide** icons, which is the project's canonical icon library:

| Used as | Lucide name |
|---|---|
| Sidebar Dashboard | `LayoutDashboard` |
| Sidebar Reading / page header | `BookOpen` |
| Add Paper / modal CTA | `Plus` |
| Mark Done | `CheckCircle` |
| Edit | `Edit2` (or `Pencil`) |
| Delete | `Trash2` |
| Scan folder | `FolderOpen` |
| Sync Mendeley | `RefreshCw` |
| Export | `Upload` |
| Search input adornment | `Search` |
| Filter button | `Filter` |
| Row external-link affordance | `ExternalLink` |
| Status banner light mode | `Sun` |
| Status banner dark mode | `Moon` |

In a TSX codebase, install `lucide-react` and use `<BookOpen size={16} strokeWidth={1.5} />` rather than reproducing the SVG paths. Sizes: 14 in ghost buttons, 15 in row icon buttons + Plus, 16 in nav + page header, 12 in light/dark toggle + external-link.

---

## Accessibility

The prototype is **not** accessibility-complete. When productionizing:
- Wrap nav buttons in a real `<nav>` with proper `aria-current="page"` on the active item.
- Convert the table to a real `<table>` with `<th scope="col">` (the prototype already uses `<th>`).
- Add `aria-label` to every icon-only button (`title` is set in the prototype but use proper labels).
- Filter tabs should be a `role="tablist"` with `role="tab"` children, or use real radio inputs.
- The modal needs focus trap, `aria-modal="true"`, `role="dialog"`, focus return on close, Esc to close.
- Status badges need a non-color signal (the dot + text already works) and sufficient contrast — verify the light-mode Reading badge (#B45309 on #FFF7ED) meets 4.5:1.
- High-priority pulsing dot: respect `prefers-reduced-motion: reduce` and disable the animation.

---

## Dark mode

The prototype's `makeTheme(dark)` factory shows the full token mapping. In a real app:
- Drive dark mode from your existing theme system (CSS variables flipped via `[data-theme="dark"]`, Tailwind `dark:` classes, or a context).
- Status badge colors **do** change per mode (see the Status cell section). Don't try to share the light palette in dark mode — text on `#FFF7ED` is unreadable on a dark canvas.
- Brand green (`#18E299`) is unchanged in dark mode by design.

---

## Out of scope / TBD

- **Dashboard page** — design pending. Wire the route, render a stub.
- **Paper detail / reader** — separate handoff. The row's external-link icon and "Edit" button should eventually open the detail view; for now they can no-op or open the existing chat/document panel from `design_system/components/`.
- **Bulk actions** — no multi-select in this design.
- **Sort** — only filter+search. No column sorting.
- **Pagination / virtualization** — not in the design. Add it if real data exceeds ~200 rows.

---

## Reference: original Docent app shell

`design_system/components/app-index.html` shows an **older** 4-tab version of the app (Ask Docent / My library / Lit review / Citations) with sidebar, chat thread, and document panel. **Use it for visual context** on the broader product, not as the source of truth for the Reading page sidebar — the new Reading sidebar is a 2-tab simplification.

---

## Implementation checklist for Claude Code

1. Read `design_system/DESIGN_SYSTEM.md` and `design_system/colors_and_type.css` first. Mirror the tokens into the codebase's token system if they aren't already there.
2. Open `designs/Reading.html` in a browser to feel the interaction.
3. Build the page in the codebase's idiomatic style (don't paste inline-style JSX).
4. Add `Reading` route + sidebar entry. Stub `Dashboard` route.
5. Wire papers from real data; mock the count stats if integrations aren't ready.
6. Implement Add modal, filter, search, mark-done, delete.
7. Skip Edit (stub) and the Tweaks panel entirely.
8. Verify dark mode + reduced motion + a11y as listed above.
