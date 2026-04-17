# Branch-value + uncertainty strict canonical replay status (2026-04-17)

## Goal

Re-run `scripts/run_branch_value_uncertainty_strict_validation_pass.py` unchanged on the strongest available real canonical regime roots and check whether the bounded promising signal survives on actual canonical artifacts.

## Canonical root selection (strongest available candidates)

I selected the following roots because they are the strongest repository-documented branch-allocation targets tied to exact-augmented hard-case and/or penalized-marginal work:

1. `outputs/branch_label_bruteforce_targets/near_tie_compare_bundle_exact_augmented_regimes_20260417`
   - Near-tie canonical bundle used by strict coupled tie-aware work.
2. `outputs/branch_label_bruteforce_targets/incomparability_exact_augmented_regimes_20260417`
   - Exact-augmented hard-region family on the current branch-allocation path.
3. `outputs/branch_label_bruteforce_targets/validation_penalized_regimes_nt_l0.20_t0.02_eu0.10_cap1.50_20260417`
   - Strongest repository-documented penalized-marginal validation root used in bounded branch-allocation validation.

## Replay execution (unchanged strict script)

Used unchanged script, same seeds/settings as prior strict bounded pass:

- script: `scripts/run_branch_value_uncertainty_strict_validation_pass.py`
- regimes: `all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer`
- seeds: `11,29,47`
- feature set: `v3`

Commands and assumptions are recorded in:

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_replay_20260417/replay_commands_and_assumptions.md`

## Result

Canonical replay is **blocked in this checkout**:

- all selected roots are missing required `regime_*` directories;
- script completed and recorded `missing_regimes`, but no evaluable rows were available.

Per-root outputs:

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_canonical_replay_near_tie_bundle_20260417/strict_validation_summary.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_canonical_replay_incomparability_20260417/strict_validation_summary.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_canonical_replay_penalized_20260417/strict_validation_summary.json`

Combined machine-readable probe summary:

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_replay_20260417/canonical_replay_probe_summary.json`

## Required gating answers (evidence-constrained)

1. Does full method still beat brittle pairwise on canonical artifacts?
   - **Undetermined** (canonical artifacts unavailable in checkout).
2. Do gains remain after controlling for coverage?
   - **Undetermined** on canonical artifacts.
3. Are near-tie gains now real, mixed, or absent?
   - **Undetermined** on canonical artifacts.
4. Is raw uncertainty still the main driver?
   - **Undetermined** on canonical artifacts.
5. Is this strong enough to treat as top continuation line?
   - **Not yet**; evidence remains bounded/proxy-only until canonical replay runs on real artifacts.
6. Or should it remain only a bounded promising line?
   - **Yes**: keep as bounded promising line pending successful canonical replay.

## Honest status classification

**Classification: bounded promising line (canonical-gating unresolved).**

Rationale: strict replay procedure was executed, but canonical target artifacts needed for evaluation were absent, preventing strong claim updates.

## Exact blocking reason to fix next

Mount or restore canonical target roots that contain all required directories:

- `regime_all_pairs_approx/`
- `regime_promoted_exact_hard_region/`
- `regime_penalized_marginal_defer/`

for at least one canonical root representative of current branch-allocation production targets.

## Recommended next Codex task

Provision canonical `outputs/branch_label_bruteforce_targets/...` artifacts into this checkout, then rerun the same strict validation script with the exact same regimes/seeds/settings and append the resulting hard-slice and coverage-controlled comparison table to this note.
