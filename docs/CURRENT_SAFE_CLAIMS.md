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

## Hard-region exact-supervision claims (2026-04-16 bounded update)

Safe to claim now:
- hard-region mining and bounded targeted exact relabeling are integrated with resumable, manifest-backed artifacts and per-row replacement provenance,
- exact-augmented supervision regimes are reproducibly materialized and can be compared in matched multi-seed runs,
- in the bounded run, hard-region exact promotion did not clearly improve the hardest slices (near-tie/adjacent-rank) versus all-pairs approximate baseline.

Not safe to claim yet:
- that targeted exact relabeling has already reduced the core bottleneck broadly,
- that hard-region exact promotion is a robust universal improvement across datasets/budgets/seeds,
- that difficult-slice supervision noise is solved.

## Hard-case feature-representation claims (2026-04-16 bounded update)

Safe to claim now:
- hard-case-focused feature-set versioning (`v1` vs `v2`) is integrated with auditable feature-coverage artifacts and matched evaluation outputs,
- richer engineered features improved pairwise logistic near-tie/adjacent slices in a bounded fixed-supervision run,
- evidence is consistent with representation quality being a meaningful part of the remaining bottleneck.

Not safe to claim yet:
- that richer features universally improve all integrated model families,
- that hard-case ambiguity is solved,
- that current bounded run results establish robust cross-dataset universal closure.

## Ternary / selective-abstention formulation claims (2026-04-16 bounded update)

Safe to claim now:
- tie-aware supervision metadata and ternary-label hooks are integrated in target-construction + learning paths with auditable artifacts,
- selective abstention and explicit fallback semantics are now runnable in matched branch-comparison experiments,
- bounded evidence indicates a real coverage-vs-accuracy tradeoff when ambiguity is handled explicitly.

Not safe to claim yet:
- that ternary/tie-aware formulation is already a robust universal improvement over forced binary comparison,
- that abstention fallback currently preserves or improves hardest near-tie behavior across settings,
- that ambiguity handling thresholds are already calibrated for high coverage and high reliability simultaneously.

## Ambiguity calibration + fallback claims (2026-04-16 bounded update)

Safe to claim now:
- calibration-aware abstention experiments are integrated with explicit calibration-fit provenance (`val`) and test-side calibration-quality metrics (Brier/ECE/NLL),
- multiple explicit fallback policies are runnable and auditable in matched ambiguity-handling comparisons,
- bounded evidence indicates fallback choice materially affects forced/top-1 behavior when abstention is enabled.

Not safe to claim yet:
- that probability calibration is universally improved by current simple calibrators in this setup,
- that calibrated abstention reliably improves hardest near-tie slices across settings,
- that ambiguity-handling bottleneck is solved.

## Dedicated near-tie policy claims (2026-04-16 bounded update)

Safe to claim now:
- a dedicated near-tie detection + routing path is integrated with configurable trigger signals (margin/relative-margin/std/calibrated-confidence/supervised near-tie flag) and manifest-backed provenance,
- multiple explicit near-tie routing policies are runnable in matched comparisons, including pairwise backup, pointwise fallback, heuristic/score-gap fallback, and a deterministic balanced/shared proxy policy,
- bounded evidence shows routing policy choice can materially change near-tie forced behavior; pointwise fallback improved near-tie slice in this run.

Not safe to claim yet:
- that dedicated near-tie routing is already a robust universal winner across datasets/budgets/seeds,
- that balanced/shared non-forced tie handling is universally better than sharp winner selection,
- that the near-tie bottleneck is solved.

## Near-tie pointwise-expert claims (2026-04-16 bounded update)

Safe to claim now:
- dedicated near-tie pointwise-expert experiments are integrated with explicit model-provenance variants (generic/specialized/reweighted) and routing-gate controls,
- a near-tie diagnostic audit now compares pairwise-vs-pointwise success/failure buckets with feature summaries (margin/relative-margin/std/rank-gap/pointwise-gap/frontier-context),
- bounded evidence indicates specialized pointwise fallback can retain the strongest near-tie forced signal while generic/reweighted variants can underperform under the same routing setup.

Not safe to claim yet:
- that near-tie-specialized pointwise is already a robust universal winner across datasets/budgets/seeds,
- that current near-tie pointwise expert quality/routing is fully calibrated and solved,
- that residual hard-case ambiguity is no longer a central bottleneck.
