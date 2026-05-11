# Stability Policy A/B Diagnostic

This note records the latest exact-case Cohere A/B diagnostic for the optional stability policy.

## Methods

- Baseline: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`
- Treatment: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_stability_redundant_anchor_v1`

## Budget 4

- Baseline exact accuracy: `7/30 = 23.3%`
- Treatment exact accuracy: `13/30 = 43.3%`
- Improved cases: `7`
- Regressed cases: `1`
- Gold in pool: `12/30 -> 16/30`

## Budget 8

- The budget 8 slice is not a valid comparison.
- The global logical Cohere cap was reached.
- The treatment scored only `4` examples and then failed on the remaining `26`.

## Warning

Do not use the budget 8 numbers as a stable estimate of treatment quality. They are cap-limited and incomplete.

## Runner Status

- The runner now permanently registers the stability treatment method.
- The treatment resolves without monkeypatching.
- The default diverse-anchor method remains stability disabled by default.

## Next Live Run

- Preferred next run: budget `4` only.
- Alternate next run: budget `8` only, but only if the logical Cohere cap is increased enough to avoid incomplete treatment slices.
