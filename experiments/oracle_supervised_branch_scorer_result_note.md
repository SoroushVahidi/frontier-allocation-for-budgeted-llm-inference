# Oracle-supervised branch scorer result note (new-paper, 2026-04-14)

## Scope
This pass stays on the **new-paper branch-allocation track** and compares:
- current proxy-supervised BT branch scorer,
- oracle-ish-supervised BT branch scorer,
- oracle upper bound (best strategy among compared methods per example).

All oracle-ish supervision is from **approximate bounded oracle-ish continuation labels**,
not exact global oracle continuation values.

## Implemented path
- `experiments/oracle_branch_labels.py`
  - adds `features_v7` and train/test `split` fields so generated oracle-ish labels are directly trainable.
- `scripts/build_oracle_pairwise_branch_dataset.py`
  - converts `branch_oracle_labels.jsonl` to BT pairwise data using `approx_oracle_continuation_value`.
- `experiments/frontier_matrix_core.py`
  - adds `adaptive_bt_pairwise_oracle` strategy for clean side-by-side evaluation.
- `scripts/run_new_paper_oracle_supervised_branch_scorer.py`
  - end-to-end bounded experiment runner:
    1) generate/load oracle-ish labels,
    2) build oracle-ish pairwise supervision,
    3) build current proxy pairwise supervision,
    4) train both BT scorers,
    5) evaluate with scalar inference (one score/branch, argmax),
    6) emit comparison artifacts.

## Main bounded pilot used for reporting
Run directory:
- `outputs/new_paper/oracle_supervised_branch_scorer/20260414T144959Z/`

Key metrics:
- proxy-supervised accuracy: **0.5833**
- oracle-ish-supervised accuracy: **0.5000**
- delta accuracy (oracle-ish - proxy): **-0.0833**
- proxy gap to oracle: **0.3333**
- oracle-ish gap to oracle: **0.4167**
- delta oracle gap (oracle-ish - proxy): **+0.0833** (worse)

## Interpretation
In this bounded simulator-backed run:
- oracle-ish supervision **did not beat** proxy supervision yet,
- oracle gap **did not improve**.

Most likely reason in this run:
- oracle-ish pairwise labels are much lower-confidence and more tie-heavy than proxy pairs
  (mean pair confidence ~0.138 and tie/uncertain rate ~0.738), reducing usable training signal density.

## Decision after this pass
- Oracle-ish labels should **not yet fully replace** proxy supervision as the main source.
- They remain a promising complementary source because they target continuation value directly, but need stronger coverage/calibration.

## Next logical expansion
1) increase depth/budget diversity in oracle-ish snapshot selection,
2) tighten pair construction (drop or downweight weak/tie-heavy pairs more aggressively),
3) add scalar regression on `approx_oracle_continuation_value` as an ablation,
4) rerun bounded simulator comparison before any real-model-backed claim.
