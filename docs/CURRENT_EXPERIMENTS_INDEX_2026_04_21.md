# Current experiments index (2026-04-21)

## Purpose

This note is the shortest current index for the repository's most important **active experiment families**.

It answers:
- which experiment families matter most right now,
- which scripts launch them,
- which output/report artifacts they produce,
- and how they fit into the current default-model story.

## Current experimental center

The repository's current experimental center is:

> **strict-phased early-coverage control under the F1 → F2 → F3 law, direct-adversary exact-loss auditing against `reasoning_beam2`, and controlled learned/capped alternatives evaluated against the current finalized broad default.**

## Highest-priority experiment families now

### 1. Final strict-phased default decision
**Question:** which strict-phased finalist should be the broad default promoted model on the evaluated broader surface?

**Primary script:**
- `scripts/run_broader_strict_phased_default_decision_eval.py`

**Primary reports/artifacts:**
- `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- `outputs/final_strict_phased_default_decision_eval_20260421T042913Z/`

**Current conclusion:**
- `strict_gate1_cap_k6` is the current broad default promoted model on the evaluated surface.

### 2. Canonical strict_gate1_cap_k6-vs-best exact-loss statistics
**Question:** for the finalized default `strict_gate1_cap_k6`, what do the remaining 100 exact losses against the strongest direct adversary look like?

**Primary script:**
- `scripts/build_canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics.py`

**Primary reports/artifacts:**
- `docs/CANONICAL_HUNDRED_STRICT_GATE1_CAP_K6_VS_BEST_FAILURE_STATISTICS_20260421T160120Z.md`
- `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/`

### 3. Strict-phased force/gate comparison stack
**Question:** how did strict forced F2/F3 and strict Gate 1/2/3 compare before the final broader default decision?

**Primary scripts:**
- `scripts/run_hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421.py`
- `scripts/run_hundred_three_gate_design_eval_strict_phased.py`

**Primary reports/artifacts:**
- `docs/STRICT_PHASED_HARD_EARLY_COVERAGE_REPORT_20260421T020917Z.md`
- `docs/HUNDRED_THREE_GATE_DESIGN_COMPARISON_STRICT_PHASED_20260421T022459Z.md`

### 4. Hard family-expansion cap follow-up
**Question:** does a hard cap on within-family expansions help enough to remain part of the default-model story, and what K values matter?

**Primary scripts:**
- `scripts/run_hard_max_family_expansions_eval.py`

**Primary reports/artifacts:**
- `docs/HARD_MAX_FAMILY_EXPANSIONS_K456_EVAL_20260421T041916Z.md`
- `outputs/hard_max_family_expansions_k456_eval_20260421T041916Z/`

**Current conclusion:**
- `K = 6` is the strongest tested capped variant and the one that entered the final broader default-decision pass.

### 5. Learned post-F2 gate
**Question:** can a learned F2→F3 gate beat the deterministic strict gates and the strict force anchors?

**Primary script:**
- `scripts/run_learned_f2_to_f3_gate_v1_eval.py`

**Primary reports/artifacts:**
- `docs/LEARNED_F2_TO_F3_GATE_EVAL_20260421T034409Z.md` (or the latest corresponding run)
- `outputs/learned_f2_to_f3_gate_<timestamp>/`

**Current role:**
- promising controlled alternative, not current default.

### 6. Manuscript-facing matched-surface multi-seed stability rerun
**Question:** does the manuscript-facing winner claim (`strict_f3`) remain stable under a materially larger seed set on the exact matched manuscript surface?

**Primary script:**
- `scripts/run_matched_surface_multiseed_main_comparison.py`

**Primary reports/artifacts:**
- `docs/MATCHED_SURFACE_MULTI_SEED_MAIN_COMPARISON_20260423T002000Z.md`
- `outputs/matched_surface_multiseed_main_comparison_20260423T002000Z/`

### 7. Manuscript-facing matched-surface multi-seed strict_f3 component-ablation rerun
**Question:** on the exact manuscript-facing matched surface, which strict_f3 components are genuinely responsible for gains vs upstream/downstream failure slices?

**Primary script:**
- `scripts/run_matched_surface_multiseed_strict_f3_ablation.py`

**Primary reports/artifacts:**
- `docs/MATCHED_SURFACE_MULTI_SEED_STRICT_F3_ABLATION_20260423T120000Z.md`
- `outputs/matched_surface_multiseed_strict_f3_ablation_20260423T120000Z/`

### 8. Manuscript-facing matched-surface s1 fairness-closure lane
**Question:** is `s1` reviewer-defensible as a main-table external comparator under strict matched realized-token accounting on the canonical manuscript-facing surface?

**Primary script:**
- `scripts/run_s1_matched_surface_fairness_closure.py`

**Primary reports/artifacts:**
- `docs/S1_MATCHED_SURFACE_FAIRNESS_CLOSURE_20260423T151500Z.md`
- `outputs/s1_matched_surface_fairness_closure_20260423T151500Z/`

## Current default-model story

If your question is "what is the current broad default promoted model?", the shortest experiment path is:
1. `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
2. `CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
3. `CANONICAL_HUNDRED_STRICT_GATE1_CAP_K6_VS_BEST_FAILURE_STATISTICS_20260421T160120Z.md`
4. `HARD_MAX_FAMILY_EXPANSIONS_K456_EVAL_20260421T041916Z.md`

## Current leading method candidates

The current broader evaluated default is:
- **`strict_gate1_cap_k6`**

Important neighboring anchors that still matter for interpretation:
- **`strict_gate1`**
- **`strict_f2`**
- **`strict_f3`**
- **`strict_gate2`**

## What is current but not front-door priority

These remain useful but are no longer the first recommended experimental entry path:
- legacy frontier-allocation scaffolds,
- older bounded imported-methodology comparisons,
- older anti-collapse bounded-eval passes that predate the strict phased law,
- historical diagnostic bundles superseded by the newer exact-loss/failure-statistics and final default-decision reports.

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
- `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- `CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
- `CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`
- `REPO_MAP.md`
