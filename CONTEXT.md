# CONTEXT - resume hint for next session

**Current Task:** Studio UI built (mock data). Settings page updated with doctor + API keys.

**Key Decisions:**
- Studio page uses simulated streaming (setTimeout); real backend wiring is next session
- `/api/doctor` runs 19 checks in parallel; settings page auto-runs it on load
- Settings API keys section uses `SecretKeyRow` — always edits empty, never exposes raw value

**Next Steps:**
1. Wire Studio to real backend: add `/api/studio/run` SSE endpoint → replace mock streaming
2. Wire sync actions (search-papers, get-paper, config-show/set) as JSON endpoints
3. Tag v1.2.0 once Studio backend is live
