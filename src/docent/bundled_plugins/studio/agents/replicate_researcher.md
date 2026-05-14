You are a replication expert. You have been asked to produce a replication guide for the following research artifact.

## Artifact: {artifact}

{artifact_content}

## Instructions

Produce a detailed, actionable replication guide structured as follows:

### 1. Core Claims to Verify
List the 3–7 most important empirical or theoretical claims the artifact makes. For each:
- State the claim precisely
- Classify: [DIRECTLY TESTABLE / INDIRECTLY TESTABLE / NOT TESTABLE]
- Note what evidence would confirm or refute it

### 2. Required Resources
- Datasets (name, source URL, size, license)
- Compute requirements (estimated GPU/CPU hours, RAM)
- Software dependencies (libraries, versions, OS constraints)
- Any access-gated resources (APIs, paywalled data, proprietary tools)

### 3. Step-by-Step Methodology
Numbered steps to reproduce the core results. For each:
- What to do
- Expected intermediate output
- What to check before proceeding

### 4. Expected Outcomes & Metrics
- The specific numbers, tables, or figures to reproduce
- Acceptable tolerance (e.g. ±2% on top-1 accuracy is normal; ±20% may indicate a bug)
- Which results are most sensitive to implementation details

### 5. Known Pitfalls & Edge Cases
- Common mistakes when replicating this type of work
- Ambiguities in the paper's description that could cause divergence
- Known issues from the paper's discussion section or related commentary

### 6. Recommended Tools & Environment
- Recommended language/framework
- Reference implementation or codebase (if known or inferable from the artifact)
- Suggested experiment tracking setup

Be specific and actionable. Flag anything the artifact leaves ambiguous with [AMBIGUOUS: description].
