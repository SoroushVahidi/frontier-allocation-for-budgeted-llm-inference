# PAPER_METHOD_NAMING_POLICY

Naming policy to keep manuscript wording consistent and reviewer-safe.

## Required primary method names

- **Broader strict-phased operational default**: `strict_gate1_cap_k6`
- **Canonical manuscript-facing matched-surface internal winner**: `strict_f3`

Always include the surface qualifier when first mentioned in a section.

## Recommended terminology

- Use **"fixed-budget adaptive test-time compute allocation"** as the project umbrella.
- Use **"next-step branch allocation"** for per-step compute routing decisions.
- Use **"answer-group-level commit control"** for continue-vs-commit behavior.
- Use **"anti-collapse branch-family control"** for family monopolization mitigation.
- Use **"diversity realization under budget"** for controlled alternative-branch coverage outcomes.

## Avoid / deprecate in manuscript text

- Avoid recentering text on the older **binary revise-routing** framing.
- Avoid unqualified "default winner" (must say which surface).
- Avoid swapping terms mid-section (e.g., "aggregation" vs "group preservation") without a first-use alias.

## Crosswalk

- "answer-support aggregation" ≈ "answer-group preservation/maturation" (same controller layer in this repo).
- "matched manuscript-facing surface" = the internal comparison surface used for `strict_f3` claims.
- "broader strict-phased surface" = operational surface for `strict_gate1_cap_k6` default claims.

## Baseline status labels (paper-safe)

Use the same bucket names as `EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md`:
- `main_table_ready`
- `appendix_only`
- `repo_only_not_paper_facing_yet`
- `discuss_only`
