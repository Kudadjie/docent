# Handoff: Docent — Studio Page

> **Delta handoff.** This document covers only what's new for the **Studio** page.
> The design system, tokens, type/color CSS, sidebar layout, status banner, and the
> reference primitives (`GhostBtn`, `IconBtn`, `StatusBadge`, etc.) defined in
> `HANDOFF.md` (Reading) all apply unchanged here. See `design_system/` for tokens
> and `designs/Reading.html` for the reference shell.

> **v2 — May 2026.** This page picked up a large second pass: run history, presets,
> a `⌘K` action palette, a phase-progress strip, live source chips, command preview,
> cost estimate, Compare diff view, "Add to Reading" handoff, drag-drop guide files,
> resumable-run sidebar pill, "Pipe → next action" chaining, polished dark mode,
> and a collapsible event-log summary. See **v2 additions** at the bottom of this doc.

## New / changed since last handoff

| Area | What's new |
|---|---|
| Sidebar nav | New 3rd item **Studio**, with the Lucide `FlaskConical` icon. Sits after Reading. Same active-state spec as Reading (brand-deep text, `BRAND+'22'` background). No count pill. |
| Layout pattern | First page in the app that uses a **nested two-column layout** inside the main pane (left form column 380px + flex right output column). |
| New components | `BackendSelector` (pill-button toggle group), `Segmented` control, `Toggle` (switch), `Stepper`, `CodeBlock` (with copy affordance), `LogLine` (phase-tagged streaming line), `PerspectiveSection` (collapsible card), `FreeTierGate` (inline blocking panel), `Chip` (mono key/value pill). |
| New patterns | Phase-tagged streaming log, inline blocking confirmation (vs. modal), action-list grouped vertical nav, result-type-dispatching output panel. |

No new color tokens, font sizes, radii, or shadows. Everything resolves through the
existing tokens in `design_system/colors_and_type.css`.

---

## Overview

**Studio** is the workbench for running AI research actions — deep research,
literature review, peer review, etc. — and seeing results stream in.

It lives at the **third** sidebar slot, after Reading. Within the main pane,
Studio splits into a fixed-width **input column** (left) and a flexible
**output column** (right). The output column always renders one of four states
(empty / running / success / failure) and dispatches the success view by action
type.

---

## Files

```
design_handoff/
├── HANDOFF.md              ← original Reading handoff (still authoritative)
├── HANDOFF_STUDIO.md       ← this file
├── designs/
│   ├── Reading.html        ← reference shell
│   ├── Studio.html         ← Studio prototype (PRIMARY)
│   └── tweaks-panel.jsx    ← do NOT ship
├── design_system/          ← unchanged; tokens still apply
├── assets/                 ← unchanged; same logo + status svgs
└── screenshots/
    ├── 04-studio-empty.png        ← right pane empty state
    ├── 05-studio-running.png      ← streaming log in flight
    ├── 06-studio-success-deep.png ← Deep research done
    ├── 07-studio-search.png       ← Search papers result
    ├── 08-studio-free-gate.png    ← Free-tier confirmation panel
    └── 09-studio-dark.png         ← dark mode
```

---

## Layout

Full-viewport flex row inside the same app shell. Sidebar (220px) and status
banner (40px) follow the spec in the Reading handoff exactly.

The Studio page itself is a flex row inside the main pane:

```
┌──────────┬────────────────────┬──────────────────────────────────────────┐
│          │      Status banner  (40px, full width)                        │
│ Sidebar  ├────────────────────┬──────────────────────────────────────────┤
│  220px   │  LEFT  (380px)     │  RIGHT  (flex 1)                         │
│          │  ─ Studio title    │  ─ Output header (action · breadcrumb)   │
│          │  ─ Action list     │  ─ Activity log                          │
│          │     · Research     │  ─ Result body                           │
│          │     · Utilities    │                                          │
│          │     · Config       │                                          │
│          │  ─ Action form     │                                          │
│          │  ─ Run button      │                                          │
└──────────┴────────────────────┴──────────────────────────────────────────┘
```

- **Left column:** fixed `380px`, `border-right: 1px solid border-subtle`,
  vertical flex column with a sticky header (Studio title), a scrollable middle
  (action list + form), and a sticky footer (Run button or free-tier gate).
- **Right column:** `flex: 1`, `min-width: 0`, vertical flex column. Its own
  internal scroll lives in the body, never the page.

---

## Left column

### Header
- Padding `20px 22px 14px`. Bottom 1px border.
- `FlaskConical` icon (16px, stroke 1.5, color `brand-deep`) + `<h1>Studio</h1>`
  (Inter 600, 18px, letter-spacing -0.3px). 9px gap.
- Subtitle: `Run AI research actions on papers and topics` (Inter 400, 12.5px,
  tertiary fg).

### Action list (groups)
Three groups in this order. Each group has a mono uppercase label
(Geist Mono 500, 10px, muted fg, letter-spacing 0.7px) above a vertical list of
buttons:

| Group | Items |
|---|---|
| **Research** | Deep research · Literature review · Peer review · Compare · Draft · Replicate · Audit |
| **Utilities** | Search papers · Get paper · Scholarly search · To notebook |
| **Config** | Show config · Set config key |

Each action button:
- Width 100%, padding `6px 10px`, border-radius 6, no border, text-align left.
- Inactive: color `fg-secondary`, weight 400, transparent bg.
- Active: color `brand-deep`, weight 500, background `${brand}1f` (~12% alpha).
- Active state also shows a 4px brand-green dot at left (9px gap to label).
  Inactive: invisible dot reserves the same space so labels don't shift.
- Hover (inactive only): background `gray-100`.

Only one action can be active at a time. Selecting an action swaps the form below.

### Action divider
1px subtle horizontal line + a mono uppercase label echoing the active action
name (e.g. `DEEP RESEARCH ─────`) so the user can see context as they fill the form.

### Form (per action)

All inputs/selects follow the Reading handoff input spec (8px radius, 1px
`border-medium`, focus → `brand` border, page bg, primary fg, 13px Inter).
Field labels: Inter 500, 12px, tertiary fg, 6px margin-bottom. Optional hints
follow the label in muted fg, weight 400.

| Action | Form |
|---|---|
| **Deep research / Literature review / Draft** | Topic (text) · Backend (pill toggle group) · Output destination (segmented `Local / Notebook / Vault`) · Guide files (collapsible) |
| **Peer review / Replicate / Audit** | Artifact (text, mono) · Backend (Free disabled) · Guide files |
| **Compare** | Artifact A · Artifact B (both mono) · Backend (Free disabled) · Guide files |
| **Search papers / Scholarly search** | Query · Max results (stepper, default 10) |
| **Get paper** | arXiv ID (mono, placeholder `2401.12345 or arxiv.org/abs/…`) |
| **To notebook** | Output file path (optional, auto-detect) · Sources file path (optional) · Max sources stepper · Three toggles in a gray-100 panel: NLM research / Quality gate / Perspectives (all on by default) |
| **Show config** | (no fields — descriptive paragraph only) |
| **Set config key** | Key (mono) · Value (mono) |

#### Backend pill toggle group
- Wraps to multiple lines on narrow widths.
- Each pill: padding `5px 12px`, radius 9999, 1px `border-medium`, Inter 500
  12px. Active: `background: brand`, color `#0d0d0d`, `border: brand`.
  Disabled: opacity 0.55, cursor not-allowed; show a `title` tooltip.
- `Free` is the default for topic-form actions and gets a small below-the-pills note:
  - Free selected → muted text: `No API key needed.`
  - Any AI backend selected → **amber** note row (left-border `#F59E0B`, bg
    `amberBg`, color `amberText`): `Runs 3–30 min. May time out over MCP.`
- For artifact/compare forms, `Free` is rendered disabled with the tooltip
  `Not available for this action`.

#### Output destination
Segmented control: padding 2 around its options, gray-100 track, white "thumb"
on active option (`box-shadow: 0 1px 2px rgba(0,0,0,0.06)`). Inter 12px.

#### Guide files (collapsible)
A row that toggles open with a chevron. When open: a path input + Add button,
followed by a vertical list of added files (mono, with an X to remove each).

#### Toggle switch
30 × 18 px pill, brand bg when on, gray-200 when off, 14 × 14 white knob,
0.15s ease. Used in the Notebook form.

#### Stepper
1px `border-medium` rounded 8px, three cells (`−` / value / `+`). Value is
mono 12px, weight 500. Inline (not full-width).

### Run button
Pinned to bottom of left column with a 1px top border. Full-width primary pill
(brand bg, dark text, Inter 600 13px, 9 × 18 padding, radius 9999). Label is
action-specific: `Run deep research`, `Search`, `Look up`, `Build notebook`,
`Show config`, `Save`.

---

## Free-tier disclaimer (blocking inline panel)

When the **Free** backend is selected on a topic-form action (Deep / Lit / Draft)
and the user clicks Run, **swap the Run button for an inline confirmation panel**
in the same footer. **Never use a browser dialog. Never auto-confirm.**

- Background: `amberBg`. Left border: 3px solid `#F59E0B`.
- Padding `14px 16px`. Margin-top 12 (to push it above its prior position).
- Header row: AlertTriangle icon + `Free tier — confirm before running`
  (Inter 600 12.5px, color `amberText`).
- Bulleted list (4 items, each preceded by a 3px solid dot in `amberText`):
  - No AI synthesis — sources only
  - Quality depends on search coverage
  - Tavily optional (1k/month free); DuckDuckGo fallback
  - This is a starting point, not a finished report
- Actions row (right-aligned): `Cancel` (ghost) · `Yes, proceed` (brand pill).

### Dismissal rules
- **Escape** closes (treated as Cancel).
- Clicking outside the panel — anywhere in the left column or the right pane —
  closes (Cancel).
- The Run button does **not** reappear until the gate resolves.
- Only after `Yes, proceed` does the run actually start.

The prototype implements Escape; outside-click dismissal is a TODO for production.

---

## Right column — Output panel

### States
| State | When | Header |
|---|---|---|
| `idle` (empty) | initial, or after Clear | hidden |
| `running` | user clicked Run, streaming | breadcrumb + pulsing dot + Stop button |
| `success` | run finished | breadcrumb + Clear button |
| `failure` | run errored | breadcrumb + Clear button |

### Header
Padding `14px 24px`, 1px bottom border. Layout: left cluster (status dot +
action label + ` · ` + breadcrumb in mono 11.5px) · right cluster (Stop or
Clear ghost button). Running state shows an 8px brand dot pulsing
(`logo-dot-blink 1.2s step-end infinite`).

### Activity log

Vertical list, newest at bottom. Auto-scrolls to bottom on every new line.
After the run completes, the log collapses into a scroll region (max-height
260px) above the result block so the user can still scrub it.

Each line:
- Phase tag (left): Geist Mono 600 9.5px, uppercase, padding `2px 6px`,
  border-radius 4. Color + bg depend on tone:
  - **info** phases (`plan` `search` `fetch` `parse` `synth` `save` `done`):
    color `brand-deep`, bg `brand+1c`.
  - **warn** phases (`warn` `cost`): color `amberText`, bg `amberBg`.
    Row also gets a 2px left border in `#F59E0B`.
  - **error** phase: color `redText`, bg `redBg`. Row gets a 2px left border
    in `#E53535`.
- Message: Inter 12.5px, secondary fg, line-height 1.5.
- The **last line while running** gets a 3-dot bounce indicator after the
  message and a low-key pulse animation on the row (`log-pulse 1.2s ease-in-out
  infinite`).

### Empty state
Centered column: 56 × 56 rounded square (radius 14) with `brand+1c` bg and a
28px `FlaskConical` icon in `brand-deep`. Below: heading `Run a research
action` (Inter 600 15) and subtext `Select an action on the left and fill in
the form to get started.` (Inter 13, tertiary fg, max-width 320, centered).

### Result variants

**Research actions (Deep / Lit / Peer review / Compare / Draft / Replicate / Audit) — success**
- CheckCircle icon in `brand-deep` + `Done` (Inter 600 14) + mono micro
  postscript: `· 4m 12s · 18 sources`.
- `Output file` label + `<CodeBlock>` with the path. The CodeBlock has a
  copy-to-clipboard affordance in its top-right (icon swaps to a green check
  for 1.2s on success).
- Below: a row of chips — `Notebook · nb_4f2c` (brand-deep) + a vault link
  pill with ExternalLink icon.

**Any action — failure**
- XCircle in `redText` + `Run failed`.
- Plain-text error message in secondary fg.
- `Fix` label + CodeBlock with the suggested command.

**Search papers / Scholarly search**
- Result count line in tertiary fg with the echoed query in mono.
- Bordered table inside an 8px rounded container. Columns: `Title | Year |
  Authors | Source | (action)`. Header bg `surface`. Each title is a link
  with an ExternalLink icon affordance. Year/source in mono. Per-row `Look up`
  ghost button (size sm) in the rightmost cell.

**Get paper**
- Title (Inter 600 16, line-height 1.35, `text-wrap: pretty`).
- Authors `·` venue+year `·` arXiv ID line.
- `Abstract` label + a scrollable card (max-height 140, surface bg, 1px border,
  radius 8, padding `12px 14px`, Inter 13).
- `AI overview` label + body text (Inter 13). Truncated at 600 chars with a
  `Show more` / `Show less` toggle in `brand-deep`.
- `Open on arXiv` primary pill (brand bg) with ExternalLink icon.

**To notebook**
- CheckCircle + `Notebook updated`.
- Chip row: `18 sources added` (brand-deep), `2 failed` (amber), `5 from NLM web` (info blue).
- Quality gate badge: brand-tinted pill with CheckCircle + `Quality gate · clean`,
  followed by `0 contradictions · 1 gap noted` in tertiary fg.
- `Perspectives` section with **three collapsible cards** (Practitioner / Skeptic /
  Beginner). Each card: 1px border, radius 8, header row (Inter 500 13) with a
  colored 8px dot and a chevron, body (Inter 12.5, line-height 1.6) reveals on click.
  Colors: Practitioner = info blue, Skeptic = amber, Beginner = brand-deep.
- Amber callout at the bottom: `Save this notebook ID` with the
  `docent config set notebook_id …` command in a CodeBlock.

**Show config**
- "Configuration (N keys)" line in tertiary fg.
- Bordered, alternating-row key/value list. Rows are a 2-col grid (`minmax(180px,
  0.4fr) 1fr`). Keys mono 11 secondary fg. Values mono 11. Unset values render
  as `(not set)` italic in muted fg. API keys masked as `first4...last4`.

**Set config key**
- CheckCircle + `Key saved`.
- Body line: `<mono>{key}</mono> was written to:` followed by a CodeBlock with
  the config path.

---

## State machine

```ts
type Status = 'idle' | 'running' | 'success' | 'failure';

interface StudioState {
  actionId: string;          // active action from ALL_ACTIONS
  form: FormState;           // superset of all action forms
  status: Status;
  logs: { phase: string; text: string }[];
  gating: boolean;           // free-tier panel visible?
}
```

- `Run` click → if (action uses Free backend) `setGating(true)` else `startRun()`.
- `startRun()` clears logs, sets `status='running'`, ticks one log entry every
  ~650ms (real backend: stream from server). On exhaustion: `status='success'`.
- `Stop` button → freezes the run at its current line, `status='success'`.
  (Real backend should mark a `cancelled` status and tag the last line as warn.)
- `Clear` → `status='idle'`, logs `[]`.

Backend integration TODOs:
- Wire `startRun` to your actual streaming endpoint (SSE / WS / chunked HTTP).
- Map server-emitted phase tags to the `PHASE_TONE` map. Unknown phases default
  to `info`.
- Drive `success / failure` from the server's final event, not from log length.

---

## Iconography (new for Studio)

| Used as | Lucide name |
|---|---|
| Studio nav + empty state | `FlaskConical` |
| Run button | `Play` |
| Stop button | `Square` |
| Result — success | `CheckCircle` |
| Result — failure | `XCircle` |
| Inline warning | `AlertTriangle` |
| Copy code | `Copy` |
| Add guide file | `Plus` |
| Open/close section | `ChevronDown` / `ChevronRight` |
| Guide file row | `File` |
| Remove pill | `X` |
| External link affordance | `ExternalLink` |

All at stroke 1.5 unless used as a CTA glyph (Play / Square / Plus / X →
stroke 2). Sizes follow the Reading handoff convention (12 / 13 / 14 / 16).

---

## Accessibility

Same baseline as the Reading handoff, plus:
- Make the action list a `<nav>` (or `role="tablist"`) with `aria-current` on
  the active item.
- Streaming log container should be `role="log"` with `aria-live="polite"`.
- Free-tier gate should be marked `role="alertdialog"` with `aria-modal="true"`
  for the duration it is open, even though it is rendered inline (it blocks
  the primary action). On open: move focus to `Yes, proceed`. On close (Cancel
  / Escape / outside-click): return focus to the Run button.
- The collapsible perspective cards and guide-files row need `aria-expanded`
  on their toggle and `aria-controls` referencing the body.
- Stop button should announce cancellation (`aria-live="polite"` toast or
  similar).
- Honor `prefers-reduced-motion`: disable `log-pulse`, `logo-dot-blink`, and
  the 3-dot bounce.

---

## Out of scope / TBD

- **Run history.** Prototype shows only the current run. Production should
  persist runs and add a history drawer.
- **Re-run with edits.** No way to clone a previous run's form yet.
- **Long-running over MCP.** The amber timeout warning is a placeholder until
  there is a real server-side keepalive or async-result pickup path.
- **Diff view for Compare.** ✅ Shipped in v2 — see below.
- **Auth flow for paid backends.** Selecting Anthropic/OpenAI/etc. should
  prompt for a key if none is set, then hand off to the existing config-set
  flow.

---

# v2 additions

The v2 pass adds 15 enhancements without changing the layout grid or any
design tokens. Everything is additive over v1.

## 1. Source files

The page is now split for maintainability:

```
designs/
├── Studio.html             ← shell + App composition + render
├── Studio v1.html          ← archived initial cut, for reference
├── studio-shared.jsx       ← theme, icons, primitives, constants, Sidebar, StatusBanner
├── studio-form.jsx         ← LeftColumn + forms + CommandPreview + CostEstimate
│                             + FreeTierGate + CmdKPalette + PresetSaveModal
└── studio-output.jsx       ← OutputPanel + PhaseStrip + SourceChips + LogStream
                              + all Result variants + HistoryDrawer
```

The `.jsx` modules export everything through `window.<name>` since each
`<script type="text/babel">` gets its own scope. Standard pattern; no extra
glue needed in production.

## 2. Status banner additions

Three new affordances sit to the right of the stat pills, left of the
dark-mode toggle:

- **`Quick action ⌘K`** — searchable mono pill that opens the Cmd-K palette.
  Border 1px medium, transparent bg, mono 11.
- **`History · N`** — toggle for the right-side history drawer. Active state
  uses brand-deep text on brand-tint bg with brand border.
- The existing dark-mode toggle and Synced indicator are unchanged.

## 3. Sidebar — live phase pill

When a run is in progress, the **Studio** nav item replaces its count-pill
slot with a live phase indicator: a small mono uppercase pill (e.g. `SYNTH`)
with a pulsing amber dot. Uses the existing `amberBg`/`amberText` tokens.
Lets users wander to Reading/Dashboard and still see the run's current phase
at a glance. When the run ends, the pill disappears.

## 4. Cmd-K action palette

Press `⌘K` (or click the banner pill) to open a centered overlay.

- Width 560, max-height 70vh, radius 14, soft drop shadow, dark backdrop.
- Top: search input + Esc kbd hint.
- Body: vertical list of all 13 actions. Each row has an icon (Sparkles for
  Research, Search for Utilities, Layers for Config), action label, short
  description (e.g. "Multi-source synthesis on a topic"), and a mono
  uppercase group label on the right.
- When no query: shows a "Recent" header with the user's last 4 actions
  (Clock icon).
- Keyboard: ↑/↓ navigates, Enter selects, Esc closes.
- Footer strip with kbd hints and a result count.

Selecting an action sets `actionId` and dismisses the palette. The action
list on the left scrolls to the chosen item (visually, no scrollIntoView call).

## 5. Pinned presets

The action list grows a fourth group **at the top**: `Presets` (Pin icon).
Each preset row is a normal action button but tagged with a Bookmark icon
and a hover-revealed trash button.

- Click a preset → loads its `actionId` and merges its `params` into the
  form state.
- "Save as preset" button appears on the research-success result block. It
  opens a small modal (`PresetSaveModal`) — name input + Save / Cancel.
- Presets persist as in-memory state for now. In production, persist to
  localStorage or the user's Docent config.

## 6. Command preview

Below every form (except the two config actions, which are trivial), a
small `CodeBlock small` shows the equivalent `docent` CLI command rebuilt
from the current form state. Updates live as the user edits.

- Label: `Equivalent CLI` (left) + `copy & paste` mono micro hint (right).
- Block has its standard top-right copy affordance (tap-to-clipboard).
- Argument quoting: strings with whitespace or quotes get double-quoted with
  escaped internal quotes.
- Flag conventions in `commandFor`:
  - Topic actions: `--topic`, `--backend`, `--out`, `--pipe`, `--guide`
  - Artifact actions: positional artifact + `--backend` + `--guide`
  - Compare: positional A B + `--backend`
  - Search/scholarly: positional query + `--max N`
  - Notebook: `--output`, `--sources`, `--max-sources`, `--no-nlm`,
    `--no-quality-gate`, `--no-perspectives`

## 7. Cost & time estimate

A small `CostEstimate` block sits in the footer of the left column, just
above the Run button (and above the free-tier gate when it's open).

- Surface: gray-100 bg, 1px border, radius 8, Clock icon + label/value column +
  backend tag on the right.
- Estimate label: `ESTIMATE` (mono micro), value: `$0.42 · ~5 min` (mono 12, weight 600).
- For Free backend: shows `Free · ~2 min` with `no API key` instead of the backend name.
- Action-specific defaults baked into `COST_BASE`. Config actions return
  `null` (no estimate shown).
- Hidden during a live run (the activity log carries that information).

## 8. Run button — keyboard hint

Run button now shows `⌘ ↵` kbd glyphs on the right of the label so the
keyboard shortcut is discoverable. `⌘+Enter` triggers Run when the form is
ready and no gate is active.

## 9. Stop button moved

While running, the Run button slot becomes a full-width **Stop run** ghost
button (red text, square icon, 1px border, transparent bg) instead of being
in the output header. Keeps the cancel action adjacent to where the user's
attention is.

## 10. Phase strip

A horizontal segmented bar above the activity log shows the action's full
phase progression:

`PLAN ── SEARCH ── FETCH ── PARSE ── SYNTH ── SAVE`

- Each phase is a dot + mono uppercase label.
- **Done** phases: 7px brand-green dot, label in `brand-deep`, connecting
  line in brand-green.
- **Current** phase (only while running): slightly larger 9px amber dot
  with `logo-dot-blink` animation, label in `amberText`.
- **Future** phases: 7px `gray-200` dot, label in `fg-muted`, connecting line
  in `border-subtle`.
- The phase list per action lives in `ACTION_PHASES` (e.g. `notebook` has
  `plan/fetch/parse/search/synth/save`, search-only has 3 stages).

## 11. Live source chips

While the run is in a `fetch` phase, the right pane shows a row of source
chips above the log:

- Header row: `SOURCES COLLECTED` (mono micro) + brand-tinted count pill.
- Each chip: pill (gray-100 bg, 1px border, radius 9999), truncated title +
  mono source/year on the right.
- Animation: each chip fades in on first appear (`fadeInUp` 0.2s).
- Drives from `line.sources` in the log script; each fetched-papers log line
  can attach an array of `{ title, year, src }`.

## 12. Collapsible event log

After a run finishes, the activity log collapses to a single button:

`▸ N EVENTS  Show activity log`

(small ghost pill, surface bg, border subtle). Click to expand back to a
scroll region (max-height 240, with a "▾ Collapse" link). Running state is
always expanded.

## 13. Run history drawer

A 300px right-edge drawer (toggled from the banner `History` button) lists
all completed runs newest-first.

- Each row: status dot (brand-green / amber-running / red-failed) + action
  label + relative time + detail line in mono.
- Active (currently displayed) run gets a brand-tinted bg + brand border.
- Header has counts and **Clear all** (trash icon) + **Close** (X).
- Empty state: history icon + "No runs yet" message.
- Selecting a run loads its full state (form values + logs + sources +
  result) back into the main panel. Status is preserved.

## 14. Compare result — diff view

The `compare` action now routes to its own result component
(`ResultCompare`) instead of the generic research success view.

- Header line: CheckCircle + `Comparison complete` + finding count.
- **Two paper headers** side-by-side (Paper A in `info-blue`, Paper B in
  `brand-deep`), each in a bordered surface card.
- **Three-column grid** with cards: `Only in A` (blue) · `Shared`
  (brand-deep) · `Only in B` (brand-deep). Each item is a surface card
  with a 1px border.
- **Contradictions** section underneath: amber callout panels (left border,
  amber bg) listing labeled disagreements between A and B.
- Output file path in a CodeBlock at the bottom.

## 15. Get paper — Add to Reading

The `getpaper` success view gains a brand-green primary pill **`Add to
Reading`** (Plus icon) next to the existing `Open on arXiv` ghost link.
On click it flips to `Added to Reading` with a CheckCircle icon and stays
disabled (idempotent). Wires into the Reading queue from the previous
handoff — for production, post to whatever endpoint the Reading page reads
from.

## 16. Pipe → next action

The Output destination segmented control on topic-form actions gains a 4th
option: `Pipe →`. When selected and a research run completes, the success
result panel appends a brand-tinted callout:

> `[pipe icon]` **Piped to To notebook** · sources file pre-filled with
> this run's output    `[Continue →]`

Clicking Continue switches `actionId` to `notebook`, pre-fills the sources
path field with the previous run's output, and resets the output panel to
idle so the user can review the notebook form and re-run.

## 17. Drag-drop guide files

The whole left column accepts dropped files when the active action supports
guides (topic / artifact / compare).

- On drag-over with files: a brand-tinted overlay covers the column with a
  dashed brand-deep border and a centered "Drop to add as guide file"
  message + upload icon.
- On drop: extracted file names are appended to `state.guides`. (In
  production, upload the file blob and store the server path.)

## 18. Dark-mode polish

Three surfaces got contrast bumps for dark mode:

- `card`: `#141414` → `#171717` so cards lift cleanly off the page bg.
- `amberBg` (in-log warn rows + callouts): 0.12 → 0.13 alpha, with a stronger
  `amberBorder` token (rgba(245,158,11,0.45) vs the prior solid amber).
- `codeBg` and `codeBorder`: dedicated tokens (`#0a0a0a` + 0.08 alpha) so
  code blocks read as a deliberate surface and not a sliver of border.

The light-mode palette is unchanged.

## 19. Keyboard shortcuts

Now wired globally:

| Shortcut | Action |
|---|---|
| `⌘ K` / `Ctrl K` | Open Cmd-K palette (toggle) |
| `⌘ ↵` / `Ctrl ↵` | Run current action (skipped if a free-tier gate is open) |
| `Esc` (in palette / modal / gate) | Cancel & close |
| `↑` `↓` (in palette) | Navigate results |
| `↵` (in palette) | Select highlighted result |

`Kbd` is a new shared primitive — a small monospace 18×18 box with
gray-100 bg + border medium + mono 10. Used in the banner pill and the Run
button hint.

## 20. New state shape (v2)

```ts
interface StudioState {
  actionId: string;
  form: FormState;           // unchanged from v1
  status: 'idle' | 'running' | 'success' | 'failure';
  logs:        { phase: string; text: string; sources?: Source[] }[];
  sources:     Source[];      // accumulated during the run
  currentPhase: string | null;
  // v2 additions
  cmdKOpen: boolean;
  historyOpen: boolean;
  savePresetOpen: boolean;
  recents: string[];          // recent action IDs, max 4
  presets: Preset[];
  runs: Run[];                // newest first
  currentRunId: string | null; // null = live run; non-null = viewing a past run
  gating: boolean;
}

interface Run {
  id: string;
  actionId: string;
  actionLabel: string;
  detail: string;             // short summary line (topic / artifact / query)
  status: 'running' | 'success' | 'failure';
  timeAgo: string;            // pre-computed for display
  startedAt: number;
  state: Partial<FormState>;  // form snapshot
  logs: LogLine[];
  sources: Source[];
  currentPhase: string | null;
}
```

