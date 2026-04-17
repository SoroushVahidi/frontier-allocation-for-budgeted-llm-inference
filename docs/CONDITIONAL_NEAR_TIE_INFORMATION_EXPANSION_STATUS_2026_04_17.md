# Conditional near-tie information expansion status (2026-04-17)

## Scope and constraints honored

- Canonical framing kept: fixed-budget branch-allocation / frontier-allocation with branch-value + uncertainty compare/defer as the coarse decision path.
- No redesign, no new dataset, no new broad feature family.
- Added step is strictly conditional and bounded to near-tie/inconclusive deferred comparisons.
- Experiment is go/no-go, not productization.

## Pre-coding insertion-point summary

Cleanest wiring points identified:

1. `scripts/run_branch_value_uncertainty_strict_validation_pass.py`
   - already has canonical `full_method` compare/defer logic and strict threshold selection with coverage floors.
2. `scripts/run_branch_value_uncertainty_derived_defer_experiment.py`
   - same branch-value + uncertainty semantics with auditable outputs and bounded experiment structure.
3. `experiments/bruteforce_branch_allocator.py` data path via `prepare_learning_tables(...)`
   - already exposes pair/candidate features needed for a tiny conditional tiebreak step (`x_pair_v3`, `near_tie_flag`, `pair_oracle_defer_score`) without introducing new artifacts.

Implementation chose a new bounded experiment script that reuses the same tables/models/threshold style, minimizing risk to canonical code.

## What was implemented

- Added `scripts/run_conditional_near_tie_information_expansion_experiment.py`.
- Modes:
  - `baseline`: unchanged canonical coarse compare/defer behavior.
  - `conditional_expand_then_decide`: only on deferred near-tie triggers, run one tiny pair-level tiebreak pass and accept only when tiebreak confidence exceeds threshold.
  - `conditional_expand_then_decide_oracleish`: same trigger, slightly stronger tiebreak setting (train+val fit + lower confidence threshold) for bounded headroom context.

### Trigger definition

Trigger only if coarse path deferred and near-tie/inconclusive conditions hold:
- low absolute gap and/or low z-gap under selected canonical thresholds,
- plus optional `near_tie_flag` inclusion (enabled in this run).

### Small extra-information step

- Extra information is a tiny pair-level tiebreak model over existing `x_pair_v3` features.
- No second large pipeline, no always-on richer model.
- Per-trigger compute accounting captured as fixed expansion-cost units.

## Bounded matched run executed

Run command:

```bash
python scripts/run_conditional_near_tie_information_expansion_experiment.py \
  --targets-root outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_root \
  --run-id conditional_near_tie_info_expansion_20260417 \
  --trigger-use-near-tie-flag
```

Matched canonical setup:
- regimes: `all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer`
- seeds: `11,29,47`
- feature set: `v3`
- strict threshold grid + coverage floor selection.

## Key outcomes (aggregate across matched runs)

### Baseline
- accepted accuracy: **0.9333**
- coverage: **0.2698**
- defer rate: **0.7302**
- near-tie accepted accuracy: **0.0000** (almost no near-tie acceptance)

### conditional_expand_then_decide
- accepted accuracy: **0.8611** (**-0.0722 vs baseline**)
- coverage: **0.7857** (**+0.5159**)
- defer rate: **0.2143** (**-0.5159**)
- near-tie accepted accuracy: **0.7667**
- trigger rate: **0.7302**
- accepted accuracy on triggered cases: **0.8381**

### conditional_expand_then_decide_oracleish
- accepted accuracy: **0.8690** (**-0.0643 vs baseline**)
- coverage: **0.9167** (**+0.6468**)
- defer rate: **0.0833** (**-0.6468**)
- near-tie accepted accuracy: **0.7667**
- trigger rate: **0.7302**
- accepted accuracy on triggered cases: **0.8492**

## Are triggered cases actually problematic?

Yes, by ambiguity proxy:
- conditional triggered mean oracle-defer score: **2.3651**
- conditional non-triggered mean oracle-defer score: **1.2000**
- positive separation indicates trigger is capturing harder/more ambiguous cases.

But improved targeting did **not** preserve baseline accepted accuracy sufficiently.

## Cost/accounting summary

Average added compute (fixed proxy units):
- conditional: **0.7302 extra units/pair** (total 5.33/run)
- oracle-ish: **1.0952 extra units/pair** (total 8.0/run)

Given the large trigger rate, the “conditional” step became broad in this bounded replay.

## Hard conclusion (go/no-go)

**Conclusion: not useful enough, switch to another idea.**

Reason:
- The method clearly reduces over-deferral and recovers near-tie accepted decisions.
- However, it causes a substantial accepted-accuracy drop versus canonical baseline (-6 to -7 points), which is too large for continuation under strict criteria.
- This looks like a calibration/precision failure under high trigger incidence, not a robust win.

## Next-best alternative

Prefer alternatives that preserve baseline precision while tackling defer collapse, e.g.:
- tighter trigger selectivity (lower trigger rate),
- explicit risk-calibrated acceptance gating for the expansion output,
- or a defer-cost-aware threshold policy without broad triggering.

## Artifact index

Run directory:
- `outputs/branch_label_bruteforce_learning/conditional_near_tie_info_expansion_20260417/`

Machine-readable artifacts:
- `conditional_near_tie_info_expansion_config.json`
- `conditional_near_tie_info_expansion_per_seed_mode.json`
- `conditional_near_tie_info_expansion_matched_summary_by_mode.json`
- `conditional_near_tie_info_expansion_aggregate_comparison_summary.json`
- `conditional_near_tie_info_expansion_trigger_diagnostics.json`
- `conditional_near_tie_info_expansion_manifest.json`

## Assumptions and caveats

- This is a bounded offline strict-validation style replay using existing artifacts only.
- “Oracle-ish” mode is bounded headroom context, not production policy.
- No claim that near-tie discrimination is solved; result is mixed-to-negative overall.
