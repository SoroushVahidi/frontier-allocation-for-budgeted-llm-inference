# Tie-aware hybrid gating audit result note (new-paper track)

Date: 2026-04-14  
Run: `outputs/new_paper/tie_aware_hybrid_gating/20260414T211020Z`

## Scope
Cheap bounded audit of a regime-gated hybrid branch scorer:
- default = proxy BT
- gated fallback = Rao-Kupper
- no heavy training, no API-backed eval, simulator only

## Inputs audited first
- `scripts/run_new_paper_tie_aware_bt.py`
- `scripts/run_new_paper_tie_aware_bt_stability.py`
- `experiments/scoring.py`
- prior tracked note: `experiments/tie_aware_bt_stability_result_note.md`

## Hybrid design
Implemented `RegimeGatedHybridBTBranchScorer` in `experiments/scoring.py`.

Behavior:
1. rank branches with proxy BT
2. inspect top-2 regime signals (score-gap, Rao tie-probability, remaining-budget, verify-count, stalled-steps)
3. if gate is inactive: keep proxy top branch
4. if gate is active: use Rao-Kupper only to decide top-vs-second branch

No meta-model added; only simple bounded rules.

## Gating rules swept (small set)
- extreme near-tie only
- medium ambiguity band
- tie-probability high
- uncertainty band excluding degenerate near-ties
- non-low-budget uncertainty

## Main result
The hybrid did **not** beat proxy BT or global Rao-Kupper in this run.

From `method_metrics.csv`:
- proxy BT mean accuracy: **0.5972**
- global Rao-Kupper mean accuracy: **0.6944** (wins vs proxy: 3/4 seeds)
- best hybrid (`extreme near-tie only`) mean accuracy: **0.5278**

So this bounded hybrid implementation reduced controller performance despite being regime-gated.

## Regime diagnosis
Pairwise regime slices still suggest Rao-Kupper can help in near-tie regimes in some seeds:
- `near_tie:extreme` mean delta (Rao-Kupper - proxy) = +0.1584
- `near_tie:medium` mean delta = +0.0522
- but several broader slices were flat/negative, and controller-level hybridization did not convert this into net gains.

## Direct answers requested
- Does a regime-gated hybrid beat plain proxy BT? **No**.
- Does it beat global Rao-Kupper? **No**.
- In which regime does Rao-Kupper seem helpful? **Mostly near-tie/medium-ambiguity pair slices, seed-dependent.**
- Is gain more stable than global Rao-Kupper? **No.**
- Keep as lightweight branch? **Only as diagnosis; not as a promoted scorer.**
- Stop patching this way? **Current evidence says this simple gating patch is not a practical improvement.**

## Conservative conclusion
Keep proxy BT as default. Keep global Rao-Kupper as optional experimental reference. Do not adopt this specific regime-gated hybrid as the next default lightweight branch.
