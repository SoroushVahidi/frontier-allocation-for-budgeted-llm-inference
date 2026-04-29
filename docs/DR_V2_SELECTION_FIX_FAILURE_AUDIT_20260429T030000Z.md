# DR_V2_SELECTION_FIX_FAILURE_AUDIT_20260429T030000Z

- **status**: diagnostic/provenance only.
- **why selection-fix v1 was tried**: prior trace audit identified DR-v2 losses as present-not-selected selection failures.

## Findings from `outputs/cohere_real_model_cost_normalized_validation_20260429T020000Z`
- Matched audited cases: 20.
- L1-correct / DR-v2-wrong cases: 3.
- Selection-fix applied on those 3 cases: 1/3.
- On the other 2/3, the fix did not apply because support condition did not pass (`gold_group_present_but_lower_support` and one unresolved trace-missing context under this audit rule set).
- On the one applied case, the selected frontier group was still wrong (`fix_applied_to_wrong_frontier_group`).

## Did the fix hurt originally correct DR-v2 cases?
- No explicit DR-v2-correct → selection-fix-wrong regression was observed in this 20-case slice.

## Bottleneck interpretation
- Bottleneck remains final selection/reranking.
- Support-only reranking signal is insufficient: it can fail to trigger on beneficial cases and can trigger toward wrong non-gold frontier groups.

## Better candidate signals visible in traces
Potentially useful non-gold diagnostics already present in metadata:
- answer entropy / support gap (`answer_entropy`, `top2_support_gap`),
- verifier-related fields (`verifier_scores_by_answer_group`, `verifier_verdicts_by_answer_group`),
- family diversity/support provenance (`answer_group_strategy_family_counts`, family normalized support),
- direct-vs-frontier agreement and override reasons,
- process-quality style fields and branch-level score summaries.

## Next recommendation
- Do **not** add another variant in this pass.
- Next targeted idea: offline score-ablation on current traces to evaluate whether a composite final-selection signal (support + verifier + diversity provenance + entropy margin) can separate the 3 unresolved L1-only-correct cases before any new live method run.

## What not to claim
- Do not claim EM gain for selection-fix v1.
- Do not claim DR-v2 improvement from this pass.
- Do not claim broad generality beyond this GSM8K budget-4 seed-11 targeted slice.
