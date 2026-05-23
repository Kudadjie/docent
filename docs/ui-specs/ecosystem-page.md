# UI Spec — Ecosystem Page (`/ecosystem`)

**Date:** 2026-05-19  
**Route:** `/ecosystem`  
**Source content:** `docs/ecosystem.md`  
**Design context:** Matches Docent's existing theme system (`var(--bg)`, `var(--fg1)`, `var(--border)`, etc.), monospace + sans fonts (`var(--mono)`, `var(--sans)`), brand green `#18E299`.

---

## 1. Overview

The Ecosystem page is an **integrations / companion tools** page. It tells users which external tools pair exceptionally well with Docent, how to install them, and how to use them alongside Docent's workflows. The page also includes a transparent **"Inside Docent"** attribution table crediting open-source patterns that were adopted into Docent's codebase.

**Who uses it:** Any Docent user who wants to extend their workflow beyond what Docent handles directly (AI synthesis, paper writing, long-form study, notebook chat).

---

## 2. Page Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ Sidebar  │ StatusBanner                                              │
│          ├────────────────────────────────────────────────────────── │
│          │ Hero header                                               │
│          │   "Docent Ecosystem"                                      │
│          │   subtitle                                                │
│          ├────────────────────────────────────────────────────────── │
│          │  ┌─────────────────────────────────────────────────────┐  │
│          │  │  Section: AI Research & Writing                     │  │
│          │  │  ┌─────────────────────────────────────────────────┐│  │
│          │  │  │ Tool card: Academic Research Skills             ││  │
│          │  │  └─────────────────────────────────────────────────┘│  │
│          │  │  Section: Research Pipeline Engines                 │  │
│          │  │  ┌─────────────────────────────────────────────────┐│  │
│          │  │  │ Tool card: Feynman                              ││  │
│          │  │  └─────────────────────────────────────────────────┘│  │
│          │  │  Section: Study & Synthesis                         │  │
│          │  │  ┌─────────────────────────────────────────────────┐│  │
│          │  │  │ Tool card: NotebookLM                           ││  │
│          │  │  └─────────────────────────────────────────────────┘│  │
│          │  │  Section: Inside Docent (attribution table)         │  │
│          │  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

The content area is a **single scrollable column** (max-width ~860px, centered). No two-column layout needed — tool cards take full column width.

---

## 3. Hero Header

```
┌──────────────────────────────────────────────────┐
│  ✦  Ecosystem                                    │
│  Companion tools that pair well with Docent      │
│                                                  │
│  Docent handles sources, queues, and pipelines.  │
│  These tools handle the rest.                    │
└──────────────────────────────────────────────────┘
```

- **Title:** "Ecosystem" — `var(--sans)`, 24px, weight 700, `var(--fg1)`
- **Icon:** `Sparkles` or `Layers` Lucide icon, `#18E299`, 18px, shown inline left of title
- **Subtitle:** 13px, `var(--fg3)`, max-width 520px
- Background: subtle radial dot grid (same as `OutputEmpty` in Studio): `radial-gradient(circle, var(--gray200) 1px, transparent 1px)`, 24px grid
- Padding: 36px top, 28px horizontal, 24px bottom

---

## 4. Section Headers

Each section groups related tools:

```
●  AI Research & Writing                          ←  amber dot
────────────────────────────────────────────────
```

- Section label: `var(--mono)`, 10px, weight 600, `var(--fg4)`, `letter-spacing: 0.7px`, `text-transform: uppercase`
- Colored dot (5×5px circle) before the label, color keyed to section:
  - AI Research & Writing → `#F59E0B` (amber)
  - Research Pipeline → `#6366f1` (indigo)
  - Study & Synthesis → `#3B82F6` (blue)
  - Inside Docent → `var(--fg4)` (neutral)
- Horizontal rule below label: `var(--border)`, 1px

---

## 5. Tool Card

Each companion tool gets one card:

```
┌──────────────────────────────────────────────────────────────────┐
│  [Icon/Logo placeholder]  Academic Research Skills         ↗     │
│  Author: Cheng-I Wu  ·  CC-BY-NC 4.0                            │
│  ──────────────────────────────────────────────────────────────  │
│  A Claude Code plugin providing a full academic workflow:        │
│  13-agent deep research, 12-agent paper writing, 7-agent peer    │
│  review, and a 10-stage end-to-end orchestrator.                 │
│                                                                  │
│  WHEN TO USE                                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ After a Docent research run → use /ars-write to draft    │   │
│  │ After a draft → use /ars-review for peer critique        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  INSTALL                                                         │
│  /plugin marketplace add Imbad0202/academic-research-skills      │
│  ▶ Copy                                                          │
└──────────────────────────────────────────────────────────────────┘
```

**Card anatomy:**

| Element | Spec |
|---------|------|
| Container | `border: 1px solid var(--border)`, `border-radius: 12px`, `padding: 20px 24px`, `background: var(--bg-card)` |
| Tool name | `var(--sans)`, 15px, weight 600, `var(--fg1)` |
| External link icon | `ExternalLink` Lucide 13px, `var(--fg4)`, top-right of name row, links to repo/site |
| Meta line | Author · License — `var(--sans)`, 12px, `var(--fg4)` |
| Divider | 1px `var(--border)`, 10px margin |
| Description | `var(--sans)`, 13px, `var(--fg2)`, `line-height: 1.65` |
| "When to use" block | Collapsible. Header: `var(--mono)`, 10px, `var(--fg4)`, uppercase. Body: indented list, 12px `var(--fg3)` |
| "Install" block | Label: `var(--mono)`, 10px, `var(--fg4)`, uppercase. Command: `CodeBlock` (styled `<pre>`) with copy button |
| "Suggested pairing" | Optional 3-step numbered list using a subtle `BRAND + '12'` tinted block |

---

## 6. Tool Card Specs — Per Tool

### 6a. Academic Research Skills

| Field | Value |
|-------|-------|
| Name | Academic Research Skills |
| Author | Cheng-I Wu |
| License | CC-BY-NC 4.0 |
| Link | https://github.com/Imbad0202/academic-research-skills |
| Install command | `/plugin marketplace add Imbad0202/academic-research-skills` (Claude Code) |
| Description | A Claude Code plugin providing a full academic workflow: 13-agent deep research, 12-agent paper writing, 7-agent peer review, and a 10-stage end-to-end orchestrator with integrity gates. |
| When to use | After Docent deep-research → `/ars-write` for paper draft; After draft → `/ars-review` for peer critique; Reviewer feedback → `/ars-revision` for coaching |
| Suggested pairing | 3-step flow: `docent studio deep-research` → save `synthesis.md` → `/ars-write synthesis.md` → `/ars-review draft.md` |
| License note | CC-BY-NC: free for personal/academic use. Required attribution format shown in a `<blockquote>` |

### 6b. Feynman

| Field | Value |
|-------|-------|
| Name | Feynman |
| Author | Companion (companion.ai) |
| License | MIT |
| Link | https://feynman.is |
| Install command | `npm install -g @companion-ai/feynman` |
| Description | An open-source AI research agent CLI. Runs multi-stage research pipelines using any major LLM provider. Docent uses Feynman as the `--backend feynman` option. |
| When to use | Long-form research briefs; when you want the highest quality synthesis; when Docent's free tier isn't enough |
| Code example | Two blocks: `docent studio deep-research "topic" --backend feynman` and `feynman /deep "topic"` |

### 6c. NotebookLM

| Field | Value |
|-------|-------|
| Name | NotebookLM |
| Author | Google |
| License | Proprietary |
| Link | https://notebooklm.google.com |
| Install | No install — web app. Accessed via Docent's `to-notebook` action |
| Description | Upload sources and chat with them, generate study guides, create audio overviews, and build flashcards. Docent's `to-notebook` command pushes research output directly into a notebook. |
| When to use | After a deep-research run to study the output; creating podcast-style audio overviews; generating flashcards |
| Code examples | `docent studio deep-research "topic" --output notebook` and `docent studio to-notebook --output-file research/output.md` |

---

## 7. "Inside Docent" Attribution Table

A special section below the tool cards with a slightly different visual treatment (neutral, not a tool card):

```
┌─────────────────────────────────────────────────────────────────┐
│  INSIDE DOCENT — Adopted Patterns                               │
│  ──────────────────────────────────────────────────────────────  │
│  Some patterns from the ecosystem are implemented directly in   │
│  Docent. Attribution is kept here for visibility.               │
│                                                                  │
│  Pattern              │ Adopted from   │ Source file   │ License │
│  ───────────────────────────────────────────────────────────────│
│  Multi-stage pipeline │ Feynman        │ pipeline.py   │ MIT     │
│  Citation verification│ ARS            │ citation_…py  │ CC-BY-NC│
│  Integrity gates      │ ARS            │ pipeline.py   │ CC-BY-NC│
└─────────────────────────────────────────────────────────────────┘
```

**Table styling:**
- Container: `border: 1px solid var(--border)`, `border-radius: 10px`, `overflow: hidden`
- Header row: `background: var(--bg-subtle)`, `var(--mono)`, 10px, weight 500, `var(--fg4)`, uppercase
- Data rows: alternating `var(--bg)` / `var(--bg-subtle)`, 12px `var(--sans)`, `var(--fg2)`
- "Pattern" column: `var(--sans)`, 13px, weight 500, `var(--fg1)`
- "Source file": `var(--mono)`, 11px, `var(--fg3)` — links to GitHub if possible
- "License": `Chip` component styled per license type (MIT = green, CC-BY-NC = amber)

---

## 8. Suggesting Additions

A footer call-to-action at the bottom of the page:

```
┌─────────────────────────────────────────────────────────────────┐
│  Know a tool that pairs well with Docent?                       │
│  Open an issue or PR adding an entry to docs/ecosystem.md       │
│                                                                  │
│  [Open GitHub Issue ↗]                                          │
└─────────────────────────────────────────────────────────────────┘
```

- Light tinted block: `background: var(--gray100)`, `border: 1px solid var(--border)`, `border-radius: 10px`
- Text: 13px `var(--fg3)`
- Button: `GhostBtn` linking to the GitHub issues URL

---

## 9. Responsive / Layout Notes

- **Single scrollable column**, no sidebar for content
- Max content width: `860px`, centered
- Cards stack vertically with `16px` gap between them
- Section headers have `28px` top margin, `12px` bottom margin
- Mobile (< 640px): card padding reduced to `14px 16px`; code blocks scroll horizontally

---

## 10. Design Notes for Claude Design

**What Claude Design needs to know:**

1. **Existing design system:** Docent uses CSS variables (`var(--bg)`, `var(--fg1)–(--fg4)`, `var(--border)`, `var(--gray100)`, `var(--gray200)`, `var(--bg-card)`, `var(--bg-subtle)`). Both dark and light modes must work.
2. **Font stack:** `var(--sans)` for prose, `var(--mono)` for code/labels/chips.
3. **Brand color:** `#18E299` (green) for active/positive states, `BRAND_DEEP = #0fa76e` for text on green backgrounds.
4. **Existing components to reuse:** `Sidebar`, `StatusBanner`, `CodeBlock` (with copy button), `Chip`, `GhostBtn` — all already exist.
5. **Icon library:** Lucide React (`lucide-react`). Use `Sparkles`, `ExternalLink`, `ChevronDown`, `Layers`.
6. **No new deps needed** — the page is purely presentational static content read from a data array.
7. **Existing page patterns to match:** The `docs/page.tsx` card+section pattern is the closest reference. The ecosystem page should feel like an extension of that.

---

## 11. Claude Design Prompt

> Design a companion tools / integrations page for the Docent academic research tool. The page lives at `/ecosystem` within a Next.js app.
>
> **Context:** Docent is a Python CLI and local web UI for academic workflows. It has an existing design system with CSS variables for dark/light theming. The primary brand color is `#18E299` (green). Fonts: a sans-serif for prose and a monospace for labels/code.
>
> **What the page contains:**
> - A hero header: "Ecosystem" with subtitle "Companion tools that pair with Docent"
> - Three tool cards (Academic Research Skills, Feynman, NotebookLM), each with: tool name, author, license, description, "when to use" section, and an install command in a copyable code block
> - An attribution table ("Inside Docent") showing open-source patterns adopted into Docent's codebase
> - A footer CTA: "Know a tool that pairs well? Open a GitHub issue"
>
> **Visual style:**
> - Clean, developer-oriented (think Linear, Vercel, Raycast docs)
> - Tool cards: subtle borders, rounded corners, white/dark-mode-aware backgrounds
> - Section headers: uppercase monospace label with a small colored dot accent
> - Code blocks: dark code block with copy button (matching existing `CodeBlock` component)
> - Must work in both dark mode and light mode using CSS variables
>
> **Constraints:**
> - Reuse existing components: `Sidebar`, `StatusBanner`, `CodeBlock`, `GhostBtn`, `Chip`
> - Use Lucide React icons only
> - No new npm dependencies
> - Single scrollable column layout, max-width 860px centered
> - File: `frontend/src/app/ecosystem/page.tsx`

---

*Spec generated from `docs/ecosystem.md` — 2026-05-19*
