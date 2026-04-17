# Cohere rerank branch-allocation comparison (cohere_rerank_penalized_hard_fallback_20260417)

- labels_dir: `outputs/branch_label_bruteforce_targets/validation_penalized_regimes_nt_l0.20_t0.02_eu0.10_cap1.50_20260417/regime_penalized_marginal_defer`
- eval_split: `all`
- states_evaluated: `80`
- hard_only_fallback: `True`
- cohere_call_coverage: `0.3750`

## Top-1 accuracy vs oracle proxy
- Cohere rerank: `0.6375`
- Heuristic score baseline: `0.5375`
- Pairwise-vote baseline: `0.7625`

## Mean oracle-value gap (lower better)
- Cohere rerank: `0.016035`
- Heuristic score baseline: `0.025347`
- Pairwise-vote baseline: `0.010989`
