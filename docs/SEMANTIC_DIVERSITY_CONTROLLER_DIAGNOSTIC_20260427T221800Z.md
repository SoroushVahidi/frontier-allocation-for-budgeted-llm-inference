# Semantic diversity controller diagnostic (20260427T221800Z)

## Status

Experimental / diagnostic only. A 10-case live Cohere run is **not** sufficient to support manuscript claims.

## Questions (see CSVs in output dir)

- Which variant had the best accuracy–cost tradeoff on `method_accuracy_summary.csv`?
- Do semantic maturation variants increase `semantic_family_count` vs `strict_f3` in `per_case_results.csv`?
- Do paired deltas in `paired_summary.csv` show improvement over `strict_f3` and movement toward `external_l1_max`?

## Next experiment

If a single variant is consistently better on **paired** accuracy vs `strict_f3` in two budgets, run 30 cases with `--allow-large-run` and the same case-selection policy.

---

## Completed run — Wulver batch (diagnostic only)

- **Execution**: submitted via Slurm (`batch/run_semantic_diversity_cohere10_20260427T221800Z.sbatch`), job ID **1011286**, exit **0**, wall clock ~15 minutes.
- **Cohere readiness**: passed (smoke chat to `command-r-plus-08-2024`).
- **Cases**: **9** distinct loss-subset examples with non-empty question/gold in `loss_cases_absent_from_tree.jsonl` (full **10** not available after filtering empty rows); **3** budgets (`4,6,8`) ⇒ **27** rows per method in `per_case_results.csv`.

### Method accuracy (`method_accuracy_summary.csv`)

| Method | n | Accuracy | Avg actions |
|--------|---|----------|-------------|
| external_l1_max | 27 | 0.815 | 1.04 |
| strict_f3 | 27 | 0.370 | 3.19 |
| semantic_minimum_maturation_frontier_v1_d2 | 27 | 0.333 | 2.56 |
| semantic_minimum_maturation_frontier_v1_d3 | 27 | 0.407 | 3.04 |
| direct_reserve_semantic_frontier_v1 | 27 | **0.667** | 4.85 |
| branching_necessity_gate_v1 | 27 | 0.407 | 3.04 |
| semantic_minimum_maturation_plus_direct_reserve_v1 | 27 | 0.593 | 4.67 |

**Interpretation**: On this narrow slice, **direct_reserve_semantic_frontier_v1** had the highest accuracy but used the most actions. This is **not** a manuscript claim (n=9; selected loss stratum).

### Semantic-family logging

- **`strict_f3`**: no `diagnostic_semantic_diversity` block (expected for the canonical controller).
- **Maturation variants**: `semantic_family_count` populated in CSV (mean ≈ **2.15** for `semantic_minimum_maturation_frontier_v1_d2` over rows with values).

### Staged failure before fix

An earlier submission (**job 1011283**, timestamp `20260427T215100Z`) failed **after** readiness because `direct_answers` contained `None` and `_normalize_answer` did not accept `None`. Fixed in code and documented in `docs/SEMANTIC_DIVERSITY_POST_READINESS_FAILURE_20260427T215100Z.md`.

### Whether to run 30 cases

Worth a **follow-up ablation on more examples**, not a conclusion: rerun with `--max-cases 30 --allow-large-run` only after reviewing `paired_summary.csv` and failure modes on this artifact.
