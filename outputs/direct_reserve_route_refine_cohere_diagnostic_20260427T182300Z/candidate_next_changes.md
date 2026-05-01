# Candidate next changes

- Cases run: 4
- Route mix: {'longer_direct_continuation': 2, 'frontier_search_challenger': 2}
- Accuracy: external_l1_max=1.000, strict_f3=0.000, direct_reserve_route_refine_v1=0.250

## Top recommendations
- Increase frontier-search trigger for multi-step numeric questions when incumbent answer length is short but unstable.
- Add one extra low-cost direct sample for uncertainty estimation before stopping with incumbent.
- Tighten challenger replacement to require both support margin and consistency with independent continuation.
