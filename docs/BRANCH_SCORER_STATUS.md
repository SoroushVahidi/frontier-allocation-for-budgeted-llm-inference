# Branch-scorer status (active branch)

## Role in current project

Branch scoring remains central to cross-controller frontier allocation, but current canonical next-step controller work is shifting toward action-conditional stop-vs-act decisions.

## Current summary

1. Pairwise BT branch scoring is one of the strongest active learned directions.
2. Robustness remains mixed; no settled universal winner.
3. Reliability-aware and external warm-start variants are promising but mixed.
4. Diagnostics continue to show supervision-target and proxy-label limitations.

## Interpretation

- Treat pairwise BT as:
  - a strong baseline,
  - an important active branch,
  - and a useful component for later hybrid controllers.
- Do not treat pairwise BT as the final solved controller.

## Connection to canonical next direction

Current canonical method direction is:
- budget-conditioned binary stop-vs-act controller,
- trained with uncertainty-aware handling,
- using cheap approximate marginal labels.

Branch scoring should continue in parallel, with explicit matched comparisons against stop-vs-act controllers as that path matures.
