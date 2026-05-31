# CONTEXT - resume hint for next session

**Current Task:** Citation scavenger + UX polish shipped. PR dev → main still pending.

**Key Decisions:**
- cite-graph is a pure discovery list (no downloads, no RM writes) — S2 citation
  graph + OA filter + abstract preview; user adds interesting papers to their RM.
- Zotero ingestion friction is a known arch limitation (no watch folder); tip added
  to HowToAddModal: select collection in Zotero desktop before clicking connector.
- Browser extension idea explored and dropped — doesn't remove steps, can't touch
  paywalled PDFs, real fix is aiming the connector at Docent-Queue collection.

**Next Steps:**
- PR dev → main (672 passed on Windows; run WSL before merging).
- Tier-4 B fan-out primitive — two consumers identified: parallel cite-graph calls
  in deep-research --expand-citations, + parallel Tavily search plan queries.
- deep-research --expand-citations flag: after S2 keyword search, run cite-graph
  on top 2–3 anchor DOIs concurrently, add OA abstracts to source pool.
