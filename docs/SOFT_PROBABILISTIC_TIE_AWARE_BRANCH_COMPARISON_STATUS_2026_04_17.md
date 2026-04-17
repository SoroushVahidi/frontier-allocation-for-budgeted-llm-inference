# Soft probabilistic tie-aware branch-comparison pass (2026-04-17, bounded)

## Scope

This pass adds one bounded soft-target supervision regime for branch-pair comparison while preserving the current scaffold:
- fixed-budget next-step branch allocation,
- pairwise comparison as the default learned object,
- `v2` features for matched comparisons,
- no controller-family redesign.

## Soft target design implemented

A new soft target design (`davidson_soft_prob_v1`) is materialized per pair for the new regime:
- `soft_target_prob_i_wins`
- `soft_target_prob_tie`
- `soft_target_prob_j_wins`

Construction uses existing signals only:
- absolute margin,
- relative margin,
- uncertainty std,
- near-tie flag,
- adjacent-rank flag,
- optional exact-vs-approx disagreement-risk flag.

Bounded behavior:
- tie probability rises smoothly with closeness + ambiguity,
- easy clear pairs are clipped to very low tie mass,
- directional mass stays sharp for easy rows and softens near hard close-calls.

## New regime created

Target regimes built from the same base labels:
- `all_pairs` (current baseline),
- `davidson_tie_aware` (hard tie-aware),
- `soft_prob_tie_aware` (new soft probabilistic tie-aware).

Output root:
- `outputs/branch_label_bruteforce_targets/soft_prob_tie_target_regimes_20260417/`

Key summary:
- `all_pairs`: `ambiguous_tie_rate=0.9747`, `mean_soft_tie_prob=0.0000`
- `davidson_tie_aware`: `ambiguous_tie_rate=0.4684`, `mean_soft_tie_prob=0.0000`
- `soft_prob_tie_aware`: `ambiguous_tie_rate=0.4684`, `mean_soft_tie_prob=0.4201`

## Minimal learner extension

A minimal soft-target learner path was added in the experiment runner:
- `soft_ternary_tie` trains multinomial logistic from soft targets via weighted pseudo-label expansion (small extension; no major pipeline rewrite).
- If soft probabilities are absent, it safely falls back to one-hot hard ternary labels.

This keeps the extension bounded while preserving graded supervision signal.

## Matched comparison run

Runner:
- `scripts/run_ternary_or_abstain_branch_comparison_experiment.py`

Run output:
- `outputs/branch_label_bruteforce_learning/soft_prob_tie_matched_20260417/`

Matched settings:
- feature set: `v2`
- seeds: `11,29,47`
- regimes: `all_pairs,davidson_tie_aware,soft_prob_tie_aware`
- fallback: `pointwise_value`

## Main bounded results (3-seed means)

From `ternary_or_abstain_report.md`:

- Baseline forced-binary reference (`all_pairs`, `binary_forced`):
  - forced pairwise: **0.7817**
  - top-1: **0.8259**
  - near-tie forced: **0.9167**
  - adjacent forced: **0.8265**

- Hard Davidson ternary (`davidson_tie_aware`, `ternary_tie`):
  - coverage: **0.2825**
  - forced pairwise: **0.7703**
  - top-1: **0.6963**
  - adjacent forced: **0.7274**

- Soft learner on hard Davidson regime (`davidson_tie_aware`, `soft_ternary_tie`):
  - accepted accuracy: **0.9048**
  - coverage: **0.4532**
  - forced pairwise: **0.8387**
  - top-1: **0.7963**
  - adjacent forced: **0.8085**

- Soft learner on soft regime (`soft_prob_tie_aware`, `soft_ternary_tie`):
  - accepted accuracy: **0.9524**
  - coverage: **0.4532**
  - forced pairwise: **0.7608**
  - top-1: **0.6926**
  - adjacent forced: **0.7197**

Conservative interpretation:
- soft training improves accepted-set quality and coverage-vs-hard-ternary in this bounded run,
- but the specific soft-target regime here did **not** beat the hard-Davidson + soft learner path on forced/top-1,
- and still does not exceed the strong forced-binary top-1 reference.

## Success / failure criterion readout

- Partial success: graded supervision is integrated and can materially improve accepted/coverage behavior vs hard ternary.
- Remaining failure: the new soft-target regime did not deliver a robust hard-slice/top-1 win over all strong references in this bounded test.

## Recommended next step if this remains weak

Given this run, the next strongest options are:
1. partial-order / incomparability objectives,
2. abstention-aware training objectives directly optimized for accepted/coverage tradeoff,
3. stronger reliability-weighted hard-pair cleanup before more structured modeling.

## Commands executed

```bash
python -m py_compile scripts/build_bruteforce_target_regimes.py scripts/build_exact_augmented_target_regimes.py scripts/run_ternary_or_abstain_branch_comparison_experiment.py experiments/bruteforce_branch_allocator.py scripts/train_bruteforce_branch_allocator.py

python scripts/run_bruteforce_branch_label_generator.py --run-id soft_prob_tie_base_20260417 --max-frontier-states 120 --episodes-per-example 1 --frontier-budget 7 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 3 --max-branches-per-state 4 --rollout-samples-per-candidate 16 --max-allocation-samples 32 --seed 31

python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce/soft_prob_tie_base_20260417 --run-id soft_prob_tie_target_regimes_20260417 --pair-strategies all_pairs,davidson_tie_aware,soft_prob_tie_aware --near-tie-margin 0.03 --tie-policy davidson_close_call --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.12 --tie-std-threshold 0.07 --tie-use-near-tie-flag --tie-include-approx

python scripts/run_ternary_or_abstain_branch_comparison_experiment.py --targets-root outputs/branch_label_bruteforce_targets/soft_prob_tie_target_regimes_20260417 --run-id soft_prob_tie_matched_20260417 --seeds 11,29,47 --feature-set v2 --regimes all_pairs,davidson_tie_aware,soft_prob_tie_aware --near-tie-margin 0.03 --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.12 --tie-std-threshold 0.07 --tie-use-near-tie-flag --tie-include-approx --abstain-confidence-threshold 0.20 --fallback-policy pointwise_value
```
