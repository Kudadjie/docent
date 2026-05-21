# Handoff: Docent — Dashboard

## Overview

This handoff covers the **Dashboard** screen of Docent — the at-a-glance landing page a grad student sees on open. Goal: in five seconds, they should know **what's next to read**, **whether they're behind on deadlines**, and **what they were researching yesterday**.

The visual reference is a Bloomberg-style information terminal — dense, monospace-led, every pixel earning its place. No marketing-page polish, no decorative gradients, no hero washes. Density *is* the design.

Lives in the same 3-region app shell as Reading & Studio:
- **Sidebar (left, 220px)** — existing `Sidebar` component from `design_handoff/designs/studio-shared.jsx`, `active="dashboard"`
- **Top status bar** — existing `StatusBanner` component from `design_handoff/designs/studio-shared.jsx`
- **Main content area** — the dashboard, fills remaining space; single internal scroll

---

## New / changed since last handoff

This page introduces **one new card surface variant** — flagged here so you don't accidentally treat it as a re-skin of the existing card token.

| Token / pattern | Existing system | Dashboard override | Rationale |
|---|---|---|---|
| Card background (dark) | `#141414` | **`#111111`** | One step darker than other cards → reads as "data tool", not "content card" |
| Card background (light) | `#ffffff` on `#ffffff` page | **`#ffffff`** on **`#f8f9fa`** page | A near-white page bg gives card edges visible separation in light mode |
| Card border radius | `16px` (md) | **`8px`** (sm) | Tighter geometry signals utility over warmth |
| Card border (dark) | `rgba(255,255,255,0.06)` | `rgba(255,255,255,0.08)` | Slightly stronger to define dense grid cells |

These are **dashboard-scoped**; do not promote them globally without a follow-up review. Everything else — color tokens, type tokens, spacing, brand green, semantic colors (amber/red/violet) — is inherited unchanged from the existing system.

> See `design_handoff/design_system/` (the original Reading handoff) for tokens, type/color CSS, and reference components. Those apply unchanged here. **The shared `studio-shared.jsx`, `tweaks-panel.jsx`, and logo assets are duplicated into this bundle** only so `Dashboard.html` opens self-contained — they are not new.

No new global components are introduced. The cards and panels described below are **page-local compositions of existing primitives** (`SectionLabel`, `CardShell`, `Divider`, `StatCell`) — not candidates for the global library yet.

---

## Fidelity

**High-fidelity (hifi).** Colors, typography, spacing, radii, and the inline data treatment are final. Recreate pixel-perfectly.

The prototype's "Tweaks" panel (dark toggle, deadlines toggle, density toggle) is **designer-only** — do not ship.

---

## Files in this bundle

```
design_handoff_dashboard/
├── HANDOFF.md                              ← this file
├── designs/
│   ├── Dashboard.html                      ← the prototype (PRIMARY)
│   ├── studio-shared.jsx                   ← shared chrome (copy of original; do not re-promote)
│   └── tweaks-panel.jsx                    ← designer-only (do NOT ship)
├── assets/
│   ├── logo.svg                            ← dark mark, light-bg use
│   ├── logo-light.svg                      ← white mark, dark-bg use
│   └── favicon.svg
└── screenshots/
    ├── 01-dashboard-dark.png               ← top of page, dark mode
    ├── 02-dashboard-dark-bottom.png        ← heatmap + quick actions, dark mode
    └── 03-dashboard-light.png              ← top of page, light mode
```

**Open `designs/Dashboard.html` in a browser** to interact. The prototype is the source of truth on spacing & micro-interactions; this document captures *intent*.

---

## Layout — top level

```
┌──────────┬──────────────────────────────────────────────┐
│          │ StatusBanner (existing component, 40px)      │
│ Sidebar  ├──────────────────────────────────────────────┤
│  220px   │ Greeting strip (~50px, flat, thin divider)   │
│          ├──────────────────────────────────────────────┤
│          │                                              │
│          │   Global stat row (4 stats, full width)      │
│          │                                              │
│          │   ┌─────────────────┬─────────────────┐      │
│          │   │ Reading card    │ Studio card     │      │
│          │   │                 │                 │      │
│          │   └─────────────────┴─────────────────┘      │
│          │                                              │
│          │   ┌─────────────────┬─────────────────┐      │
│          │   │ Activity        │ Quick Actions   │      │
│          │   │ heatmap         │                 │      │
│          │   └─────────────────┴─────────────────┘      │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

- **Sidebar:** 220px fixed. Use the existing `Sidebar` with `active="dashboard"`.
- **Status bar:** existing `StatusBanner` at its native height (40px). The original brief asked for 48px — this handoff intentionally keeps the existing component height for cross-page consistency. If 48px is later required globally, change it in the shared component.
- **Greeting strip:** flat, no gradient, 1px bottom divider. Padding `14px 24px`.
- **Content area:** padding `18px 24px 28px`, internal flex column with `gap: 16px`, single vertical scroll. Background `#0d0d0d` (dark) / `#f8f9fa` (light).

---

## Section specs

### 1. Greeting strip

| Side  | Content                                                   | Type                                                  |
|-------|-----------------------------------------------------------|-------------------------------------------------------|
| Left  | `Good {morning\|afternoon\|evening}, {first_name}`        | Inter 16px / weight 600 / fg1, `letter-spacing: -0.2px` |
|       | middle-dot separator `·`                                  | fg-muted, 14px                                        |
|       | program label (e.g. `MSc Coastal Engineering`)            | Inter 14px / regular / fg3                            |
| Right | current date+time, e.g. `WED 20 MAY 2026 · 2:30 PM`       | Geist Mono 11px, muted, `letter-spacing: 0.5px`       |

Greeting verb keys off local hour: <12 morning, <17 afternoon, else evening. Date is `prefers locale = en-US`, always uppercase mono.

### 2. Global stat row

A single horizontal card, four equal columns separated by 1px vertical dividers (`color-divider`).

| Column   | Number             | Label    |
|----------|--------------------|----------|
| Queued   | `12`, fg-primary   | `QUEUED` |
| Reading  | `2`, **#18E299**   | `READING`|
| Done     | `8`, fg-muted (dim)| `DONE`   |
| Outputs  | `18`, **#8B5CF6**  | `OUTPUTS`|

- **Number:** Geist Mono 28px / weight 600 / `letter-spacing: -0.5px` / `line-height: 1`
- **Label:** Geist Mono 10px / weight 500 / fg-muted / `letter-spacing: 1px` / uppercase
- Cell padding `18px 22px`, vertical gap between number and label `6px`

### 3. Reading card

Header: `READING — QUEUE` (mono 10px, muted) · **·Active** indicator with a 6px brand-green dot (`pulse-dot 2.2s` animation) on the right.

Four labeled sections, each separated by a 1px divider:

| Section       | Content                                                                                             |
|---------------|-----------------------------------------------------------------------------------------------------|
| **STATS**     | One line, mono 13px: `12 queued · 2 reading · 8 done`. The `2` is brand green. Numbers slightly brighter than text. |
| **NEXT UP**   | Paper title (Inter 13px / weight 500 / fg1, single-line ellipsis) above the meta line: `#1 · Storm surge · CES701` in Geist Mono 11px muted. |
| **DEADLINES** *(conditional)* | `{n} past due` in `#D45656` · `{n} due soon` in `#C37D0D`. Mono 11px. Render only if either count > 0. |
| **IN PROGRESS** | Paper title (single-line ellipsis) on left, **Reading badge** on right — a tiny outline pill (`1px solid rgba(24,226,153,0.4)`, brand-deep text, 4px green dot). |

Footer (`10px 18px`, 1px top divider):
- Left: `Synced 3h ago` — Geist Mono 10px / muted / uppercase
- Right: `Open →` — Inter 12px / weight 500 / **#18E299**, plain text (no border)

Section label pattern is shared across all dashboard cards:
- Wrapper: `padding: 14px 18px`, `display: flex`, `gap: 8px`
- Label: Geist Mono **9px** / weight 500 / `letter-spacing: 0.85px` / uppercase / `color-section-label`
- An optional 5px accent dot precedes the label on stat sections (green for Reading, violet for Studio)
- An optional right-aligned element (badge, timestamp) on the same row

### 4. Studio card

Header: `STUDIO — OUTPUTS` (mono 10px, muted) · `· 2h ago` timestamp on the right in violet.

| Section     | Content                                                                                                                                  |
|-------------|------------------------------------------------------------------------------------------------------------------------------------------|
| **STATS**   | `18 outputs · 3 today · 6 this week` — mono 13px. The `18` is violet (`#8B5CF6`), other numbers fg-primary.                              |
| **RECENT**  | Three rows. Each row: topic (Inter 13px / weight 400 / fg1, ellipsis) left · timestamp `2H AGO` (Mono 10px muted uppercase) right. `5px 0` vertical padding per row. |
| **BY TYPE** | `7 research · 6 notes · 5 briefs` — Mono 11px. Numbers fg-secondary weight 500, units fg-muted.                                          |

Footer:
- Left: `Last run 2h ago` (Mono 10px muted uppercase)
- Right: `Open →` Inter 12px / weight 500 / **#8B5CF6**

### 5. Activity heatmap

Header: `ACTIVITY — LAST 8 WEEKS` (mono 9px label) · `22 sessions total` on the right (Mono 10px; the `22` is fg-primary weight 500, the rest fg-muted).

Grid:
- **5 rows × 8 columns** of 18×18 cells, 5px gap, no left-axis labels
- Rows = Mon → Fri; Columns = wk-8 → wk-1 (oldest left, most recent right)
- Four intensity levels:

| Level | Light                           | Dark                                  |
|-------|---------------------------------|---------------------------------------|
| 0     | `rgba(0,0,0,0.05)` (1px subtle border) | `rgba(255,255,255,0.04)` (1px subtle border) |
| 1     | `rgba(24,226,153,0.30)`         | `rgba(24,226,153,0.22)`               |
| 2     | `rgba(24,226,153,0.60)`         | `rgba(24,226,153,0.48)`               |
| 3     | `#0fa76e` (brand-deep)          | `#18E299` (brand)                     |

- Cell radius 3px, no border on filled cells
- Each cell has a tooltip: `Week {n} · {Mon|Tue|…} · {n} sessions`

Legend row beneath grid, vertical gap `14px`:
- `less ░ ░ ▒ █ more` — Mono 9px muted uppercase; the four swatches are the same four intensities at 10×10 px

### 6. Quick Actions

Header: `QUICK ACTIONS` (mono 9px muted).

Four rows, each row:

| Region | Content                                  | Style                                                              |
|--------|------------------------------------------|--------------------------------------------------------------------|
| Left   | 16×16 stroke icon (1.5px stroke)         | `width: 22px` slot, fg-tertiary                                    |
| Middle | Action label (Inter 13px / regular / fg1)| flex grows                                                         |
| Right  | Keyboard shortcut key                    | Mono 10px / weight 500 / fg3, in a 22×20 chip with 4px radius and `1px solid borderMd` background `gray100` |

Actions (in order):
1. Add to queue · `A`
2. New studio run · `S`
3. Feynman research · `F`
4. Backup now · `B`

Row hover: `background: rgba(0,0,0,0.025)` (light) / `rgba(255,255,255,0.025)` (dark). 12ms transition. Each row is a `<button>` (full row clickable).

### 7. Footer line

Below the bottom row, a small mono breadcrumb in section-label style:
- Left: `Docent · Dashboard · MSc Coastal Engineering`
- Right: `v0.4.1 · dark` (theme name reflects current mode)

Mono 9px / muted / `letter-spacing: 0.85px` / uppercase. Top padding `4px`. This is intentional dashboard chrome — keep it.

---

## Color contract

| Role                  | Dark         | Light             |
|-----------------------|--------------|-------------------|
| Page background       | `#0d0d0d`    | `#f8f9fa`         |
| Card background       | `#111111`    | `#ffffff`         |
| Card border           | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.06)` |
| Divider               | `rgba(255,255,255,0.06)` | `rgba(0,0,0,0.05)` |
| Section label color   | `#606060`    | `#888888`         |
| Data muted            | `#707070`    | `#888888`         |
| Data bright           | `#ededed`    | `#0d0d0d`         |
| Row hover overlay     | `rgba(255,255,255,0.025)` | `rgba(0,0,0,0.025)` |
| Accent — Reading      | `#18E299` (dark) / `#0fa76e` (light interactive) | |
| Accent — Studio       | `#8B5CF6`    | `#8B5CF6`         |
| Warning               | `#C37D0D`    | `#C37D0D`         |
| Error                 | `#D45656`    | `#D45656`         |

**Brand green stays exactly `#18E299`** across both modes for instant recognition.

---

## Interaction & state notes

- Dashboard is a **read-mostly** screen. The only real interactions are: hover on Quick Action rows, click `Open →` to navigate to Reading or Studio, keyboard shortcut keys (A/S/F/B) trigger the corresponding quick action.
- All cards have a thin entry presence (no opacity fade in the shipping build — the prototype's `fadeIn` was removed because it interfered with html-to-image capture). Keep the *layout-final* state from frame one.
- The `· Active` indicator on the Reading card animates a slow `pulse-dot` (opacity 1 → 0.35 → 1 over 2.2s). It's the only motion on the page. Don't add more.
- Deadlines section is conditionally rendered: hide the entire labeled section (label + content + the divider below it) when both counts are zero. The example screenshots show the populated state (`1 past due · 2 due soon`).

---

## Responsive

This handoff prototype is sized for desktop (≥1024px effective content width). On narrower viewports:
- The 2×2 grid of cards/panels collapses to single column — `grid-template-columns: 1fr` below ~900px.
- The 4-up stat row stays horizontal — numbers are tight enough to fit even at 600px content width.
- Below ~600px, stat row reflows to 2×2.

Not part of this hifi spec — propose responsive rules in implementation review.

---

## Open questions / follow-ups

- **Keyboard shortcuts** — the `A/S/F/B` shortcuts shown are aspirational. Confirm with engineering whether to wire them globally or only inside the dashboard route. If only inside the route, dim the chip when blurred.
- **Activity heatmap interaction** — currently tooltip-only. Should clicking a cell deep-link into Studio runs from that day? Probably yes, but out of scope for v1.
- **Per-program greeting copy** — currently `MSc Coastal Engineering` is a static string from the user profile. Confirm we have this field populated for all users, or fall back to dropping the second clause.
- **"Synced N ago" copy** — uses relative time. Decide refresh cadence (probably 1m tick).

---

*— Dashboard handoff, May 2026*
