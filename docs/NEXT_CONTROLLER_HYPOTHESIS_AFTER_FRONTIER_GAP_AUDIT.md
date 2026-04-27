# NEXT_CONTROLLER_HYPOTHESIS_AFTER_FRONTIER_GAP_AUDIT

This note defines next-controller candidates after the frontier-gap audit. It does not implement controller changes.

## A) `semantic_minimum_maturation_frontier_v1`

- Failure mode targeted: bad seeding hidden by redundant roots, and bad maturation where plausible branches never reach depth 2/3.
- Diagnostic evidence required:
  - high root-branch count but low semantic-family count,
  - high redundancy ratio,
  - losses where plausible families exist but remain shallow.
- Core behavior:
  - cluster early branches into semantic reasoning families,
  - enforce per-family minimum maturation depth (`d_min=2` or `3`) for viable families,
  - do not treat redundant roots as independent coverage,
  - allocate remaining budget adaptively after maturation floor.
- New logs required:
  - `family_id`, `family_cluster_features`, `family_viability`,
  - per-family maturation depth progression,
  - forced maturation actions and released actions.
- Evaluation:
  - compare vs `strict_f3` and `external_l1_max` on matched budget slices,
  - primary: accuracy and absent-from-tree reduction,
  - secondary: present-not-selected, family redundancy ratio, family depth>=2/3 share.
- Different from `strict_f2/strict_f3/gate1-cap-k6`:
  - existing methods enforce root-depth coverage by branch lineage, not semantic-family normalization.

## B) `direct_reserve_semantic_frontier_v1`

- Failure mode targeted: bad allocation and bad selection in cases where direct answer is already strong.
- Diagnostic evidence required:
  - many cases where `external_l1_max` is correct while `strict_f3` is absent-from-tree,
  - low incremental gain from full frontier search under weak semantic diversity.
- Core behavior:
  - preserve direct/L1 incumbent,
  - seed semantic families as challengers,
  - permit challenger replacement only with guarded evidence (margin + consistency + maturity),
  - keep incumbent when challenger evidence remains weak/fragmented.
- New logs required:
  - incumbent confidence state over time,
  - challenger-over-incumbent replacement triggers and blocked replacements,
  - challenger maturity and support margin at decision points.
- Evaluation:
  - pairwise strict comparison with `strict_f3` and `external_l1_max`,
  - report win/loss and regression buckets where incumbent guard prevented harm.
- Different from `strict_f2/strict_f3/gate1-cap-k6`:
  - explicit incumbent-challenger contract with guarded replacement, not pure frontier concentration.

## C) `branching_necessity_gate_v1`

- Failure mode targeted: unnecessary branching when branches are redundant, plus token/cost overhead without gain.
- Diagnostic evidence required:
  - low semantic diversity and high redundancy in early branches,
  - high cost per useful branch on cases where direct baseline is already reliable.
- Core behavior:
  - early gate estimates whether branching is necessary,
  - if direct incumbent is high-confidence and early families are redundant: avoid expensive frontier search,
  - if direct confidence is weak and semantic diversity is high: open frontier search.
- New logs required:
  - gate features and gate score,
  - gate decision (open/skip frontier),
  - post-hoc correctness of gate decisions.
- Evaluation:
  - compare quality-cost Pareto against `strict_f3` and `external_l1_max`,
  - include token/cost/latency with matched accuracy deltas.
- Different from `strict_f2/strict_f3/gate1-cap-k6`:
  - adds explicit branching-necessity decision before frontier expansion.

## Rollout recommendation

1. Prototype `semantic_minimum_maturation_frontier_v1` first (most directly tied to diagnosed semantic coverage gap).
2. Add `direct_reserve_semantic_frontier_v1` as a risk-control variant.
3. Add `branching_necessity_gate_v1` after gate-feature logging is stable.
