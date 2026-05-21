# CONTEXT - resume hint for next session

**Current Task:** UI polish sprint — theme flash, loading screen, hydration errors, dashboard gradient.

**Key Decisions:**
- Loading screen: body::before/::after via injected <style> in <head>; 2s min + window.load; spins correctly
- Theme flash fixed via prefers-color-scheme CSS cascade (no JS needed for matching OS preference)
- Dashboard cards/tokens all converted to CSS variables; no dark?color:color inline patterns remain

**Next Steps:**
1. Review and tweak guided tour text across all 6 pages (still pending from before this session)
2. Run UI test checklist against http://localhost:7432
3. Fix any failures, then tag v1.2.0
