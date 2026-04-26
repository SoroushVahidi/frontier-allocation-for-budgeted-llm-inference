# Method and variant map

This map separates canonical manuscript methods from diagnostic variants. It is anonymous
and claim-boundary oriented.

| Display name | Runtime name | Purpose | Evidence status | Canonical? | Diagnostic-only? | Caveats |
|---|---|---|---|---:|---:|---|
| strict_f3 | `strict_f3` / broad diversity depth-3 runtime | Current canonical frontier method family for matched-surface claims | Paper-facing canonical | yes | no | Do not modify behavior during diagnostic cleanup. |
| strict_gate1_cap_k6 | `strict_gate1_cap_k6` | Budget-capped gate variant used in canonical comparisons | Paper-facing canonical where referenced by paper artifacts | yes | no | Claims must use canonical artifact outputs. |
| strict_f2 | `strict_f2` | Depth-2 frontier baseline/variant | Supporting/canonical depending on table | conditional | no | Keep label tied to exact paper artifact source. |
| strict_f3 anti-collapse weak | `strict_f3_anti_collapse_weak_v1` | Anti-collapse diagnostic/canonical-support variant | Supporting | conditional | usually | Do not promote without matching artifact evidence. |
| direct reserve strong | `direct_reserve_strong_v1` | Direct-reserve generation baseline with strong prompt family | Diagnostic current | no | yes | Useful comparator, not paper headline method. |
| direct reserve strong plus diverse | `direct_reserve_strong_plus_diverse_v1` | Strongest current diagnostic direct-reserve generation method | Diagnostic current | no | yes | Base selector reached 0.60 selected-gold on fresh scorer slice. |
| direct reserve margin gated | `direct_reserve_strong_plus_diverse_margin_gated_v1` | Margin-gated selector comparison | Diagnostic current | no | yes | Not promoted; 5-case replay showed brittleness despite fresh-slice 0.75 comparison result. |
| learned logistic scorer | logistic candidate scorer | Candidate reranker over direct-reserve candidates | Diagnostic current | no | yes | Fresh disjoint GSM8K: 0.65 selected-gold, zero degradation vs base. |
| learned random forest scorer | RF candidate scorer | Strong learned candidate reranker | Diagnostic current | no | yes | Fresh disjoint GSM8K: 0.70 selected-gold vs base 0.60, zero degradation. |
| learned pairwise logistic scorer | pairwise logistic candidate ranker | Pairwise ranking over candidate feature differences | Diagnostic current | no | yes | Fresh disjoint GSM8K: 0.70 selected-gold vs base 0.60, zero degradation. |
| learned HGB scorer | HGB candidate scorer | Candidate reranker audit model | Diagnostic/deprecated for recommendation | no | yes | Exclude from recommendations; degraded on fresh validation. |

## Interpretation

- `direct_reserve_strong_plus_diverse_v1` is the strongest current diagnostic generation method.
- `direct_reserve_strong_plus_diverse_margin_gated_v1` remains a comparison method, not a promoted method.
- Learned RF and pairwise scorers are the strongest learned-scorer candidates after the fresh zero-overlap GSM8K validation.
- HGB should not be recommended unless future evidence shows no degradation.
