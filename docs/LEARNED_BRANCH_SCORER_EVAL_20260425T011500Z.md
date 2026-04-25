# Learned branch scorer diagnostic eval (20260425T011500Z)

This pass adds a **diagnostic-only** offline/local learned scorer pipeline to test whether learned reranking can reduce `present_not_selected` on cases where gold is already present in explored candidates.

## What data was used?
- Source run table: `outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/cohere/per_example_rows.csv`.
- Scope for this bounded run: provider=`cohere`, dataset=`openai/gsm8k`, seeds `{11,23}`, budgets `{4,6,8}`, and `--max-cases 60`.
- Built dataset package: `outputs/learned_branch_scorer_dataset_20260425T010000Z/`.

## Is this true branch/node-level data?
Mostly **proxy answer-group/case-level** in this run.
- Existing artifacts used here expose per-method case outputs and failure flags.
- Full branch/node candidate traces were not consistently available in this bounded pass, so candidate rows are reconstructed from method-level selections.
- This limitation is explicitly encoded in dataset metadata (`proxy_answer_group_only`).

## Which split was used?
Requested split families were implemented (seed holdout, budget holdout, joint holdout), but for this bounded subset there were not enough rows in those cells, so the script used a documented fallback split (`fallback_random`, 80/20 index split).

## Which model performed best?
All three lightweight models tied in this bounded run (`accuracy=1.0`, `auc=1.0`, `top1_group_selection_accuracy=0.75` on fallback test rows). The selected model manifest picks the first tie winner by configured sort order.

## Did the scorer reduce `present_not_selected`?
In this bounded run, yes on the gold-present subset:
- `strict_f3` gold-present `present_not_selected_rate`: `0.4444`.
- `learned_branch_scorer_v1` gold-present `present_not_selected_rate`: `0.0`.

## Did it improve gold-present cases?
Yes in this bounded run:
- gold-present top-1 selection accuracy moved from `0.5556` (`strict_f3`) to `1.0` (`learned_branch_scorer_v1`).

## Did it improve or harm absent-from-tree cases?
No evidence of improvement in absent-from-tree mechanism itself (as expected):
- absent-from-tree rate is driven by whether any candidate is correct in the pool.
- learned reranking cannot recover absent gold answers; this pass treats absent-from-tree as unchanged mechanism.

## Did it improve the direct-reserve hybrid?
Not conclusively in this bounded run.
- `direct_reserve_gate_rerank_proxy` rows were unavailable in the selected prediction subset (`n_cases=0` for that method in eval summary).
- `learned_on_direct_reserve_proxy` is implemented as an offline proxy layer, but without direct-reserve rows in this subset it effectively reduced to the same available candidate pool.

## Is it strong enough for real-model validation?
Not yet from this run alone.
- This pass is useful as **diagnostic evidence** that learned reranking can help `present_not_selected` on a bounded proxy dataset.
- It is not sufficient to claim robust real-model improvement.

## Diagnostic-only status
This remains diagnostic-only and should not replace canonical `strict_f3`.

> “A lightweight learned scorer provides diagnostic evidence about whether learned answer/branch ranking can reduce present-not-selected failures. It does not by itself address absent-from-tree failures and remains diagnostic until validated in a matched real-model run.”
