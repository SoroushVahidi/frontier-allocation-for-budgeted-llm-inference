# Repository Status and Evidence Map (2026-04-29)

## Branch/recent-state audit
- Current working branch: `work`.
- Latest local commit: `c2e1b21`.
- Recent merged PRs visible from local git history:
  - `#305` (merge commit `db658b5`) internal-method audit/preflight package.
  - `#304` (merge commit `403bdeb`) earlier Cohere validation/report package.
- Open PR status cannot be authoritatively determined from local git-only context.

### Codex-local chunk tooling presence on current branch
Confirmed present on this branch:
- `scripts/plan_cohere_real_model_chunks.py`
- `scripts/run_cohere_chunk.py`
- `scripts/status_cohere_chunk_progress.py`
- `scripts/aggregate_cohere_chunks.py`
- `docs/CODEX_LOCAL_RESUMABLE_COHERE_EXPERIMENT_RUNBOOK_20260429.md`

No discrepancy found for these files on current branch.

---

## Evidence hierarchy (claim safety)

### 1) Canonical paper-facing evidence (claim-eligible)
Canonical paper claims must be grounded in outputs generated from:
- `scripts/paper/run_all_neurips_paper_artifacts.py`

Canonical output roots:
- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

Claim gating document:
- `docs/PAPER_SOURCE_OF_TRUTH.md`

### 2) Diagnostic real-model evidence (supporting only unless promoted)
Includes:
- Cohere/OpenAI real-model runs
- preflight checks
- partial/incomplete launch attempts
- Codex-local chunk runs and resumptions
- readiness/failure audits

These are **not** headline manuscript evidence unless explicitly promoted by a future canonical decision/update path.

### 3) Diagnostic-only method variants (excluded from live claim runs)
- `direct_reserve_semantic_frontier_v2_thresholded_ordered` is diagnostic-only.
- It appears in semantic diagnostic registry paths but is not runtime-present in live `build_frontier_strategies(...)` runner specs.
- It must remain excluded from live full comparisons unless runner support is intentionally extended later.

### 4) Partial / incomplete / provenance-only artifacts
Examples:
- tiny 10-example checks
- interrupted chunk attempts
- launch-attempt logs with partial coverage
- Wulver/Slurm handoff docs in a Codex-only session (historical unless manually ported)

These artifacts are useful for provenance/debugging and planning, but should not drive paper headline claims.

---

## What is currently safe to claim
- The repository has a canonical paper artifact pipeline and explicit claim boundaries.
- Real-model evidence exists but is diagnostic/supporting by default.
- Method surface distinctions (manuscript-facing representative vs broader operational defaults) are documented and must be kept explicit.

## What should not be claimed
- No universal dominance claims from partial real-model slices.
- No promotion of diagnostic-only variants into live-comparison claims without explicit runner extension and fresh canonical evidence.
- No manuscript claim changes from incomplete Codex-local chunk runs.

---

## Script map: canonical vs diagnostic

### Canonical artifact generators
- `scripts/paper/run_all_neurips_paper_artifacts.py`
- Supporting claim-scoped generators listed in `docs/RESULTS_GUIDE.md`.

### Diagnostic real-model tooling
- `scripts/run_cohere_real_model_cost_normalized_validation.py`
- `scripts/plan_cohere_real_model_chunks.py`
- `scripts/run_cohere_chunk.py`
- `scripts/status_cohere_chunk_progress.py`
- `scripts/aggregate_cohere_chunks.py`

---

## Current completion snapshot (Codex-local chunk path)
- Chunk system is implemented and usable.
- Runs to date are partial/incomplete for the 100-scored-per-slice target.
- Continue with resumable chunk execution; do not rewrite claim language until completed matched slices exist.

## Codex-local chunk reliability notes
- No Slurm/Wulver dependency for chunk planning, per-chunk execution, status, or aggregation scripts.
- `scripts/run_cohere_chunk.py --dry-run` prints exact command line without API invocation.
- Chunk status and aggregate scripts now tolerate missing `slice_summary.csv` and `pairwise_comparisons.csv`, emitting schema-valid CSVs.

- Persistence policy: for Codex-local resumable Cohere runs, track compact ledgers under `outputs/cohere_compact_ledgers/` to survive cross-task environments; do not rely on untracked raw JSONL files alone.
