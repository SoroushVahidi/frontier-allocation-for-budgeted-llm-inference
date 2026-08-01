# Value-aware target regime bounded comparison (v2, 2026-04-19)

## What was implemented

This pass hardens supervision against brittle hard winner labels by adding:

1. **Budget-conditioned state value schema** in `state_value_targets.jsonl`:
   - `Q_commit(s,r)`
   - `Q_expand(s,j,r)` for each active branch
   - `best_action_overall` over `{commit_now} ∪ {expand:j}`
   - `delta_best_expand_commit`, `delta_best_two_expands`, ambiguity bucket, provenance, and fallback assumptions.
2. **Gap/regret-aware branch labels** per candidate/pair:
   - `delta_expand_commit`
   - `delta_pair`
   - regret proxies (`regret_vs_best_action`, pairwise regrets).
3. **Ambiguity-aware supervision plumbing** with configurable near-tie handling already present in learner config.
4. **Expand-vs-commit decomposition metric path**:
   - added a state-level commit value regressor (`state_commit_ridge`) trained from state aggregates,
   - added explicit expand-vs-commit accuracy and mean-regret evaluation.

## Exact target definitions used in this run

For each frontier state `s` with residual budget `r`:

- `Q_commit(s,r)`: utility of committing immediately (`_state_utility` on current branches).
- `Q_expand(s,j,r)`: expected utility when one unit is first allocated to branch `j`, then residual budget is allocated by exact/approx candidate allocation search.
- `best_action_overall = argmax({Q_commit} ∪ {Q_expand_j})`.
- `delta_expand_commit(j) = Q_expand(s,j,r) - Q_commit(s,r)`.
- `delta_pair(j,k) = Q_expand(s,j,r) - Q_expand(s,k,r)`.
- Regret fields are measured against the best available action value for the state.

## Bounded matched run

- Script: `scripts/run_value_aware_target_regime_comparison.py`
- Run directory: `outputs/branch_label_bruteforce_learning/value_aware_target_regime_comparison_20260419_v2`
- Methods compared on the same generated states/seeds/budgets:
  - `baseline_default`
  - `value_aware`
  - `value_aware_ambiguity`
  - `value_aware_ambiguity_decomposed`

## Key metrics (test)

- Pairwise accuracy remained flat at `0.611` across methods.
- Near-tie pairwise accuracy dropped (`0.60 -> 0.20`) for ambiguity-enabled runs.
- Ranking top-1 improved (`0.20 -> 0.40`) for ambiguity-enabled runs.
- **Expand-vs-commit quality improved strongly** for ambiguity-enabled runs:
  - accuracy: `0.00 -> 0.60`
  - mean regret: `0.1410 -> 0.0041`.

## Interpretation

- This bounded run indicates **partial bottleneck reduction**:
  - clear gain on expand-vs-commit decision quality and regret,
  - no pairwise aggregate gain,
  - and degradation on the near-tie pairwise slice.
- So the supervision change helps decision decomposition but does **not** yet robustly fix hard near-tie branch ranking.

## Next best step

Run the same comparison on a larger exact-heavy state set and tune ambiguity-band weighting separately for:

1. branch ranking loss,
2. defer/decomposition loss,

to avoid improving expand-vs-commit by sacrificing near-tie branch discrimination.
