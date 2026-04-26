# PAPER_BASELINE_HONESTY_STATUS

Conservative baseline-status summary for manuscript drafting.

Primary source: `EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md`.

## Buckets to use in manuscript text

### 1) Direct internal baselines

- Internal direct comparators from current method family and strict-phased surfaces.
- Use canonical internal comparison docs for these rows.

### 2) Near-direct adapters (main-table ready)

- `l1_length_control_rl`
- `s1_simple_test_time_scaling`
- `tale_token_budget_aware_reasoning`

These are currently the conservative main-table external set.

### 3) Adjacent / import-validated baselines (appendix-only)

- `best_route_microsoft`
- `cascade_routing`
- `lets_verify_step_by_step`
- `mob_majority_of_bests`
- `openr`
- `rest_mcts`
- `tree_plv`
- `when_solve_when_verify`
- `efficient_contextual_llm_cascades`

Use as supportive context, not core headline comparator rows.

### 4) Discuss-only baselines

Use for narrative context and related-work framing only; do not place in empirical comparison tables in current repo state.

### 5) Blocked / repo-only-not-paper-facing-yet

- `conformal_thinking_mode_a`
- `learning_how_hard_to_think_mode_a`
- `qstar_style_adapter`
- `training_free_difficulty_proxies_mode_a`

Current status: keep out of manuscript-facing empirical tables.

## Honesty rules

- Never upgrade a bucket without fresh auditable artifacts and updated readiness docs.
- Keep adapter-scope caveats explicit for near-direct and adjacent methods.
- If a reviewer asks for a missing baseline, disclose current bucket and blocker rather than over-claiming parity.
