# ToT Matched-Budget Baseline Report

## What was implemented
This repository now includes matched-budget Tree-of-Thoughts-style adapter baselines:

- `tot_bfs_matched_budget`
- `tot_beam_matched_budget`
- `tot_dfs_matched_budget`

These are **adapter baselines** integrated into the existing frontier-allocation evaluation harness.

## Reproduction status
This work is **not** an official full reproduction of Yao et al. (NeurIPS 2023) or the Princeton ToT reference repository. It is a fair-budget adapter for this codebase's branch-generator/controller API.

## Budget accounting and fairness
- One budget action equals one branch expansion call.
- No free verifier/evaluator calls are granted to ToT variants.
- Scoring/ranking for frontier pruning is folded into expansion-time accounting (no extra action debits outside the ledger).

## Datasets, budgets, and seeds
The new runner `scripts/run_tot_matched_budget_baseline.py` targets:

- Main math surface: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- Non-math expansion surface (when feasible): `google-deepmind/natural-plan`, `Idavidrein/gpqa`, `TIGER-Lab/MMLU-Pro`
- Budgets: `4, 6, 8`
- Seeds: `11, 23, 37, 41, 53`

## What questions this supports
After running the new matched-budget baseline bundle, the paper can support an additional claim of comparison against a matched-budget search-style external baseline (ToT-adapter variants) under the same parser/evaluation pipeline.

## What remains related-work-only (not implemented here)
- **ReST-MCTS\***: not implemented because it requires process-reward-guided self-training / learned reward machinery outside this repository's current evaluation-only adapter scope.
- **Graph of Thoughts**: not implemented because graph merge/distill/feedback operations would require a stricter graph-native adapter and may drift away from the local frontier-allocation comparability objective.

## Claim-safety note
Generated artifacts and text should avoid claiming:
- official ToT reproduction,
- universal dominance of any method.

Use paired statistical tests in `pairwise_statistical_tests.csv` to support scoped, matched-surface conclusions.
