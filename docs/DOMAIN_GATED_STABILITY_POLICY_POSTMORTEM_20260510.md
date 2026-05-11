# Domain-Gated Stability Policy Postmortem

This note records the outcome of the clean budget-4 exact-case Cohere A/B run after PR #388.

## Result Summary

- Baseline `diverse_anchor`: `10/30 = 33.3%`
- Treatment `stability_redundant_anchor_v1` with `multi_step_arithmetic_only_v1` gate: `8/30 = 26.7%`
- Improved cases: `2`
- Regressed cases: `4`
- Gold-in-tree: baseline `12/30`, treatment `11/30`
- Money: baseline `6/10`, treatment `3/10`
- Ratio: baseline `1/10`, treatment `3/10`
- Multi-step: baseline `3/10`, treatment `2/10`

The gate behaved as designed:

- `multi_step_arithmetic` allowed: `10/10`
- `money_cost_revenue` blocked: `10/10`
- `ratio_percent` blocked: `10/10`

But the end-to-end treatment was worse than baseline.

## Why It Is Not Recommended

- The gated stability line did not improve the exact-case comparison overall.
- It reduced the money slice substantially and did not preserve the multi-step win.
- Gold-in-tree moved slightly in the wrong direction.
- The treatment was not better than the ungated stability run, so the extra gate did not recover the earlier signal.

## Why 50-Case Expansion Is Not Justified

- The 30-case evidence is already negative for the gated treatment.
- Expanding to 50 cases would amplify a method that is not currently beating the default diverse-anchor baseline.
- The better next step is to study the failure modes, not to scale up a weaker treatment.

## Recommendation

- Keep `stability_redundant_anchor_v1` as experimental/internal only.
- Do not treat it as the recommended production method.
- The recommended current method remains `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`.
- Avoid broad claims about the gated stability line until it is revalidated on a different design.

## Next Research Direction

Focus on a cheaper, more selective adaptation:

- uncertainty-triggered retry
- cheap verifier or lightweight confidence gate
- do not use blanket or domain-gated redundancy as the next default improvement path

## Provenance

- NoAPI analysis used existing `/tmp` Cohere artifacts only.
- No new paid API calls were run for this postmortem.
