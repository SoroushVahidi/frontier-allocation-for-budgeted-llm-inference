# Repository hygiene audit — 2026-05-02

Navigation and classification pass: **add indexes and cross-links**; **no provenance destruction**.

## What was cleaned / organized

- Added root front door: `START_HERE_CURRENT.md`.
- Added method classifier: `docs/METHOD_STATUS_TABLE.md`.
- Added artifact classifier: `docs/ARTIFACT_STATUS_TABLE.md`.
- Added operational short runbook: `scripts/CURRENT_RUNBOOK.md`.
- Updated **minimally** (navigation sections / links only): `README.md`, `docs/CURRENT_PROJECT_STATUS.md`, `docs/DOCS_INDEX.md`, `docs/REPO_MAP.md`, `docs/REPO_ORGANIZATION_GUIDE_20260501.md`, `scripts/README.md`.

## What was intentionally not deleted, moved, or renamed

- **All timestamped `outputs/` trees** — untouched.
- **Historical docs and scripts** — untouched.
- **No rewriting** of conclusions inside existing narrative docs beyond adding pointers to the new tables.

## `.gitignore`

- **No change** in this pass. Artifact policy remains as in the existing root `.gitignore` (broad ignore of raw `outputs/**/*.jsonl` with curated exceptions).

## Files deleted, moved, or renamed

- **None.**

## Repository scale (approximate, local snapshot)

| Metric | Approximate value |
|--------|-------------------|
| `docs/` top-level files | ~836 |
| `scripts/*.py` (depth 1) | ~440 |
| `outputs/` top-level directories | ~446 |
| Tracked files (`git ls-files`) | ~7990 |
| `du -sh outputs` | ~9.4G |
| `du -sh logs` | ~11M |
| `du -sh archive` | ~131K |

(`git status` failed in this environment with `fatal: unable to create threaded lstat: Resource temporarily unavailable` — likely filesystem/NFS; commits were not blocked when using explicit `git add` paths in prior work.)

## Tests / checks run (this pass)

```bash
python scripts/check_repo_health.py
python -m pytest -q tests/test_frontier_router.py tests/test_check_repo_health_paths.py
```

**Results:** `check_repo_health.py` reported **OK**. Pytest subset: **8 passed** (same commands as `make reviewer-test` subset used in recent commits).

## Dangerous-to-reinterpret artifacts

- Any **`outputs/cohere_real_model_cost_normalized_validation_*`** folder **without** confirming **verifier backend** (mock vs Cohere) and **score coverage** (`docs/PAPER_SOURCE_OF_TRUTH.md`, `docs/OUTPUTS_ARTIFACT_INDEX.md`).
- **Cache-limited** selector comparisons: non-zero missing scores or fallback-to-incumbent (`docs/CURRENT_PROJECT_STATUS.md`).
- **`outputs/best_selector_vs_external_l1_comparison_*/`** until missing-score metrics are zero.
- **88-case external-loss** paths: selected subset, not random GSM8K (`docs/BEST_METHODS_ON_EXTERNAL_LOSS_CASES_100_20260430T195659Z.md`).
- **Recovery-track** selector packages must not be read as **runtime-promoted** controller evidence.

## Ignored / untracked artifact policy (reminder)

- Large JSONL caches, many logs, and most raw `outputs/**` blobs stay **out of git** unless whitelisted; see root `.gitignore`.
- **Do not** `git add -f` ignored caches without an explicit retention audit (`docs/SELECTOR_EVIDENCE_RETENTION_POLICY_20260501.md`, etc.).

## Remaining messiness / risks

- **Many overlapping “start here” docs** (`CANONICAL_START_HERE.md`, `SELECTOR_WORK_START_HERE_20260501.md`, …); `START_HERE_CURRENT.md` is the **short** current pointer—older files remain valid for depth.
- **Hundreds of `outputs/` timestamps** are not row-level indexed here; use `docs/OUTPUTS_ARTIFACT_INDEX.md`, `docs/ARTIFACT_INDEX_20260501.md`, and folder manifests.
- **Long `broad_diversity_aggregation_*` method strings** confuse newcomers; `docs/METHOD_STATUS_TABLE.md` maps them to `strict_f3` / `strict_gate1_cap_k6`.

## Recommended future cleanup tasks

1. Optional: one **machine-generated** `outputs/` top-level index (CSV/MD) from directory names + manifest presence—**append-only**, no moves.
2. Gradually mark **superseded** docs with a single line at top pointing to `START_HERE_CURRENT.md` or `docs/CURRENT_PROJECT_STATUS.md`.
3. After any fully scored external comparison, add **one** new row to `docs/ARTIFACT_STATUS_TABLE.md` rather than repurposing old folders.
