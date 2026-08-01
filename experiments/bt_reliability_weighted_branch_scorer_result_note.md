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

## Pilot outcomes from this pass (April 14, 2026 refresh)

- Smoke test (GSM8K simulator, n=8): `outputs/new_paper/bt_reliability_weighted_branch_scorer/20260414T025505Z/`
  - plain BT controller accuracy: `0.6250`
  - reliability-weighted BT: `0.5000`
  - weighted + filtering: `0.3750`
  - conclusion: this smoke run favored plain BT; filtered remained weakest.
- Meaningful GSM8K simulator comparison (n=48): `outputs/new_paper/bt_reliability_weighted_branch_scorer/20260414T025646Z/`
  - adaptive baseline (`adaptive_min_expand_1`): `0.3958`
  - plain BT: `0.5833`
  - reliability-weighted BT: `0.5417`
  - weighted + filtering: `0.5208`
  - oracle upper bound: `0.9375`
  - conclusion: plain BT remained strongest in this GSM8K setting.
- Meaningful MATH simulator comparison (EleutherAI/hendrycks_math, n=32): `outputs/new_paper/bt_reliability_weighted_branch_scorer/20260414T025831Z/`
  - adaptive baseline (`adaptive_min_expand_1`): `0.4062`
  - plain BT: `0.5625`
  - reliability-weighted BT: `0.5938`
  - weighted + filtering: `0.5312`
  - oracle upper bound: `1.0000`
  - conclusion: reliability weighting improved over plain BT in this run.
- Real-model-backed small run attempt (GSM8K, OpenAI API enabled): `outputs/new_paper/bt_reliability_weighted_branch_scorer/20260414T030018Z/`
  - pairwise dataset + BT training artifacts were produced,
  - controller evaluation was bounded with `timeout 180s` and exited with code `124`,
  - therefore no completed `method_metrics.csv` / `run_manifest.json` was produced.
  - this is recorded as incomplete rather than treated as a win/loss.

## Additional diagnostics added in this pass

- BT training artifacts now include explicit training retention stats:
  - total pairs, used pairs, dropped-low-confidence count, dropped-uncertain count.
- BT training artifacts now include confidence-bin pair accuracy on test:
  - `<0.2`, `0.2-0.5`, `>=0.5`.
- Reliability runner exports these diagnostics into `scorer_diagnostics.csv`
  to make “do low-confidence pairs hurt?” checks auditable.
- In current simulator datasets, `pair_confidence` is heavily concentrated at `>=0.5`,
  so low-confidence filtering by threshold alone has little effect; uncertain-pair
  filtering (`tie_or_uncertain`) is currently the stronger ablation lever.
