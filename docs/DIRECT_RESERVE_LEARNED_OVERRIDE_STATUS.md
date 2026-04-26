# Direct Reserve Learned Override Status

## Runtime pairing invariant

`direct_reserve_strong_plus_diverse_learned_override_v1` is diagnostic-only and must remain a selector wrapper around `direct_reserve_strong_plus_diverse_v1`, not a separate generator.

The required invariant is:

- run the exact same candidate generation path as base plus-diverse,
- preserve base selection metadata,
- apply learned selector only on the already generated candidate pool,
- if override is unavailable or does not trigger, return exactly the base selected answer.

Tiny real validation indicated degradations while override did not trigger. That pattern signals a likely pairing/fallback inconsistency rather than learned-selector harm. The current fix centralizes learned override as a wrapper over a base plus-diverse controller instance and enforces fallback equality metadata (`base_selected_answer`, `learned_selected_answer`, `final_selected_answer`, `learned_override_triggered`).

Future real validation should use paired candidate pools or deterministic replay for interpretation. If base and learned methods are run as separate stochastic API calls, answer differences cannot be attributed to learned override behavior alone.

## Paired selector evaluation update

Paired offline selector evaluation is now implemented via `scripts/run_direct_reserve_paired_selector_eval.py`. It evaluates base/support/learned selectors on the same candidate pools from direct-reserve validation artifacts and reports threshold-swept overrides, improvements, degradations, and control degradations.

See:

- `docs/DIRECT_RESERVE_PAIRED_SELECTOR_EVAL_STATUS.md`
- `outputs/direct_reserve_paired_selector_eval_20260426T_REPAIRED_FIRST/`
- `outputs/direct_reserve_paired_selector_eval_20260426T_REPAIRED_OVERLAP_DIAGNOSTIC/`

Important clarification:

- Wrapper implementation is correct (same generation path, selector post-hoc, exact no-trigger fallback).
- Evaluation quality depends on paired candidate pools **and** correct artifact labeling.
- In this checkout, `20260426T151700Z` is overlapping with first slice and must not be treated as true fresh evidence.
- If the true fresh package is unavailable, current paired results remain useful diagnostics but are insufficient for fresh-generalization claims.

