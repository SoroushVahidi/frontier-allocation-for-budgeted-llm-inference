# BT reliability-weighted branch scorer — audit and result note

## Audit of current BT path

What is working well now:
- Ordered-history v7 features and pairwise BT supervision improved simulator-backed branch selection.
- Inference remains efficient and scalar (one utility score per branch, argmax).

Next bottleneck:
- Pairwise labels are heterogeneous in trustworthiness.
- Some pair comparisons are borderline (small preference margins, unstable local trajectories, weak budget fit), so uniform loss weighting can overfit noisy supervision.

Why focus on noisy pairwise supervision now:
- After adding richer branch encoding, supervision quality is the likely limiter.
- Confidence-weighted BT is a low-risk extension that keeps the same pairwise-train/scalar-infer design while reducing impact of weak labels.

## Reliability-aware additions in this pass

- Pairwise dataset now records transparent weak reliability signals:
  - `preference_margin`
  - `pair_confidence`
  - `tie_or_uncertain`
  - component signals (`rel_*` columns)
- BT training supports:
  - plain unweighted BT
  - confidence-weighted BT
  - optional low-confidence filtering and uncertain-pair dropping
- Controller comparisons now include:
  - `adaptive_min_expand_1`
  - `adaptive_bt_pairwise` (plain)
  - `adaptive_bt_pairwise_reliability`
  - `adaptive_bt_pairwise_reliability_filtered`

## Honest interpretation guidance

- Reliability scores are **weak heuristics**, not true label correctness probabilities.
- Treat gains as pilot evidence for next-iteration scorer training, not a final solution.

## Pilot outcomes from this pass

- GSM8K simulator run: `outputs/new_paper/bt_reliability_weighted_branch_scorer/20260414T021946Z/`
  - plain BT controller accuracy: `0.4667`
  - reliability-weighted BT: `0.6000`
  - weighted + filtering: `0.6000`
  - conclusion: reliability weighting improved over plain BT in this run.
- MATH simulator run: `outputs/new_paper/bt_reliability_weighted_branch_scorer/20260414T022105Z/`
  - plain BT controller accuracy: `0.7500`
  - reliability-weighted BT: `0.5000`
  - weighted + filtering: `0.4500`
  - conclusion: plain BT remained strongest in this run.
- Real-model-backed attempt: `outputs/new_paper/bt_reliability_weighted_branch_scorer/20260414T022228Z/`
  - training completed, evaluation timed out under `timeout 120s`; no stable API-backed comparison table available yet.
