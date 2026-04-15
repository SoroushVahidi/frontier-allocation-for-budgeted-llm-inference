# Experiment status (canonical summary)

## Established infrastructure

- Frontier/controller allocation scaffold is in place.
- Anti-collapse controller mechanisms are implemented and auditable.
- Branch-scorer training/evaluation pipelines are runnable.
- Dataset and baseline integration/readiness tooling is established.

## Promising directions

- Pairwise BT branch scoring is among the strongest active learned directions.
- Tie-aware and ambiguity-aware diagnostics are informative for target quality.
- Oracle headroom framing remains useful for evaluating allocation opportunity.

## Promising but mixed outcomes

- Reliability-aware BT variants: mixed robustness.
- External warm-start variants: useful in some settings, not a canonical winner.
- Several targeted branch-scorer variants: local gains without broad robustness.

## Mixed/negative findings to retain

- Proxy-target mismatch remains a recurring failure mode.
- Robust controller-level superiority over strongest heuristics is not yet consistently demonstrated.
- Real-model evidence is still narrower than desired for strong claims.

## Not-yet-supported claims

- No robust universal learned-controller winner claim.
- No claim that scale/heavier models are the immediate fix.
- No claim that current proxy labels are reliable oracle marginal-utility targets.
