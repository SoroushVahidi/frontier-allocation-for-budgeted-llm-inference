# Claims guide

**Last updated:** 2026-05-28 — FTA canonical. Supersedes outcome-verifier-selector era content.

This is the shortest claim-scope guide for readers, reviewers, and agents. It does not replace
`docs/PAPER_SOURCE_OF_TRUTH.md` or `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`; it summarises
the current safe interpretation.

## Current safe claims

**Main result — Failure-Trace Allocator (FTA / FIX-2+FIX-4):**

- FTA achieves **86.67% (260/300)** on Final-300 (Cohere × GSM8K, seed=71, budget=6); independently reproduced.
- FTA achieves **80.69% (581/720)** on Aggregate-720 (seeds 41+61+71); source-stratified CI lower bounds vs L1/S1/TALE and best-external are all strictly positive.
- FTA gate features (`override_reason`, `frontier_support`, external unanimity) are gold-free at runtime; leakage audit PASS.
- FTA adds zero model calls at selection time after candidates are generated.
- `external_l1_max` (L1) is the primary external comparator: 83.00% Final-300, 77.64% Agg-720.
- FIX-2 fires 63/300 cases; FIX-4 fires 3/300 cases; 234/300 cases use the unmodified frontier answer.
- FIX-4 causes zero regressions (3 wins, 0 losses).

**Supporting — D9 gated selector:**

- D9 grouped 5-fold CV: **50.18% ± 2.52%** vs frontier 34.36% (+15.82pp) on 550 multi-provider D6 pools.
- D9 gate has 0 false overrides at all tested thresholds (0.3–0.8).
- D6 standalone is negative; D9 gate is required for a positive outcome.

## Required disclosures (must appear in paper)

1. **CI vs pooled ensemble includes zero** — Final-300 delta +2.33pp [−0.67, +5.67]; Agg-720 delta +0.83pp [−1.11, +2.78]. Do not claim statistical superiority over pooled ensembles.
2. **Budget** — Full pool generation costs 4×B=6 = **24 logical calls per example**. FTA itself adds zero post-generation calls.
3. **Scope** — Evaluation is Cohere × GSM8K only. Do not extrapolate to MATH-500 or other settings.
4. **Seed=61** — The 59.17% seed=61 component in Agg-720 was a failure-enriched base run for FIX-6 testing, not a random sample.

## Current unsafe claims

Do not claim any of the following unless a new canonical promotion document explicitly supports it:

- FTA statistical superiority over the pooled ensemble (CI includes zero at both n=300 and n=720).
- FTA result on any benchmark other than Cohere × GSM8K.
- Full pool generation costs only B=6 calls (it costs 24).
- D8.1 selector results as independent held-out end-to-end accuracy (they are test-split only).
- D6 net gain as positive standalone across all pools (it is negative: net=−38).
- Any claim from an output folder without reading its manifest and the relevant canonical doc.

## Canonical sources

Read these before writing paper text or reviewer responses:

1. `docs/CURRENT_CANONICAL_STATE_20260527.md`
2. `REVIEWER_FIRST.md`
3. `docs/LATEST_RESULTS_AND_CLAIMS.md`
4. `docs/PAPER_SOURCE_OF_TRUTH.md`
5. `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
6. `docs/CURRENT_EXTERNAL_BASELINE_GAP.md`
7. `docs/ARTIFACT_STATUS_TABLE.md`
