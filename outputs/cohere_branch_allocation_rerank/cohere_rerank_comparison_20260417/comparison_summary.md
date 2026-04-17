# Cohere rerank branch-allocation bounded comparison (2026-04-17)

## Chosen path
- Primary: Option A (candidate-set Cohere Rerank listwise branch scorer).
- Supportive variant: Option B (near-tie/hard-only Cohere fallback on top of pairwise vote).

## Key metrics (top-1 vs oracle proxy)
- Option A all-states Cohere rerank: `0.3375`
- Option B hard-only fallback Cohere: `0.6375` (coverage `0.3750`)
- Pairwise-vote baseline: `0.7625`
- Heuristic-score baseline: `0.5375`

## Interpretation
- In this bounded run, pure Cohere rerank underperformed in aggregate against in-repo pairwise-vote baseline.
- Hard-only fallback improved over pure Cohere and heuristic baseline, but remained below pairwise-vote baseline.
- Result is useful as an auditable external listwise comparison point, not as a replacement for current canonical methods yet.

## Artifacts
- `outputs/cohere_branch_allocation_rerank/cohere_rerank_penalized_all_states_20260417/summary_metrics.json`
- `outputs/cohere_branch_allocation_rerank/cohere_rerank_penalized_hard_fallback_20260417/summary_metrics.json`
- `outputs/cohere_branch_allocation_rerank/cohere_rerank_comparison_20260417/comparison_summary.json`
- `outputs/cohere_branch_allocation_rerank/cohere_rerank_comparison_20260417/option_assessment.json`
