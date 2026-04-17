# Abstention operating-point calibration sweep status (2026-04-17 bounded)

## Scope preserved

This pass keeps the same method family:
- fixed-budget branch-allocation framing,
- pairwise default learned object,
- `v2` hard-case representation,
- partial-order incomparability target regime,
- cost-sensitive expected-cost abstention decision rule.

No controller-family redesign, no new datasets, and no target-family replacement were introduced.

## Implementation changes

Primary implementation is in:
- `scripts/run_ternary_or_abstain_branch_comparison_experiment.py`

Added one bounded abstention operating-point calibration pass with:
- bounded sweep knobs:
  - unresolved-class upweight,
  - directional->unresolved cost,
  - unresolved->directional cost,
  - optional abstention decision margin,
- validation-based model selection rule:
  - maximize accepted accuracy subject to a coverage floor,
- explicit machine-readable selection artifact output:
  - `abstention_cost_calibration_selection.json`,
- explicit matched reporting split between:
  - `partial_order_cost_sensitive_abstain_previous`,
  - `partial_order_cost_sensitive_abstain_calibrated`.

## Selection rule used

- Rule: **maximize validation accepted pairwise accuracy subject to validation coverage >= floor**.
- Coverage floor in this bounded pass: `0.40`.

## Bounded sweep grid used

- unresolved class upweight: `1.00, 1.20, 1.35`
- directional->unresolved cost: `0.35, 0.45`
- unresolved->directional cost: `0.55, 0.70`
- abstention decision margin: `0.00, 0.03`

## Matched run command (bounded)

```bash
python scripts/run_ternary_or_abstain_branch_comparison_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/abstain_cost_target_regimes_20260417 \
  --run-id abstention_cost_sensitive_partial_order_calibrated_20260417 \
  --output-dir outputs/branch_label_bruteforce_learning \
  --seeds 11,29,47 \
  --feature-set v2 \
  --regimes partial_order_promoted_exact_hard_region \
  --near-tie-margin 0.03 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx \
  --fallback-policy pointwise_value \
  --abstention-unresolved-class-upweight 1.35 \
  --abstention-cost-directional-to-unresolved 0.35 \
  --abstention-cost-unresolved-to-directional 0.70 \
  --calibration-enable-sweep \
  --calibration-coverage-floor 0.40 \
  --calibration-grid-unresolved-upweight 1.00,1.20,1.35 \
  --calibration-grid-cost-directional-to-unresolved 0.35,0.45 \
  --calibration-grid-cost-unresolved-to-directional 0.55,0.70 \
  --calibration-grid-decision-margin 0.00,0.03
```

## Output artifacts

- `outputs/branch_label_bruteforce_learning/abstention_cost_sensitive_partial_order_calibrated_20260417/ternary_or_abstain_results.json`
- `outputs/branch_label_bruteforce_learning/abstention_cost_sensitive_partial_order_calibrated_20260417/ternary_or_abstain_summary.json`
- `outputs/branch_label_bruteforce_learning/abstention_cost_sensitive_partial_order_calibrated_20260417/abstention_cost_calibration_selection.json`
- `outputs/branch_label_bruteforce_learning/abstention_cost_sensitive_partial_order_calibrated_20260417/abstention_cost_config.json`
- `outputs/branch_label_bruteforce_learning/abstention_cost_sensitive_partial_order_calibrated_20260417/ternary_or_abstain_report.md`

## Run outcome in this workspace

The run completed structurally but with `rows: 0`, indicating the expected target-regime inputs were not present in this workspace path during execution.

Therefore, this pass delivers:
- calibrated operating-point code path,
- auditable sweep/selection machinery,
- machine-readable selection artifact schema,
- but **not** a populated empirical matched comparison in this environment.

## Failure criterion status

Because the required target-regime inputs were unavailable here, calibration effectiveness could not be adjudicated on metrics. The immediate next step is to rerun this calibrated pass on the canonical partial-order regime artifacts and then evaluate:
- unresolved usage remains non-trivial,
- coverage rises from the prior aggressive abstention point,
- accepted-accuracy/coverage utility improves versus the previous operating point.

If that rerun still cannot recover a reasonable operating point, the next best step should be:
- **better abstention utility design** (before broader redesign),
with reliability-weighted hard-pair cleanup as a secondary follow-up if utility tuning alone remains unstable.
