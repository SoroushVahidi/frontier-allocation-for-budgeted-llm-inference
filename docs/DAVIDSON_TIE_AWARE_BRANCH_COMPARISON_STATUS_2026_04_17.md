# Davidson-style tie-aware branch-comparison pass (2026-04-17, bounded)

## Scope

This pass implements one bounded tie-aware supervision regime for branch-pair labels:
- `i_wins`
- `tie`
- `j_wins`

The goal is to stop forcing the hardest close-call pairs into ordinary binary supervision while preserving broad directional coverage for easy pairs.

Repository direction is unchanged:
- fixed-budget frontier allocation / next-step branch allocation,
- pairwise branch comparison as default learned object,
- `v2` feature representation for matched learner comparison,
- no controller-family redesign.

## Implemented target design

A new tie policy (`davidson_close_call`) was added to pair-label annotation:

A pair is labeled `tie` only when **both** hold:
1. **closeness condition** (`close_call`): at least one of
   - absolute margin <= threshold,
   - relative margin <= threshold,
   - near-tie flag (if enabled),
2. **ambiguity-risk condition** (`ambiguous_risk`): at least one of
   - pair uncertainty std >= threshold,
   - adjacent-rank pair,
   - exact-vs-approx disagreement-risk flag (if present).

This is a bounded Davidson-style interpretation: ties are reserved for close calls with additional ambiguity risk, not all low-margin points.

By contrast, the legacy tie policy (`legacy_or`) labels tie when any trigger fires, which is intentionally broader.

## New regime created

Using `scripts/build_bruteforce_target_regimes.py`, two matched regimes were materialized from the same base labels:
- `all_pairs` (legacy tie policy for baseline forced binary treatment context),
- `davidson_tie_aware` (new Davidson-style close-call + risk tie policy).

Output root:
- `outputs/branch_label_bruteforce_targets/davidson_tie_target_regimes_20260417/`

Key target-summary difference:
- baseline `all_pairs` ambiguous tie rate: **0.9747**,
- `davidson_tie_aware` ambiguous tie rate: **0.4684**.

This confirms the new regime concentrates ties on a narrower hard subset while retaining directional labels elsewhere.

## Matched comparison run

Runner:
- `scripts/run_ternary_or_abstain_branch_comparison_experiment.py`

Run:
- `outputs/branch_label_bruteforce_learning/davidson_tie_matched_20260417/`

Matched settings:
- feature set: `v2`,
- seeds: `11,29,47`,
- regimes: `all_pairs`, `davidson_tie_aware`,
- fallback policy: `pointwise_value`.

## Main results (3-seed means)

### Binary forced (reference)

Unchanged between regimes (as expected for forced binary path):
- forced pairwise accuracy: **0.7817**,
- top-1: **0.8259**,
- near-tie forced accuracy: **0.9167**,
- adjacent forced accuracy: **0.8265**.

### Ternary tie-aware (key comparison)

`all_pairs` (legacy broad tie):
- accepted accuracy: **0.0000**,
- coverage: **0.0000**,
- forced pairwise accuracy: **0.7305**,
- tie-detection F1: **1.0000**,
- top-1: **0.6926**.

`davidson_tie_aware` (new close-call tie):
- accepted accuracy: **0.8333**,
- coverage: **0.2825**,
- forced pairwise accuracy: **0.7703**,
- tie-detection F1: **0.4405**,
- near-tie forced accuracy: **0.9167**,
- adjacent forced accuracy: **0.7274**,
- top-1: **0.6963**.

Interpretation:
- the new tie policy avoids the catastrophic tie-overuse/coverage collapse seen under broad ties,
- improves ternary forced accuracy vs legacy broad ties,
- but still leaves a substantial abstention/coverage cost and does not beat the strong forced-binary top-1 reference.

## Success/failure criterion readout

- **Success (partial):** more honest hard-case treatment was achieved; ties are now concentrated on hard close-calls rather than nearly all pairs.
- **Failure (remaining):** this bounded pass did not produce a clean end-metric win over forced binary on headline top-1/forced path; gains are mostly in supervision honesty and tie selectivity.

## Next step recommendation

Given this outcome, the most justified next step is:
1. **softer probabilistic targets** around the close-call region (rather than hard tie class boundaries), and/or
2. **partial-order/abstention training objective** with coverage-aware optimization.

A full structured-output abstention model could be a follow-on only after the above simpler soft-target pass is tested.

## Commands executed

```bash
python -m py_compile scripts/build_bruteforce_target_regimes.py scripts/build_exact_augmented_target_regimes.py scripts/run_ternary_or_abstain_branch_comparison_experiment.py scripts/train_bruteforce_branch_allocator.py experiments/bruteforce_branch_allocator.py

python scripts/run_bruteforce_branch_label_generator.py --run-id davidson_tie_base_20260417 --max-frontier-states 120 --episodes-per-example 1 --frontier-budget 7 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 3 --max-branches-per-state 4 --rollout-samples-per-candidate 16 --max-allocation-samples 32 --seed 31

python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce/davidson_tie_base_20260417 --run-id davidson_tie_target_regimes_20260417 --pair-strategies all_pairs,davidson_tie_aware --near-tie-margin 0.03 --tie-policy davidson_close_call --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.12 --tie-std-threshold 0.07 --tie-use-near-tie-flag --tie-include-approx

python scripts/run_ternary_or_abstain_branch_comparison_experiment.py --targets-root outputs/branch_label_bruteforce_targets/davidson_tie_target_regimes_20260417 --run-id davidson_tie_matched_20260417 --seeds 11,29,47 --feature-set v2 --regimes all_pairs,davidson_tie_aware --near-tie-margin 0.03 --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.12 --tie-std-threshold 0.07 --tie-use-near-tie-flag --tie-include-approx --abstain-confidence-threshold 0.20 --fallback-policy pointwise_value
```
