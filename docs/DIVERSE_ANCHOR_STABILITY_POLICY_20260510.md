# Diverse Anchor Stability Policy

This document describes the optional `stability_redundant_anchor_v1` policy for the domain-aware diverse-anchor method.

## Status

- Default production behavior remains unchanged.
- The policy is **disabled by default**.
- The recommended production method remains `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`.

## Purpose

The policy is a narrow, experimental retry mechanism for candidate generation:

- preserve the current direct-L1 anchor behavior;
- preserve PAL/frontier protections;
- optionally allocate one extra validation/retry action to the highest-priority non-direct-L1 anchor when budget allows;
- expose metadata so experiments can measure whether the extra attempt changes the candidate pool.

## When It Runs

The policy only activates when explicitly enabled in controller configuration or through an experimental method wiring.

It records:

- `stability_policy`
- `stability_policy_enabled`
- `stability_extra_anchor_attempts`
- `stability_target_anchor_id`
- `stability_reason`
- `candidate_pool_stability_features`

## Experimental Method

The experimental method ID is:

`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_stability_redundant_anchor_v1`

It keeps the same domain-aware anchor ordering as the default diverse-anchor method, but enables:

- `enable_diverse_anchor_stability_policy=True`
- `diverse_anchor_stability_policy="stability_redundant_anchor_v1"`
- `diverse_anchor_stability_extra_anchor_attempts=1`

## Notes

The earlier stability analysis on the 30-case replay showed that the guard experiment was not a good default. This policy is therefore isolated as an opt-in experiment, not a production selector change.

Postmortem:

- `docs/DOMAIN_GATED_STABILITY_POLICY_POSTMORTEM_20260510.md`
- Do not use `stability_redundant_anchor_v1` for broad claims or as a recommended next method.
