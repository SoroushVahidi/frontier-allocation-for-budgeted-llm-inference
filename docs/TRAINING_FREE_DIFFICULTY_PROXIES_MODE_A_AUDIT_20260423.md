# Audit: training_free_difficulty_proxies_mode_a (2026-04-23)

## A) Was this baseline already present?

No. A repository-wide search found no existing DIPA/training-free difficulty-proxy baseline package before this pass.

## B) Official public code verification

Primary sources checked:

- OpenReview page: https://openreview.net/forum?id=ztGHhyicWs
- OpenReview PDF: https://openreview.net/pdf?id=ztGHhyicWs

Result:

- no clearly attributable official public repository was verified from those sources during this pass.
- this integration is therefore explicitly adapter-based and non-official.

## C) Scientific implementation summary

Implemented query-level global-budget allocator preserving core paper mechanics:

- one pull = one additional generation attempt on one unsolved instance,
- active set of unsolved instances only,
- arm elimination on success,
- cheap input proxy initialization,
- generation-based MGL-style proxy updates after failures,
- DIPA-style probabilistic pull policy `P_i ∝ 1 / M_i^lambda`.

## D) Sanity bundle and fairness

Policies evaluated under identical budget accounting and identical attempt bank:

- `uniform`
- `fixed_round_robin`
- `easy_to_hard_mgl`
- `hard_to_easy_mgl`
- `dipa_mgl`

Fairness notes:

- all policies share the same pre-generated per-instance attempt records,
- only allocation order differs,
- global budget and success-removal semantics are identical.

## E) Diagnostic findings (run: 20260423T023500Z)

From `diagnostic_summary.json` (run `20260423T023500Z`):

- DIPA is mixed and often not strongest under this substrate.
- `hard_to_easy_mgl` is stronger on this run at several budgets.
- This suggests gains are not yet robustly attributable to the current DIPA approximation.
- Budget-specific deltas are explicitly logged for candid interpretation.

## F) Recommendation

Use the run’s machine-produced recommendation from `status.json` / `diagnostic_summary.json` as the gating signal.

Current run recommendation (`status.json`):

- `repo_only_not_paper_facing_yet`.
- Do not force into the main baseline table until DIPA-style policy is stably competitive versus uniform/fixed and ordering references.

## G) Claim boundary (must keep)

- `adapter_based`
- `control_equivalence: adjacent`
- query/sample-level fixed-budget allocator (not branch-level control-equivalent)
- paper-inspired matched-substrate comparator, not official reproduction
