# Lightweight algorithm audit result note (new-paper, 2026-04-14)

This pass stays entirely on the **new-paper track** and uses only cheap/interpretable methods.
No heavy training and no API-backed evaluation were used.

## Run
- Output root: `outputs/new_paper/lightweight_algorithm_audit/20260414T155307Z/`

## Clean data source used
- Primary analysis source: held-out rows from the proxy BT pairwise dataset built from
  `build_v3_ranking_dataset.py` + `build_bt_pairwise_branch_dataset.py` in this run.
- This was chosen because it is the closest cheap supervised signal for current proxy BT behavior,
  and includes ordered-history features plus pair confidence/reliability metadata.

## Main failure pattern (single biggest)
- Strongest error slice: **small score-separation pairs** (`abs_node_3_score_diff <= 0.06`).
- Slice stats:
  - coverage: `0.236`
  - error rate: `0.322`
  - error lift vs global pair error: `+0.110`
- Global held-out pair error was `0.212`.

Interpretation:
- The current algorithm is mostly solid on high-confidence/high-separation pairs,
  but degrades materially in low-separation comparisons where branch utilities are close.

## Over-reliance signals
- Interpretable probes (shallow decision tree + logistic regression on error target)
  indicate strongest error correlation with low confidence and small score separation.
- This suggests over-reliance on a narrow score-like signal in near-tie contexts,
  where history/reliability cues are not resolving ambiguities well.

## Cheap improvement tested
- Implemented a lightweight post-hoc BT inference calibration:
  1) if BT top-2 score gap is very small, fallback to raw-score ranking,
  2) apply mild penalty in low-budget + stalled + high-verify regime.

## Before vs after
- Baseline proxy BT controller accuracy: `0.6250`
- Calibrated lightweight variant: `0.53125`
- Delta: `-0.09375` (worse)

## Decision
- Keep the **failure-slice analysis** as the useful output.
- Do **not** adopt this specific calibration as a practical baseline improvement.
- Baseline proxy BT remains hard to beat with simple hand-crafted post-hoc rules.

## What to avoid next
- Avoid stacking additional ad-hoc inference rules without first improving near-tie signal quality.
- Avoid expensive large-model retraining until low-separation discrimination is improved with bounded/cheap methods.
