# Cohere full comparison attempt (2026-04-29)

- git commit: `993b2ca`
- thresholded/ordered excluded: `direct_reserve_semantic_frontier_v2_thresholded_ordered` is diagnostic_only and runtime-missing in runner specs.

## Commands
```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260429T_COHERE_FULL_COMPARISON --providers cohere --datasets openai/gsm8k,HuggingFaceH4/MATH-500 --budgets 2,4,6,8 --seeds 11,13,17 --methods strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3 --target-scored-per-slice 100 --max-examples 100 --emit-trace-audit --resume --validate-methods-only
python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260429T_COHERE_FULL_COMPARISON --providers cohere --cohere-model command-r-plus-08-2024 --datasets openai/gsm8k,HuggingFaceH4/MATH-500 --budgets 2,4,6,8 --seeds 11,13,17 --methods strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3 --target-scored-per-slice 100 --max-examples 100 --emit-trace-audit --resume
```

## Validation table
| method_id | status | runtime_present | reason |
|---|---|---|---|
| strict_f3 | runnable | yes | runtime present in runner build_frontier_strategies specs |
| strict_gate1_cap_k6 | runnable | yes | runtime present in runner build_frontier_strategies specs |
| strict_f2 | runnable | yes | runtime present in runner build_frontier_strategies specs |
| direct_reserve_semantic_frontier_v2 | runnable | yes | runtime present in runner build_frontier_strategies specs |
| direct_reserve_semantic_frontier_v2_selection_fix_v1 | runnable | yes | runtime present in runner build_frontier_strategies specs |
| external_l1_max | runnable | yes | runtime present in runner build_frontier_strategies specs |
| tale | runnable | yes | runtime present in runner build_frontier_strategies specs |
| s1 | runnable | yes | runtime present in runner build_frontier_strategies specs |
| self_consistency_3 | runnable | yes | runtime present in runner build_frontier_strategies specs |
