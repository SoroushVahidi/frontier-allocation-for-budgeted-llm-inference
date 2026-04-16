# Learning branch-allocation models from brute-force labels

## Goal

Train learned branch-allocation policies for the core next-step frontier decision:

> Which active branch should receive the next unit of compute under remaining budget `B`?

This pipeline uses expensive brute-force/near-brute-force supervision labels as targets.

## Inputs

Expected label directory from `run_bruteforce_branch_label_generator.py`:

- `candidate_labels.jsonl`
- `pairwise_labels.jsonl`
- `state_summaries.jsonl`

## Model families implemented

1. **Pairwise model** (`pairwise_logreg`)
   - Trained on pairwise preferences (`pairwise_labels.jsonl`) using feature differences.
2. **Pointwise model** (`pointwise_ridge`)
   - Trained on per-branch scalar continuation labels (`candidate_labels.jsonl`).
3. **Outside-option model** (`outside_option_logreg`)
   - Trained on whether branch beats best in-state outside option (`branch_vs_outside_gap > 0`).

## Feature extraction

Feature family: `ALLOC_FEATURE_NAMES` in `experiments/bruteforce_branch_allocator.py`.

Primary branch/state features include:

- remaining budget,
- branch score/depth/stall/recent delta/verify count/age,
- parent-relative score,
- allocation-evaluation diagnostics,
- exact/approx mode indicators.

`run_bruteforce_branch_label_generator.py` now stores `features_branch_v1` in candidate rows so learning does not collapse to branch-id-only heuristics.

## Training script

- `scripts/train_bruteforce_branch_allocator.py`

Outputs under `outputs/branch_label_bruteforce_learning/<run_id>/`:

- `models.json`
- `evaluation.json`
- `manifest.json`
- `progress.json`
- `report.md`

Resume behavior:

- `--resume` exits early if `models.json`, `evaluation.json`, and `manifest.json` already exist.

## Evaluation script

- `scripts/evaluate_bruteforce_branch_allocator.py`

Recomputes evaluation from `models.json` + label directory and writes JSON + markdown report.

## Metrics reported

For each model family:

- pairwise accuracy,
- ranking top-1 accuracy (winner agreement),
- agreement with brute-force labels,
- near-tie pairwise accuracy,
- far-margin pairwise accuracy,
- pairwise margin Brier score,
- pairwise accuracy by exact/approx mode,
- pairwise accuracy by remaining-budget slice,
- pairwise accuracy by dataset slice.

## Safe claims

Safe:

- this is learned approximation to expensive branch-allocation supervision,
- ranking/allocation alignment can be measured against brute-force label artifacts,
- near-tie behavior is explicitly audited.

Not safe:

- claiming oracle-equivalent real-model allocation performance,
- claiming universal gains across all controllers/datasets from one label run,
- interpreting this as a stop-centric final controller result.

## Small pilot command

```bash
python scripts/train_bruteforce_branch_allocator.py \
  --labels-dir outputs/branch_label_bruteforce/pilot_small \
  --run-id pilot_learning \
  --seed 17
```

## Heavier command

```bash
python scripts/train_bruteforce_branch_allocator.py \
  --labels-dir outputs/branch_label_bruteforce/heavy_bruteforce_gsm8k \
  --run-id heavy_learning_gsm8k \
  --seed 17 \
  --pairwise-max-iter 1200 \
  --outside-max-iter 1200 \
  --pointwise-alpha 0.5
```

## Re-evaluation command

```bash
python scripts/evaluate_bruteforce_branch_allocator.py \
  --labels-dir outputs/branch_label_bruteforce/heavy_bruteforce_gsm8k \
  --models-json outputs/branch_label_bruteforce_learning/heavy_learning_gsm8k/models.json
```
