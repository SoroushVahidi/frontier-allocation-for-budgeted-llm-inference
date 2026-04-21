# Current experiments index (2026-04-21)

## Purpose

This note is the shortest current index for the repository's most important **active experiment families**.

It answers:
- which experiment families matter most right now,
- which scripts launch them,
- which output/report artifacts they produce,
- and how they fit into the current default-model decision path.

## Current experimental center

The repository's current experimental center is:

> **strict-phased early-coverage control under the F1 → F2 → F3 law, plus direct-adversary exact-loss auditing against `reasoning_beam2`, plus controlled learned/capped alternatives.**

This means the current top-priority experiment families are no longer generic frontier sweeps first.
They are the experiments that answer:
- what the best strict-phased default candidate is,
- what still goes wrong against the strongest direct adversary,
- whether learned post-F2 gating is worthwhile,
- and whether hard family-expansion caps help or hurt.

## Highest-priority experiment families now

### 1. Strict-phased force/gate comparison
**Question:** under the strict F1 → F2 → F3 law, should the controller use forced F2, forced F3, Gate 1, Gate 2, or Gate 3?

**Primary scripts:**
- `scripts/run_hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421.py`
- `scripts/run_hundred_three_gate_design_eval_strict_phased.py`

**Primary reports/artifacts:**
- `docs/STRICT_PHASED_HARD_EARLY_COVERAGE_REPORT_20260421T020917Z.md`
- `docs/HUNDRED_CASE_HARD_EARLY_COVERAGE_DEPTH3_EVAL_20260421T020917Z.md`
- `docs/HUNDRED_THREE_GATE_DESIGN_COMPARISON_STRICT_PHASED_20260421T022459Z.md`
- `outputs/hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421T020917Z/`
- `outputs/hundred_three_gate_design_eval_strict_phased_20260421T022459Z/`

**Why it matters:**
This is the current cleanest intervention family for the repo's main bottleneck: upstream tree-entry / branch-family-collapse failure under budget.

### 2. Newest-vs-best exact-loss statistics
**Question:** for the newest selected method, what do the remaining 100 exact losses against the strongest direct adversary look like?

**Primary scripts:**
- `scripts/build_new_hundred_newest_vs_best_failure_statistics.py`

**Primary reports/artifacts:**
- `docs/NEW_HUNDRED_NEWEST_VS_BEST_FAILURE_STATISTICS_20260421T032711Z.md`
- `outputs/new_hundred_newest_vs_best_failure_statistics_20260421T032711Z/`

**Why it matters:**
This is the current strongest exact-loss failure-statistics view for the newest selected method against `reasoning_beam2`.

### 3. Learned post-F2 gate
**Question:** can a learned F2→F3 gate beat the deterministic strict gates and the strict F2 / strict F3 anchors?

**Primary scripts:**
- `scripts/run_learned_f2_to_f3_gate_v1_eval.py`

**Primary reports/artifacts:**
- `docs/LEARNED_F2_TO_F3_GATE_EVAL_20260421T034409Z.md` (or the latest corresponding run)
- `outputs/learned_f2_to_f3_gate_<timestamp>/`

**Why it matters:**
This is the main experiment for moving from hand-designed post-F2 gating to a value-of-computation or learned gate under the strict phased law.

### 4. Hard family-expansion cap
**Question:** does a hard cap on within-family expansions reduce harmful monopolization enough to help overall performance?

**Primary scripts:**
- `scripts/run_hard_max_family_expansions_eval.py`

**Primary reports/artifacts:**
- `docs/HARD_MAX_FAMILY_EXPANSIONS_EVAL_20260421T040333Z.md`
- `outputs/hard_max_family_expansions_eval_20260421T040333Z/`

**Why it matters:**
This is the main blunt-constraint anti-collapse experiment family. It is useful both as a potential safeguard and as a diagnostic of whether family monopolization itself is a major causal driver.

## Current default-model decision path

If your question is "what should the current default promoted model be?", the shortest experiment path is:
1. strict-phased force/gate comparison,
2. newest-vs-best exact-loss statistics,
3. learned post-F2 gate,
4. hard family-expansion cap,
5. broader matched evaluation still pending.

## Current leading method candidates

Pending broader matched evaluation, the strongest current candidates remain:
- **strict Gate 1**,
- **strict Gate 2**,
- with **strict forced F3** still useful as a simple anchor.

## What is current but not front-door priority

These remain useful but are no longer the first recommended experimental entry path:
- legacy frontier-allocation scaffolds,
- older bounded imported-methodology comparisons,
- older anti-collapse bounded-eval passes that predate the strict phased law,
- historical diagnostic bundles superseded by the newer exact-loss/failure-statistics reports.

## Practical navigation rule

If you are unsure where to start:
- use `CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md` for the current interpretation,
- use this file for experiment-family navigation,
- use `CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md` for artifact-family navigation,
- and use `scripts/CANONICAL_START_HERE.md` for runnable entry points.

## Cross-links

Also see:
- `CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
- `CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
- `CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
- `CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`
- `REPO_MAP.md`
