# Run record: Slurm job 1011561 (semantic-diversity loss-full Cohere diagnostic)

**Purpose:** Single place to pin **what ran**, **how it ended**, and **headline results**. Diagnostic only — not a manuscript claim.

## Slurm

| Field | Value |
|--------|--------|
| **Job ID** | `1011561` |
| **Name** | `semdiv-loss-full` |
| **State (sacct)** | `COMPLETED` |
| **Exit code** | `0:0` |
| **Elapsed** | `00:13:17` |
| **Primary node** | `n0111` |
| **sbatch** | `batch/run_semantic_diversity_loss_full_20260427T232800Z.sbatch` |

## Timestamp / outputs (repository-relative)

| Field | Value |
|--------|--------|
| **Timestamp** | `20260427T232800Z` |
| **Output directory** | `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/` (gitignored; present on machine that ran the job) |
| **Slurm logs (example paths)** | `outputs/slurm_logs/semantic_diversity_loss_full_20260427T232800Z_1011561.out` / `.err` (gitignored) |

**Readiness (from sbatch stdout):** Cohere smoke test **succeeded**; `cohere_mode ok=True`, runner exit code **0**. No `run_failure_issue.md` for a successful path.

## Design of the run

- **Mode:** live Cohere, `--selection-profile loss-full`, `--max-cases 30` (with `--allow-large-run`), budgets **4, 6, 8**, full traces enabled.
- **Manifest `n_selected_cases`:** **9** unique `example_id`s (loss JSONL + filters did not fill 30).
- **Per-method rows:** **27** each = 9 cases × 3 budgets; **162** total non-error rows in `per_case_results.csv` (6 methods × 27).

## Headline results (aggregate, this cohort only)

| Method | Accuracy (this run) | Avg actions (this run) |
|--------|----------------------|-------------------------|
| `direct_reserve_semantic_frontier_v1` | **0.7407** | ~4.56 |
| `external_l1_max` | 0.6667 | ~1.00 |
| `semantic_minimum_maturation_plus_direct_reserve_v1` | 0.5556 | ~4.67 |
| `branching_necessity_gate_v1` | 0.4074 | ~3.11 |
| `strict_f3` | 0.3333 | ~3.26 |
| `semantic_minimum_maturation_frontier_v1_d3` | 0.3333 | ~2.85 |

**Takeaway:** **`direct_reserve_semantic_frontier_v1`** improved strongly vs **`strict_f3`** on paired rows; comparison vs **`external_l1_max`** is **narrow on this small cohort** — replicate before trusting externally.

## Related docs (committed)

- Full narrative: `docs/SEMANTIC_DIVERSITY_LOSS_FULL_RESULT_ANALYSIS_20260427T232800Z.md`
- Controller auto-report: `docs/SEMANTIC_DIVERSITY_CONTROLLER_DIAGNOSTIC_20260427T232800Z.md`
- Next steps plan: `docs/NEXT_SEMANTIC_DIVERSITY_EXPERIMENT_PLAN.md`
- Compact CSV snapshot: `docs/semantic_diversity_loss_full_final_decision_snapshot_20260427T232800Z.csv`
- Offline re-analysis script: `scripts/analyze_semantic_diversity_diagnostic_run.py`

```bash
python scripts/analyze_semantic_diversity_diagnostic_run.py --timestamp 20260427T232800Z
```

## Claim boundary

Do **not** cite job **1011561** alone as proof for the paper; **N=9** examples with selection bias toward loss cases. Use only as **internal diagnostic evidence** pending larger runs (`NEXT_SEMANTIC_DIVERSITY_EXPERIMENT_PLAN.md`).
