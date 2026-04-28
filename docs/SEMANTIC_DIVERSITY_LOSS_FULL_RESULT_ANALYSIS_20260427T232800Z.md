# Semantic diversity loss-full result analysis (20260427T232800Z)

## Job / data inputs

- Run directory: `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z`
- Rows in `per_case_results.csv` (non-error): **162**
- Manifest `n_selected_cases`: **9**

## A. Did new ideas improve results?

- Aggregate: best method **`direct_reserve_semantic_frontier_v1`** at accuracy **0.7407** vs strict_f3 **0.3333** vs external_l1_max **0.6667**.
- Interpretation: **mixed / diagnostic only** unless paired deltas are consistent.

### Method accuracy summary

| method | n | accuracy | avg_actions | avg_est_cost_proxy | avg_latency |
|---|---|---|---|---|---|
| branching_necessity_gate_v1 | 27 | 0.4074 | 3.11 | 0.000299 | nan |
| direct_reserve_semantic_frontier_v1 | 27 | 0.7407 | 4.56 | 0.000437 | nan |
| external_l1_max | 27 | 0.6667 | 1.00 | 0.000096 | nan |
| semantic_minimum_maturation_frontier_v1_d3 | 27 | 0.3333 | 2.85 | 0.000274 | nan |
| semantic_minimum_maturation_plus_direct_reserve_v1 | 27 | 0.5556 | 4.67 | 0.000448 | nan |
| strict_f3 | 27 | 0.3333 | 3.26 | 0.000313 | nan |

### Paired deltas

- strict_f3 vs external_l1_max: **n=27**, mean(delta strict - external)= **-0.3333**, wins/losses/ties={'win': 1, 'loss': 10, 'tie': 16}

- `direct_reserve_semantic_frontier_v1` vs strict_f3: n=27, mean_delta=0.4074, wins=13 losses=2 ties=12
  - vs external_l1_max: n=27, mean_delta=0.0741, wins=5 losses=3 ties=19
  - budgets with positive mean delta vs strict_f3: **3 / 3**
- `semantic_minimum_maturation_plus_direct_reserve_v1` vs strict_f3: n=27, mean_delta=0.2222, wins=10 losses=4 ties=13
  - vs external_l1_max: n=27, mean_delta=-0.1111, wins=3 losses=6 ties=18
  - budgets with positive mean delta vs strict_f3: **3 / 3**
- `semantic_minimum_maturation_frontier_v1_d3` vs strict_f3: n=27, mean_delta=0.0000, wins=5 losses=5 ties=17
  - vs external_l1_max: n=27, mean_delta=-0.3333, wins=2 losses=11 ties=14
  - budgets with positive mean delta vs strict_f3: **1 / 3**
- `branching_necessity_gate_v1` vs strict_f3: n=27, mean_delta=0.0741, wins=6 losses=4 ties=17
  - vs external_l1_max: n=27, mean_delta=-0.2593, wins=3 losses=10 ties=14
  - budgets with positive mean delta vs strict_f3: **2 / 3**

### strict_f3 vs external_l1_max by budget
- budget 6: n=9, mean(strict-external)=-0.3333
- budget 8: n=9, mean(strict-external)=-0.5556
- budget 4: n=9, mean(strict-external)=-0.1111

## Job completion (Slurm)

- **`sacct`**: `COMPLETED`, `ExitCode 0:0`, elapsed **~13:17**, max RSS batch step **~123 MB**.
- **Readiness**: stdout shows `smoke_test: success model=command-r-plus-08-2024` (API key presence printed only as `present`).
- **Issue artifacts**: **no** `cohere_api_key_issue.md` or `run_failure_issue.md` observed for this completed run.

## Scope caveat

- Manifest **`n_selected_cases`: 9** (not 30): the loss JSONL + filters (`strict_f3` rows with nonempty question/gold and loss-full prioritization) only yielded nine distinct `example_id`s for this rerun.
- **Generalization is limited** — treat headline accuracies as **cohort diagnostics**, not population estimates.

---

## B. Which idea helped most?

- **Direct reserve (`direct_reserve_semantic_frontier_v1`)** clearly helped **vs `strict_f3`** on this cohort:
  - Aggregate accuracy **0.741** vs strict **0.333** (difference **+0.407** on paired rows).
  - Positive mean paired delta vs `strict_f3` on **all three budgets** (4 / 6 / 8).
  - Mean paired delta vs **`external_l1_max`**: **+0.074** (narrow lead on paired rows).
- **`semantic_minimum_maturation_plus_direct_reserve_v1`** sits **between** strict and direct reserve (**0.556** accuracy), beating strict consistently (**+0.222** mean paired delta) but **losing** to external on average (**−0.111** mean paired delta vs external).
- **`semantic_minimum_maturation_frontier_v1_d3` (alone)** **does not** beat strict on aggregate (ties at **0.333**); paired delta vs strict is **0** on average — **no standalone maturation lift** here.
- **`branching_necessity_gate_v1`**: small lift vs strict (**+0.074** mean paired delta); still well below direct reserve.

## C. What did not help (or underperformed)?

- **Semantic minimum maturation without direct reserve (`…_d3`)**: **no aggregate gain** vs `strict_f3`; still far from external on paired comparisons.
- **Branching necessity gate**: modest; accuracy **0.407** — better than strict but not competitive with direct reserve or external on this run.
- **One paired regression case** appeared in the rescue table (`strict_f3_regression` count **1**) — new methods are not uniformly safe vs strict.

## D. Absent-from-tree / “rescue” interpretation

- **`absent_from_tree_rescue_audit.csv`**: **0** rows with `absent_from_tree_rescue==1` — the diagnostic definition of “rescued from confirmed absent” did **not** fire as **gold re-entering tree + correct** in one step.
- Row-level **`absent_from_tree_meta`**: direct-reserve variants sometimes still flag absence (**e.g. 3 rows for DR, 5 for semantic+DR** from per-case aggregates in the automated table) — interpret as **telemetry**, not a clean “fixed tree coverage” proof.
- **`rescue_case_table.csv` (pair-level)** counts:
  - **`direct_reserve_rescue`** / **`both_rescue`** / **`semantic_plus_direct_reserve_rescue`** show cases where a new method fixes strict’s miss **without** requiring external to stay the only solver — consistent with **direct answer path / reserve-style behavior** helping more than deep tree repair alone.
  - **`external_only_still_unsolved`**: **1** — at least one hard case remains where externals/help methods still fail together (check table for detail).

## E. Semantic family diversity vs accuracy

- Experimental controllers that emit **`diagnostic_semantic_diversity`** report **semantic_family_count ~2.1–2.3** on average for **`…_d3`**, **`branching_necessity_gate_v1`**, and **`semantic_minimum_maturation_plus_direct_reserve_v1`**.
- **`strict_f3`** / **`external_l1_max`** rows often leave semantic-family fields **empty** in `per_case_results.csv` — **do not** compare raw family counts across those methods without acknowledging **telemetry asymmetry**.
- Where families are logged, **higher family count does not guarantee** higher `is_correct` on this small cohort (several taxonomy rows remain **unknown / seeding-related**).

## F. Bottlenecks (failure_taxonomy + audits)

- Dominant automated categories: **`unknown_unclassified`** (81), **`bad_seeding_absent_answer_group`** (40), plus smaller buckets for **underweighted correct groups** and **not_applicable_or_correct**.
- **Incumbent replacement audit**: **0** incumbent replacements recorded for direct-reserve variants — gains are **not** explained by challenger replacement churn in this run (rules may be inactive or flags not triggered).
- **Cost / actions**: `external_l1_max` uses **~1 action** on average vs **~4.5–4.7** for direct-reserve-style methods — **large action/token proxy penalty** for internal search vs L1 external baseline.

### Token / cost tradeoff (proxy)

- Estimated **cost proxy** (from `token_cost_latency_summary.csv`): external **lowest** (~`9.6e-5` per-row style magnitude on sample rows); direct reserve / combined ~**4×** that proxy vs external on typical rows — **accuracy gains trade for compute**.
- **Accuracy per action (aggregate, diagnostic)**:
  - `external_l1_max`: ~**0.667** / **1.0** ≈ **0.67** correct per action (trivial baseline action count).
  - `direct_reserve_semantic_frontier_v1`: ~**0.741** / **4.56** ≈ **0.16** correct per action.
  - `strict_f3`: ~**0.333** / **3.26** ≈ **0.10**.
- **Pareto sketch**: external remains **cheap**; direct reserve **Pareto-improves accuracy vs strict_f3** but **not vs external on cost** — it buys accuracy with **more actions/tokens**.

## G. Next algorithmic change (single recommendation)

**Prioritize `direct_reserve_semantic_frontier_v2` tuning plus commit-time verification**, *not* “more maturation alone”:

- Evidence shows **direct reserve** moves accuracy toward / past external on this cohort, while **maturation-only** does not.
- Next step is to **preserve DR’s wins** while **cutting unnecessary expansions** and adding **commit/rerank discipline** — consistent with high action counts and **zero incumbent replacement** events.

(If engineering effort must pick one alternative: **better semantic setup seeding** to attack `bad_seeding_absent_answer_group`.)

## H. Larger experiment?

- **Recommendation:** **yes — same cohort style, but only top 2–3 methods** (`external_l1_max`, `strict_f3`, `direct_reserve_semantic_frontier_v1`, optionally `semantic_minimum_maturation_plus_direct_reserve_v1`), **expand case sourcing** so `n_selected_cases` can approach **30** unique IDs if the pool allows — **explicit approval** still required before >30.

See **`docs/NEXT_SEMANTIC_DIVERSITY_EXPERIMENT_PLAN.md`** for concrete sbatch-style planning and stopping criteria.

---

### Rescue types (automated counts)

- **both_rescue**: 8
- **direct_reserve_rescue**: 5
- **all_correct**: 5
- **other**: 3
- **all_wrong**: 2
- **semantic_plus_direct_reserve_rescue**: 2
- **external_only_still_unsolved**: 1
- **strict_f3_regression**: 1

### Semantic diversity proxies (row-based means)

| Method | Avg semantic_family_count | Notes |
|--------|---------------------------|--------|
| Maturation / gate variants | ~2.1–2.3 where populated | Telemetry present |
| strict_f3 / external_l1_max | Often blank in CSV | Compare only with caution |

### Failure taxonomy (aggregate row counts)

- unknown_unclassified: 81  
- bad_seeding_absent_answer_group: 40  
- not_applicable_or_correct: 29  
- correct_answer_group_present_but_underweighted: 12  

### Incumbent replacement (audit snapshot)

- `direct_reserve_semantic_frontier_v1`: **27** rows, **0** with incumbent replaced flagged.  
- `semantic_minimum_maturation_plus_direct_reserve_v1`: **27** rows, **0** with incumbent replaced flagged.

## I. Manuscript

- **Default:** **no manuscript change.** This is a **small, biased loss cohort** (9 examples × 3 budgets × 6 methods).
- **At most**, a cautious appendix sentence could mention **directional improvement of direct reserve vs strict_f3 on absent-from-tree–biased diagnostics** — only after **replication on a larger, independently selected cohort**.

### Generated artifacts

- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/rescue_case_table.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/final_decision_summary.csv`
- Snapshot for git: `docs/semantic_diversity_loss_full_final_decision_snapshot_20260427T232800Z.csv`

### Analyzer script

- Re-run offline: `python scripts/analyze_semantic_diversity_diagnostic_run.py --timestamp 20260427T232800Z`
