# DISCOUNTED MULTISTEP TARGET STATUS (2026-04-18)

## Scope and insertion-point summary
This pass is a bounded target-design experiment in the canonical fixed-budget branch-allocation framing: which active branch should get the next unit of compute.

Insertion points reused from the current multistep path:
- Target construction and regime generation: `scripts/build_bruteforce_target_regimes.py`.
- Matched evaluation path: `scripts/run_multistep_branch_utility_target_experiment.py`.
- Same upstream labels and same canonical seeds/settings as the latest multistep validation pass.

No broad framework redesign was introduced.

## Exact discounted target definition
For each candidate branch `b`, we reuse the existing horizon-specific multistep proxy values `V_h(b)` from the existing self-followup utility construction, then define:

\[
U_\gamma(b) = \frac{\sum_{h=1}^{3} \gamma^{h-1} V_h(b)}{\sum_{h=1}^{3} \gamma^{h-1}}
\]

with strictly decreasing weights for `gamma < 1`.

- `V_1, V_2, V_3` are computed by the existing multistep utility path.
- This is a target-construction change (not a post-hoc score-only adjustment).
- Pair labels in discounted regimes are rebuilt from `U_gamma` margins.

## Gamma / coefficient values tested
Compared modes (matched setting):
1. `baseline_current_matched` (`all_pairs`)
2. `multistep_k3_current` (`multistep_branch_utility_target_k3`)
3. `discounted_gamma_1_00` (`discounted_multistep_branch_utility_target_gamma100`)
4. `discounted_gamma_0_80` (`discounted_multistep_branch_utility_target_gamma080`)
5. `discounted_gamma_0_60` (`discounted_multistep_branch_utility_target_gamma060`)

Discount coefficients:
- gamma 1.00: `(w1, w2, w3) = (1.00, 1.00, 1.00)`
- gamma 0.80: `(w1, w2, w3) = (1.00, 0.80, 0.64)`
- gamma 0.60: `(w1, w2, w3) = (1.00, 0.60, 0.36)`

## Commands run
```bash
python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417/regime_all_pairs_approx \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id discounted_multistep_branch_utility_target_validation_20260418 \
  --pair-strategies all_pairs,multistep_branch_utility_target_k3,discounted_multistep_branch_utility_target_gamma100,discounted_multistep_branch_utility_target_gamma080,discounted_multistep_branch_utility_target_gamma060 \
  --near-tie-margin 0.03

python scripts/run_multistep_branch_utility_target_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/discounted_multistep_branch_utility_target_validation_20260418 \
  --run-id discounted_multistep_branch_utility_target_validation_eval_20260418 \
  --output-root outputs/branch_label_bruteforce_learning \
  --seeds 11,29,47 \
  --feature-set v3 \
  --near-tie-margin 0.03
```

## Main metrics (matched)
Aggregate (mean across seeds):

- Baseline current matched:
  - accepted accuracy: `0.5595`
  - near-tie accepted accuracy: `0.2000`
  - adjacent-rank accepted accuracy: `0.5460`
  - strict-slice accepted accuracy: `0.1667`
- Current multistep k3:
  - accepted accuracy: `0.7063` (`+0.1468` vs baseline)
  - near-tie accepted accuracy: `0.6000`
  - adjacent-rank accepted accuracy: `0.6381`
  - strict-slice accepted accuracy: `0.5833`
- Discounted gamma 1.00:
  - identical to current k3 on this slice.
- Discounted gamma 0.80:
  - identical to current k3 on this slice.
- Discounted gamma 0.60:
  - identical to current k3 on accepted/near-tie/adjacent/strict aggregate metrics (`delta vs k3 = 0.0000` on accepted accuracy).

Coverage remains `1.0` and defer rate remains `0.0` for all compared modes.

## Discount-specific diagnostics
- Target diagnostics by gamma are written to:
  - `target_diagnostics_by_gamma.json`
- Ranking-change/disagreement diagnostics are written to:
  - `disagreement_diagnostics.json`

Observed disagreement vs current k3:
- gamma 1.00: no state-level ranking changes.
- gamma 0.80: no state-level ranking changes.
- gamma 0.60: one changed state in seed 11 (`exopenai_gsm8k_3_ep7_d3`).

The only observed ranking disagreement is concentrated in the dominant failure bucket (share `1.0` on changed states for that comparison).

## Dominant failure-group analysis
Failure taxonomy output is written to:
- `per_seed_failure_taxonomy.json`
- `dominant_failure_group_comparison_summary.json`

Dominant group tracked:
- `delayed_payoff_overvaluation_with_outside_option_miss`

Aggregate across seeds:
- Current k3 dominant-group failures mean: `0.6667`
- gamma 1.00 dominant-group failures mean: `0.6667`
- gamma 0.80 dominant-group failures mean: `0.6667`
- gamma 0.60 dominant-group failures mean: `0.3333`

Per-seed change pattern:
- Seed 11: dominant failures reduced from `1 -> 0` at gamma 0.60.
- Seed 29: unchanged (`1 -> 1`).
- Seed 47: unchanged (`0 -> 0`).

## Assumptions and caveats
- Small support: state-level denominators are low; failure-count shifts are directional, not statistically stable.
- This pass intentionally changes only target construction and matched target-induced supervision labels.
- gamma 0.80 produced no ranking change relative to k3 on this slice.

## Hard conclusion
Bounded result: **interesting but not yet better than current multistep as a family-level win**.

- Discounting at gamma 0.60 did reduce the dominant delayed-payoff-overvaluation failures on this slice.
- However, aggregate accepted accuracy and hard-slice metrics were unchanged versus current k3, and moderate discounting (gamma 0.80) did not move decisions.
- Therefore this does **not** yet clear a strong go decision as a generally better replacement family; it supports a narrower claim that far-horizon value calibration can help specific dominant-failure cases and is worth further bounded calibration work.
