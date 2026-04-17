# Penalized-marginal left/right/defer target regime note (2026-04-17)

## Scope

This note records the canonical hard-case branch-allocation extension that adds a **budget-priced, three-way pairwise supervision target**:

- `left_better`
- `right_better`
- `defer`

The target is built in `scripts/build_bruteforce_target_regimes.py` under strategy:

- `penalized_marginal_defer`

## Label semantics

For pair `(branch_i, branch_j)` at state `s`:

- `delta_u_i = estimated_value_if_allocate_next(branch_i)`
- `delta_u_j = estimated_value_if_allocate_next(branch_j)`
- `delta_c_i, delta_c_j` from `--penalized-delta-c-mode`
- `lambda` from `--penalized-lambda`
- `tau(s)` from:
  - `--penalized-tau-base`
  - `--penalized-tau-relative-scale`
  - `--penalized-tau-uncertainty-scale`
  - `--penalized-tau-budget-scale`

Then:

- `left_better` if `(delta_u_i - lambda*delta_c_i) > (delta_u_j - lambda*delta_c_j) + tau(s)`
- `right_better` if `(delta_u_j - lambda*delta_c_j) > (delta_u_i - lambda*delta_c_i) + tau(s)`
- `defer` otherwise

## Output fields added on pair rows

The regime writes pairwise rows with:

- `penalized_marginal_value_i`
- `penalized_marginal_value_j`
- `penalized_marginal_gap`
- `penalized_lambda`
- `penalized_tau_state`
- `penalized_tau_components`
- `penalized_ternary_label_name` (`left_better`/`right_better`/`defer`)
- `penalized_marginal_defer_target`
- `ternary_defer_label` + `ternary_defer_label_source=penalized_marginal_value_with_budget_price`

## Training/eval integration

- `experiments/bruteforce_branch_allocator.py` now preserves precomputed `ternary_defer_label` rows from this regime.
- `scripts/run_ternary_or_abstain_branch_comparison_experiment.py` now includes formulation:
  - `penalized_marginal_defer`

Additional reported metrics include:

- accepted-pair accuracy
- defer/abstention rate and coverage
- fallback-on-deferred accuracy
- near-tie and adjacent slices
- spend proxy via coverage (`realized_spend_proxy_per_pair`)
- deferred-vs-accepted value-gap proxy (`deferred_mean_pair_value_gap`, `accepted_mean_pair_value_gap`)

## Provenance and compatibility

- This is additive: existing strategies and targets remain unchanged.
- The canonical layout and manifests are preserved; the new regime appears as another `regime_*` output.
