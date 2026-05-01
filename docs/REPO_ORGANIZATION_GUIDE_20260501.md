# Repository organization guide — 2026-05-01

## Purpose

This guide is the lightweight cleanup and navigation contract for the repository after the recovery-track selector decision and the addition of the self-consistency literature baseline.

It is intentionally conservative: it organizes interpretation and navigation without deleting timestamped evidence, rewriting historical conclusions, or promoting diagnostic artifacts into paper-facing claims.

## Current clean entry points

Read in this order for normal work:

1. `README.md`
2. `docs/CURRENT_PROJECT_STATUS.md`
3. `docs/DOCS_INDEX.md`
4. `docs/REPO_MAP.md`
5. `docs/PAPER_SOURCE_OF_TRUTH.md`
6. `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`

For selector work, then read:

1. `docs/CURRENT_SELECTOR_DECISION.md`
2. `configs/selected_selector_current.json`
3. `docs/LITERATURE_SELECTOR_BASELINES.md`
4. `docs/FAST_SELECTOR_EXECUTION_POLICY.md`
5. `docs/SELECTOR_CHOOSING_PLAYBOOK_20260501.md`

For reproducibility / reviewer work, then read:

1. `docs/CANONICAL_INSTALL_AND_DEV.md`
2. `docs/REVIEWER_10_MINUTE_REPRODUCTION.md`
3. `scripts/CANONICAL_START_HERE.md`
4. `scripts/README.md`

## Current canonical interpretation layer

The following files should be treated as the active interpretation layer:

| File | Role |
|---|---|
| `README.md` | Short front door and current state. |
| `docs/CURRENT_PROJECT_STATUS.md` | Day-to-day current status and next action. |
| `docs/DOCS_INDEX.md` | Current/documentation/provenance classification. |
| `docs/REPO_MAP.md` | Directory and artifact map. |
| `docs/PAPER_SOURCE_OF_TRUTH.md` | Claim-eligible evidence hierarchy. |
| `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md` | Safe vs unsafe claim wording. |
| `docs/CURRENT_SELECTOR_DECISION.md` | Current selected verifier selector and caveats. |
| `docs/LITERATURE_SELECTOR_BASELINES.md` | Selector baselines such as self-consistency. |

If these files conflict with older dated documents, prefer the active interpretation layer unless a later dated audit explicitly supersedes it.

## Artifact classes

### Canonical / current selector artifacts

These are the current recovery-track selector-decision artifacts:

- `outputs/unified_selector_evidence_20260501T145906Z/`
- `outputs/outcome_verifier_answer_group_selector_20260501T152447Z/`
- `outputs/outcome_verifier_scores_cohere_smoke10_20260501T162328Z/`
- `outputs/outcome_verifier_answer_group_selector_repro_linkage_20260501T181534Z/`
- `outputs/selected_selector_audit_20260501T181608Z/`
- `outputs/final_selector_decision_20260501T175547Z/`

They support the narrow claim that the selected Cohere cached outcome-verifier selector is the audited working selector for the recovery selector-evidence track.

They do **not** support runtime promotion or an `external_l1_max` defeat claim.

### Literature-baseline artifacts

Self-consistency majority-vote artifacts live under timestamped `outputs/self_consistency_*` folders.

Use them as literature-baseline evidence only when the comparison uses the same paired slice and clear dataset/candidate-pool contract.

### Diagnostic external-baseline artifacts

`outputs/best_selector_vs_external_l1_comparison_*/` contains bounded external-baseline comparison outputs.

Cache-limited selected-verifier comparisons remain diagnostic until:

```text
missing_candidate_score_count = 0
fallback_to_incumbent_due_to_missing_scores = 0
selected_candidate_not_in_pool_count = 0
```

### Historical / provenance artifacts

Older timestamped outputs, negative baselines, failed or blocked regeneration attempts, transfer audits, and schema-debug folders should normally be preserved. They explain why a path was abandoned or why a claim is unsafe.

## Cleanup rules

1. Do not delete timestamped real-model outputs unless a dedicated cleanup audit classifies them as disposable.
2. Do not overwrite timestamped output folders. Create a new timestamped folder instead.
3. Do not rewrite historical conclusions to match current results.
4. Prefer indexing, labeling, and cross-linking over deletion.
5. Do not promote diagnostic artifacts to paper-facing evidence without updating `docs/PAPER_SOURCE_OF_TRUTH.md` and `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`.
6. Do not make paid API calls until the call count, dataset, method, budget, seed, and expected output package are known.
7. Keep verifier inputs gold/oracle/evaluation-only free.
8. Compare selector families only on matched paired slices when making headline claims.

## Safe next engineering cleanup

Good cleanup tasks:

- Keep `README.md`, `CURRENT_PROJECT_STATUS.md`, `DOCS_INDEX.md`, and `REPO_MAP.md` synchronized after each major selector/baseline PR.
- Add small artifact-index rows rather than moving or deleting old output folders.
- Add missing `--help` examples to script docs.
- Add tests for new selector scripts before adding new outputs.
- Add manifests for new comparison runs with score-coverage and fallback counts.

Avoid for now:

- Deleting old outputs.
- Renaming timestamped evidence folders.
- Collapsing diagnostic and canonical outputs into one folder.
- Claiming selected-verifier superiority over `external_l1_max` before full score coverage.
- Treating self-consistency and verifier results from different slices as a headline comparison.

## Current next action

Run a fully scored paired pilot where the selected verifier selector, self-consistency majority vote, original DR-v2, and `external_l1_max` are compared on the same cases with zero missing selected-verifier scores.
