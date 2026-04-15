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
- s1, TALE, and L1 MODE B paths are partial adapter/reporting paths and explicitly blocked unless official/full outputs are imported.
- BEST-Route is documented as blocked-for-fair-adaptation in this repo (not falsely presented as runnable).

Not safe to claim yet:
- that BEST-Route is currently a fair runnable comparison in this repository,
- that any s1/TALE/L1 MODE B full official reproduction has been completed in-repo.

- compute_optimal_tts is explicitly blocked (provenance and fairness protocol incomplete) rather than ambiguously link-only.
