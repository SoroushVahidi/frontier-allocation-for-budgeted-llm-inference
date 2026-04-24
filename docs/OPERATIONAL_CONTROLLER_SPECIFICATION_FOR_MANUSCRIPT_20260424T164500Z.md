# Operational controller specification for manuscript (20260424T164500Z)

This document maps the manuscript controller description to exact implementation-level behavior in code.

## Scope

- Primary manuscript-facing methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`
- Comparator-boundary method: `external_l1_max`
- Source implementation family: `GlobalDiversityAggregationController` + output-layer repair pipeline

## Operational definitions

- **Branch data structure**: `BranchState` stores branch id, steps, score, predicted answer, done/pruned flags, verify count, and histories.
- **Frontier state**: mutable `branches` list in `GlobalDiversityAggregationController.run()`; active frontier is non-pruned subset.
- **Answer-group construction**: `_normalize_answer()` canonicalizes numeric/text outputs into answer-group keys; per-step support tracked in `answer_support_counts`.
- **Branch family definition**: `branch_family_ids` assigns each branch to a root-family lineage; repeat/cap controls operate per family.
- **V_t(b) implementation**: continuation value base from `self.scorer.score_branch(b)`, then combined with quality/readiness/diversity-derived terms.
- **A_t(b) implementation**: allocation priority after anti-collapse adjustments (`adjusted_priority_delta`) and optional gate interventions.
- **C_t(b) implementation**: commit evidence from group support margin, top-group readiness, and one-step continuation estimate.
- **R_t(b) implementation**: output-layer repair via deterministic extraction/canonicalization and bounded rescue (`choose_repair_answer`).
- **Commit rule**: `_commit_by_answer_group_margin` requires action minimum + support threshold + support margin + readiness + low continuation value.
- **Budget enforcement (4/6/8)**: action loop guarded by `while actions < self.max_actions`; each expand/verify consumes budget action units.

## Method instantiations used in manuscript runs

- `strict_f3` runtime strategy name:
  - `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1`
- `strict_gate1_cap_k6` runtime strategy name:
  - `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control`
- `strict_f2` runtime strategy name:
  - `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1`
- `external_l1_max` runtime strategy name:
  - `external_l1_max`

## strict_f3 vs strict_gate1_cap_k6 (implementation difference)

- Both share the same core global-diversity/anti-collapse machinery.
- `strict_gate1_cap_k6` additionally enables hard max-family expansion cap logic (base cap 6 with mode-controlled relax behavior).
- `strict_f3` does not apply the strict gate-k6 cap and uses depth-3 early root coverage forcing configuration.
- `strict_f2` is the depth-2 coverage-forced variant without k6 family-cap gating.

## Heuristic vs closed-form boundary

- Implementation is deterministic and auditable, but several control terms are not encoded as a single closed-form formula.
- The score used operationally is a composition of continuation scoring + support/quality/readiness + anti-collapse gates/penalties.
- Strategy names encode some operational semantics (e.g., gate/cap mode), requiring explicit lookup tables for manuscript transparency.

## Appendix: Operational controller specification

We instantiate the manuscript controller as a deterministic fixed-budget allocator over a frontier of branch states. At each step, every active branch receives an implementation-level continuation priority composed from branch score, answer-group support structure, and anti-collapse regularizers. The controller then applies bounded intervention gates (coverage floor, early answer-group preservation, repeat-family cooldown, conditional family cap) before selecting a single action. The commit mechanism is not free-form: it is triggered only when support concentration and readiness exceed predefined thresholds while one-step continuation value is sufficiently low. Output extraction and repair are likewise deterministic: branch-local answer extraction is preferred, canonicalization is dataset-aware, and rescue only applies under explicit consensus conditions. This appendix-level specification should be treated as the experiment-level ground truth for reproducibility.

## Recommended main-text replacement paragraph

“Our controller score should be interpreted as a compact abstraction of a deterministic operational policy rather than a single closed-form objective. The experiments use an explicit implementation-level controller with fixed thresholds, branch-family caps, answer-group support aggregation, and bounded output-layer repair; Appendix X provides the exact operational definitions and code-level parameterization used in all reported runs.”
