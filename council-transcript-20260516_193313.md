# Council Transcript — Strip Feynman from Docent?
**Date:** 2026-05-16 19:33  
**Advisors:** 5 · **Peer Reviews:** 4/5 (reviewer 5 hit usage limit) · **Chairman:** 1

---

## Original Question

> "I have been thinking. Maybe I should strip feynman out of docent totally. I just loaded some Anthropic credits and tried running feynman through docent and an error surfaced. I know i am about to go down a rabbit hole of errors and solving them. But is it worth the overhead? I mean if I need feynman I could just run the cli. If I can make the docent native as robust of feynman shouldn't I? Because feynman is an early open source product and bugs and breaking changes would surface and I have to deal with them through docent. Sigh. Do you think its worth it?"

---

## Framed Question

Docent is a Python research assistant CLI/MCP tool (solo-maintained, ~v1.2.0) with a "studio" module for AI-powered research pipelines. It has a native free-tier pipeline (Tavily + Semantic Scholar + CrossRef, parallel execution, Claude synthesis) that was recently built. It also integrates Feynman — an early-stage open-source AI research agent CLI — as an optional deep-research backend. The developer just hit an error running Feynman through Docent after loading Anthropic credits, and is worried about absorbing Feynman's upstream instability. Feynman can be run independently via its own CLI. The question: **should Feynman be stripped from Docent entirely, making the native pipeline the sole research backend?** What's at stake: maintenance overhead, codebase complexity, feature parity, user experience, and the solo developer's limited bandwidth.

---

## Advisor Responses

### The Contrarian

The framing of this question already reveals the answer the developer wants to hear — and that's exactly where the danger is.

Stripping Feynman sounds like "simplification," but it's actually a capability bet. The native pipeline (Tavily + Semantic Scholar + CrossRef + Claude synthesis) is fast and cheap, but it is fundamentally a *retrieval-and-stitch* system. Feynman, whatever its instability, represents a qualitatively different research mode — agentic, iterative, capable of following chains of reasoning across sources. These are not substitutes. Removing Feynman doesn't simplify the product; it changes what the product *is*.

The actual problem isn't Feynman's existence in Docent — it's the coupling. One error path through a subprocess call is causing the developer to consider abandoning an entire capability tier. That's a coupling problem, not a feature-fit problem. Fix the abstraction: wrap Feynman behind a proper backend interface with graceful degradation, clear error surfacing, and zero retry logic inside Docent. Let Feynman fail loudly and independently.

The fatal flaw in removing it: the moment Feynman stabilizes — or a successor agentic research tool matures — the developer will want it back. Rebuilding the integration from scratch costs more than maintaining a thin adapter that degrades gracefully today.

One hard question the developer is avoiding: Is the native pipeline actually good enough for the use cases Feynman currently serves? If the answer is "mostly," that's not the same as "yes." Users who came for deep research will notice.

Don't strip Feynman. Strip the tight coupling. The maintenance overhead is in the wiring, not the feature.

---

### The First Principles Thinker

The question as posed is wrong.

"Should Feynman be stripped from Docent?" presupposes the problem is Feynman. It isn't. The actual problem is: **Docent has no stable abstraction boundary between its research logic and its execution backends.**

That's what you're trying to solve. And it has a clean first-principles answer.

If you ask "what is Docent's job?" — it's to give researchers a reliable, composable research pipeline. Reliability requires that upstream instability doesn't propagate inward. The root failure isn't that Feynman is unstable; it's that Feynman's instability reaches Docent's internals with no firewall.

Strip that down further: any external CLI dependency that can fail, change its interface, or break on API key issues should be behind an **isolation layer**, not wired directly into Docent's execution path. That's a design axiom, not a Feynman-specific judgment.

So the real decision is: **should Docent be a single-backend tool, or a backend-agnostic pipeline orchestrator with a stable internal contract?** If the former, yes, strip Feynman. If the latter, the native pipeline and Feynman should both implement the same interface (`ResearchBackend` or similar), so neither one's failure mode touches the other.

Given solo bandwidth, there's a third answer: **strip the integration now, document Feynman as a manual post-processing option in the docs, and revisit when Feynman stabilizes.** This isn't the same as "remove it forever" — it's deferring the abstraction cost until the dependency earns the integration.

What you shouldn't do: keep the current tight coupling and just tolerate the pain. That's not a decision. That's drift.

---

### The Expansionist

The framing here is wrong — you're treating Feynman as a liability when it's actually a distribution channel.

Feynman users who hit Docent's integration are a warm acquisition funnel. They already believe in AI-assisted research; they just found a better-packaged version of the workflow. Strip Feynman out and you're closing that door entirely.

The bigger upside hiding here: the native pipeline you just shipped is *already* better than Feynman for most users — parallel execution, structured synthesis, no external CLI dependency. That's the product. Feynman is now the on-ramp for a specific power-user segment who wants maximum depth and doesn't mind complexity.

Don't strip it — demote it to a clearly-labelled "advanced / experimental" backend with a single wrapper that catches upstream errors gracefully and surfaces a clean fallback message. Two lines of try/except and a `--backend feynman` flag that prints a stability warning. The maintenance overhead drops to near zero because you're no longer responsible for Feynman's internals — you're just a thin caller.

The real opportunity: if Feynman's architecture stabilises or gets abandoned, Docent is positioned to absorb its best ideas into the native pipeline. You're watching a live experiment in AI research agents from the inside. That's intelligence you can't buy.

Killing Feynman now also signals to users that Docent is getting *smaller*. The opposite signal — "we have multiple backends, here's the tradeoff matrix" — signals a maturing platform. That's the story that attracts contributors and eventually sponsors, which solves the solo-maintainer bandwidth problem you're actually worried about.

Contain the blast radius. Don't amputate the upside.

---

### The Outsider

The integration is a trap you can't see because you built it.

From the outside: you have a CLI tool that works, and a separate CLI tool that sometimes breaks. You've connected them, which means your tool now breaks when theirs does. You absorbed their instability without absorbing their codebase. That's the worst position to be in.

Users don't distinguish between "Feynman failed" and "Docent failed." When someone runs `docent studio deep-research` and gets an error, they blame Docent. Your README, your GitHub issues, your support burden. The error you just hit proves this is already happening.

The "optional backend" framing feels safe but isn't. Every integration you maintain is a surface that can break. Optional features don't get tested as rigorously, documentation drifts, and error messages become cryptic. Users who chose Feynman specifically will file bugs you can't fix.

Here's the clean read: you built a native pipeline. It works. It runs in parallel. It's yours. The moment you shipped that, Feynman became redundant overhead — not a feature, a liability.

Strip it. Point users to Feynman's own CLI in a single README line: "For deep research via Feynman, run it directly." That's a one-sentence migration path. Users who want Feynman will find it. You lose nothing except the maintenance cost.

The one thing I'd flag: before you remove it, check if any users actually use the Feynman path in practice. If adoption is zero, the decision is trivial. If it's non-zero, give them a deprecation notice in the next release. Either way, the answer is the same — just the timeline changes.

---

### The Executor

Strip it. Here's the Monday morning reality.

You have a broken integration you need to debug, for a backend you don't control, that a solo user can already run independently via its own CLI. That's three red flags that all point the same direction.

The concrete cost of keeping Feynman:
- Every Feynman upstream release is a potential Docent bug report you have to triage
- Your error surface doubles — users can't tell if the failure is Docent or Feynman
- You're writing defensive wrapper code around an "early-stage" project that will keep changing under you
- The error you just hit is the first of many. Early-stage tools break constantly.

The concrete cost of stripping it:
- One deletion PR, probably under 200 lines
- Update the docs to say "for Feynman, run it directly"
- Done in an afternoon

Feature parity argument is weak here. Feynman is a separate CLI — users who want it can use it. You're not removing the capability from the world, you're removing the maintenance burden from your plate. That's a real distinction.

Your native pipeline already exists and works. That's your moat. Invest there.

First step Monday: `git grep -r "feynman"` to count the actual lines. If it's under 300 lines of integration code, strip it this week. If it's more, that's more reason to strip it — you've already sunk too much into wrapping someone else's unstable tool.

Don't wait for another error. The current error is the diagnostic. Strip it.

---

## Peer Reviews

### Peer Review 1
**Strongest: E (First Principles).** It reframes the question correctly — the problem is a missing abstraction boundary, not Feynman specifically. It gives the developer a durable design axiom and a pragmatic third path (strip now, revisit later) that doesn't foreclose future value.

**Biggest blind spot: C (Expansionist).** "Distribution channel" and "acquisition funnel" make no sense for a solo-maintained CLI with no monetization, no onboarding funnel, and no user analytics.

**All missed:** The developer already built a native pipeline that eliminates Feynman's value proposition. Nobody asked: does the Feynman integration have any real users? Zero users makes the debate academic. Pull usage data first.

---

### Peer Review 2
**Strongest: E (First Principles).** Reframes correctly. ResearchBackend interface suggestion is actionable and architecturally sound. Avoids the binary strip/keep trap.

**Biggest blind spot: C (Expansionist).** SaaS playbook framing ("acquisition funnel", "maturing platform") applied to a hobby-scale CLI. No contributors or sponsors to attract at this stage.

**All missed:** The actual error. If it's a subprocess hanging issue (common on Windows, where Docent runs), the fix is a two-line `timeout` parameter. Error first, architecture second.

---

### Peer Review 3
**Strongest: E (First Principles).** Correctly reframes as architectural coupling problem. "ResearchBackend interface" is concrete. Offers pragmatic middle path without forcing the binary.

**Biggest blind spot: C (Expansionist).** "Distribution channel" wishful thinking. Feynman users don't discover Docent through Feynman. The warm acquisition story requires a user base that doesn't exist yet. Also ignores that absorbing an unstable tool's errors damages reputation with exactly the power users it claims to attract.

**All missed:** How many real users are on the Feynman backend today? Usage data should gate this decision entirely.

---

### Peer Review 4
**Strongest: E (First Principles).** Reframes correctly. Three concrete paths with clear tradeoffs. Produces a reusable design principle.

**Biggest blind spot: C (Expansionist).** No evidence Feynman users are discovering Docent through Feynman — pure speculation. Also undersells maintenance cost of "thin wrapper" around actively-changing early-stage CLI.

**All missed:** The actual error. Subprocess hang, API key issue, interface change? The failure category determines the answer. A one-time auth error argues for keeping Feynman with better error handling. A recurring interface break argues for stripping immediately.

---

## Chairman's Verdict

### Where the Council Agrees

Every advisor agrees the current coupling is the real problem. Whether they recommend stripping Feynman or abstracting it, all five land on the same diagnosis: an external CLI that can fail arbitrarily should not be directly wired into Docent's execution path. The debate is entirely about what to do *after* you accept that premise, not about the premise itself.

All five also agree on one practical point: if you keep Feynman, it must be behind a stable interface with clean error surfacing. No one defends the status quo.

### Where the Council Clashes

**Strip it vs. abstract it.** The Executor (A) and the Outsider (D) say strip it — the maintenance cost is real, users blame Docent for Feynman's failures, and the native pipeline already covers the core use case. The Contrarian (B) and Expansionist (C) say keep it — Feynman represents a qualitatively different research mode (agentic, iterative) that the native retrieval-and-stitch pipeline cannot replicate, and the abstraction cost is a one-time investment. First Principles (E) refuses the binary: strip now and defer the abstraction decision until Feynman earns reintegration.

**What Feynman actually is.** B argues it's a capability tier, not just a backend — removing it changes what Docent *is*, not just how it works. D and A argue it's redundant overhead once the native pipeline shipped. This is the crux, and it's genuinely unresolved in the council because nobody checked whether the native pipeline can actually substitute for Feynman's depth on the research tasks that matter to real users.

**The "distribution channel" argument (C) was unanimously rejected by all four peer reviewers.** That framing dies here. It does not apply to a solo-maintained v1.2.0 CLI.

### Blind Spots the Council Caught

Two blind spots that matter more than any advisor's recommendation:

1. **Nobody knows what broke.** All five advisors argued architecture while ignoring the diagnostic: what was the actual error? A subprocess timeout (common on Windows, where Docent runs) is a two-line fix. An API key misconfiguration is a one-time setup issue. A Feynman interface change is a recurring maintenance tax. The failure category determines the answer.

2. **Nobody knows if anyone uses the Feynman backend.** For a ~v1.2.0 solo project, Feynman adoption is likely zero or near-zero. If that's true, the entire debate is academic. Zero real users means strip it with no deprecation notice and no regret.

### The Recommendation

**Strip the integration now. Do not rebuild the abstraction yet.**

The First Principles framing is correct: defer the abstraction cost until Feynman earns it. The Contrarian is right that the native pipeline and Feynman are not substitutes — agentic iteration is qualitatively different from retrieval-and-stitch. But that argument assumes Feynman is stable enough to be worth the integration. It isn't, by the developer's own evidence. A capability you cannot reliably deliver is not a capability — it's a liability with a marketing description.

The Outsider is right that users blame Docent for Feynman's failures. That reputation cost is not theoretical; the error that triggered this council is proof it has already started.

The correct move: strip the Docent-side integration. Add one line to the README and docs: "For deep research via Feynman, run `feynman research "..."` directly — see [link]." Feynman remains available to users who want it. Your maintenance burden drops to zero. Your error surface shrinks to what you control.

When Feynman stabilizes — meaning: stable subprocess interface, predictable output format, no hanging on Windows — revisit the integration. At that point, implement the ResearchBackend protocol that E describes, and Feynman slots in as a first-class backend. That abstraction is worth building once the dependency earns it. It is not worth building to keep a broken integration alive.

Do not do what C recommends. Do not maintain a "thin wrapper" around an actively-changing early-stage tool. Thin wrappers accumulate debt invisibly.

### The One Thing to Do First

Before touching any code: determine what the actual error was.

Run `git grep -r "feynman" --name-only` to see the integration surface. Then look at the error you hit. If it was a subprocess timeout or Windows pipe issue — a single `timeout=30` parameter may fix it entirely, and the architectural question becomes moot for now. If it was a Feynman interface change (function signature, output format, CLI flag renamed) — that's the recurring maintenance tax pattern, and you strip it today. If it was an API key issue — that's a one-time setup problem, not an architectural one.

The error is the diagnostic. Read it before you make the architectural decision.

---

*Anonymization map: A = Executor, B = Contrarian, C = Expansionist, D = Outsider, E = First Principles*
