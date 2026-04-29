# Outputs artifact index (orientation only)

`outputs/` is a **store**, not an interpretation authority. Read `docs/PAPER_SOURCE_OF_TRUTH.md` before citing anything.

## Canonical paper-facing roots (claim-eligible when regenerated via canonical scripts)

| Path | Role |
|------|------|
| `outputs/paper_tables/` | Tables for manuscript / anonymous artifact |
| `outputs/paper_plot_data/` | Numeric series behind plots |
| `outputs/paper_figures/` | Figures |

Generator (typical): `python scripts/paper/run_all_neurips_paper_artifacts.py`

## Diagnostic real-model / API-backed artifacts

Examples (non-exhaustive):

- `outputs/real_model_*`, `outputs/cohere_real_model_*`, `outputs/openai_*`, cross-provider audit bundles  
- `outputs/cohere_real_model_cost_normalized_validation_<timestamp>/` — per-example JSONL, manifests when finalized; **supporting/diagnostic** unless promoted.

**Interpretation:** useful for DR-v2 vs `external_l1_max`, cost-normalized validation, selector diagnostics; **not** automatic substitutes for canonical paper tables unless a canonical doc says so.

## Mock-backed vs Cohere-backed selector provenance (OV rerank)

For `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`:

| Timestamp | Role |
|-----------|------|
| `20260429T_OV_RERANK_100CASE` | **Mock-backed diagnostic provenance** (OV verifier backend env not set → controller default mock). Do **not** describe as a completed “real Cohere outcome verifier” experiment. |
| `20260429T_OV_RERANK_100CASE_COHERE_BACKEND` | **Real Cohere-backend** OV verifier run (explicit env). Treat as the authoritative slice for Cohere verifier backend once scored rows complete and reports are generated. |

Do **not** mix rows from these timestamps when interpreting verifier-backend behavior.

## Partial / interrupted / provenance-only

- Any run with incomplete scored counts per method, interrupted processes, or superseded timestamps: **provenance only** unless reopened under a new timestamp with clear README/doc note.

## Active runs

If a validation job is in progress, **do not delete or hand-edit** its output directory while the process writes `per_example_records.jsonl` / heartbeats. Checking file mtimes or scored counts read-only is fine.

More detail: `outputs/README.md`.
