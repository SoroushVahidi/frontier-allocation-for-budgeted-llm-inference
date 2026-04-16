# Brute-force label scaling status (2026-04-16, multi-dataset campaign)

This note records a real multi-dataset brute-force / near-brute-force branch-label scaling campaign, merged-corpus consolidation, and learned allocator scaling evaluation.

## Commands executed

### Part A — Large-scale label generation

```bash
for ds in openai/gsm8k HuggingFaceH4/MATH-500 meituan-longcat/AMO-Bench; do
  for seed in 11 29; do
    for maxb in 4 5 6; do
      python scripts/run_bruteforce_branch_label_generator.py \
        --run-id multi_dataset_scaling_20260416_$(echo $ds | tr '/-' '__')_b${maxb}_s${seed} \
        --dataset-name "$ds" \
        --max-frontier-states 36 \
        --episodes-per-example 2 \
        --frontier-budget 8 \
        --min-remaining-budget 2 \
        --max-remaining-budget "$maxb" \
        --init-branches 4 \
        --max-branches-per-state 5 \
        --rollout-samples-per-candidate 20 \
        --max-allocation-samples 48 \
        --seed "$seed" \
        --disable-mock-data-fallback
    done
  done
done

for ds in openai/gsm8k HuggingFaceH4/MATH-500 meituan-longcat/AMO-Bench; do
  python scripts/run_bruteforce_branch_label_generator.py \
    --run-id multi_dataset_scaling_20260416_exact_$(echo $ds | tr '/-' '__')_s11 \
    --dataset-name "$ds" \
    --max-frontier-states 12 \
    --episodes-per-example 1 \
    --frontier-budget 6 \
    --min-remaining-budget 2 \
    --max-remaining-budget 4 \
    --init-branches 3 \
    --max-branches-per-state 3 \
    --rollout-samples-per-candidate 20 \
    --exact-mode \
    --max-exact-branches 4 \
    --max-exact-remaining-budget 5 \
    --seed 11 \
    --disable-mock-data-fallback
 done
```

### Part B — Corpus consolidation

```bash
python scripts/merge_bruteforce_branch_label_runs.py \
  --run-ids-file /tmp/label_runs.txt \
  --run-id multi_dataset_scaling_merged_20260416_v2 \
  --near-tie-margin 0.03
```

### Part C — Learned allocator training/evaluation scaling

```bash
python scripts/run_bruteforce_allocator_scaling_experiment.py \
  --labels-dir outputs/branch_label_bruteforce_merged/multi_dataset_scaling_merged_20260416_v2 \
  --run-id multi_dataset_scaling_learning_20260416_v2 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03
```

## Datasets successfully used

- `openai/gsm8k`
- `HuggingFaceH4/MATH-500`
- `meituan-longcat/AMO-Bench`

GPQA Diamond was not included in this pass.

## Corpus size and scaling summary

Merged corpus: `outputs/branch_label_bruteforce_merged/multi_dataset_scaling_merged_20260416_v2/`

- Frontier states: **684**
- Candidate rows: **1,857**
- Pairwise rows: **1,755**
- Raw rollout rows: **441,660**

Compared to prior medium GSM8K run (220 states / 593 candidate / 559 pairwise):

- states scale-up: **3.11x**
- candidate-row scale-up: **3.13x**
- pairwise-row scale-up: **3.14x**

### Counts by dataset (candidate rows)

- `openai/gsm8k`: 619
- `HuggingFaceH4/MATH-500`: 619
- `meituan-longcat/AMO-Bench`: 619

### Counts by remaining budget (candidate rows)

- budget 2: 285
- budget 3: 450
- budget 4: 540
- budget 5: 372
- budget 6: 210

### Exact vs approximate provenance

- approx: 1,770 candidate rows
- exact: 87 candidate rows

### Near-tie and outside-option diagnostics

(using near-tie threshold `|margin| <= 0.03`)

- near-tie pairwise rows: 412 / 1,755 (**0.235**)
- outside-option gap abs distributions and pairwise margin abs distributions are reported per dataset in:
  - `outputs/branch_label_bruteforce_merged/multi_dataset_scaling_merged_20260416_v2/merged_summary.json`

## Learned allocator metrics (multi-seed)

Training/eval artifacts: `outputs/branch_label_bruteforce_learning/multi_dataset_scaling_learning_20260416_v2/`

### Full-corpus held-out metrics (mean over seeds 11, 29, 47)

- **Pairwise learner**
  - pairwise accuracy: **0.619**
  - top-1 ranking accuracy: **0.449**
  - near-tie pairwise accuracy: **0.525**
- **Pointwise learner**
  - pairwise accuracy: **0.659**
  - top-1 ranking accuracy: **0.563**
  - near-tie pairwise accuracy: **0.569**
- **Outside-option learner**
  - pairwise accuracy: **0.563**
  - top-1 ranking accuracy: **0.462**
  - near-tie pairwise accuracy: **0.466**

Agreement with brute-force labels is numerically the reported pairwise accuracy.

### Per-dataset held-out slices (full-corpus models)

From `pairwise_accuracy_by_dataset`:

- pointwise model is strongest in this run family, with consistently higher accuracy on GSM8K and AMO-Bench than on MATH-500.
- performance is therefore improved but still dataset-sensitive.

### Exact-mode slice (when available)

Exact rows were included but are still sparse (87 candidate rows total), so exact-slice test metrics are noisy and low-confidence.

### Cross-dataset generalization (leave-one-dataset-out)

Leave-one-dataset-out training/evaluation was run for all seeds and all three datasets. Pairwise-model held-out dataset pairwise accuracy was in roughly the **0.55–0.61** range across seeds/datasets, showing non-trivial but not robustly high cross-dataset transfer.

## Part D — Scaling interpretation (safe)

- Label corpus size is materially larger than the prior medium GSM8K run (about **3.1x** on all key row-count axes).
- Learned allocator quality improved to moderate levels and is clearly trainable at this scale, with pointwise > pairwise > outside-option in this campaign.
- Improvements are **not uniformly broad**; dataset sensitivity remains and cross-dataset transfer is only moderate.
- **Bottleneck status:** still **partially resolved** (improved but not closed).

This pass reduces the remaining labeled-data bottleneck substantially, but does not justify a claim that supervision-target quality is solved.
