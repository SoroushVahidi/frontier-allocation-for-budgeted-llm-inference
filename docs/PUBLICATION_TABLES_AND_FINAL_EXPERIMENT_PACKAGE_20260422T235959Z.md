# Publication tables and final experiment package (20260422T235959Z)

## 1) Main-paper-ready tables

Main-paper table sources are now packaged under:
- `outputs/publication_tables_package/20260422T235959Z/`

Main-paper tables:
1. `table1_main_near_direct_ranking.csv` / `.md`
2. `table2_published_adjacent_baselines.csv` / `.md`
3. `table3_internal_ablation_why_strict_f3.csv` / `.md`
4. `table4_budget_robustness.csv` / `.md`
5. `table5_multi_run_stability.csv` / `.md`
6. `table6_failure_mechanism_summary.csv` / `.md`

## 2) Appendix-ready tables

1. `appendix_a_full_baseline_taxonomy.csv` / `.md`
2. `appendix_b_claim_safety_matrix.csv` / `.md`
3. `appendix_c_per_dataset_near_direct_results.csv` / `.md`
4. `appendix_d_extended_budget_robustness.csv` / `.md`
5. `appendix_e_extended_failure_slices.csv` / `.md`

Also included:
- `main_paper_dataset_plan.csv` / `.md`
- `appendix_dataset_plan.csv` / `.md`

## 3) Reused vs newly run experiments

### Reused evidence bundles
- Canonical in-house decision and identity lock (`strict_f3`).
- Canonical external baseline comparison and strongest fair external lock (`external_l1_max`).
- Paper-facing baseline packaging, fairness/claim-boundary audit, and simple-scaling coverage decision.
- Robustness bundles for budget, repeated-evaluation stability, and failure mechanisms.

### Newly run in this pass
- No new model-training or new-dataset experiments were run.
- Only table/packaging generation and artifact regeneration from canonical matched outputs were run.

## 4) Publication-critical empirical gap check

Decision: **No publication-critical empirical gap remains for the current claim-bounded paper package.**

Non-blocking gap still present:
- Current canonical reported results remain math-heavy (`gsm8k`, `MATH-500`, `aime_2024`).
- This is captured as a transparent expansion plan item (DROP first, then MuSR) in dataset-plan artifacts.

## 5) Exact manuscript-safe wording

Use the following safe wording:

1. "On the canonical matched near-direct surface, `strict_f3` outperforms the strongest fair external baseline (`external_l1_max`) by 0.161111 mean accuracy."
2. "Main-table ranking is restricted to `strict_f3` plus near-direct external adapter baselines (`external_s1_budget_forcing`, `external_tale_prompt_budgeting`, `external_l1_exact`, `external_l1_max`) under shared substrate conventions."
3. "Across matched budgets 4/6/8, `strict_f3` remains above `external_l1_max` at every budget."
4. "Repeated evaluation on available seeds indicates stable ranking order (`strict_f3` above `external_l1_max`), noting this is evaluation-seed stability rather than training-seed variation."
5. "Against `external_l1_max`, strict-loss analysis shows 56 losses for `strict_f3`, dominated by `absent_from_tree` with `present_not_selected` as secondary."

## 6) Caption / footnote guidance

- Main-table externals are inference-only adapters on a matched substrate; not full official post-training reproductions.
- Adjacent baselines are reported separately and not merged into near-direct leaderboard claims.
- Discussion-only methods are cited with blockers; they are not ranked as integrated empirical baselines.
- Any unofficial adapter rows (e.g., Q*-style) must remain caveated and never framed as official reproductions.

## 7) Package index files included

- `status.json`
- `summary.json`
- `summary.md`
- `manifest.json`
- `main_paper_tables_index.csv`
- `appendix_tables_index.csv`
- `table_generation_notes.md`
- `config_snapshot.json`
- `command_snapshot.txt`

All generated artifacts are text-only (`.py`, `.md`, `.json`, `.csv`, `.txt`) and no binary files were created.
