# Canonical transfer-alignment pass (PRM800K) — 2026-04-16

## Objective

Test one bounded, decision-aligned way to use non-degenerate PRM800K supervision so it can matter on hard/ambiguous branch-allocation cases, instead of broad global blending.

## Read-first diagnosis from repaired pass artifacts

From the repaired pass:

- PRM prior is non-degenerate and shifts scores.
- Broad blend changed candidate scores but did not change pairwise decisions, so metrics remained unchanged.

Interpretation: ingestion/degeneracy was fixed; transfer alignment to decision boundaries remained the bottleneck.

## Chosen bounded intervention (single method)

Intervention: **uncertainty-gated PRM blend** (`prm800k_uncertainty_gated_blend`).

Why this is decision-aligned:

- only apply external influence on candidates most likely to matter for hard decisions:
  - high uncertainty (`allocation_value_std >= 0.03`), or
  - low gap to frontier top (`|score_gap_to_top| <= 0.04`).
- outside those targeted regions, preserve internal canonical scorer unchanged.

Score form:

- `s_base = internal reweighted pointwise score`
- `s_broad = broad PRM blended score`
- `s_aligned = s_base + gate * (s_broad - s_base)` where `gate in {0,1}` by the thresholds above.

No architecture family changes were introduced.

## Protocol (fixed)

- Internal evaluation corpus (unchanged):
  - `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1`
- External artifact used:
  - `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- Matched seed/features/weights:
  - seed `17`, feature set `v2`, same canonical runner and intervention settings.

## Exact commands run

```bash
python scripts/run_canonical_branch_learning_pass.py \
  --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 \
  --output-root outputs/canonical_branch_learning_pass \
  --run-id real_canonical_learning_20260416_external_prm800k_transfer_alignment \
  --seed 17 --near-tie-margin 0.03 --feature-set v2 \
  --hard-case-mult 1.75 --exact-promoted-mult 2.0 \
  --uncertainty-weighting \
  --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 \
  --external-supervision prm800k_uncertainty_gated_blend \
  --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 \
  --external-source-key prm800k --external-source-split train \
  --external-pointwise-blend-alpha 0.2 \
  --external-gate-uncertainty-std-threshold 0.03 \
  --external-gate-top-gap-threshold 0.04
```

## Compared models

- strongest internal anchor: `reweighted::pointwise`
- repaired broad blend: `external::prm800k_pointwise_blend_from_reweighted_pointwise`
- aligned-transfer variant: `external::prm800k_uncertainty_gated_blend_from_reweighted_pointwise`

## Metrics (broad-blend vs aligned-transfer vs anchor)

### Aggregate

- pairwise acc: anchor `1.0000`, broad `1.0000`, aligned `1.0000`
- top1 acc: anchor `1.0000`, broad `1.0000`, aligned `1.0000`

### Hard slices

All unchanged (anchor == broad == aligned):

- near-tie: `1.0000` (n=2)
- adjacent-rank: `1.0000` (n=14)
- small-margin: `1.0000` (n=11)
- exact-promoted: `1.0000` (n=1)
- exact-only: `1.0000` (n=12)
- approx-only: `1.0000` (n=9)

### Dataset slices

- `HuggingFaceH4/MATH-500`: `1.0000` (n=9) for all three
- `openai/gsm8k`: `1.0000` (n=12) for all three

### Budget slices

- budget=2: `1.0000` (n=12) for all three
- budget=3: `1.0000` (n=3) for all three
- budget=4: `1.0000` (n=6) for all three

## Behavioral activity diagnostics

### Broad blend

- candidate score changed fraction: `1.0000` (all test candidates shifted)
- pair decision changed fraction: `0.0000`
- hard-slice pair decisions changed: `0 / 14`

### Aligned transfer (targeted)

- targeted candidate fraction: `0.6667` (14/21)
- targeted changed fraction: `1.0000` (all targeted candidates shifted)
- candidate score changed fraction (overall): `0.6667`
- pair decision changed fraction: `0.0000`
- hard-slice pair decisions changed: `0 / 14`

Conclusion from activity diagnostics:

- aligned intervention is behaviorally active exactly where intended (targeted candidates),
- but still does not move branch-comparison decisions on this eval split.

## Conservative conclusion

- non-degenerate external signal: ✅
- decision-aligned targeted usage: ✅
- measurable branch-allocation gains: ❌ (none observed)

This indicates current bottleneck is still **decision-boundary movement** rather than external ingestion or raw score-shift generation.

## Recommendation (next pass)

- Keep Math-Shepherd waiting.
- Next narrow pass should focus on comparator-boundary movement (e.g., tie-break-only override when internal pairwise confidence is low), while keeping the same canonical protocol and conservative claims.

## Files added/modified

- Modified: `scripts/run_canonical_branch_learning_pass.py`
- Added: `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_TRANSFER_ALIGNMENT_PASS_2026_04_16.md`
- Added: `docs/canonical_external_supervision_prm800k_transfer_alignment_pass_2026_04_16_summary.json`
