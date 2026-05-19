# CONTEXT - resume hint for next session

**Current Task:** Design overhaul from Claude Design v2 files — gradient wash, fonts, ecosystem page, all pages updated.

**Key Decisions:**
- Hero gradient uses 3 colours (BRAND green #18E299 + blue #3B82F6 + violet #8B5CF6) via CSS var `--hero-grad`
- Inter + Geist Mono fonts added via Google Fonts in layout.tsx
- Ecosystem page at /ecosystem — violet accent for companion tools, pink for contribute section
- User is running `npm run dev` (Next.js dev server) not `docent ui`

**Next Steps:**
1. User reviews the live design — ask for feedback on colours/layout
2. Tag v1.2.0 once fully verified
3. Build with `python scripts/build_ui.py` before any release
