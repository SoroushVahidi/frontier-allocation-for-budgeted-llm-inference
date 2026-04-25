# CLAIM_BOUNDARIES

Use conservative, contract-aware wording.

## Preferred wording

- matched action-budget surface
- matched-budget adapter baselines
- near-direct external baselines under explicit contract
- supporting/diagnostic real-model audits
- exploratory/provenance-only
- not evidence of universal dominance
- not token/latency/cost matched unless explicitly stated

## Disallowed (or requires explicit historical context label)

- SOTA / state-of-the-art
- dominates / universal dominance
- provider-independent dominance
- real-model dominance
- “strict_f3 beats external_l1_max” without matched-contract qualifiers
- “beats previous methods” without adapter/matched-budget qualifiers
- “main-paper real-model evidence”
- any claim that Cohere/OpenAI diagnostics establish superiority over external_l1_max without explicit contract and evidence scope

## Real-model boundary

Real-model runs are retained for diagnostic/supporting value. They are useful for stress-testing transfer and failure modes, but are not promoted as universal performance evidence.
