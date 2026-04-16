# GBDT branch allocator status (LightGBM/CatBoost) — 2026-04-16

## Scope and framing

This status note covers the **GBDT ranking (gradient-boosted decision tree ranking)** upgrade for fixed-budget next-step branch allocation.

Canonical decision remains:

> Given two active branches under remaining budget `B`, which branch should receive the next unit of compute?

Pointwise branch value and outside-option are supporting views only.

## What was integrated

Implemented in the existing brute-force branch allocator learning stack:

- **LightGBM ranker** (`lightgbm_ranker`) using `lambdarank` objective.
- **CatBoost ranker** (`catboost_ranker`) using `YetiRankPairwise` loss.
- Existing linear learners retained as matched anchors:
  - `pairwise` logistic regression,
  - `pointwise` ridge,
  - `outside_option` logistic regression.

## Uncertainty-aware pairwise training rules added

Added configurable pairwise training controls:

- Near-tie policy: `none` / `filter` / `downweight`.
- Near-tie downweight multiplier.
- Optional uncertainty-aware pair weighting from:
  - margin magnitude,
  - pair-level `allocation_value_std`,
  - exact vs approx mode.

Training rules are persisted via `config` in manifests/results.

## Commands executed

```bash
python -m pip install -q lightgbm catboost

python scripts/train_bruteforce_branch_allocator.py \
  --labels-dir outputs/branch_label_bruteforce_merged/gbdt_upgrade_synthetic_20260416 \
  --run-id gbdt_upgrade_baseline_20260416 \
  --seed 17 \
  --near-tie-margin 0.03

python scripts/train_bruteforce_branch_allocator.py \
  --labels-dir outputs/branch_label_bruteforce_merged/gbdt_upgrade_synthetic_20260416 \
  --run-id gbdt_upgrade_uncertainty_20260416 \
  --seed 17 \
  --near-tie-margin 0.03 \
  --pairwise-near-tie-action downweight \
  --pairwise-near-tie-downweight 0.2 \
  --uncertainty-weighting \
  --margin-weight-power 1.0 \
  --std-weight-scale 4.0 \
  --approx-mode-weight 0.8 \
  --exact-mode-weight 1.1

python scripts/run_bruteforce_allocator_scaling_experiment.py \
  --labels-dir outputs/branch_label_bruteforce_merged/gbdt_upgrade_synthetic_20260416 \
  --run-id gbdt_upgrade_scaling_baseline_20260416 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03

python scripts/run_bruteforce_allocator_scaling_experiment.py \
  --labels-dir outputs/branch_label_bruteforce_merged/gbdt_upgrade_synthetic_20260416 \
  --run-id gbdt_upgrade_scaling_uncertainty_20260416 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03 \
  --pairwise-near-tie-action downweight \
  --pairwise-near-tie-downweight 0.2 \
  --uncertainty-weighting
```

## Data note

In this workspace snapshot, the previously documented merged real corpus paths were not present as files.
A synthetic merged-format corpus was generated for integration/evaluation smoke:

- `outputs/branch_label_bruteforce_merged/gbdt_upgrade_synthetic_20260416/`
- size: 216 states, 864 candidates, 1296 pairwise rows.

Interpretation is bounded to this corpus and should **not** be treated as final real-corpus evidence.

## Matched metrics (single-seed run, seed 17)

From `gbdt_upgrade_baseline_20260416`:

- Pairwise accuracy (test):
  - pairwise logreg: **0.8846**
  - pointwise ridge: **0.8846**
  - LightGBM LambdaRank: **0.8846**
  - CatBoost YetiRankPairwise: **0.8974**
- Top-1 accuracy (test):
  - pairwise logreg: **0.9231**
  - pointwise ridge: **0.8462**
  - LightGBM LambdaRank: **0.6923**
  - CatBoost YetiRankPairwise: **0.7692**
- Near-tie slice pairwise accuracy:
  - pairwise logreg: **0.2000**
  - LightGBM: **0.4000**
  - CatBoost: **0.2000**
- Far-margin slice pairwise accuracy:
  - pairwise logreg: **0.9315**
  - LightGBM: **0.9178**
  - CatBoost: **0.9452**
- Exact-mode slice pairwise accuracy (via by-mode):
  - pairwise logreg: **0.8333**
  - LightGBM: **0.8333**
  - CatBoost: **0.8333**

Per-dataset pairwise accuracy (baseline run):

- pairwise logreg: amo_bench 0.8000, gsm8k 0.9000, math_500 1.0000
- LightGBM: amo_bench 0.8667, gsm8k 0.8667, math_500 0.9444
- CatBoost: amo_bench 0.8333, gsm8k 0.9000, math_500 1.0000

Per-budget pairwise accuracy (baseline run):

- pairwise logreg: B2 0.8750, B3 0.9333, B5 0.8333
- LightGBM: B2 0.9167, B3 0.9333, B5 0.7917
- CatBoost: B2 0.9167, B3 0.9333, B5 0.8333

## Multi-seed matched scaling summary (3 seeds, full-corpus mean)

From `gbdt_upgrade_scaling_baseline_20260416/scaling_experiment_summary.json`:

- Pairwise accuracy mean:
  - pairwise logreg: **0.9012**
  - pointwise ridge: **0.8997**
  - LightGBM: **0.8550**
  - CatBoost: **0.9001**
- Top-1 mean:
  - pairwise logreg: **0.7229**
  - pointwise ridge: **0.7532**
  - LightGBM: **0.6840**
  - CatBoost: **0.7619**
- Leave-one-dataset-out mean pairwise:
  - pairwise logreg: **0.8935**
  - pointwise ridge: **0.9009**
  - LightGBM: **0.8536**
  - CatBoost: **0.8853**

## Uncertainty-aware comparison result

Comparing baseline vs uncertainty-weighted runs:

- Single-seed run: pairwise logreg improved on pairwise accuracy (0.8846 -> 0.9231) and near-tie slice (0.2000 -> 0.6000).
- Multi-seed scaling: pairwise logreg averages decreased under this specific weighting setup (full-corpus pairwise 0.9012 -> 0.8846).
- GBDT results stayed effectively unchanged because the uncertainty controls currently target pairwise linear training path.

Conservative read: uncertainty-aware weighting **can help in some slices/runs** but is **not yet robustly improving** across seeds in this configuration.

## Answers to required questions

1. **Was LightGBM integrated successfully?**
   - Yes. Trains/runs in pipeline, model artifacts and metrics emitted.
2. **Was CatBoost integrated successfully?**
   - Yes. Trains/runs in pipeline, model artifacts and metrics emitted.
3. **Did GBDT materially improve over linear anchors?**
   - On this bounded synthetic corpus, CatBoost is broadly competitive but not materially above linear anchors overall; LightGBM underperforms linear anchors on key means.
4. **Did uncertainty-aware filtering/weighting help?**
   - Mixed. Helpful in single-seed near-tie slice for pairwise logreg; not robustly positive in 3-seed average.
5. **Broad or dataset-specific improvement?**
   - Mixed and dataset/budget dependent; no broad universal improvement signal in this bounded run.
6. **Main bottleneck now: target noise, model class, or both?**
   - Evidence remains more consistent with **target-noise/target-fidelity bottleneck plus some model-class sensitivity**, not a clean “just switch to GBDT” solution.

## Artifact paths

- Single-run baseline:
  - `outputs/branch_label_bruteforce_learning/gbdt_upgrade_baseline_20260416/`
- Single-run uncertainty:
  - `outputs/branch_label_bruteforce_learning/gbdt_upgrade_uncertainty_20260416/`
- Multi-seed scaling baseline:
  - `outputs/branch_label_bruteforce_learning/gbdt_upgrade_scaling_baseline_20260416/`
- Multi-seed scaling uncertainty:
  - `outputs/branch_label_bruteforce_learning/gbdt_upgrade_scaling_uncertainty_20260416/`
