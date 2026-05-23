# Docent Design System

## Overview

**Docent** is a personal AI assistant built for graduate students — helping them read, research, write, and navigate the demands of advanced academic life. The product is a web/mobile app that combines AI chat, document analysis, citation management, and research synthesis into one focused tool.

The visual language is inspired by Mintlify's documentation-as-product philosophy: clean white canvases, confident typography, and a signature green accent that signals intelligence and freshness without overwhelming the interface.

---

## Sources

- **Design reference:** `uploads/DESIGN-mintlify.md` — A comprehensive Mintlify-inspired design system specification covering colors, type, spacing, components, and dark mode. This was the primary design specification provided.
- No codebase or Figma links were provided. The design system was constructed from the written specification.

---

## CONTENT FUNDAMENTALS

### Tone & Voice

Docent speaks like a brilliant, encouraging academic colleague — not a corporate product, and not a generic chatbot. The voice is:

- **Calm and precise.** Short sentences. No filler. Every word earns its place.
- **Encouraging, not cheerleading.** "You're making progress" beats "Amazing work! 🎉"
- **First-person from the product:** "I found 3 sources that may help." The app speaks as "I" / "me."
- **Second-person to the user:** "Your thesis draft…", "You might consider…"
- **Academic-adjacent but not stuffy.** Docent knows what a lit review is, but explains it plainly.

### Casing

- **Headlines:** Sentence case only. ("Build your literature review faster" not "Build Your Literature Review Faster")
- **Buttons & CTAs:** Sentence case. ("Get started", "Upload paper", "Ask Docent")
- **Labels & navigation:** Sentence case, no periods.
- **Uppercase reserved for:** technical mono labels, section stamps (e.g., "BETA"), badge tags.

### Emoji

**None in the UI.** The interface is clean and scholarly. Emoji are never used as icons or decorative elements. Occasional ✓ checkmarks are acceptable in confirmations only.

### Specific Examples

| Context | Good | Avoid |
|---------|------|-------|
| Hero headline | "Your grad school AI, finally." | "The #1 AI Tool for Grad Students! 🎓" |
| Empty state | "No papers yet. Upload one to get started." | "You haven't added anything yet! Let's fix that 🚀" |
| Error | "Something went wrong. Try again." | "Oops! That's on us. 😅" |
| Onboarding | "What are you working on?" | "Welcome! We're SO excited to have you here!" |
| AI response | "I found two conflicting arguments in chapters 3 and 4." | "Great question! Let me help you with that!" |

---

## VISUAL FOUNDATIONS

### Color System

- **Background:** Pure white (`#ffffff`) throughout. No gray background sections.
- **Primary text:** Near-black (`#0d0d0d`) — softer than pure black for extended reading.
- **Body text:** Gray 700 (`#333333`) for paragraphs, descriptions.
- **Muted text:** Gray 500 (`#666666`) for secondary labels, captions.
- **Brand accent:** Green (`#18E299`) — used sparingly for CTAs, hover states, focus rings, brand identity. Never decorative fills.
- **Light green surface:** (`#d4fae8`) for badges, hover tints.
- **Dark green:** (`#0fa76e`) for text on green surfaces.

### Typography

- **Primary:** Inter (loaded from Google Fonts or bundled)
- **Monospace:** Geist Mono (for code labels, technical tags, AI model references)
- **Only three weights:** 400 (reading), 500 (UI/interaction), 600 (headings/announcement)
- **Display tight tracking:** -1.28px at 64px, -0.8px at 40px — compressed, deliberate headlines
- **Uppercase signals:** Section labels and mono badges use uppercase + positive tracking (0.6–0.65px)

### Backgrounds & Surfaces

- White (`#ffffff`) is the universal surface.
- Hero sections use a soft atmospheric green-to-white gradient wash.
- Cards are white on white, separated by `1px solid rgba(0,0,0,0.05)` borders.
- No alternating gray backgrounds. No color section fills. Depth through whitespace and borders only.
- Near-white tint (`#fafafa`) for very subtle surface differentiation (e.g., logo grids, secondary panels).

### Spacing

- Base unit: **8px**
- Scale: 4, 8, 12, 16, 24, 32, 48, 64, 96px
- Card padding: 24–32px
- Section padding: 48–96px vertical
- Component gaps: 8–16px

### Corner Radii

| Name | Value | Use |
|------|-------|-----|
| xs | 4px | Inline code, tiny tags, tooltips |
| sm | 8px | Nav buttons, icon containers |
| md | 16px | Cards, content containers |
| lg | 24px | Featured cards, panels |
| pill | 9999px | Buttons, inputs, badges — the **signature shape** |

### Borders

- **Default card border:** `1px solid rgba(0,0,0,0.05)` — barely visible
- **Interactive element border:** `1px solid rgba(0,0,0,0.08)`
- No heavy outlines. Separation is entirely border-opacity-driven.

### Shadows & Elevation

- **Level 0 (flat):** No shadow. Page background, text blocks.
- **Level 1 (card):** `rgba(0,0,0,0.03) 0px 2px 4px` — ambient whisper
- **Level 2 (button):** `rgba(0,0,0,0.06) 0px 1px 2px` — micro-depth
- No heavy drop shadows. The system is paper-flat with borders doing most of the work.

### Animation & Hover States

- **Hover on buttons/links:** opacity 0.9, color shift to brand green (`#18E299`) for text links
- **Hover on cards:** subtle border darkening from 5% to 8% opacity
- **Transitions:** `opacity 0.15s ease`, `border-color 0.15s ease` — fast, restrained
- **No bounces, no springs.** Fades and color shifts only.
- **No scroll animations.** Content appears statically.

### Imagery

- Product screenshots use subtle 1px borders and 16–24px radius containers
- Atmospheric gradient behind hero images (green-white cloud wash)
- Imagery color temperature: **cool, clean** — no warm filters
- No hand-drawn illustrations, no grain textures, no decorative patterns

### Dark Mode

- Background: `#0d0d0d`, Text: `#ededed`, Muted: `#a0a0a0`
- Brand green unchanged: `#18E299`
- Card: `#141414`, Borders: `rgba(255,255,255,0.08)`
- Shadows stronger in dark mode: `rgba(0,0,0,0.4) 0px 2px 4px`

---

## ICONOGRAPHY

No proprietary icon font or custom SVG set was specified. Based on the Mintlify design system and Docent's academic context, the following approach is used:

- **Icon library:** Lucide Icons (CDN: `https://unpkg.com/lucide@latest`) — clean, stroke-weight consistent, matches the minimalist aesthetic
- **Style:** Stroke-only (no filled icons), 1.5px stroke weight, consistent 20–24px size in UI
- **No emoji used as icons**
- **No unicode characters as icons**
- Academic-relevant icons used: `BookOpen`, `FileText`, `Search`, `MessageSquare`, `Upload`, `Sparkles`, `GraduationCap`, `FlaskConical`, `Quote`
- Lucide substituted for any custom iconography — **flag:** if Docent has a proprietary icon set, provide SVGs to replace these.

---

## File Index / Manifest

```
README.md                       ← This file: full design system documentation
SKILL.md                        ← Agent skill definition
colors_and_type.css             ← CSS custom properties: colors, type, spacing
assets/                         ← Logos and brand assets
  logo.svg                      ← Docent wordmark (generated)
  favicon.svg                   ← Docent favicon mark
preview/                        ← Design System tab cards
  colors-primary.html
  colors-neutrals.html
  colors-semantic.html
  colors-dark-mode.html
  type-display.html
  type-body.html
  type-mono.html
  spacing-tokens.html
  spacing-radii.html
  elevation.html
  buttons.html
  inputs.html
  cards.html
  badges.html
  navigation.html
ui_kits/
  app/
    README.md
    index.html                  ← Main app prototype (chat + document view)
    Sidebar.jsx
    ChatThread.jsx
    DocumentPanel.jsx
    Header.jsx
    Onboarding.jsx
```
