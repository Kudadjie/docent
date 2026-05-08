---
name: Full UI real-life testing before release
description: Hard rule — user must complete full real-life UI testing across the entire app before any new version is published
type: feedback
---

Do full real-life UI testing across the entire Docent UI before publishing any new release.

**Why:** UI changes ship frequently; programmatic type-checks and lint pass even when interactions are broken. Only a real human clicking through the app catches regressions.

**How to apply:**
- Before running `git tag` or publishing to PyPI, remind the user to test the full UI end-to-end
- Minimum checklist: reading page (sync, add, edit, mark done, export, stats), settings page (edit config fields, check version, clear queue), docs page (scroll, TOC links), dark mode toggle on every page, screen resize behavior
- Do NOT count a release ready until the user explicitly confirms they've done this
- This applies even for "small" releases — scope creep in UI is invisible until you click it
