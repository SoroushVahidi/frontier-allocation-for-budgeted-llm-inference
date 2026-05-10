# Failure-family-centered schema-grounded bank report

We intentionally center this bank on **our failures**, not only cases where external baselines win. This prevents overfitting to contradiction examples and promotes family-level improvements.

## Why not chase isolated baseline-winning cases
- Isolated counterexamples are often noisy and do not transfer.
- Family-level recurrence (>=5) indicates stable error mechanisms worth engineering effort.

## Repeated families with support
- Families at/above support threshold should be tested as schema-grounded retry candidates.
- Weak-support families are useful for format sanity only, not broad algorithm claims.

## What to test as format sanity vs algorithmic improvement
- **Format sanity:** parse_format/unknown_or_mixed or low-support families.
- **Algorithmic improvement:** strong recurrent families in before/after state, ratio, ledger, target-difference, average structures.

## Recommendation
- Run tiny format-sanity probe first, then family-level dev probe only on supported families.
- Keep non-overlap holdout untouched for validation of generalization.
