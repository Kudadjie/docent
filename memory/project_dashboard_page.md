---
name: project-dashboard-page
description: Planned dashboard page for Docent UI — display cards for Reading and Studio; design + build before v1.2.0 ships
metadata:
  type: project
---

Build a dashboard page in the Docent UI before tagging v1.2.0.

**Why:** Currently no landing/overview page — just individual section pages. A dashboard gives users a high-level view of activity.

**Scope (v1.2.0):** Two display cards only — Reading and Studio (the only active sections right now). No other cards until more sections are built out.

**How to apply:** After Studio UI real-life tests pass, run a design session via Claude design (`/design-shotgun` or similar) to agree on the visual direction, then implement. Do not code before design is approved. Gate on: Studio page tests green → design → implement → ship v1.2.0.
