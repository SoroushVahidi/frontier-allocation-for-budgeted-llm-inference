# Repository map and canonical path

## Project scope (current)

Canonical scope is the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches,
- oracle frontier headroom,
- anti-collapse controller design.

## What this map is for

Use this file to answer three questions quickly:
1. What part of the repo is canonical?
2. Where should a collaborator start?
3. Which artifacts and scripts matter first for the current paper path?

## Directory map

- `docs/` — canonical project interpretation, bottlenecks, safe claims, planning notes, and supporting references.
- `scripts/` — runnable entry points and orchestration wrappers.
- `experiments/` — implementation modules and compact experiment/result notes.
- `configs/` — dataset, baseline, schema, and experiment configuration files.
- `datasets/` — dataset policy/readme assets.
- `external/` — external baseline references and integration notes.
- `outputs/` — generated artifacts, audits, corpora, and paper-support outputs.

## Canonical collaborator path

A new collaborator should follow this order:

1. Read [`PROJECT_MASTER_PLAN.md`](PROJECT_MASTER_PLAN.md).
2. Read [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md).
3. Read [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md).
4. Read [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md).
5. Read [`PAPER_POSITIONING_NOTE.md`](PAPER_POSITIONING_NOTE.md).
6. Read [`README.md`](README.md).
7. Use [`../scripts/README.md`](../scripts/README.md) only after the canonical path is clear.

## Canonical scripts now

These are the main current-paper entry points.

### Internal supervision / canonical corpus path
- `scripts/run_bruteforce_branch_label_generator.py`
- `scripts/merge_bruteforce_branch_label_runs.py`
- `scripts/build_bruteforce_target_regimes.py`
- `scripts/build_canonical_branch_learning_corpus.py`
- `scripts/run_canonical_branch_learning_pass.py`

### Supporting hard-slice / exact-supervision path
- `scripts/mine_bruteforce_hard_regions.py`
- `scripts/expand_bruteforce_exact_hard_regions.py`
- `scripts/build_exact_augmented_target_regimes.py`
- `scripts/run_hard_region_exact_supervision_experiment.py`
- `scripts/run_hard_case_feature_representation_experiment.py`

### External-supervision and readiness path
- `scripts/build_external_prm_mathshepherd_apps_corpus.py`
- `scripts/verify_external_reasoning_datasets.py`
- `scripts/generate_external_reasoning_dataset_integration_report.py`

## Canonical artifact families now

- `outputs/branch_label_bruteforce*/` — source branch-allocation supervision runs.
- `outputs/branch_learning_corpora*/` — canonical processed corpora.
- `outputs/canonical_branch_learning_pass/` — matched internal/external learning comparisons.
- `outputs/external_baseline_completeness*/` — baseline-integration status artifacts.

## Classification labels

### Canonical
- frontier/controller allocation scaffold,
- branch-priority / next-step allocation work,
- canonical corpora and matched learning passes,
- dataset and external-supervision readiness artifacts,
- paper-facing evaluation and audit paths.

### Exploratory
- reliability-aware BT variants,
- warm-start lines,
- one-off ambiguity/tie-handling diagnostics,
- narrower method notes that are useful but not yet canonical.

### Historical
- old manuscript / binary revise-routing material,
- dated memos superseded by the current canonical docs.

## Practical rule

When in doubt:
- use the canonical docs first,
- treat exploratory notes as evidence traces rather than the default repo story,
- and use the canonical corpus / matched-learning path before exploring older helper workflows.
