# Current safe claims (canonical)

## Safe to claim now

- The repository is a strong research platform for fixed-budget adaptive test-time compute allocation.
- Cross-controller frontier allocation is a clear and distinct framing.
- Branch-priority / next-step allocation is the correct conceptual center of the current project.
- Anti-collapse design matters for realized budget use and controller behavior.
- The current bottleneck is **decision-aligned supervision quality** for budget-aware branch comparison.
- Internal supervision, canonical corpus construction, and matched learning infrastructure are now mature enough for a serious paper-facing story.
- External process supervision can now be integrated conservatively and made non-degenerate.
- PRM800K-assisted methods can produce small stable gains over the internal anchor in rebuilt corpus families, though method separation remains limited.

## Not safe to claim yet

- That any current learned controller is a robust universal winner.
- That current proxy labels already capture true oracle marginal utility adequately.
- That broad vs aligned PRM usage is already cleanly separated.
- That exact-promoted held-out behavior is well characterized.
- That external process supervision has already solved the branch-allocation bottleneck.
- That Math-Shepherd integration is already justified as the next research step.
- That broader scale or heavier models alone will resolve current weaknesses.
- That current real-model evidence is already broad and decisive.

## Preferred wording

Prefer language such as:
- “suggests”,
- “is consistent with”,
- “promising but mixed”,
- “active-development method maturity”,
- “bounded matched comparisons”,
- “decision-aligned supervision”,
- “proxy-label mismatch”,
- “budget-aware branch comparison”,
- “non-degenerate but not yet decisive external signal”.

## Wording to avoid

Avoid language such as:
- “solves”,
- “final”,
- “robust winner”,
- “universally better”,
- “external supervision closes the bottleneck”,
- “only scale is missing”,
- “broad and aligned are clearly separated” when they are not.

## Practical writing rule

Every central claim in the paper should map cleanly to one of the following supported evidence types:
1. a frontier/controller experiment,
2. a target-design or corpus-construction audit,
3. an oracle-headroom analysis,
4. a matched controller comparison,
5. a bounded hard-slice evaluation,
6. or a clearly bounded external-supervision result.

If a claim does not map to one of these, it is probably not safe to present as established.

## Internal supervision claims

Safe to claim now:
- medium-scale and multi-dataset brute-force label corpora have been generated in-repo with explicit provenance,
- approximate labels have strong but imperfect bounded agreement with exact tiny-state labels,
- canonical processed branch-learning corpora now exist with schema, manifests, checksums, and slice summaries,
- matched internal learning passes can be run reproducibly on canonical corpora.

Not safe to claim yet:
- that the supervision bottleneck is fully solved,
- that approximate labels are exact substitutes for exact labels,
- that current learned allocators trained on these labels are robust universal winners.

## Hard-slice and ambiguity claims

Safe to claim now:
- hard-region exact-supervision tooling, richer hard-case feature sets, ternary/abstention variants, calibration/fallback paths, and near-tie routing experiments are integrated with auditable artifacts,
- bounded evidence indicates that hard-slice behavior is sensitive to representation quality, routing policy, fallback policy, and comparator semantics,
- hard-slice ambiguity is now better instrumented than before.

Not safe to claim yet:
- that the hard-slice ambiguity problem is solved,
- that exact-promoted behavior is currently well measured in held-out evaluation,
- that any one ambiguity-handling method is already a robust universal winner.

## External supervision claims

Safe to claim now:
- PRM800K and Math-Shepherd are integrated conservatively as candidate-first external process-supervision sources,
- APPS is registry-integrated as a verifier-backed coding dataset candidate but remains environment-caveated,
- the original PRM800K degeneracy was traced to a schema/extraction mismatch and repaired,
- repaired PRM800K-assisted methods can beat the internal anchor stably in rebuilt corpus families,
- comparator-boundary PRM use is diagnostically meaningful and can produce net-helpful flips.

Not safe to claim yet:
- that PRM800K broad vs aligned usage is decisively separated,
- that PRM800K assistance clearly improves all relevant hard slices,
- that external process supervision now justifies moving immediately to Math-Shepherd,
- that external process supervision has already solved the budget-aware branch-comparison problem.

## External baseline claims

Safe to claim now:
- s1, TALE, and L1 MODE A paths are runnable in-repo with auditable artifacts,
- multiple external baselines now have strict runnable-adjacent validator paths with explicit claim boundaries,
- compute_optimal_tts is explicitly blocked rather than ambiguously link-only.

Not safe to claim yet:
- that all external baselines are fully reproduced in-repo,
- that runnable-adjacent imports are direct control-equivalent reproductions,
- that the external baseline picture is fully reviewer-proof in every possible sense.

## Bottom-line safe paper stance

The safest current framing is:

> **The repository now supports a serious paper story built around branch-priority / next-step allocation, internal supervision maturity, and careful matched evaluation. The strongest remaining uncertainty is not basic infrastructure but whether current supervision and evaluation are sufficiently decision-aligned on the hardest budget-sensitive slices.**
