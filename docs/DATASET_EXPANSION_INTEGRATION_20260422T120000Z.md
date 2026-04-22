# Dataset expansion integration (20260422T120000Z)

## Purpose

This pass adds the next priority expansion package to broaden evaluation coverage beyond the repository's math-heavy core, in this explicit order:

1. DROP
2. MuSR
3. BIG-Bench Hard
4. AQuA

This is an integration/readiness/smoke pass. It is not a claim of model-performance improvement.

## Attempted datasets and outcome

| Priority | Dataset | Canonical key in repo | Access path used | Status | Notes |
|---:|---|---|---|---|---|
| 1 | DROP | `allenai/drop` | loader `ucinlp/drop` | integrated | Canonical key kept as `allenai/drop`; loader currently uses verified public mirror `ucinlp/drop`. |
| 2 | MuSR | `TAUR-Lab/MuSR` | `TAUR-Lab/MuSR` | integrated | Access + smoke sample succeeded on task-family splits. |
| 3 | BIG-Bench Hard | `openeval/BIG-Bench-Hard` | `openeval/BIG-Bench-Hard` | integrated | Access + smoke sample succeeded; rows remain task-packed and require explicit task-unpacking policy in full pipelines. |
| 4 | AQuA | `deepmind/aqua_rat` | `deepmind/aqua_rat` | integrated | Access + smoke sample succeeded on `raw` config with MCQ options surfaced in normalization. |

## What was added in this pass

### 1) Dataset access/integration support

- Added priority-expansion verification script: `scripts/verify_dataset_expansion_access.py`.
- Added canonical bundle generator: `scripts/generate_dataset_expansion_report.py`.
- Existing registry/loading support in `experiments/hf_datasets.py` was reused (no parallel architecture introduced).

### 2) Dataset-readiness checks

- Produced readiness artifacts under:
  - `outputs/dataset_expansion_access/20260422T120000Z/readiness.json`
  - `outputs/dataset_expansion_access/20260422T120000Z/readiness.csv`

### 3) Smoke-test support

- Smoke sampling is run per dataset through repo-standard formatting in `sample_hf_examples`.
- PASS in this environment for all four priority datasets.

### 4) Canonical text-only integration artifacts

Bundle path:
- `outputs/dataset_expansion_integration/20260422T120000Z/`

Included files:
- `status.json`
- `summary.json`
- `summary.md`
- `manifest.json`
- `dataset_status_matrix.csv`
- `dataset_schema_summary.csv`
- `dataset_sample_preview.jsonl`
- `config_snapshot.json`
- `command_snapshot.txt`

### 5) Documentation and navigation

- Added this manuscript-facing integration note.
- Added links in docs and output navigation pages.

## Scientific breadth contribution (reviewer-facing)

- **DROP**: adds paragraph-grounded evidence selection and span/numeric reasoning.
- **MuSR**: adds long-context narrative disambiguation and multi-hypothesis reasoning.
- **BIG-Bench Hard**: adds cross-domain reasoning diversity beyond math-centric tasks.
- **AQuA**: adds MCQ-format reasoning with option normalization discipline.

## Failure/blocker accounting (required explicit honesty)

No dataset fully failed in this run. Explicit caveats:

- **DROP canonical source caveat (temporary/source-path policy caveat):**
  - The repo keeps canonical key `allenai/drop` but currently loads from `ucinlp/drop` in this environment.
  - This is documented in registry provenance and run artifacts.
  - Next feasible path if strict ownership source is required: load from AllenAI DROP AWS Open Data registry and pin conversion manifest.

- **BIG-Bench Hard evaluation-policy caveat (structural for full training/eval pipelines):**
  - HF rows are task-packed; this pass validates access and smoke normalization only.
  - Full benchmark pipelines should document and pin task-unpacking policy.

## Main-paper useful vs appendix useful

### Main-paper useful now

- Drop-in expansion-readiness claim with reproducible machine-readable artifacts.
- Conservative breadth claim: the evaluation layer now includes non-math-heavy regimes (DROP/MuSR/BBH/AQuA).

### Appendix-useful details

- Schema-level field summaries.
- Sample preview rows.
- Command/config snapshots and per-dataset provenance caveats.

## Manuscript-safe wording

Use conservative wording like:

1. "We integrated DROP, MuSR, BIG-Bench Hard, and AQuA into the repository's dataset-access and smoke-readiness stack with machine-readable status artifacts."
2. "These additions are evaluation-breadth integrations and do not by themselves imply performance gains."
3. "DROP is tracked under canonical key `allenai/drop` with environment-verified loader fallback to `ucinlp/drop`, recorded in run manifests."
4. "BIG-Bench Hard integration currently validates access and schema-level smoke normalization; full task-unpacking policy is documented separately for benchmark-grade runs."

## Final priority ordering after this pass

Ordering remains unchanged and fully executed:

1. DROP
2. MuSR
3. BIG-Bench Hard
4. AQuA

## Binary-file policy

All artifacts created in this pass are text-only (`.py`, `.md`, `.json`, `.csv`, `.txt`, `.jsonl`). No binary files were created.
