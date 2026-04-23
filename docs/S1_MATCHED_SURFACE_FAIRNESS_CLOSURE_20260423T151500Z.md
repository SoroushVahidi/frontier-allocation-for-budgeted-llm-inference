# S1 matched-surface fairness closure (20260423T151500Z)

## Purpose
Provide reviewer-defensible, artifact-backed fairness closure for the s1 baseline on the canonical manuscript-facing matched surface.

## Exact s1 variant/path used
- Variant/path: `mode_a_inference_only_adapter`
- Runtime method id: `external_s1_budget_forcing`
- Backbone/model context: `simulated_branch_generator (repo matched-surface harness)`

## Exact matched surface used
- `outputs/canonical_full_method_ranking_20260421T212948Z`
- Datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']
- Budgets: [4, 6, 8]
- Seeds: [11, 23, 37, 41, 53, 67]
- Subset size per (dataset, seed): 20

## Exact fairness contract
1. Same matched-surface dataset/budget/seed scope as manuscript-facing comparison.
2. Inference-side MODE A adapter lane only (no full official training-stack claim).
3. Report nominal budget and realized test-time token accounting separately.
4. Count continuation override accounting from forced-continue events.

## Token-accounting policy
- Nominal reasoning budget: `budget_actions * action_to_token_equivalent`.
- Realized reasoning tokens: controller-trace estimate from generated reasoning steps.
- Final answer tokens: estimate from final predicted answer text.
- Continuation/override tokens: `forced_continue_events * wait_token_word_count`.
- Total generated tokens: realized reasoning + final answer tokens.

## Main-table acceptability
- Safe for main table: **True** (with explicit MODE A boundary).
- Remaining caveat: MODE A adapter comparison on shared repository harness; not a full official s1 post-training stack reproduction. Token accounting is realized-token estimate from controller traces (reasoning/final/override separated).

## Recommended manuscript wording
- "We include s1 as an external MODE A inference-side comparator on the canonical matched surface under explicit matched realized-token accounting; this is a fairness-controlled adapter comparison and does not claim full official s1 post-training-stack reproduction."
