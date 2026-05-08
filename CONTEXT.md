# CONTEXT — resume hint for next session

**Current Task:** research-to-notebook tool fully shipped (Phases A–F + budget stubs complete).

**Key Decisions:**
- Docent pipeline: 6-stage (planner→fetch→gap→writer→verifier→reviewer); all model/provider settings BYOK-configurable
- Budget guards: Feynman (daily file-backed, 90% threshold) + OcClient (same pattern, oc_budget_usd)
- update_check.py: generic npm/GitHub checker, 24h cache; research on_startup checks Feynman

**Next Steps:**
1. REAL-LIFE TESTS — run `docent research deep "storm surge Ghana" --backend docent` and verify full pipeline end-to-end; test `to-notebook`, `usage`, Feynman update notification
2. v1.2.0 release — merge dev → main, tag, publish
3. Phase B-hardening (thoughts_review §4/9/10): CLI robustness, state resilience, docent doctor
