# TALE matched-surface fairness closure (20260423T160500Z)

## Purpose
Produce a reviewer-defensible, artifact-backed TALE comparison lane on the canonical manuscript-facing matched surface with explicit matched realized-token accounting fields.

## Exact TALE variant/path used
- Variant/path: `mode_a_inference_only_adapter (TALE-EP style prompt budgeting)`
- Runtime method id: `external_tale_prompt_budgeting`
- Backbone/model context: `simulated_branch_generator (repo matched-surface harness)`
- Official reference consulted for fidelity boundary: https://github.com/GeniusHTX/TALE

## Exact matched surface used
- `outputs/canonical_full_method_ranking_20260421T212948Z`
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- Budgets: `[4, 6, 8]` actions
- Seeds: `[11, 23, 37, 41, 53, 67]`
- Subset size per (dataset, seed): `20`

## Exact fairness contract
1. Same manuscript-facing matched-surface dataset/budget/seed scope.
2. TALE is evaluated as inference-side MODE A adapter only (no TALE-PT/full-training-stack reproduction claim).
3. TALE budget-estimator hyperparameters are frozen from `configs/tale_prompt_budgeting_v1.json` before test evaluation.
4. Reporting separates nominal budget, TALE predicted budget, realized reasoning tokens, final-answer tokens (if tracked), and total generated tokens.
5. No hidden test-set tuning or post-hoc budget search in this lane.

## Token-accounting policy
- Nominal reasoning budget: `budget_actions * action_to_token_equivalent`.
- TALE assigned/predicted budget: `metadata.token_budget_predicted` (char-length linear estimator).
- Realized reasoning tokens: `metadata.realized_reasoning_tokens_estimate` when available, else `actions_used * action_to_token_equivalent` fallback.
- Final answer tokens: counted only when `metadata.final_answer_tokens_estimate` is present.
- Total generated tokens: priority = `metadata.total_generated_tokens_estimate` -> `metadata.generated_tokens_estimate` -> derived fallback.

## Main-table acceptability decision
- Safe for main table: **True**, with explicit MODE A adapter boundary and accounting caveat.

## Remaining caveat (exact)
- This remains an inference-only MODE A TALE adapter on the shared repository harness, not full official TALE-PT reproduction.
- For this baseline path, realized reasoning tokens are proxy-accounted from action usage when explicit reasoning-token traces are unavailable; total generated-token fields are derived from available adapter metadata.

## Recommended manuscript wording
> We include TALE as a MODE A inference-side external comparator on the canonical matched surface, with frozen pre-test budget-allocation settings and explicit nominal-vs-realized token accounting (including predicted budget, realized reasoning tokens, and generated-token totals). This row is a fairness-controlled TALE-style adapter comparison and does not claim full official TALE-PT training-stack reproduction.

## Artifact bundle
- `outputs/tale_matched_surface_fairness_closure_20260423T160500Z/`
  - `manifest.json`
  - `config_snapshot.json`
  - `run_summary.json`
  - `per_example_results.csv`
  - `fairness_report.json`
  - `fairness_report.csv`
  - `token_accounting_summary.csv`
  - `comparison_ready_rows.csv`
  - `notes.txt`
