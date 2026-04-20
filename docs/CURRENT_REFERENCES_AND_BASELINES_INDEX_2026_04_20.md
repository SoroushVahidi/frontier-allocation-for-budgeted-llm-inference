# Current references and baselines index (2026-04-20)

## Purpose

This note is the compact current index for:
- the most relevant reference buckets,
- the current important baseline families,
- and the safest starting points for paper-facing citation and comparison planning.

It is a navigation note, not a formal bibliography.

## Fastest reading path

If you want the shortest current literature/baseline path, read:
1. `CURRENT_SAFE_CLAIMS.md`
2. `CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
3. `CURRENT_BRANCH_ALLOCATION_AND_ANTI_COLLAPSE_REFERENCES_2026_04_20.md`
4. `CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md`
5. `main_baselines.md`
6. `FULL_METHOD_COMPARISON_STATUS_2026_04_18.md`

## Current most relevant reference buckets

### 1. Adaptive test-time compute allocation
This remains the broad neighboring AI framing.

### 2. Metareasoning / value of computation
Still important as the conceptual backbone for fixed-budget next-step allocation.

### 3. Fixed-budget small-gap allocation / best-arm framing
Still useful for understanding hard close-branch decisions under limited budget.

### 4. Budget-aware tree search / widen-vs-deepen control
This is now one of the most important newer buckets for the repo's current branch-family anti-collapse direction.

### 5. Residual-progress / low-marginal-gain allocation
Increasingly important because the repo is now experimenting with low-marginal-gain same-family cooldown and related residual-progress logic.

### 6. Process signals / verifiers / completion-aware evidence
Useful as ingredients and bounded corrections, not as the whole method story.

### 7. Answer aggregation / final-answer handling
Still important because not all residual errors are pure tree-generation failures.

## Current most useful focused reference memo

For the current branch-family anti-collapse paper direction, use first:
- `CURRENT_BRANCH_ALLOCATION_AND_ANTI_COLLAPSE_REFERENCES_2026_04_20.md`

That note is the current shortest answer to:
- which recent references are closest to fixed-budget branch-family control,
- which ones motivate low-marginal-gain cooldown logic,
- and how to separate closest method neighbors from ingredient or adjacent-only references.

## Current baseline priorities

### Most important practical comparison target
- `self_consistency_3`

### Important internal / broad-family baselines
- broad diversity baseline variants
- earlier strong broad-family variants
- reasoning-style internal baselines still used in canonical comparison bundles
- current anti-collapse and low-marginal-gain refinement variants inside the same broad family

### Important external / adjacent baselines
Use the current comparison and completeness notes for exact runnable status, especially for:
- s1
- TALE
- L1
- BEST-Route
- When To Solve, When To Verify
- cascade-routing style neighbors
- MoB / best-of-N style neighbors
- ReST-MCTS / search-guided neighbors

## Current writing rule

When writing the paper, keep these separated:
- **core conceptual references**,
- **closest branch-allocation / tree-search neighbors**,
- **direct/near-direct comparison baselines**,
- **adjacent baselines**,
- **ingredient references**.

Do not blur them into one undifferentiated related-work paragraph.

## Current safest reference-facing documents

- `CURRENT_BRANCH_ALLOCATION_AND_ANTI_COLLAPSE_REFERENCES_2026_04_20.md`
- `CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md`
- `REFERENCES_AUDIT_AND_CURATION_2026_04_18.md`
- `main_baselines.md`
- `BASELINE_REPAIR_AND_STATUS_AUDIT_20260420T225833Z.md`
- `main_datasets.md`
- `FULL_METHOD_COMPARISON_STATUS_2026_04_18.md`
- `external_baseline_completeness_report.md`

## Current baseline status matrix (v1)

- `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json` (and `.csv`)
- Regenerate: `python scripts/build_baseline_repair_and_status_audit.py`

## Current results cross-link

For artifact-backed result bundles and current comparison outputs, see:
- `CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`

## Practical paper-planning rule

Use this index first when you need to answer:
- which baseline families matter most now,
- which references belong in the main paper rather than only the appendix,
- which current references are closest to the repo's anti-collapse / branch-allocation direction,
- and which current comparison artifacts support those claims.
