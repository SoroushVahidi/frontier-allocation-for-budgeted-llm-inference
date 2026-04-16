# Canonical comparator-boundary pass (PRM800K) — 2026-04-16

## Scope

This pass is intentionally narrow and comparator-boundary-specific for branch allocation under budget.

Chosen intervention (single method):

- **`prm800k_comparator_boundary_tiebreak`**
- Rule: only override internal pair decisions when both are true:
  - internal pair margin is small (`|s_i - s_j| <= boundary_pair_margin_threshold`), and
  - pair uncertainty is non-trivial (`pair_uncertainty_std_mean >= boundary_pair_uncertainty_std_threshold`).
- In that eligible region, use PRM-broad blended scorer only as tie-break comparator; outside it, keep internal comparator decision unchanged.

No broad architecture changes were introduced.

## Read-first transfer-alignment confirmation

Read artifact first:

- `docs/canonical_external_supervision_prm800k_transfer_alignment_pass_2026_04_16_summary.json`

Confirmed from latest repaired/aligned transfer artifact:

- candidate-score movement occurred (broad and aligned paths changed candidate scores),
- but **pair decision changed count remained 0**,
- therefore **no metric deltas** vs anchor.

Boundary-plausible regions from that artifact are exactly the hard/fragile slices:

- near-tie,
- adjacent-rank,
- small-margin.

## Canonical protocol targets (kept fixed)

- Internal eval corpus path (required):
  - `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1`
- External artifact path:
  - `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- Canonical runner:
  - `scripts/run_canonical_branch_learning_pass.py`

## Exact commands run

```bash
python -m py_compile scripts/run_canonical_branch_learning_pass.py
python scripts/run_canonical_branch_learning_pass.py --help | head -n 80
python scripts/run_canonical_branch_learning_pass.py \
  --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 \
  --output-root outputs/canonical_branch_learning_pass \
  --run-id real_canonical_learning_20260416_external_prm800k_comparator_boundary \
  --seed 17 --near-tie-margin 0.03 --feature-set v2 \
  --hard-case-mult 1.75 --exact-promoted-mult 2.0 \
  --uncertainty-weighting \
  --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 \
  --external-supervision prm800k_comparator_boundary_tiebreak \
  --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 \
  --external-source-key prm800k --external-source-split train \
  --external-pointwise-blend-alpha 0.2 \
  --external-gate-uncertainty-std-threshold 0.03 \
  --external-gate-top-gap-threshold 0.04 \
  --external-boundary-pair-margin-threshold 0.02 \
  --external-boundary-pair-uncertainty-std-threshold 0.02
```

## Execution outcome

Canonical pass execution is **blocked in this workspace** because the required canonical corpus rows are missing locally:

- missing: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1/rows/candidate_rows.jsonl`

As a result, this workspace cannot produce fresh anchor vs broad vs aligned vs boundary metrics for this pass yet.

## What was implemented for the pass

In `scripts/run_canonical_branch_learning_pass.py`:

- Added new external supervision mode:
  - `prm800k_comparator_boundary_tiebreak`
- Added bounded comparator-boundary controls:
  - `--external-boundary-pair-margin-threshold`
  - `--external-boundary-pair-uncertainty-std-threshold`
- Added comparator-boundary pair predictor:
  - base comparator unless boundary-eligible,
  - PRM-blended tie-break only in boundary-eligible region.
- Added boundary diagnostics payload (when run data is present), including:
  - eligible pair count/fraction,
  - eligible pairs where external disagrees with internal,
  - changed pair count/fraction,
  - changed helpful/harmful/neutral counts,
  - changed-by-dataset and changed-by-budget,
  - changed hard-slice count,
  - top-1 changed/helpful/harmful state counts.
- Added pairwise-tournament top-1 evaluation path for comparator-defined methods.

## Current scientific diagnosis (conservative)

- Confirmed from latest transfer artifact: candidate-score movement existed but pairwise boundary movement was zero.
- This pass now adds exactly the narrow comparator-boundary mechanism needed to test true decision-boundary movement.
- In this workspace, final empirical verdict is pending availability of canonical artifact rows.

## Math-Shepherd status

- **Math-Shepherd should still wait** until this comparator-boundary pass is actually executed on the required canonical corpus and shows non-trivial, directionally helpful boundary flips with metric support.

## Next pass recommendation

1. Restore/sync required canonical corpus + external rows at the exact paths above.
2. Re-run the exact command in this report.
3. Evaluate anchor vs broad vs aligned vs boundary using the new diagnostics and only promote if:
   - pairwise decisions actually flip in fragile regions,
   - flips are directionally helpful,
   - aggregate/hard-slice metrics improve with non-trivial support.
