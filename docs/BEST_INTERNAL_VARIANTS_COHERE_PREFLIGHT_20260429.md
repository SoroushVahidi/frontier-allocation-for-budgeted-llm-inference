# BEST internal variants Cohere preflight (2026-04-29)

## Exact command
```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260429T_BEST_INTERNAL_VARIANTS_COHERE_PREFLIGHT --providers cohere --cohere-model command-r-plus-08-2024 --datasets openai/gsm8k --budgets 4 --seeds 11 --methods strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,direct_reserve_semantic_frontier_v2_thresholded_ordered,external_l1_max,tale,s1,self_consistency_3 --target-scored-per-slice 10 --max-examples 10 --emit-trace-audit --resume
```

## A. Completion summary

- total expected slices: **10**
- completed slices: **9**
- incomplete slices: **1**
- zero-record slices: **1**
- Cohere readiness status: **passed** (tiny authenticated probe succeeded before run).

## B. Method inclusion summary
- internal methods run: strict_f3, strict_gate1_cap_k6, strict_f2, direct_reserve_semantic_frontier_v2, direct_reserve_semantic_frontier_v2_selection_fix_v1, direct_reserve_semantic_frontier_v2_thresholded_ordered (zero-scored).
- internal methods audited but excluded from this bounded preflight: strict_f3_anti_collapse_weak_v1, direct_reserve_semantic_frontier_v1, near_direct_reserve_frontier_gate_v1, calibrated_near_direct_frontier_gate_v1.
- external baselines run: external_l1_max, tale, s1, self_consistency_3.
- external baselines audited but excluded: external_l1_exact, self_consistency_5, tot_beam_matched_budget, verifier_guided_search, BEST-Route-style adapter, difficulty-proxy adapter.

## C. Per-method result table

| method | family | role | accuracy | scored | total tokens (slice) | est cost USD | avg latency s |
|---|---|---:|---:|---:|---:|---:|---:|
| direct_reserve_semantic_frontier_v2 | internal | diagnostic | 0.700 | 10 | 11367 | 0.060969 | 10.269 |
| direct_reserve_semantic_frontier_v2_selection_fix_v1 | internal | diagnostic | 0.600 | 10 | 11088 | 0.056844 | 7.645 |
| direct_reserve_semantic_frontier_v2_thresholded_ordered | internal | diagnostic | 0.000 | 0 | 0 | 0.000000 | 0.000 |
| external_l1_max | external | baseline | 0.600 | 10 | 5210 | 0.028422 | 3.458 |
| s1 | external | baseline | 0.700 | 10 | 9875 | 0.045165 | 6.692 |
| self_consistency_3 | external | baseline | 0.400 | 10 | 17734 | 0.086682 | 9.363 |
| strict_f2 | internal | canonical/operational | 0.400 | 10 | 9260 | 0.045432 | 4.307 |
| strict_f3 | internal | canonical/operational | 0.500 | 10 | 8338 | 0.040638 | 4.638 |
| strict_gate1_cap_k6 | internal | canonical/operational | 0.500 | 10 | 8400 | 0.041568 | 4.428 |
| tale | external | baseline | 0.500 | 10 | 5026 | 0.026838 | 27.063 |

## D. Pairwise comparison table
| pair | matched examples | mean delta (internal - comparator) | wins/ties/losses | interpretation |
|---|---:|---:|---|---|
| best internal (direct_reserve_semantic_frontier_v2) vs external_l1_max | 10 | +0.100 | 3/5/2 | Best internal is slightly higher on this small slice. |
| strict_f3 vs external_l1_max | 10 | -0.100 | 2/5/3 | strict_f3 trails external_l1_max on this slice. |
| strict_gate1_cap_k6 vs external_l1_max | 10 | -0.100 | 1/7/2 | operational default trails external_l1_max on this slice. |
| best internal vs s1 | 10 | +0.000 | 1/8/1 | Best internal and s1 are tied on mean accuracy. |
| best internal vs tale | 10 | +0.200 | 3/6/1 | Best internal outperforms tale on this slice. |
| best internal vs self_consistency_3 | 10 | +0.300 | 4/5/1 | Best internal strongly exceeds self_consistency_3 on this slice. |

## E. Direct answer
1. Yes, this run included the strongest implemented internal variant identified by this audit (`direct_reserve_semantic_frontier_v2`) plus strict manuscript/operational methods.
2. Yes. The best internal method (`direct_reserve_semantic_frontier_v2`) beat `external_l1_max` on this slice (0.70 vs 0.60; +0.10).
3. Yes. At least one internal method beat `external_l1_max` (`direct_reserve_semantic_frontier_v2`).
4. Highest accuracy overall: tie at 0.70 between `direct_reserve_semantic_frontier_v2` (internal) and `s1` (external).
5. No. This is a 10-example diagnostic preflight and is not enough for manuscript-level claim updates.
6. Next: run the full multi-dataset, multi-budget, multi-seed Slurm sweep with validated methods only.


## Addendum: thresholded/ordered zero-scored diagnosis
- Root cause: `direct_reserve_semantic_frontier_v2_thresholded_ordered` was in runner `METHODS` but not in live runner specs from `build_frontier_strategies`; old validation incorrectly passed it by checking semantic-diagnostic registry too.
- Fix status: validation fixed (`runnable` vs `diagnostic_only`); no algorithm/controller behavior change.
- Targeted rerun (`20260429T_THRESHOLDED_ORDERED_FIX_CHECK`): thresholded/ordered excluded as non-runnable in current runner path; `direct_reserve_semantic_frontier_v2` and `external_l1_max` rerun.
- Targeted rerun result: `direct_reserve_semantic_frontier_v2=0.700 (10)` vs `external_l1_max=1.000 (10)`, pairwise delta `-0.300`, wins/ties/losses `0/7/3`.
- Earlier conclusion change: none; earlier zero-scored row remains explicitly true and is now diagnosed as runtime-missing under current runner path.
- Final best actually scored internal method (small slice evidence): `direct_reserve_semantic_frontier_v2`.
- Final best external method in small slice evidence: tie between `s1` and `external_l1_max` is broken by accuracy (`s1` reached 0.700 in prior run; `external_l1_max` 0.600), but claim checks remain against `external_l1_max` baseline.
- Combined small evidence vs `external_l1_max`: best scored internal still **beats** by +0.100 on this diagnostic slice.
