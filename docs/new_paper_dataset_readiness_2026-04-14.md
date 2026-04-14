# New-paper external reasoning datasets: readiness snapshot (2026-04-14)

This note records the first **practical readiness/preparation pass** after external reasoning dataset integration.

- Track scope: **new-paper only** (frontier allocation, branch scoring, verifier learning, pairwise branch ranking, trajectory/process supervision).
- Prepared run: `outputs/prepared_reasoning_datasets/20260414T035501Z/`.
- Preparation command:
  - `python scripts/prepare_external_reasoning_datasets.py --sample-rows 6 --preview-per-dataset 6`

## Tiered recommendation

### Tier 1 (use now)

- `ultrainteract_pair`
- `deepstep_math_5k`
- `math_verify_s1k_r1`
- `mt_bench_human_judgments`
- `prometheus_preference_collection`

### Tier 2 (promising backup)

- `judgelm_100k`
- `judgelm_collection_v1`
- `math_shepherd`
- `prm800k`
- `prometheus_feedback_collection`
- `webinstruct_verified`
- `arctraj`
- `ultrainteract_sft`

### Tier 3 (low priority / not worth using now)

- `pairs` (not integrated: no canonical standalone dataset artifact)
- `agentprm_/_inverseprm` (not integrated: gated/missing stable public artifact)

## Concrete usage guidance for Codex (next step)

1. **Pairwise branch ranking first:** `ultrainteract_pair`, `mt_bench_human_judgments`, `prometheus_preference_collection`, with `judgelm_100k` as immediate backup.
2. **Branch scoring + verifier warm start:** `deepstep_math_5k` and `math_verify_s1k_r1` first, then optionally mix `math_shepherd` / `prm800k`.
3. **Trajectory/process auxiliary supervision:** `webinstruct_verified` and `ultrainteract_sft` are helpful as auxiliary trajectory data; `arctraj` stays backup because parsing/task-fit overhead is higher.
4. **Do not overclaim fit:** external datasets are useful warm-start supervision, but **not sufficient by themselves** for frontier-allocation labels. Keep repo-specific labels in scope:
   - brute-force oracle branch labels,
   - continuation-value labels tied to this codebase,
   - and weak-to-strong transfer setup if needed.

## Artifacts produced

- `dataset_preparation_report.json`
- `dataset_preparation_report.md`
- `dataset_readiness_ranking.csv`
- `normalized_schema_summary.csv`
- lightweight normalized previews in `normalized_previews/*.jsonl`

All artifacts are small, auditable, and avoid raw dataset dumps.
