# Fairness report: s1 baseline integration

## Primary comparison policy
- Primary manuscript-safe comparison is `adaptive_min_expand_1` vs `external_s1_budget_forcing` under unchanged base model settings.
- Both methods are run on the same sampled examples, seeds, and budget grid.

## Budget matching policy
- Internal action budgets are mapped to token-equivalent budgets via fixed conversion: 1 action = 64.0 token-equivalent units.
- We report both action-budget and token-equivalent columns so tables can be audited.

## MODE B import guardrails
- MODE B is a strict official/full results import path with required schema + metadata + provenance validation.
- Imported results are rejected if metadata is incomplete/inconsistent or if fairness checks fail.

## Caveats
- Inference-only adapter does not claim exact token-level stop-token parity with upstream vLLM internals.
- MODE B does not claim in-repo reproduction of s1 post-training assets.
