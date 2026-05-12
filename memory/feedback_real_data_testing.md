---
name: Insist on real-data testing after every build step
description: After every Docent build step, prompt the user to manually test the new behavior with real-life data (real PDFs, real folders, real DOIs) — not just programmatic smoke tests. Don't accept "import works" or "--version prints" as verification.
type: feedback
---

After every Docent build step, prompt the user to manually test the new behavior with real-life data — not just programmatic smoke tests like `--version`, import checks, or type checks.

**Why:** User flagged on 2026-04-26 that our "verifiable success" smoke tests have been technical (does it import, does the command exist, does the type check pass) rather than functional (does `paper add <real-DOI>` actually pull the right metadata? does `paper scan --folder` against a real folder of PDFs produce the expected database entries? did the first-run config prompt actually fire on the user's machine?). Karpathy-guideline #4 ("verifiable success") in `CLAUDE.md` already calls for happy path + obvious failure modes — we'd been doing the cheap half. Real-data tests catch class-of-bug that programmatic ones can't: encoding issues, network/API quirks, Rich rendering on the user's terminal, Windows path edge cases, first-run UX.

**How to apply:** When closing out a build step, do NOT just run a programmatic smoke test and check the box in `build_progress.md`. Instead:
1. State explicitly what real-world test the user should run, with a concrete invocation (e.g. "run `docent reading sync-from-mendeley` against your live Mendeley library, confirm entries appear; then run `docent reading next` and confirm the overlay shows fresh metadata").
2. Include at least one obvious-failure test (e.g. "now run it on a folder with one corrupted PDF — does it skip gracefully?").
3. Wait for the user to report back before marking the step done.
4. If the test surfaces a bug, the step is not done — fix and re-test before checking the box.

Apply this retroactively too: if a recent step shipped without real-data validation, surface that as an open item before moving forward.

**Hard rule (added 2026-05-08): no UI implementation until real-life tests pass.**
Never open a UI task for a tool that hasn't been real-life tested. The sequence is always: ship CLI → real-life test → implement UI. No exceptions.

**Pending real-life tests (research tool, shipped 2026-05-08):**
- `docent research deep "<topic>" --backend docent` — full 6-stage Docent pipeline end-to-end
- `docent research to-notebook` — sources package written, NotebookLM opens in browser
- `docent research usage` — Feynman + OC daily spend display
- Feynman update notification visible at startup
- After all pass → implement research tool into UI
