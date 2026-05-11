# Stability Policy Budget 4 Triage

This note records the clean budget-4 exact-case A/B run and the resulting policy decision.

## Methods

- Baseline: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`
- Treatment: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_stability_redundant_anchor_v1`

## Budget 4 Result

- Baseline exact accuracy: `12/30 = 40.0%`
- Treatment exact accuracy: `13/30 = 43.3%`
- Improved cases: `3`
- Regressed cases: `2`
- Gold in tree: baseline `17/30`, treatment `15/30`
- Average answer groups: `3.0 -> 3.367`
- Entropy: `0.994 -> 1.091`
- Frontier collapse: `2/30 -> 1/30`

## Case Diagnosis

- Improved cases: `openai_gsm8k_217`, `openai_gsm8k_36`, `openai_gsm8k_458`
- Worsened cases: `openai_gsm8k_17`, `openai_gsm8k_551`

The clean run supports a domain-gated interpretation:

- `multi_step_arithmetic` improved overall (`2/10 -> 4/10`)
- `money_cost_revenue` regressed slightly (`7/10 -> 6/10`)
- `ratio_percent` was neutral (`3/10 -> 3/10`)

## Policy Decision

- Keep the production diverse-anchor method unchanged.
- Keep the experimental stability treatment enabled, but gate redundant-anchor repetition by domain.
- Default gate: allow `multi_step_arithmetic` only.
- Block `money_cost_revenue` and `ratio_percent` unless explicitly overridden.
- Explicit override: `all_domains_v1`

## Metadata Added

- `stability_domain_gate`
- `stability_domain_gate_allowed`
- `stability_domain_gate_reason`

## Next Live Run

- Preferred: rerun budget `4` only with the gated treatment.
- Alternate: rerun budget `8` only if the logical-call cap is raised enough to avoid incomplete treatment slices.
