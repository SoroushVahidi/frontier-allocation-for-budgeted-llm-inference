# Top-priority dataset expansion readiness (2026-04-17)

This pass adds and verifies only the current top-priority external datasets identified in `docs/DATASET_EXPANSION_PRIORITIES_2026_04_17.md`:

1. DROP
2. MuSR
3. BIG-Bench Hard
4. AQuA

The pass is integration/readiness only (not a broad training/evaluation sweep).

## Runtime integration decisions

- **DROP**
  - Requested path checked: `allenai/drop`.
  - Current clean loader path in this environment: `ucinlp/drop`.
  - Registry key tracked in repo: `allenai/drop` (canonical key), with explicit fallback provenance note to `ucinlp/drop` and AWS registry.
  - Conservative status: **ready with source-path caveat**.

- **MuSR**
  - Loader path: `TAUR-Lab/MuSR`.
  - Split family observed: `murder_mysteries`, `object_placements`, `team_allocation`.
  - Conservative status: **ready**.

- **BIG-Bench Hard**
  - Loader path: `openeval/BIG-Bench-Hard`.
  - Current row shape appears task-packed (`examples` field).
  - Conservative status: **ready for evaluation-first integration** (task-unpacking policy still needed for some training uses).

- **AQuA**
  - Requested path checked: `aqua_rat`.
  - Current canonical HF path in this environment: `deepmind/aqua_rat`.
  - Configs observed: `raw`, `tokenized` (defaulted to `raw` in this pass).
  - Conservative status: **ready**.

## Access/load results in this environment

From `outputs/dataset_expansion_20260417/hf_access/hf_access_summary.json`:

- `allenai/drop` (loading via repo id `ucinlp/drop`): **ok=true**
- `TAUR-Lab/MuSR`: **ok=true**
- `openeval/BIG-Bench-Hard`: **ok=true**
- `deepmind/aqua_rat`: **ok=true**

## Basic schema/split observations (bounded)

- DROP (`validation`): keys include `passage`, `question`, `answers_spans`.
- MuSR (`murder_mysteries`): keys include `narrative`, `question`, `choices`, `answer_choice`, `answer_index`.
- BIG-Bench Hard (`train`): keys include `canary`, `examples`.
- AQuA (`validation`, `raw`): keys include `question`, `options`, `correct`, `rationale`.

## License/access notes (bounded)

From `outputs/dataset_expansion_20260417/integration_report/dataset_integration_report.json` (`hub_metadata` + per-dataset notes):

- DROP mirror (`ucinlp/drop`): license metadata surfaced as `cc-by-sa-4.0`; requested `allenai/drop` HF id unresolved here.
- MuSR: license metadata surfaced as `cc-by-4.0`.
- BIG-Bench Hard: no explicit license field surfaced in this bounded probe; treat as **manual license confirmation required** before redistribution-sensitive usage.
- AQuA (`deepmind/aqua_rat`): license metadata surfaced as `apache-2.0`.

## Conservative usage classification for current bottleneck

- DROP: **evaluation-first**
- MuSR: **evaluation-first**
- BIG-Bench Hard: **evaluation-first**
- AQuA: **both** (evaluation + training candidate)

Rationale: this keeps the repository centered on hard ambiguous near-tie decision quality and avoids over-committing noisy/format-heavy conversions before targeted design work.

## Artifacts produced in this pass

- `outputs/dataset_expansion_20260417/hf_access/hf_access_summary.json`
- `outputs/dataset_expansion_20260417/hf_access/hf_access_summary.csv`
- `outputs/dataset_expansion_20260417/hf_access/hf_access_note.md`
- `outputs/dataset_expansion_20260417/smoke/smoke_summary.json`
- `outputs/dataset_expansion_20260417/integration_report/dataset_integration_report.json`
- `outputs/dataset_expansion_20260417/integration_report/dataset_integration_report.md`

## Ready/not-ready summary

Ready now (for bounded integration):
- MuSR
- BIG-Bench Hard
- AQuA (`deepmind/aqua_rat`)
- DROP via tracked fallback loader path (`allenai/drop` key -> `ucinlp/drop` repo id)

Needs manual resolution before strict paper-freeze use:
- DROP canonical source policy (HF `allenai/drop` vs mirror/AWS path).
- BIG-Bench Hard license confirmation (not explicit in quick card metadata probe).
