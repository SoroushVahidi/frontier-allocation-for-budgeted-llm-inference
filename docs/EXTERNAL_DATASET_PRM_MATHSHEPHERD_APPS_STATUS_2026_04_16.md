# Targeted external dataset integration status (PRM800K, Math-Shepherd, APPS) — 2026-04-16

This pass integrates a small, high-value dataset set conservatively into the canonical dataset/corpus pathway.

## What was added in code

- Added APPS (`codeparrot/apps`) into external reasoning dataset specs + registry as verifier-backed, derived-supervision candidate (not branch-native).
- Added canonical-aligned builder for this trio: `scripts/build_external_prm_mathshepherd_apps_corpus.py`.

## Access / integration status

| Dataset | Access status | Role classification | Native vs derived for branch-allocation | Immediate usability | Key caveat |
|---|---|---|---|---|---|
| PRM800K | ✅ | supervision (process/step) | native step labels; branch-allocation rows are derived | candidate-style usable now | pairwise/outside derivation limited in this conservative pass |
| Math-Shepherd | ✅ | supervision (process/step) | native step labels; branch-allocation rows are derived | candidate-style usable now | pairwise/outside derivation limited in this conservative pass |
| APPS | ⚠️ | verifier-backed coding dataset | branch-allocation supervision is derived (not native) | partially integrated / blocked in this env | HF loader path fails here (`apps.py` dataset-script incompatibility) |

## Canonical artifact paths produced

- `outputs/external_reasoning_datasets_audit_prm_mathshepherd_apps/external_reasoning_dataset_access.json`
- `outputs/external_reasoning_datasets/prm_mathshepherd_apps_20260416/dataset_integration_report.json`
- `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416/summary.json`
- `outputs/external_dataset_target_pass_20260416_summary.json`

## Mapping to canonical branch-learning row view

- PRM800K: mapped to candidate-style rows with `is_human_labeled=true`, `is_rollout_estimated=false`, `is_verifier_backed=false`; current conservative build produced candidate rows only.
- Math-Shepherd: same conservative mapping as PRM800K in this pass (candidate-first, derived branch semantics).
- APPS: intended mapping is verifier-backed candidate/outside-option derived rows; in this environment loader incompatibility blocked row materialization.

## Branch-allocation alignment (explicit)

- Branch abstraction for PRM800K/Math-Shepherd: a partial reasoning step/prefix candidate within a solution trajectory.
- Next-unit-of-compute interpretation: whether spending one more local reasoning step on that branch is likely useful, approximated by step-quality supervision.
- Branch abstraction for APPS: partial code candidate / solution attempt; next compute unit corresponds to additional generation/edit/verification steps with testcase feedback.
- Label-quality limitation: all three are not branch-allocation-native; mapping is derived and remains a proxy for the true allocation decision.

## Usable now vs caveated

- PRM800K usable now for candidate-style supervision (`128 candidate rows in current canonical external corpus sample build`).
- Math-Shepherd usable now for candidate-style supervision (`128 candidate rows in current canonical external corpus sample build`).
- APPS currently caveated/blocked in this environment (dataset-script incompatibility under current datasets loader).

## Recommendation for next learning pass (concise)

- Use **PRM800K first** for the next targeted pass (clean access + human-labeled step supervision + conservative branch-candidate mapping), then fold in Math-Shepherd under the same protocol; keep APPS as verifier-backed pending adapter fix.
