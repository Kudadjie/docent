# Docent Design System — Studio Notes

> **The canonical design system is [`HANDOFF.md`](./HANDOFF.md).** Read it first.
> This file only records Studio-specific decisions under the 2026 overhaul. The
> previous dark-first Studio handoff has been retired.

Studio is built from `frontend/src/app/studio/` — `page.tsx` (shell + status bar),
`_form.tsx` (left action rail + run form), `_output.tsx` (right results panel).

## Layout

Two-pane app shell inside the standard sidebar + status bar:
- **Left rail** (`_form.tsx`): serif `Studio` title + sans sub-line, then grouped
  action lists (ACTIONS / UTILITIES / CONFIG) and the run button pinned at the bottom.
- **Right panel** (`_output.tsx`): empty-state (serif "Run a studio action") → live
  run progress → results. Background is `--bg` (no gradient — the old green/violet
  hero wash was removed).

## Colour roles (how the system maps here)

| Element | Token / value | Rationale |
|---|---|---|
| Page title | `--serif`, weight 500, `--fg1` | Editorial page header (§3). |
| Title icon (FlaskConical) | `style={{ color: 'var(--fg2)' }}` | Theme-aware, never a hardcoded hex. |
| Active action in the rail | `--brand` fill / `--brand-deep` text (neutral ink) | Selection is chrome → neutral, not green. |
| **Run button** (Run deep research, Proceed, Save preset) | `--cta` green + `--on-cta` | The page's single primary action. |
| Segmented mode toggle (active) | `--brand` ink fill + `--on-primary` text | Neutral active chrome. |
| Run progress / phase chips / done dots | success green `#5db872` / `#3f8f54` / `rgba(93,184,114,a)` | Green here is **semantic "complete/running,"** not chrome — it stays green on purpose. |
| "OA" / open-access badges | success green | Semantic "available." |
| Drop-to-add-guide-file zone | `--brand-light` fill + `--border-md` | Neutral highlight. |

The key distinction: **green-as-action** (the Run button → `--cta`) vs
**green-as-status** (progress, done, OA → success green). Selection/active chrome is
neutral ink. Do not collapse these three roles into one colour.

## Status bar extras

`StatusBanner` renders Studio's `Quick action ⌘K`, `History`, and `Outputs` toggles.
Toggle labels are **sans** (not mono); active toggles use neutral `--brand-light` /
`--brand-deep`. Keyboard chips (`Ctrl` `K`) keep `--mono`.

## Everything else

Buttons, inputs, badges, dark-mode derivation, spacing, radius, and the
lucide-`color=` theming caveat are all defined in `HANDOFF.md`. Studio adds no new
primitives — it composes the shared system.
