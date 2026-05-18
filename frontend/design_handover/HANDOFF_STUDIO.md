# Handoff: Docent — Studio Page

> **Delta handoff.** This document covers only what's new for the **Studio** page.
> The design system, tokens, type/color CSS, sidebar layout, status banner, and the
> reference primitives (`GhostBtn`, `IconBtn`, `StatusBadge`, etc.) defined in
> `HANDOFF.md` (Reading) all apply unchanged here. See `design_system/` for tokens
> and `designs/Reading.html` for the reference shell.

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
- **Diff view for Compare.** The prototype routes Compare to the generic
  research-success view; Compare should eventually render a side-by-side diff.
- **Auth flow for paid backends.** Selecting Anthropic/OpenAI/etc. should
  prompt for a key if none is set, then hand off to the existing config-set
  flow.
