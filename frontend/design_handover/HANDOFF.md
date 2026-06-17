# Docent Design System

> **This file supersedes the previous dark-first / mint-green handoff.** It is the
> single source of truth for the Docent web UI after the 2026 design overhaul.
> The old Reading and Studio handoffs have been folded into this one document.

## 1. Philosophy

Docent's UI is **Airtable-structured, Claude-warmed**:

- **White, calm canvas** with **near-black ink chrome** (Airtable's sober workflow look). No atmospheric gradients, no accent walls — whitespace and hairlines do the framing.
- **Serif display headlines** (Claude's editorial voice) on every page title and large empty-state heading.
- **One branded action colour**: a dark, logo-derived **green** reserved for *primary actions only*. Chrome (nav, tabs, selection) stays neutral ink so the green reads as "do this."
- **Coral is NOT a UI colour.** It survives only as a signature-card token (`--sig-coral`) for future full-bleed callout cards, used scarcely. Do not paint chrome coral.
- **Colour-block first, shadows rare.** Depth comes from the white-vs-navy surface contrast and 1px hairlines, not drop shadows.

Three things carry the brand: the **serif headline**, the **green primary button**, and the **logo mark**. Everything else is quiet.

## 2. Colour Tokens

All colours are CSS variables in `frontend/src/app/globals.css`. Light is the default theme; dark is a derived warm-slate variant. **Never inline a hex — always use the token** so both themes and future retints stay correct. The only exception is semantic status colours used in lucide `color=` props (which cannot resolve CSS vars — see §6).

### Accent / action
| Token | Light | Dark | Use |
|---|---|---|---|
| `--brand` | `#181d26` ink | `#ededed` | Neutral chrome accent: active-nav text, selected fills, tab underline. **Not** a CTA colour. |
| `--brand-light` | `#eef0f2` | `rgba(255,255,255,.08)` | Active-nav / selected background tint (neutral). |
| `--brand-deep` | `#0d1218` | `#d0d0d0` | Pressed / active text. |
| `--cta` | `#0a7d54` | `#0a7d54` | **Primary action buttons only** (Sync, Run, Save, Continue). Dark shade of the logo green `#18E299`. |
| `--cta-deep` | `#086a47` | — | CTA press/active. |
| `--cta-light` | `rgba(10,125,84,.12)` | — | CTA soft tint. |
| `--on-cta` | `#ffffff` | `#ffffff` | Text on a CTA button. |
| `--on-primary` | `#ffffff` | `#181d26` | Text on an ink-filled surface. |

### Surfaces
| Token | Light | Dark |
|---|---|---|
| `--bg` | `#ffffff` | `#14171c` |
| `--bg-subtle` | `#f8fafc` | `#181d26` |
| `--bg-card` | `#ffffff` | `#1d1f25` |
| `--gray100` | `#eef0f2` | `#252830` |
| `--gray200` | `#e0e2e6` | `#30343d` |
| `--row-hover` | `#f6f8fa` | `#1d2027` |
| `--border` | `rgba(20,23,30,.09)` | `rgba(255,255,255,.08)` |
| `--border-md` | `rgba(20,23,30,.14)` | `rgba(255,255,255,.13)` |

### Text
| Token | Light | Dark | Use |
|---|---|---|---|
| `--fg1` | `#181d26` | `#f4f6f8` | Ink — headlines, primary text |
| `--fg2` | `#333840` | `#d6d9dd` | Body, title icons |
| `--fg3` | `#41454d` | `#9297a0` | Muted, sub-text |
| `--fg4` | `#767b84` | `#6b7280` | Captions, fine print, inactive icons |

### Signature / semantic
| Token | Value | Use |
|---|---|---|
| `--surface-dark` | `#181d26` | Navy signature/feature cards on white |
| `--sig-coral` | `#cc785c` | Reserved — full-bleed callout cards only (currently unused) |
| `--sig-forest` / `--sig-cream` | `#0a2e0e` / `#f5e9d4` | Reserved signature fills |
| `--teal` | `#5db8a6` | Info accent, loading spinner |
| `--success` | `#5db872` | "Done" / healthy / synced |
| `--amber-accent` / `--amber-text` | `#e8a55a` / `#B45309` (dark `#e8a55a`) | "Reading" / warning |
| `--error` | `#c64545` | Errors, "high priority" |
| `--link` | `#1b61c9` (dark `#6ba5f5`) | Inline body links |

**Status colour conventions** (used by `StatusBadge`, `OrderIndicator`, dots):
- Queued → teal `#5db8a6` · Reading → amber `#e8a55a` · Done → success green `#5db872` · Removed → grey.
- Priority: high `#c64545`, medium `#d4a017`, low `#5db872`.
- Success-state greens in components use literal `#3f8f54` (text) / `#5db872` (dot) / `rgba(93,184,114,a)` (tint) — these read on both themes.

## 3. Typography

Loaded in `layout.tsx`: **Schibsted Grotesk** (body/UI), **Cormorant Garamond** (serif display, a Tiempos/Copernicus substitute), **JetBrains Mono** (code + keyboard keys).

| Token | Family | Use |
|---|---|---|
| `--serif` | `Tiempos Headline, Cormorant Garamond, EB Garamond, Georgia, serif` | **Page titles & large empty-state headings only.** Weight 500, `letter-spacing: -0.01em`. Use the `.serif-display` utility class. |
| `--sans` | `Schibsted Grotesk, Inter, system-ui, …` | Everything else: body, nav, buttons, labels, captions. A distinctive editorial grotesk chosen over Inter for more character beside the serif (Inter remains the fallback). |
| `--mono` | `JetBrains Mono, …` | Code blocks and keyboard-key chips (`Ctrl` `K`) **only**. |

**Rules**
- Page title pattern: `<h1 className="serif-display">` at 26px (standard page) / 28–52px (hero pages like Plugin Builder, Ecosystem), beside a theme-aware lucide icon (`style={{ color: 'var(--fg2)' }}`, **not** a hardcoded colour), with a sans sub-line in `--fg3` underneath.
- **Labels are sans, not mono.** Caption/stat labels (e.g. QUEUE · FOLDER · DONE) use Inter 11px/500 uppercase with `letter-spacing: 0.4px`. Mono uppercase reads "robotic" — reserve mono for keys and code.
- Display weight stays 500, never 700.

## 4. Spacing, Radius, Elevation

- **Spacing** snaps to 4px. Section rhythm ~96px on marketing-style pages; tool pages use tighter 16–28px header padding.
- **Radius**: 8px for buttons/inputs/tabs, 10–12px for cards/dropdowns/modals, `9999px` for badges/pills and the status pill, full for avatars/icon-buttons.
- **Elevation**: flat by default; 1px `--border` hairline for separation; cards rely on surface contrast. Drop shadows only on floating overlays (dropdowns, modals, popovers) at low alpha.

## 5. Components

### Buttons
- **Primary (CTA)** — `background: var(--cta)`, `color: var(--on-cta)`, 8px radius. One per view; the only green element. Reserve for the page's main action.
- **Secondary** — `background: var(--bg-card)`, `color: var(--fg1)`, `1px solid var(--border-md)`, 8px radius. Everything else (Refresh, Export, Edit, Replace…).
- **Ghost / toolbar** (`reading/GhostBtn.tsx`) — transparent, hairline border, `--fg2` text, 8px radius; active state uses neutral `--brand-light` fill + `--brand-deep` text.

### Sidebar (`components/Sidebar.tsx`)
- 220px expanded ↔ **64px collapsed icon rail**; state persists in `localStorage['docent:nav-collapsed']`.
- Collapsed logo is theme-aware: `/favicon.svg` (dark mark) on light, `/favicon-dark.svg` (light mark) on dark. Expanded uses `/logo.svg` / `/logo-dark.svg`.
- **Collapse is read synchronously** in the `useState` initializer and the width transition is gated until after first paint (`navMounted`) so navigating between tabs never animates an expand→collapse shift.
- Active item: `--brand-light` fill + `--brand-deep` ink text (neutral, never green). Tooltips (`title`) appear on icons when collapsed.

### Status bar (`components/StatusBanner.tsx`)
- 48px, `--bg-subtle`, hairline bottom. Stat labels/values in **Inter** (not mono). Idle/done dot = `--success`, working = amber, error = red. The `docent` pill stays sans.

### Tables, badges, modals
- `PaperTable`: hairline row dividers, `--row-hover` hover, drop indicator uses `--brand-deep`.
- `StatusBadge` / `OrderIndicator`: semantic colours per §2.
- Modals: `--bg-card`, 10–12px radius, low-alpha shadow, `--overlay` backdrop. Save/Continue buttons are green CTAs.

## 6. Dark mode & theming rules

- The pre-paint script in `layout.tsx` resolves the theme (`localStorage['docent:dark']` → system → light default) and sets `data-theme` **before first paint**; the loader is white/slate with a teal spinner.
- **Use tokens, not hex**, so colours flip automatically. A hardcoded hex breaks in one theme (this is how the dark-mode icon bug happened).
- **lucide `color=` cannot resolve CSS vars** (it becomes an SVG `stroke` attribute). For theme-aware icons use `style={{ color: 'var(--…)' }}` instead. Only use a literal hex in `color=` when the colour is a fixed semantic that reads on both themes (e.g. status red/amber/teal).

## 7. Do / Don't

**Do**
- Anchor pages on the white canvas; let whitespace + hairlines frame.
- Put a serif `<h1>` + sans sub-line on every page header.
- Use exactly one green `--cta` action per view.
- Keep nav/tab/selection chrome neutral ink.
- Keep status colours semantic (teal/amber/green/red).

**Don't**
- Don't paint chrome green or coral. Green = primary action; coral = reserved signature only.
- Don't use mono for labels — only keys and code.
- Don't hardcode hex in components; use tokens.
- Don't add gradients/glows to heroes.
- Don't bold the serif past 500.

## 8. Build & assets

- Source: `frontend/src/`. Build the shipped static bundle with **`python scripts/build_ui.py`** (run synchronously), which exports to `src/docent/ui_dist/`. Launch with `docent ui` on **port 7432**.
- Keep only the original logo assets in `public/`: `logo.svg`, `logo-dark.svg`, `logo-light.svg`, `favicon.svg`, plus the new `favicon-dark.svg` (collapsed-rail dark mark). Status SVGs unchanged.
- The Dashboard page was archived out of the app (`archive/ui-dashboard/`); root redirects to `/reading`.
