# New-paper safe claims and overclaim guardrail

Use this note to keep wording publication-safe for the new-paper track.

## Safe to claim now

- The new-paper track studies **cross-controller frontier allocation under fixed budget**.
- Branch-scoring quality is a central bottleneck for controller-level gains.
- Pairwise/continuation-oriented signals appear more aligned than static branch-promise targets.
- External reasoning datasets are integrated and useful for warm-start/preparation workflows.

## Not safe to claim yet

- External data “solves” branch scoring.
- Reliability-weighted BT is already a global winner.
- The current branch-scorer method is final.
- Real-model evidence is already broad/decisive.
- Current labels are true oracle counterfactual marginal values.

## Recommended wording patterns

Prefer:
- “suggests”, “is consistent with”, “improves in this setting”,
- “preparation/integration layer”,
- “promising but mixed across settings”,
- “proxy labels” or “approximate labels”.

Avoid:
- “solves”, “proves” (without theorem/proof),
- “state-of-the-art”, “robust winner” (without broad evidence),
- “oracle labels” when labels are heuristic/proxy-derived.

## Current positioning sentence

A safe one-liner is:

> The current evidence supports cross-controller frontier allocation as a distinct and promising direction, with pairwise branch scoring as the strongest active line, while robustness and label quality remain the main unresolved issues.
