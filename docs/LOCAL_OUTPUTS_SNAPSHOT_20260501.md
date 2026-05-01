# Local `outputs/` snapshot (2026-05-01)

This commit adds **previously untracked** experiment and smoke directories under `outputs/` from the MMFS checkout, so they are reproducible from git history instead of only on disk.

## Scale

| Metric | Value |
|--------|------|
| Untracked paths staged (dirs + loose files under `outputs/`) | 214 |
| Files in the resulting commit | 3,273 |
| Approximate staged payload | ~0.30 GiB on disk (same order as the pre-commit working-tree scan) |

The working tree `outputs/` tree was about **9.4 GiB** before this commit; most of that mass lives in **HF `compressed_*.tar.gz` caches** and **multi-hundred-megabyte `branch_scorer_v3_dataset.jsonl` pools**, which **cannot** be pushed to GitHub (hard **100 MiB** blob limit).

## Excluded from git (see `.gitignore`)

- `outputs/**/compressed_*.tar.gz` — duplicated Llama / MATH128 HF archives (~277 MiB and ~1.3 GiB each) under several `when_solve_when_verify_*` and `hf_adjacent_suite` trees.
- `outputs/branch_scorer_v3_heavy_ml/datasets/**/branch_scorer_v3_dataset.jsonl` and `outputs/branch_scorer_v3_heavy_ml/pooled/branch_scorer_v3_dataset.jsonl` — pooled dataset shards ~200–605 MiB each.

Re-fetch those artifacts locally if you need branch-scorer v3 heavy ML or HF import-package reruns.

## Largest top-level trees on disk (before exclusions)

Largest directories by `du` included multi-gigabyte HF download folders and `branch_scorer_v3_heavy_ml/`; after exclusions the remaining tracked files inside those dirs are small sidecars (metadata, logs, partial CSVs) where present.

## Prior `git add -A` failure

An earlier monolithic `git add -A` over this tree failed with `fatal: unable to write new index file` after ~16 minutes (likely index rewrite pressure on GPFS). This snapshot was staged **per top-level subdirectory** under `outputs/` to reduce peak index work.
