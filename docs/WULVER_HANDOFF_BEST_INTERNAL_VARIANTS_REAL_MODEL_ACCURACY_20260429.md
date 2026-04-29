# WULVER handoff — best internal variants real-model accuracy full run

> **Historical / provenance-only note (Codex environment):** this document is a Wulver/Slurm handoff artifact and is **not directly executable in the current Codex-only environment** without manual porting to local chunked execution scripts.

- methods included in full run: `strict_f3, strict_gate1_cap_k6, strict_f2, direct_reserve_semantic_frontier_v2, direct_reserve_semantic_frontier_v2_selection_fix_v1, external_l1_max, tale, s1, self_consistency_3`.
- methods excluded and why:
  - `direct_reserve_semantic_frontier_v2_thresholded_ordered`: diagnostic-only in current runner path (`validation_status=diagnostic_only`, runtime missing from runner specs).
  - `strict_f3_anti_collapse_weak_v1, direct_reserve_semantic_frontier_v1, near_direct_reserve_frontier_gate_v1, calibrated_near_direct_frontier_gate_v1`: audited/implemented but outside this bounded strongest-method full comparison scope.
  - `external_l1_exact, self_consistency_5, tot_beam_matched_budget, verifier_guided_search, BEST-Route-style adapter, difficulty-proxy adapter`: not selected here (unregistered/not implemented for this runner or out of scope).

## Exact full command
`python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260429T_BEST_INTERNAL_VARIANTS_REAL_MODEL_ACCURACY_FULL --providers cohere --cohere-model command-r-plus-08-2024 --datasets openai/gsm8k,HuggingFaceH4/MATH-500 --budgets 4,6,8 --seeds 11,23 --methods strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3 --target-scored-per-slice 50 --max-examples 50 --resume --emit-trace-audit`

- exact sbatch command: `sbatch batch/run_best_internal_variants_real_model_accuracy_20260429.sbatch`
- expected output directory: `outputs/cohere_real_model_cost_normalized_validation_20260429T_BEST_INTERNAL_VARIANTS_REAL_MODEL_ACCURACY_FULL/`
- expected summary files: `method_summary.csv`, `slice_summary.csv`, `pairwise_comparisons.csv`, `incomplete_slices.csv`, `cost_normalized_summary.csv`, `claim_safety_table.csv`.
- resume command: rerun exact full command with `--resume`.
- summarize-only/postprocess command: rerun exact full command with `--summarize-only --resume`.
- inspect incomplete slices: `cat outputs/.../incomplete_slices.csv` and filter `incomplete_reason`.
- if `external_l1_max` wins: treat as external-baseline superiority for that evaluated surface; do not claim internal dominance.
- if `direct_reserve_semantic_frontier_v2` wins: treat as encouraging but require full-sweep consistency/statistical checks before any manuscript claim change.
- claim-safety guardrails: diagnostic-only until full evidence converges; do not edit canonical paper source-of-truth tables from this run alone.
