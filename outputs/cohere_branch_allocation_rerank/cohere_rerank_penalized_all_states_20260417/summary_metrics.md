# Cohere rerank branch-allocation comparison (cohere_rerank_penalized_all_states_20260417)

- labels_dir: `outputs/branch_label_bruteforce_targets/validation_penalized_regimes_nt_l0.20_t0.02_eu0.10_cap1.50_20260417/regime_penalized_marginal_defer`
- eval_split: `all`
- states_evaluated: `80`
- hard_only_fallback: `False`
- cohere_call_coverage: `1.0000`

## Top-1 accuracy vs oracle proxy
- Cohere rerank: `0.3375`
- Heuristic score baseline: `0.5375`
- Pairwise-vote baseline: `0.7625`

## Mean oracle-value gap (lower better)
- Cohere rerank: `0.042803`
- Heuristic score baseline: `0.025347`
- Pairwise-vote baseline: `0.010989`
