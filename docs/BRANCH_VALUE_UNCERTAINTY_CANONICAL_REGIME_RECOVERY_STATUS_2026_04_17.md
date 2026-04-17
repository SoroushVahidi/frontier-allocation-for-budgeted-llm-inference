# Branch-value + uncertainty canonical regime recovery status (2026-04-17)

## Scope

This note covers only the current canonical branch-allocation / frontier-allocation line for fixed-budget adaptive test-time compute allocation.

## Exact diagnosis

The strict validation harness (`scripts/run_branch_value_uncertainty_strict_validation_pass.py`) requires a target root with all three regime directories:

- `regime_all_pairs_approx`
- `regime_promoted_exact_hard_region`
- `regime_penalized_marginal_defer`

and each regime directory must contain:

- `candidate_labels.jsonl`
- `pairwise_labels.jsonl`
- `state_summaries.jsonl`

In this checkout:

1. None of the canonical candidate roots exist:
   - `outputs/branch_label_bruteforce_targets/near_tie_compare_bundle_exact_augmented_regimes_20260417`
   - `outputs/branch_label_bruteforce_targets/incomparability_exact_augmented_regimes_20260417`
   - `outputs/branch_label_bruteforce_targets/validation_penalized_regimes_nt_l0.20_t0.02_eu0.10_cap1.50_20260417`
2. The prior strict-validation proxy root is also missing:
   - `outputs/branch_label_bruteforce_targets/strict_validation_proxy_20260418`
3. No compliant `regime_*` directories with required label files were found anywhere in this repository tree.
4. Upstream roots referenced by the regime build commands are also missing (e.g., `outputs/branch_label_bruteforce/...` and exact-expansion roots), so regeneration cannot proceed from checked-in artifacts alone.

## Cause classification

The missing canonical regime issue in this checkout is **not** a regime naming mismatch or partial file corruption.
It is an **artifact availability/provenance gap**: required outputs were produced in prior local runs but are not present now (consistent with repository output ignore policy and non-committed runtime artifacts).

## Recovery path attempted

Minimal, repo-consistent path attempted:

1. Locate existing canonical roots and verify required regime/file presence.
2. Locate any alternative root/regime naming variants in-repo.
3. Locate upstream inputs needed to regenerate exact-augmented roots.
4. Re-run strict validation harness unchanged using the strongest canonical candidate root to verify replay status.

Result: recovery/regeneration is currently blocked by missing upstream label artifacts.

## Strict validation replay status (unchanged harness)

Command replayed unchanged with matched settings:

- script: `scripts/run_branch_value_uncertainty_strict_validation_pass.py`
- regimes: `all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer`
- seeds: `11,29,47`
- feature set: `v3`

Run id:

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_canonical_recovery_probe_20260417`

Outcome:

- replay executes but reports missing all required regime directories and yields zero-row diagnostic aggregates.
- canonical comparison metrics are still unavailable from real canonical artifacts in this checkout.

## Repository-recorded artifacts for this recovery attempt

- Machine-readable diagnosis:
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_recovery_20260417/recovery_diagnosis_summary.json`
- Machine-readable manifest:
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_recovery_20260417/recovery_attempt_manifest.json`
- Commands / assumptions / caveats:
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_recovery_20260417/recovery_commands.md`
- Strict harness replay outputs:
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_canonical_recovery_probe_20260417/strict_validation_summary.json`
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_canonical_recovery_probe_20260417/strict_validation_results.json`
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_canonical_recovery_probe_20260417/strict_validation_config.json`
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_canonical_recovery_probe_20260417/strict_validation_manifest.json`

## Precise blocker and conservative next step

### Blocker

Required canonical target roots and all known upstream generation inputs are absent in this checkout.

### Required next input to unblock

Materialize one full canonical targets root containing the three required regime directories and required label JSONL files (either by restoring archived outputs or by rerunning upstream label+exact-expansion generation in an environment where those source artifacts exist).

### Next recommended Codex task

Perform a **source-artifact restoration task** (not method redesign):

1. Restore or mount the missing upstream source roots (`outputs/branch_label_bruteforce/...` plus exact-expansion roots) from the canonical artifact store/run cache.
2. Rebuild one canonical target root using existing repository scripts and frozen parameters.
3. Re-run `scripts/run_branch_value_uncertainty_strict_validation_pass.py` unchanged on that restored root.
