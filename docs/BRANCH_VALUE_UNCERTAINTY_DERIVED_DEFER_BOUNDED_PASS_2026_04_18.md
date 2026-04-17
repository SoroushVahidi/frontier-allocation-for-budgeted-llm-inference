# Branch-level value + uncertainty derived compare/defer bounded pass (2026-04-18)

## Why this pass was added

This bounded pass implements the next target-design step recorded in:

- `docs/RESEARCH_TAKEAWAYS_ON_TARGET_DESIGN_AND_SELECTIVE_ALLOCATION_2026_04_18.md`
- `docs/RESEARCH_TAKEAWAYS_ON_VALUE_TARGETS_AND_ABSTENTION_2026_04_18.md`

Specifically, it moves supervision emphasis away from brittle hard pairwise wins and toward:

1. branch-level budget-conditioned value supervision,
2. explicit uncertainty/risk handling,
3. derived compare/defer decisions from value separation + uncertainty.

## Best insertion point chosen

Smallest clean insertion point was the existing brute-force target-regime + learning path used by:

- `scripts/run_ternary_or_abstain_branch_comparison_experiment.py`
- `scripts/run_near_tie_pointwise_expert_experiment.py`
- `experiments/bruteforce_branch_allocator.py`

The new pass adds one bounded script (no framework rewrite):

- `scripts/run_branch_value_uncertainty_derived_defer_experiment.py`

It reuses existing artifact schema (`candidate_labels.jsonl`, `pairwise_labels.jsonl`, `state_summaries.jsonl`) and existing feature/metadata construction via `prepare_learning_tables`.

## Target and uncertainty design used

### Branch-level value target

Primary target:

- `estimated_value_if_allocate_next`

This is treated as the current repository-grounded proxy for budget-conditioned one-step continuation value.

### Uncertainty / reliability signals

The pass combines existing uncertainty/provenance signals with a learned residual-risk head:

- `allocation_value_std` (existing branch uncertainty signal),
- mode provenance features (`mode_exact`, `mode_approx`, `mode_degenerate`) already in candidate vectors,
- learned residual-risk head trained on absolute value prediction residual proxy,
- pair-level outside-option competitiveness (`pair_best_vs_outside_gap`) in defer gating.

### Derived compare/defer rule

For a pair `(i, j)` the method predicts:

- value difference `Δ = v_i - v_j`,
- pair uncertainty scale `σ_pair = sqrt(σ_i^2 + σ_j^2)`,
- uncertainty-adjusted gap `z_gap = |Δ| / σ_pair`.

Decision:

- choose higher-value branch if both absolute and uncertainty-adjusted separation are sufficient,
- defer/unresolved otherwise,
- also defer when outside-option gap is small under low confidence.

Thresholds are selected on validation split with a coverage floor (bounded selective objective).

## Baselines in this bounded pass

Compared against in-repo runnable baselines from the same target artifacts:

1. binary pairwise logistic baseline (`train_models` pairwise head),
2. value-only forced comparator (no defer gate, sign of predicted value difference).

## Commands run (this pass)

```bash
python -m py_compile scripts/run_branch_value_uncertainty_derived_defer_experiment.py
python scripts/run_branch_value_uncertainty_derived_defer_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/value_uncertainty_bounded_smoke_20260418 \
  --run-id branch_value_uncertainty_derived_defer_20260418_smoke \
  --regimes all_pairs_approx \
  --seeds 11,29,47 \
  --feature-set v2
```

## Artifacts written

### New script

- `scripts/run_branch_value_uncertainty_derived_defer_experiment.py`

### Run artifacts

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_derived_defer_20260418_smoke/value_uncertainty_compare_defer_config.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_derived_defer_20260418_smoke/value_uncertainty_compare_defer_results.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_derived_defer_20260418_smoke/value_uncertainty_compare_defer_summary.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_derived_defer_20260418_smoke/value_uncertainty_compare_defer_manifest.json`

### Bounded smoke target root used for local runnability

- `outputs/branch_label_bruteforce_targets/value_uncertainty_bounded_smoke_20260418/regime_all_pairs_approx/candidate_labels.jsonl`
- `outputs/branch_label_bruteforce_targets/value_uncertainty_bounded_smoke_20260418/regime_all_pairs_approx/pairwise_labels.jsonl`
- `outputs/branch_label_bruteforce_targets/value_uncertainty_bounded_smoke_20260418/regime_all_pairs_approx/state_summaries.jsonl`

## Bounded smoke results (not a final canonical claim)

Aggregate over 3 seeds in the local bounded smoke corpus:

- derived accepted accuracy: `1.0000`
- derived coverage: `0.7778`
- derived defer rate: `0.2222`
- binary pairwise baseline accuracy: `0.9444`
- value-only forced baseline accuracy: `0.9722`
- paired delta vs binary: `+0.0556`
- paired delta vs value-forced: `+0.0278`

Hard slices:

- near-tie accepted accuracy (derived): `0.3333`
- adjacent-rank accepted accuracy (derived): `1.0000`

These smoke numbers only confirm that the new value+uncertainty compare/defer path is implemented and auditable in-repo.

## Caveats and assumptions

- This run used a bounded synthetic smoke target root for in-repo execution proof; headline conclusions require re-running on canonical real target regimes.
- This is not a final model-class sweep or canonical winner claim.
- Raw value magnitude is not treated as confidence; uncertainty-adjusted gating is explicit.

## Recommended next step

Run the new script on canonical exact-augmented target regimes already used by current hard-case experiments and compare with:

- binary hard pairwise baseline,
- penalized-marginal defer regime,
- strongest tie-aware/defer-aware baseline currently used in matched runs.

Keep this method as a bounded candidate pass unless it remains robust on near-tie, adjacent-rank, and budget slices under canonical artifacts.
