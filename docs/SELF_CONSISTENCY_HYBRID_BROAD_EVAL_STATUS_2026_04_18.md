# Self-consistency hybrid broad evaluation status (2026-04-18)

## Purpose

This pass tests whether the bounded selective self-consistency hybrid can move from a localized hard-state gain into broad multi-dataset competitiveness against `self_consistency_3`.

## What was compared

Matched simulator setting (same seeds, budgets, subsets, controller harness):
- `self_consistency_3`
- `adaptive_min_expand_1` (canonical pre-hybrid representative)
- `intermediate_trap_aware_near_tie_v1`
- `selective_sc_hybrid_v1`

Context-only (not executed in this harness):
- `multistep_k3_current`
- `best_bounded_learned_branch_score_current`

## Datasets / budgets / seeds

- `openai/gsm8k`
- `HuggingFaceH4/MATH-500`
- `HuggingFaceH4/aime_2024`
- `olympiadbench`
- budgets: `4, 6, 8`
- seeds: `11, 23, 37`
- subset size per dataset/seed: `24`

## Broad result: does hybrid materially narrow the overall gap?

Short answer: **No (not materially).**

From `aggregate_comparison_summary.json` / `budget_gap_reduction.json`:
- mean acc over budgets:
  - `self_consistency_3`: `0.4931`
  - `adaptive_min_expand_1`: `0.3773`
  - `selective_sc_hybrid_v1`: `0.3935`
- gap to self-consistency:
  - vs canonical: `0.1157`
  - vs hybrid: `0.0995`
  - gap reduction: `0.0162`
- material narrowing flag (thresholded in this pass): `false`

Interpretation:
- hybrid improves over canonical broadly,
- but not enough to claim broad displacement or parity with `self_consistency_3`.

## Where hybrid helps

- Hybrid beats canonical on a non-trivial fraction of matched instances:
  - `where_hybrid_beats_canonical.rate = 0.2488`
- Gap reduction is stronger at higher budgets than at budget 4:
  - budget 6 reduction: `+0.0243`
  - budget 8 reduction: `+0.0278`

## Where hybrid still fails vs self-consistency

- Hybrid still loses to self-consistency on many matched examples:
  - `where_hybrid_loses_to_sc.rate = 0.2905`
- Hard/near-tie slices remain SC-favored in this run:
  - near-tie acc: SC `0.5000` vs hybrid `0.3540`
  - disagreement acc: SC `0.7143` vs hybrid `0.2857`

## Activation behavior audit

From `activation_behavior_summary.json`:
- hard-case activation rate: `0.8484` (very high)
- consensus override rate: `0.0023` (very low)
- near-tie activation rate: `0.7847`
- disagreement activation rate: `0.0081`
- wasted-on-easy rate: `0.1516`
- missed-hard-case rate: `0.0174`

Interpretation:
- activation is **not too rare**;
- likely **too frequent** for hard-case mode,
- but consensus override is extremely conservative/rare.

## Failure-gap taxonomy (SC still ahead)

From `failure_gap_taxonomy.json`:
- dominant remaining reasons:
  - `insufficient_diversity_or_aggregation`: `236`
  - `over_conservative_gating`: `15`
- mapped categories:
  - premature commitment: present, smaller than diversity/aggregation issue
  - insufficient diversity + weak answer aggregation: dominant
  - wrong activation region: not dominant in this pass
  - cost/budget inefficiency: not dominant in this pass summary

## Hard conclusion

The selective SC hybrid is now a **real bounded improvement over the canonical pre-hybrid representative**, but in this broad pass it remains primarily a hard-state-oriented refinement and **not yet a serious broad competitor to `self_consistency_3`**.

Most of the remaining broad gap is still consistent with:
1. insufficient effective diversity when it matters,
2. weak/rare answer aggregation override despite frequent activation,
3. continued SC advantage from robust multi-path aggregation and reduced commitment risk.
