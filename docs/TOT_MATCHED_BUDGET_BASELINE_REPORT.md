# Matched-budget ToT-style adapter baseline (manuscript-facing)

## What was implemented

This repository includes matched-budget **ToT-style** adapter baselines (not an official ToT paper replication):

- `tot_bfs_matched_budget`
- `tot_beam_matched_budget`
- `tot_dfs_matched_budget`

They are integrated alongside frontier methods under the **same action-budget ledger** and output-layer repair pipeline used elsewhere in the repo.

### Budget accounting (high level)

- One budget action corresponds to one branch expansion (and verify actions where a method uses them).
- ToT-style adapters do not receive free off-ledger verifier calls.
- Pruning/ranking inside beam-style adapters is accounted for within the controller’s expansion loop.

### Related work not implemented here

- **ReST-MCTS-style process supervision**: out of scope for this evaluation-only adapter bundle (would require additional learned reward machinery).
- **Graph-of-Thoughts-style merging**: out of scope (would require a graph-native adapter distinct from this repo’s branch API).

---

## Scope and honest framing

This report summarizes **matched-budget ToT-style BFS / beam / DFS adapter baselines** evaluated under the **same per-problem action budget** as the frontier allocation methods.

- **This is not an official Tree-of-Thoughts (ToT) reproduction** and must not be described as one.
- The adapters are **recognizable search-shaped baselines** (breadth-like round-robin multi-root expansion, fixed-width beam scheduling, depth-biased stack expansion) implemented on the repository’s branch generator contract.
- Results here are from the **local simulator** (`--api-backend simulator`) unless you rerun with a remote generator; treat them as **protocol and engineering validation**, not a claim about proprietary frontier models.

### Manuscript-safe wording (recommended)

- “We compare against matched-budget ToT-style BFS/beam/DFS adapters under the same action-budget ledger.”
- “The result supports comparison against a recognizable search-style baseline under matched-budget adapter conditions.”
- “This is not an official ToT reproduction.”

### Forbidden wording (do not use)

Avoid any claim that implies an **official ToT paper replication**, **blanket superiority over all search methods**, or **“problem solved / closed”** narratives about Tree-of-Thoughts-style reasoning. Keep comparisons explicitly **adapter-level** and **matched-budget**.

---

## Canonical run bundled in this repository

| Field | Value |
| --- | --- |
| Output directory | `outputs/tot_matched_budget_baseline_20260425T011500Z/` |
| Script | `scripts/run_tot_matched_budget_baseline.py` |
| Paper table builder | `scripts/paper/build_tot_matched_budget_baseline_table.py` |
| Paper CSV / TeX / plot data | `outputs/paper_tables/table_tot_matched_budget_baseline.csv`, `outputs/paper_tables/table_tot_matched_budget_baseline.tex`, `outputs/paper_plot_data/tot_matched_budget_baseline.csv` |

### Protocol (exactly what was executed)

- **Methods:** `strict_f3_anti_collapse_weak_v1`, `strict_f3`, `strict_gate1_cap_k6`, `tot_bfs_matched_budget`, `tot_beam_matched_budget`, `tot_dfs_matched_budget`, `self_consistency_3`, `self_consistency_5`, `external_l1_max`
- **Datasets loaded successfully:** `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- **Datasets attempted but skipped:** `TIGER-Lab/MMLU-Pro` (HF load raised `ValueError` in this environment; see `manifest.json` → `infeasible_datasets`)
- **Non-math datasets:** `google-deepmind/natural-plan` and `Idavidrein/gpqa` were **not** part of the CLI slice for the bundled timestamp above; the default script attempts them when listed in `--datasets` (clone / HF token requirements may apply).
- **Budgets:** `4`, `6`, `8`
- **Seeds:** `11`, `23`, `37`, `41`, `53`
- **Subset size:** `20` problems per dataset per seed (simulator; pooled **n_cases = 900** per method across 3 datasets × 5 seeds × 20 examples × 3 budgets)

---

## Headline numerical results (pooled over the bundled run)

From `main_summary.csv` (mean accuracy, mean actions):

| Method | Mean accuracy | Mean actions |
| --- | ---: | ---: |
| `strict_f3_anti_collapse_weak_v1` | **0.6578** | 5.37 |
| `strict_f3` | 0.6500 | 5.37 |
| `strict_gate1_cap_k6` | 0.6189 | 5.29 |
| `tot_beam_matched_budget` (**best ToT adapter**) | 0.6022 | 5.34 |
| `self_consistency_3` | 0.5789 | 5.91 |
| `tot_bfs_matched_budget` | 0.5722 | 3.90 |
| `self_consistency_5` | 0.5556 | 6.00 |
| `tot_dfs_matched_budget` | 0.5289 | 3.32 |
| `external_l1_max` | 0.4767 | 2.05 |

### Does `strict_f3_anti_collapse_weak_v1` beat the best ToT adapter overall?

**Yes on this bundled simulator slice (pooled across datasets, seeds, budgets, and examples).**  
Best ToT adapter by mean accuracy: **`tot_beam_matched_budget` at 0.6022** vs **`strict_f3_anti_collapse_weak_v1` at 0.6578** (gap **+0.0556**).

Paired tests (`pairwise_statistical_tests.csv`, **n_paired = 900**):

| Comparison | Mean difference (a − b) | 95% bootstrap CI (approx.) | Permutation p |
| --- | ---: | --- | ---: |
| `strict_f3_anti_collapse_weak_v1` vs `tot_beam_matched_budget` | +0.0556 | [0.0167, 0.0944] | 0.0070 |
| `strict_f3_anti_collapse_weak_v1` vs `tot_bfs_matched_budget` | +0.0856 | [0.0456, 0.1233] | 0.0005 |
| `strict_f3_anti_collapse_weak_v1` vs `tot_dfs_matched_budget` | +0.1289 | [0.0856, 0.1756] | 0.0005 |
| `strict_f3_anti_collapse_weak_v1` vs `strict_f3` | +0.0078 | [-0.0022, 0.0200] | 0.248 |

**Interpretation:** Under the bundled simulator protocol, the anti-collapse weak strict frontier variant is **decisively ahead of all three ToT-style adapters** at conventional paired-test thresholds, while the **small advantage over default `strict_f3`** is **not** significant at α = 0.05 (CI straddles zero).

---

## Per-dataset and per-budget behavior

See:

- `per_dataset_summary.csv` — accuracy pooled across budgets/seeds for each dataset × method.
- `per_dataset_budget_summary.csv` — finer slices: dataset × budget × method.
- `per_budget_summary.csv` — pooled across datasets for each budget × method.

---

## Pairwise tests required for the paper table

The runner emits at least:

- `strict_f3_anti_collapse_weak_v1` vs each ToT adapter (`tot_bfs_*`, `tot_beam_*`, `tot_dfs_*`)
- `strict_f3_anti_collapse_weak_v1` vs `self_consistency_5`, `self_consistency_3`, `external_l1_max`, `strict_f3`
- **Best ToT adapter** (`tot_beam_matched_budget` on this slice) vs `self_consistency_5` and `external_l1_max`

---

## Where should this go in the paper?

**Recommendation:** **Appendix primary placement** with a **short main-text sentence** pointing to matched-budget ToT-style adapters (not official ToT).

**Rationale:** The bundled artifact is **simulator-only**, uses a **moderate subset size**, and **does not** include every optional dataset (e.g. MMLU-Pro failed to load here). That is enough for a **transparent baseline comparison**, but not, on its own, a headline claim about proprietary models or blanket search superiority.

---

## Artifacts checklist

Under `outputs/tot_matched_budget_baseline_<timestamp>/`:

- `manifest.json`
- `per_case_outcomes.csv`
- `main_summary.csv`
- `per_dataset_summary.csv`
- `per_dataset_budget_summary.csv`
- `per_budget_summary.csv`
- `per_seed_summary.csv`
- `pairwise_statistical_tests.csv`
- `failure_decomposition.csv`
- `token_latency_accounting.csv`
- `summary.md`

---

## Re-running or scaling the protocol

```bash
python scripts/run_tot_matched_budget_baseline.py --timestamp "$(date -u +%Y%m%dT%H%M%SZ)"
python scripts/paper/build_tot_matched_budget_baseline_table.py
```

Use larger `--subset-size` (e.g. 120) for closer-to-manuscript statistical power; keep `--datasets` explicit so skipped datasets are always recorded in `manifest.json`.
