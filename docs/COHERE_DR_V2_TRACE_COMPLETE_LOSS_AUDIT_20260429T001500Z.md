# COHERE_DR_V2_TRACE_COMPLETE_LOSS_AUDIT_20260429T001500Z

## 1) What was run?
- Smoke run: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260429T000001Z --providers cohere --datasets openai/gsm8k --budgets 4 --seeds 11 --methods direct_reserve_semantic_frontier_v2,external_l1_max --max-examples 2 --target-scored-per-slice 2 --emit-trace-audit --resume`
- Targeted run: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260429T001500Z --providers cohere --datasets openai/gsm8k --budgets 4 --seeds 11 --methods direct_reserve_semantic_frontier_v2,external_l1_max --max-examples 20 --target-scored-per-slice 20 --emit-trace-audit --resume`
- Audit: `python scripts/analyze_cohere_dr_v2_trace_losses.py --input-dir outputs/cohere_real_model_cost_normalized_validation_20260429T001500Z`

## 2) How many matched cases were audited?
- 20 matched scored cases (GSM8K, budget 4, seed 11).

## 3) How many L1-correct / DR-v2-wrong cases were found?
- 3 cases (classified as `selection_failure_present_not_selected`).

## 4) DR-v2 loss fractions among L1-correct / DR-v2-wrong
- absent from frontier: 0 / 3 = 0.00
- present but not selected: 3 / 3 = 1.00
- extraction/canonicalization failure: 0 / 3 = 0.00
- commit/over-exploration failure: 0 / 3 = 0.00
- unclassifiable trace-missing: 0 / 3 = 0.00

## 5) Dominant bottleneck
- Dominant observed bottleneck in this targeted pass: selection failure (gold-equivalent candidate present, not selected).

## 6) Next algorithmic fix recommended
- `improve_final_selection_or_reranking` (from `dr_v2_next_algorithm_decision.json`).

## 7) What should not be claimed?
- Do not claim broad superiority or infer cross-budget/cross-dataset behavior from this targeted GSM8K budget-4 diagnostic.
- Do not claim DR-v2 promotion; this is a bottleneck audit only.
- Do not claim Wulver/Slurm submission.
