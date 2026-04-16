# Current safe claims (canonical)

## Safe to claim now

- The repository is a strong research platform for fixed-budget adaptive test-time compute allocation.
- Cross-controller frontier allocation is a clear and distinct framing.
- Anti-collapse design matters for realized budget use and controller behavior.
- Pairwise BT branch scoring is a strong active learned direction and a meaningful baseline line.
- The current bottleneck is supervision-target quality / proxy-label mismatch.
- The most promising near-term controller direction is budget-conditioned binary stop-vs-act with uncertainty-aware handling.
- The repo already supports a serious paper story built around framing, evaluation lens, and supervision-target diagnosis.

## Not safe to claim yet

- That any current learned controller is a robust universal winner.
- That current proxy labels already capture true oracle marginal utility adequately.
- That external warm-start or reliability-aware variants are settled canonical winners.
- That broader scale or heavier models alone will resolve current weaknesses.
- That current real-model evidence is already broad and decisive.
- That external baseline comparisons are already complete and reviewer-proof.

## Preferred wording

Prefer language such as:
- “suggests”,
- “is consistent with”,
- “promising but mixed”,
- “active-development method maturity”,
- “bounded matched comparisons”,
- “proxy-label mismatch”,
- “approximate marginal labels”,
- “opportunity-cost-aware STOP semantics”.

## Wording to avoid

Avoid language such as:
- “solves”,
- “final”,
- “robust winner”,
- “universally better”,
- “oracle labels” when the labels are still proxies,
- “only scale is missing”.

## Practical writing rule

Every central claim in the paper should map cleanly to one of the following supported evidence types:
1. a frontier/controller experiment,
2. a target-design audit,
3. an oracle-headroom analysis,
4. a matched controller comparison,
5. or a clearly bounded real-model result.

If a claim does not map to one of these, it is probably not safe to present as established.


## External baseline claims (2026-04-16 update)

Safe to claim now:
- s1, TALE, and L1 MODE A paths are runnable in-repo with auditable artifacts (manifest, summary, per-example rows, fairness report, comparison tables).
- s1 MODE B is a strict official/full import + verification path and is usable only when a valid package passes verification; TALE and L1 MODE B remain blocked adapter/reporting paths unless official/full outputs are imported.
- BEST-Route has a strict adjacent import validator path and can be used as runnable-adjacent only after validation (`scripts/verify_best_route_import.py`).
- when_solve_when_verify has a strict adjacent import validator path and can be used as runnable-adjacent only after validation (`scripts/verify_when_solve_when_verify_import.py`).
- cascade_routing has a strict adjacent import validator path and can be used as runnable-adjacent only after validation (`scripts/verify_cascade_routing_import.py`).
- mob_majority_of_bests has a strict adjacent import validator path and can be used as runnable-adjacent only after validation (`scripts/verify_mob_import.py`).
- rest_mcts has a strict adjacent import validator path and can be used as runnable-adjacent only after validation (`scripts/verify_rest_mcts_import.py`).
- openr has a strict adjacent import validator path and can be used as runnable-adjacent only after validation (`scripts/verify_openr_import.py`).

Not safe to claim yet:
- that BEST-Route is a direct apples-to-apples control-equivalent reproduction in this repository,
- that when_solve_when_verify is fully reproduced in-repo or control-equivalent to frontier/action-native controllers,
- that cascade_routing is fully reproduced in-repo or control-equivalent to frontier/action-native controllers,
- that mob_majority_of_bests is fully reproduced in-repo or control-equivalent to frontier/action-native controllers,
- that rest_mcts is fully reproduced in-repo or control-equivalent to frontier/action-native controllers,
- that openr is fully reproduced in-repo or control-equivalent to frontier/action-native controllers,
- that any s1/TALE/L1 MODE B full official reproduction has been completed in-repo.

- compute_optimal_tts is explicitly blocked (provenance and fairness protocol incomplete) rather than ambiguously link-only.

## Brute-force label-data claims (2026-04-16 medium run)

Safe to claim now:
- a real GSM8K-backed medium-scale brute-force/near-brute-force label corpus has been generated in-repo (220 states, 593 candidate rows, 559 pairwise rows),
- approximate-mode labels have high but imperfect agreement with exact tiny-state labels on overlapping feasible states,
- the generated labels are usable for bounded pilot learning runs (training/evaluation completes, non-trivial held-out metrics).

Not safe to claim yet:
- that label-data bottleneck is fully solved,
- that approximate labels are exact substitutes for tiny-state exact labels,
- that current learned allocators trained on these labels are robust universal winners.

## Brute-force label-data scaling claims (2026-04-16 multi-dataset run)

Safe to claim now:
- a larger merged supervision corpus has been generated in-repo across GSM8K, MATH-500, and AMO-Bench with multi-seed/multi-budget coverage and explicit per-row provenance,
- merged corpus scale is materially larger than the prior medium GSM8K corpus (about 3.1x on states/candidate/pairwise row counts),
- learned branch allocators trained on this corpus achieve non-trivial held-out and leave-one-dataset-out performance, with measurable near-tie sensitivity diagnostics.

Not safe to claim yet:
- that scaled labels fully close supervision-target mismatch,
- that exact-slice results are conclusive given current sparse exact coverage,
- that cross-dataset robustness is solved or that any learner is a robust universal winner.

## GBDT branch-allocator claims (2026-04-16 bounded update)

Safe to claim now:
- LightGBM LambdaRank and CatBoost YetiRankPairwise are integrated in-repo as matched branch-allocation ranking baselines with auditable artifacts.
- Pairwise near-tie filtering/downweighting and uncertainty-aware weighting are implemented with explicit configuration traces.

Not safe to claim yet:
- that GBDT ranking materially and universally outperforms current linear branch-allocation baselines across datasets/budgets/seeds,
- that uncertainty-aware weighting is already a robust universal improvement.

## Target-fidelity branch-comparison claims (2026-04-16 bounded update)

Safe to claim now:
- manifest-backed pair-construction regimes and pair-quality metadata are integrated for branch-comparison supervision,
- exact-vs-approx disagreement can now be audited with explicit dataset/budget/margin/pair-type/branch-count slices,
- bounded matched evidence indicates supervision-regime changes can move pairwise-learning outcomes more than model-class changes in the same all-pairs setup.

Not safe to claim yet:
- that supervision-target bottleneck is fully solved,
- that one pair-construction regime is a robust universal winner across all datasets/budgets/seeds,
- that approximate labels are broadly interchangeable with exact labels outside bounded, audited slices.
