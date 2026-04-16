# Target fidelity branch-comparison status (2026-04-16)

## Scope

This note records the next step after the GBDT model-class pass: improving branch-comparison supervision quality for fixed-budget next-step branch allocation.

Core decision remains:

> under remaining budget `B`, which active branch should receive the next unit of compute?

Data note for this workspace run: evidence here is from bounded synthetic merged-format corpora (`target_fidelity_synth_*` paths), used to exercise the full supervision-quality pipeline end to end.

## What was added

### 1) Pair-construction target-regime builder

New script: `scripts/build_bruteforce_target_regimes.py`.

Implemented pair-selection regimes:

- `all_pairs` (baseline)
- `top_vs_rest`
- `adjacent_rank` (hard-neighbor)
- `high_margin_only`
- `uncertainty_filtered`

Added pair-quality metadata fields in output pairs:

- `margin_abs`
- `relative_margin`
- `near_tie_flag`
- `pair_uncertainty_std_mean`
- `pair_uncertainty_std_max`
- `pair_mode_provenance`
- `outside_gap_i`, `outside_gap_j`, `outside_gap_abs_diff`
- `pair_type` (`top_vs_rest` / `adjacent_rank` / `generic`)
- `label_source` (`approx_original` / `exact_original` / `exact_promoted`)

### 2) Exact-vs-approx targeted audit

New script: `scripts/audit_bruteforce_exact_vs_approx_pairs.py`.

Audit slices reported:

- dataset
- budget
- margin bucket
- branch count
- pair type

### 3) Matched regime learning runner

New script: `scripts/run_target_fidelity_regime_experiment.py`.

This keeps model families fixed and varies target regimes so supervision effects can be isolated.

## Commands executed

```bash
python -m pip install -q lightgbm catboost

python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_merged/target_fidelity_synth_approx_20260416 \
  --run-id target_fidelity_regimes_20260416 \
  --exact-labels-dir outputs/branch_label_bruteforce_merged/target_fidelity_synth_exact_20260416 \
  --promote-exact-over-approx \
  --near-tie-margin 0.03 \
  --high-margin-threshold 0.08 \
  --max-pair-std 0.08

python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_merged/target_fidelity_synth_exact_20260416 \
  --run-id target_fidelity_regimes_exact_20260416 \
  --pair-strategies all_pairs,top_vs_rest,adjacent_rank,high_margin_only,uncertainty_filtered \
  --near-tie-margin 0.03 \
  --high-margin-threshold 0.08 \
  --max-pair-std 0.08

python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_merged/target_fidelity_synth_approx_20260416 \
  --run-id target_fidelity_regimes_no_promo_20260416 \
  --pair-strategies all_pairs \
  --near-tie-margin 0.03

python scripts/audit_bruteforce_exact_vs_approx_pairs.py \
  --approx-labels-dir outputs/branch_label_bruteforce_targets/target_fidelity_regimes_no_promo_20260416/regime_all_pairs \
  --exact-labels-dir outputs/branch_label_bruteforce_targets/target_fidelity_regimes_exact_20260416/regime_all_pairs \
  --output-dir outputs/branch_label_bruteforce_targets/target_fidelity_regimes_20260416/exact_vs_approx_audit_pairs

python scripts/run_target_fidelity_regime_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/target_fidelity_regimes_20260416 \
  --run-id target_fidelity_matched_20260416 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03 \
  --pairwise-near-tie-action none

python scripts/run_target_fidelity_regime_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/target_fidelity_regimes_20260416 \
  --run-id target_fidelity_matched_weighted_20260416 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03 \
  --pairwise-near-tie-action downweight \
  --pairwise-near-tie-downweight 0.2 \
  --uncertainty-weighting
```

## Exact-vs-approx trustworthiness (targeted audit)

From `exact_vs_approx_audit_pairs/exact_vs_approx_audit.json`:

- Overall agreement: **0.9221**
- Margin buckets:
  - near-tie (`|margin| <= 0.03`): **0.5380**
  - low (`0.03 < |margin| <= 0.08`): **0.8893**
  - mid (`0.08 < |margin| <= 0.15`): **1.0000**
  - high (`|margin| > 0.15`): **1.0000**
- Pair type agreement:
  - adjacent-rank: **0.8611**
  - top-vs-rest: **0.9884**
  - generic: **0.9722**
- Dataset agreement:
  - gsm8k: **0.9329**
  - math_500: **0.9352**
  - amo_bench: **0.8981**

Conservative interpretation: approximate labels are much less trustworthy in near-tie and adjacent-neighbor comparisons.

## Matched regime learning results (3-seed means)

Primary comparison model here is pairwise logistic (linear anchor), with pointwise and GBDT models also reported.

### Pairwise logistic (fixed model class, regime changes)

From `target_fidelity_matched_20260416/target_fidelity_summary.json`:

- all_pairs: pairwise **0.9012**, top1 **0.7229**, near-tie **0.6490**, far-margin **0.9356**, exact-slice **0.9028**
- high_margin_only: pairwise **0.9718**, top1 **0.6991**, near-tie **0.0000**, far-margin **0.9718**, exact-slice **0.9454**
- top_vs_rest: pairwise **0.9535**, top1 **0.6840**, near-tie **0.5000**, far-margin **0.9720**, exact-slice **1.0000**
- uncertainty_filtered: pairwise **0.9386**, top1 **0.7078**, near-tie **0.0000**, far-margin **0.9386**, exact-slice **0.9221**
- adjacent_rank: pairwise **0.8153**, top1 **0.6840**, near-tie **0.6270**, far-margin **0.8662**, exact-slice **0.8056**

### Weighted-cleaning variant

From `target_fidelity_matched_weighted_20260416/target_fidelity_summary.json`:

- Pairwise model with near-tie downweight + uncertainty weighting was generally weaker than the non-weighted regime-run for this synthetic benchmark.

### Comparison vs model-class-only effect

In the all-pairs regime (same targets), model-class differences are small on pairwise accuracy:

- pairwise logistic: **0.9012**
- pointwise ridge: **0.8997**
- CatBoost ranker: **0.8986**
- LightGBM ranker: **0.8579**

But changing target regime with fixed pairwise logistic produces much larger shifts (up to about +0.0706 from all_pairs to high_margin_only).

Conservative answer on this bounded run: **target construction changes moved metrics more than model-class swaps did**.

## Filtering/reweighting rules tested

Implemented and/or run in this pass:

- pair construction filters:
  - high margin threshold
  - uncertainty threshold + near-tie exclusion
  - top-vs-rest and adjacent-rank structural selection
- learning-time cleaning/weighting:
  - near-tie action: none vs downweight
  - near-tie downweight multiplier
  - uncertainty-weighting enabled/disabled
  - exact/approx provenance-aware weighting hooks already wired in learner config

## Bottleneck interpretation update

This pass improves diagnosis precision:

- supervision fidelity problems are strongly concentrated in near-tie/ambiguous pairs,
- adjacent hard-neighbor pairs are more disagreement-prone than top-vs-rest,
- changing pair construction can improve pairwise alignment more than switching from linear to GBDT alone (in this bounded setting).

Conservative conclusion: bottleneck remains **partially resolved but more sharply localized** to target fidelity / near-tie ambiguity.

## Artifacts

- Target regimes (promoted exact where available):
  - `outputs/branch_label_bruteforce_targets/target_fidelity_regimes_20260416/`
- Exact regimes:
  - `outputs/branch_label_bruteforce_targets/target_fidelity_regimes_exact_20260416/`
- Approx no-promotion regime (audit input):
  - `outputs/branch_label_bruteforce_targets/target_fidelity_regimes_no_promo_20260416/`
- Exact-vs-approx audit:
  - `outputs/branch_label_bruteforce_targets/target_fidelity_regimes_20260416/exact_vs_approx_audit_pairs/`
- Matched regime experiment:
  - `outputs/branch_label_bruteforce_learning/target_fidelity_matched_20260416/`
- Matched regime + weighting variant:
  - `outputs/branch_label_bruteforce_learning/target_fidelity_matched_weighted_20260416/`
