# Brute-force label data status (2026-04-16)

This note records a real medium-scale branch-label generation pass and a bounded exact-vs-approx quality comparison pass.

## Run commands (executed)

### Medium-scale generation (GSM8K, approx mode)

```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --run-id gsm8k_medium_20260416 \
  --dataset-name openai/gsm8k \
  --max-frontier-states 220 \
  --episodes-per-example 2 \
  --frontier-budget 8 \
  --min-remaining-budget 2 \
  --max-remaining-budget 5 \
  --init-branches 4 \
  --max-branches-per-state 5 \
  --rollout-samples-per-candidate 20 \
  --max-allocation-samples 48 \
  --seed 23 \
  --disable-mock-data-fallback
```

### Exact-vs-approx comparison slice (same seeded state capture)

```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --run-id gsm8k_exact_slice_20260416 \
  --dataset-name openai/gsm8k \
  --max-frontier-states 90 \
  --episodes-per-example 1 \
  --frontier-budget 6 \
  --min-remaining-budget 2 \
  --max-remaining-budget 4 \
  --init-branches 3 \
  --max-branches-per-state 3 \
  --rollout-samples-per-candidate 28 \
  --exact-mode \
  --max-exact-branches 4 \
  --max-exact-remaining-budget 5 \
  --seed 31 \
  --disable-mock-data-fallback

python scripts/run_bruteforce_branch_label_generator.py \
  --run-id gsm8k_approx_slice_20260416 \
  --dataset-name openai/gsm8k \
  --max-frontier-states 90 \
  --episodes-per-example 1 \
  --frontier-budget 6 \
  --min-remaining-budget 2 \
  --max-remaining-budget 4 \
  --init-branches 3 \
  --max-branches-per-state 3 \
  --rollout-samples-per-candidate 28 \
  --max-allocation-samples 8 \
  --seed 31 \
  --disable-mock-data-fallback
```

### Pilot learner training + quality aggregation

```bash
python scripts/train_bruteforce_branch_allocator.py \
  --labels-dir outputs/branch_label_bruteforce/gsm8k_medium_20260416 \
  --run-id gsm8k_medium_20260416_pilot \
  --seed 23 \
  --near-tie-margin 0.03

python scripts/analyze_bruteforce_label_quality.py \
  --medium-run-dir outputs/branch_label_bruteforce/gsm8k_medium_20260416 \
  --exact-run-dir outputs/branch_label_bruteforce/gsm8k_exact_slice_20260416 \
  --approx-run-dir outputs/branch_label_bruteforce/gsm8k_approx_slice_20260416 \
  --training-eval-json outputs/branch_label_bruteforce_learning/gsm8k_medium_20260416_pilot/evaluation.json \
  --near-tie-margin 0.03 \
  --output-json outputs/branch_label_bruteforce/gsm8k_medium_20260416/quality_report.json \
  --output-md outputs/branch_label_bruteforce/gsm8k_medium_20260416/quality_report.md
```

## Artifacts

- `outputs/branch_label_bruteforce/gsm8k_medium_20260416/`
- `outputs/branch_label_bruteforce/gsm8k_exact_slice_20260416/`
- `outputs/branch_label_bruteforce/gsm8k_approx_slice_20260416/`
- `outputs/branch_label_bruteforce_learning/gsm8k_medium_20260416_pilot/`

## Medium-scale corpus summary

- Frontier states labeled: **220**
- Candidate rows: **593**
- Pairwise rows: **559**
- Raw rollout rows: **137,620**
- Mode counts: `{"approx": 220}`

## Label quality summary

Using near-tie threshold `|margin| <= 0.03`:

- Near-tie pairwise rate: **0.242** (135 / 559)
- Margin `|abs|` distribution: p50 **0.0668**, p90 **0.1614**
- Branch-vs-outside `|gap|` distribution: p50 **0.0670**, p90 **0.1640**
- Winner branch-vs-outside gap p50: **0.0540**

Per-budget near-tie rates were fairly stable:

- budget 2: 0.259
- budget 3: 0.241
- budget 4: 0.248
- budget 5: 0.232

## Exact-vs-approx agreement (overlapping feasible tiny states)

- Overlap states: **90**
- Overlap candidate rows: **205**
- Winner agreement: **86 / 90 = 0.956**
- Branch-vs-outside sign agreement: **197 / 205 = 0.961**
- Branch-vs-outside absolute gap difference: p50 **0.0000**, p90 **0.0289**

Interpretation: approximate mode is reasonably aligned with exact mode on tiny feasible states and appears usable as a supervision source, but not perfect (there are disagreements).

## Pilot learner usability check

Training ran successfully on the medium corpus.

Held-out test metrics:

- Pairwise model: pairwise accuracy **0.558**, top-1 ranking accuracy **0.407**
- Pointwise model: pairwise accuracy **0.519**, top-1 ranking accuracy **0.370**
- Outside-option model: pairwise accuracy **0.519**, top-1 ranking accuracy **0.407**

Interpretation: labels are usable for learning in a bounded pilot sense, but not yet high-signal enough to claim robust strong generalization.

## Canonical interpretation update

Status of “not enough label data” bottleneck after this run:

> **partially resolved**.

What is now true:
- pipeline exists and was run at medium scale with real GSM8K-backed examples,
- branch-comparison supervision volume is materially larger than tiny pilots,
- approximate labels show strong-but-imperfect agreement with exact tiny-state labels,
- learning runs end-to-end successfully.

What is still not true:
- bottleneck fully resolved,
- robust high-accuracy learned allocator already demonstrated,
- evidence broad across datasets/seeds/budgets to claim closure.
