# Direct-reserve learned scorer status

This note consolidates the direct-reserve learned candidate-scorer evidence. It is diagnostic-current, not canonical manuscript evidence.

## Motivation

Hand-written margin, support, and entropy rules are brittle. The direct-reserve runs often discover a correct candidate but lose at final selection, so selecting among discovered candidates is a key bottleneck.

## Evidence sequence

| Step | Result | Interpretation |
|---|---|---|
| First 20-case Cohere slice | base plus-diverse 0.60; learned logit/RF/pairwise 0.85; HGB 0.55 | Strong but same-slice diagnostic evidence |
| Second validation | 20/20 overlap with first slice | Useful replay/provenance, not disjoint generalization |
| Disjoint planner | old `raw_case_results.csv` source exhausted after excluding prior IDs | Correctly blocked reuse of old IDs |
| Fresh GSM8K planner | loaded `openai/gsm8k` and produced 20 zero-overlap fresh cases | Unblocked genuine unseen-problem validation |
| Fresh validation | base 0.60; support 0.55; max-gap 0.40; margin-gated 0.75; logit 0.65; RF 0.70; pairwise 0.70; HGB 0.40 | RF/pairwise beat base by 10 points with zero degradation |

## Fresh validation details

- Planned fresh IDs: 20.
- Overlap with prior scorer slices: 0.
- RF/pairwise improvements over base: 2.
- RF/pairwise degradations against base: 0.
- RF/pairwise control degradation: 0.
- HGB degraded and should be excluded from recommendations.

## Current recommendation

Implement a diagnostic-only learned override next, using RF and/or pairwise logistic scorers with `direct_reserve_strong_plus_diverse_v1` as fallback. Do not make the learned scorer canonical/default until larger fresh validation confirms the result across more cases, seeds, and possibly providers.
