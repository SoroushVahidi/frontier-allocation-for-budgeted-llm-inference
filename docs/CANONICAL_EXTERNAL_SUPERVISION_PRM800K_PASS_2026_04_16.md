# Canonical external-supervision pass: PRM800K (2026-04-16)

## Objective

Test whether externally integrated process-supervision data (PRM800K) improves the canonical branch-allocation learning setup, with internal evaluation fixed to branch-priority / next-step allocation over active branches.

## Canonical corpora and artifacts used

- Internal canonical evaluation corpus (fixed): `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1`
- External corpus artifact (built/reused): `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- External dataset used in this pass: **PRM800K only** (`source_dataset_key=prm800k`, `source_split=train`)

## External provenance (explicit)

From `summary.json` in the external corpus artifact:

- `source_dataset_key`: `prm800k`
- `source_split`: `train`
- human-labeled vs rollout-estimated vs verifier-backed (PRM slice):
  - `human_labeled_true=128`
  - `rollout_estimated_true=0`
  - `verifier_backed_true=0`
- native vs derived supervision interpretation (PRM slice):
  - `native_supervision_interpretation=0`
  - `derived_supervision_interpretation=128`

Interpretation caveat: in this conservative build, PRM rows were integrated as **derived candidate-quality supervision** (candidate-first) rather than native branch-allocation labels.

## Training path added (conservative, matched)

Added one bounded external-supervision path in the canonical runner:

- New path: `external-supervision=prm800k_pointwise_blend`
- Mechanism:
  1. Fit a lightweight external ridge prior on PRM candidate quality in canonical feature space (derived mapping).
  2. Blend this prior with the internal reweighted pointwise model weights:
     - `w_blend = (1-alpha)*w_internal + alpha*w_external`
     - `b_blend = (1-alpha)*b_internal + alpha*b_external`
  3. Evaluate under the unchanged canonical internal protocol/slices.

No large architecture changes were introduced.

## Exact commands run

1. Build external corpus artifact:

```bash
python scripts/build_external_prm_mathshepherd_apps_corpus.py \
  --run-id external_prm_mathshepherd_apps_20260416 \
  --output-root outputs/branch_learning_corpora_external \
  --max-rows-per-dataset 128
```

2. Matched canonical baseline run:

```bash
python scripts/run_canonical_branch_learning_pass.py \
  --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 \
  --output-root outputs/canonical_branch_learning_pass \
  --run-id real_canonical_learning_20260416_baseline_repro \
  --seed 17 --near-tie-margin 0.03 --feature-set v2 \
  --hard-case-mult 1.75 --exact-promoted-mult 2.0 \
  --uncertainty-weighting \
  --intervention balanced_hardcase_weighting --intervention-target-boost 0.6
```

3. PRM800K-assisted run (same protocol + one external path):

```bash
python scripts/run_canonical_branch_learning_pass.py \
  --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 \
  --output-root outputs/canonical_branch_learning_pass \
  --run-id real_canonical_learning_20260416_external_prm800k_pointwise_blend \
  --seed 17 --near-tie-margin 0.03 --feature-set v2 \
  --hard-case-mult 1.75 --exact-promoted-mult 2.0 \
  --uncertainty-weighting \
  --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 \
  --external-supervision prm800k_pointwise_blend \
  --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 \
  --external-source-key prm800k --external-source-split train \
  --external-pointwise-blend-alpha 0.2
```

## Baseline vs PRM800K-assisted comparison

Anchor comparison:

- strongest matched baseline anchor: `reweighted::pointwise`
- external anchor: `external::prm800k_pointwise_blend_from_reweighted_pointwise`

### Aggregate

- Pairwise accuracy: baseline **1.0000** vs PRM-assisted **1.0000** (delta **+0.0000**)
- Top-1 accuracy: baseline **1.0000** vs PRM-assisted **1.0000** (delta **+0.0000**)

### Hard slices

- near-tie: baseline 1.0000 (n=2) vs PRM 1.0000 (n=2), delta +0.0000
- adjacent-rank: baseline 1.0000 (n=14) vs PRM 1.0000 (n=14), delta +0.0000
- small-margin: baseline 1.0000 (n=11) vs PRM 1.0000 (n=11), delta +0.0000
- exact-promoted: baseline 1.0000 (n=1) vs PRM 1.0000 (n=1), delta +0.0000
- exact-only: baseline 1.0000 (n=12) vs PRM 1.0000 (n=12), delta +0.0000
- approx-only: baseline 1.0000 (n=9) vs PRM 1.0000 (n=9), delta +0.0000

### Dataset slices

- `HuggingFaceH4/MATH-500`: baseline 1.0000 (n=9) vs PRM 1.0000 (n=9)
- `openai/gsm8k`: baseline 1.0000 (n=12) vs PRM 1.0000 (n=12)

### Budget slices

- budget=2: baseline 1.0000 (n=12) vs PRM 1.0000 (n=12)
- budget=3: baseline 1.0000 (n=3) vs PRM 1.0000 (n=3)
- budget=4: baseline 1.0000 (n=6) vs PRM 1.0000 (n=6)

## What improved / did not improve

- Improved: **no measurable gain** on aggregate or hard slices in this pass.
- Did not improve: branch-comparison quality, hard-slice behavior, budget slices were unchanged.

## Honest PRM800K diagnosis

- PRM800K here is process supervision, not native branch-allocation supervision.
- In this run, the external prior fit was degenerate (near-constant), so the blended scorer did not materially alter the internal scorer behavior.
- Therefore this pass does **not** provide evidence that external process supervision solved the branch-allocation bottleneck; it only validates a conservative integration/evaluation path.

## Math-Shepherd next-pass recommendation

Proceed to Math-Shepherd as the next external pass **only after** improving non-degenerate candidate-quality extraction/mapping (so external priors carry signal). Keep APPS blocked/caveated until loader compatibility is resolved conservatively.

## Files added/modified in this pass

- Modified: `scripts/run_canonical_branch_learning_pass.py`
- Modified: `scripts/build_external_prm_mathshepherd_apps_corpus.py`
- Added: `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_PASS_2026_04_16.md`
- Added: `docs/canonical_external_supervision_prm800k_pass_2026_04_16_summary.json`
