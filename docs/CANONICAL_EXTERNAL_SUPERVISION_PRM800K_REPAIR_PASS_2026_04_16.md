# Canonical targeted external-supervision repair pass (PRM800K) — 2026-04-16

## Objective

Repair the external-to-canonical extraction/mapping path so PRM800K provides a **non-degenerate** candidate-quality auxiliary signal before judging branch-allocation impact under the canonical protocol.

## Degeneracy diagnosis (evidence-based)

### Prior failure mode

In the previous PRM pass, PRM800K candidate rows had collapsed quality (`quality_score=0.0` for all sampled PRM rows), which forced the external prior into a near-constant solution.

Root cause:

1. PRM800K schema is nested (`question` is a dict; labels live under `label.steps[].completions[]` with ratings), but extraction logic treated these as flat fields (`problem`, `steps`, `labels`) and therefore missed native step ratings.
2. The fallback path produced derived coarse rows with empty branch text and default score 0.0.
3. External prior fit then saw effectively constant targets, yielding degenerate coefficients/intercept behavior.

## What was changed (bounded repair only)

### 1) PRM800K extraction fix

Implemented dedicated PRM parser in external corpus builder:

- Parse `label.steps[].completions[]` directly.
- Extract native step ratings (`-1/0/1`) and normalize to `quality_score=(rating+1)/2`.
- Preserve candidate-level metadata (`step_index`, `completion_index`, chosen completion).
- Preserve provenance fields (`source_dataset_key`, `source_split`, human/rollout/verifier flags, native vs derived interpretation).
- Build conservative derived pairwise/outside rows from native step ratings.

### 2) External-to-canonical mapping + blend-path safety

In canonical runner:

- Improved PRM row feature mapping using parsed step/completion structure.
- Added prior-fit diagnostics:
  - target mean/std,
  - nonconstant feature count,
  - explicit degenerate-target guard.
- Added blend safeguard by matching external prior weight norm to base model norm before blending.
- Added score-shift diagnostics to verify the repaired prior actually changes internal candidate scores.

No architecture family changes were introduced.

## External artifact rebuilt

- Rebuilt external corpus path:
  - `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- Provenance remains explicit in `summary.json` with per-dataset counters (split, human/rollout/verifier, native-vs-derived).

## Exact commands run

```bash
python scripts/build_external_prm_mathshepherd_apps_corpus.py \
  --run-id external_prm_mathshepherd_apps_20260416 \
  --output-root outputs/branch_learning_corpora_external \
  --max-rows-per-dataset 128
```

```bash
python scripts/run_canonical_branch_learning_pass.py \
  --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 \
  --output-root outputs/canonical_branch_learning_pass \
  --run-id real_canonical_learning_20260416_baseline_repro_repaired_mapping \
  --seed 17 --near-tie-margin 0.03 --feature-set v2 \
  --hard-case-mult 1.75 --exact-promoted-mult 2.0 \
  --uncertainty-weighting \
  --intervention balanced_hardcase_weighting --intervention-target-boost 0.6
```

```bash
python scripts/run_canonical_branch_learning_pass.py \
  --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 \
  --output-root outputs/canonical_branch_learning_pass \
  --run-id real_canonical_learning_20260416_external_prm800k_pointwise_blend_repaired_mapping \
  --seed 17 --near-tie-margin 0.03 --feature-set v2 \
  --hard-case-mult 1.75 --exact-promoted-mult 2.0 \
  --uncertainty-weighting \
  --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 \
  --external-supervision prm800k_pointwise_blend \
  --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 \
  --external-source-key prm800k --external-source-split train \
  --external-pointwise-blend-alpha 0.2
```

## Is external signal still degenerate?

No.

After repair:

- PRM candidate rows used in prior fit: `n=6616`
- Quality distribution is non-constant: `{0.0: 2806, 0.5: 1379, 1.0: 2431}`
- Prior fit: `status=ok`, `target_std=0.4439`, `nonconstant_feature_count=8`
- Internal test score shift from blended prior is real:
  - mean abs shift: `0.0311`
  - max abs shift: `0.0475`

So the repair successfully fixed the non-degenerate extraction/mapping problem.

## Baseline vs repaired PRM800K-assisted comparison (canonical internal eval fixed)

Internal evaluation corpus (unchanged):

- `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1`

Anchor comparison:

- strongest canonical anchor: `reweighted::pointwise`
- repaired external anchor: `external::prm800k_pointwise_blend_from_reweighted_pointwise`

### Aggregate

- pairwise accuracy: baseline `1.0000` vs external `1.0000` (delta `+0.0000`)
- top-1 accuracy: baseline `1.0000` vs external `1.0000` (delta `+0.0000`)

### Hard slices

- near-tie: baseline `1.0000` (n=2) vs external `1.0000` (n=2), delta `+0.0000`
- adjacent-rank: baseline `1.0000` (n=14) vs external `1.0000` (n=14), delta `+0.0000`
- small-margin: baseline `1.0000` (n=11) vs external `1.0000` (n=11), delta `+0.0000`
- exact-promoted: baseline `1.0000` (n=1) vs external `1.0000` (n=1), delta `+0.0000`
- exact-only: baseline `1.0000` (n=12) vs external `1.0000` (n=12), delta `+0.0000`
- approx-only: baseline `1.0000` (n=9) vs external `1.0000` (n=9), delta `+0.0000`

### Dataset slices

- `HuggingFaceH4/MATH-500`: baseline `1.0000` (n=9) vs external `1.0000` (n=9)
- `openai/gsm8k`: baseline `1.0000` (n=12) vs external `1.0000` (n=12)

### Budget slices

- budget=2: baseline `1.0000` (n=12) vs external `1.0000` (n=12)
- budget=3: baseline `1.0000` (n=3) vs external `1.0000` (n=3)
- budget=4: baseline `1.0000` (n=6) vs external `1.0000` (n=6)

## Conservative conclusion

- **Fixed:** external extraction/mapping degeneracy (signal now non-degenerate and behaviorally active).
- **Not yet achieved:** measurable branch-allocation gains on aggregate or hard slices in this matched pass.

Therefore, this pass separates three claims cleanly:

1. extraction path bug fixed ✅
2. non-degenerate PRM auxiliary prior achieved ✅
3. branch-allocation bottleneck improved ❌ (not shown here)

## Recommendation on Math-Shepherd next

Do **not** proceed to Math-Shepherd yet. First improve transfer-to-bottleneck sensitivity (or harder internal eval coverage) so a non-degenerate external signal has a chance to move branch-comparison outcomes.

## Files added/modified

- Modified: `scripts/build_external_prm_mathshepherd_apps_corpus.py`
- Modified: `scripts/run_canonical_branch_learning_pass.py`
- Added: `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_REPAIR_PASS_2026_04_16.md`
- Added: `docs/canonical_external_supervision_prm800k_repair_pass_2026_04_16_summary.json`
