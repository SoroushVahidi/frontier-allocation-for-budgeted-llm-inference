# Canonical manuscript-facing package policy (2026-04-22)

## Scope
This policy locks manuscript-facing story, table placement, and claim boundaries to the repository’s resolved evidence.

Core framing preserved:
- fixed-budget adaptive test-time compute allocation for LLM reasoning,
- frontier / next-step branch allocation under budget.

## Final internal method and runners-up
- **Main manuscript method:** `strict_f3`.
- **Primary internal runner-up / broader-default anchor:** `strict_gate1_cap_k6`.
- Historical note: broader strict-phased default-decision surfaces remain valid context for operational-default discussion, but not for replacing the manuscript-facing winner.

## External comparison placement (canonical)

### Main-table externals (MODE A boundary only)
- `l1_length_control_rl`
- `tale_token_budget_aware_reasoning`
- `s1_simple_test_time_scaling`

These are reported as matched-substrate MODE A comparators only; not official full-stack reproductions.

### Appendix-only externals
- `best_route_microsoft`
- `cascade_routing`
- `lets_verify_step_by_step`
- `mob_majority_of_bests`
- `openr`
- `rest_mcts`
- `tree_plv`
- `when_solve_when_verify`

These remain reviewer-useful adjacent comparators with non-equivalent control spaces.

### Keep out of manuscript empirical tables (repo-only / discuss-only)
- Repo-only/not paper-facing-yet rows include both new MODE A additions:
  - `learning_how_hard_to_think_mode_a`
  - `training_free_difficulty_proxies_mode_a`
- Discuss-only rows remain related-work framing references, not integrated empirical baselines.

## Exact claim boundary (safe)
The paper may claim:
1. On the canonical matched manuscript-facing internal surface, `strict_f3` is the strongest internal method in current evidence.
2. `strict_gate1_cap_k6` is a strong runner-up and broader-default anchor on separate strict-phased default surfaces.
3. Main-table external comparisons are limited to readiness-approved MODE A near-direct comparators under explicit caveats.

The paper should **not** claim:
- universal superiority across all possible surfaces,
- control-equivalent fairness versus appendix-only adjacent baselines,
- official full-stack reproduction status for MODE A adapter baselines.

## Main table vs appendix policy
- Main table: `strict_f3`, `strict_gate1_cap_k6` (anchor), plus readiness-approved main-table externals only.
- Appendix: adjacent external baselines and expanded diagnostics.
- Repo-only/discuss-only rows must not be silently promoted to manuscript empirical leaderboards.

## Recommended naming for manuscript
- Method naming in title/body: **strict_f3** (with subtitle/context: strict-phased frontier allocator under fixed budget).
- Mention `strict_gate1_cap_k6` as runner-up/default anchor, not as manuscript lead.

## Provenance pointers
- Internal decision package: `docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
- External readiness package: `docs/CANONICAL_EXTERNAL_BASELINE_PAPER_READINESS_DECISION_2026_04_22.md`
- Machine-readable readiness matrix: `docs/external_baseline_paper_readiness_decision_matrix.json`

## What changed in manuscript-facing policy
1. Re-centered manuscript lead method to `strict_f3` consistently.
2. Explicitly separated main-table externals from appendix-only and repo-only/discuss-only groups.
3. Removed any implication that repo-only MODE A additions belong in paper-facing empirical main tables.
