# New-paper current bottlenecks (plain-language note)

## Main bottleneck

The current core bottleneck is **not compute infrastructure**. It is the quality of the local supervision signal used to decide where the next unit of compute should go.

## Main algorithmic weakness

Current branch scorers still rely on imperfect proxy labels (including pairwise preferences with noisy confidence). That creates unstable transfer across seeds/budgets/datasets and prevents a clear, robust default winner.

## Why the repository is strong but the method is not final

- Strong:
  - clear two-track separation,
  - runnable frontier/controller infrastructure,
  - multiple branch-scorer variants with auditable notes,
  - dataset integration/readiness tooling.
- Not final:
  - learned allocation signal is still partially proxy-based,
  - reliability weighting and external warm-start remain mixed,
  - real-model evidence is still narrower than desired.

## Practical next non-heavy step

Run a focused calibration pass on the pairwise BT line:
1. improve confidence spread / uncertain-pair handling,
2. rerun the same robustness protocol (multi-seed/budget/init-branches),
3. keep external warm-start as optional regularizer,
4. update safe-claim wording only if robustness improves.

This is a low-risk cleanup step that can tighten evidence without launching heavy new experiments.
