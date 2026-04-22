# Robustness pass: budget, stability, and failure mechanisms (20260422T045249Z)

## Scope and identity lock
- Our method remains **`strict_f3`**.
- Strongest fair external baseline remains **`external_l1_max`**.
- This pass adds robustness artifacts only; it does not change method identity or baseline taxonomy.

## Inputs and availability notes
- Canonical substrate used: `outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv`.
- Requested source-of-truth folders `outputs/full_our_method_vs_external_baselines_comparison/20260422T230000Z/` and `outputs/our_method_vs_strongest_external_loss_analysis/20260422T230000Z/` were not present in this checkout, so strongest-baseline lock is taken from already-approved docs and fairness package text.
- Dataset coverage available on this canonical substrate is exactly: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`.
- A science anchor such as `gpqa_diamond` is not present in this canonical substrate and is therefore explicitly out-of-scope for this pass.

## Methods, datasets, budgets, seeds used
- Methods compared (budget robustness): `strict_f3`, `external_l1_max`, `external_s1_budget_forcing`.
- Methods compared (stability + failure mechanism): `strict_f3`, `external_l1_max`.
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`.
- Budget points: **4, 6, 8** (matched grid).
- Seeds available on this substrate: **11, 23**.
- Stability interpretation: repeated **evaluation-seed** stability, not training-seed variation.

## 1) Budget sweep / cost-quality robustness
Artifacts: `outputs/budget_sweep_robustness/20260422T045249Z/`.

Head-to-head (`strict_f3` minus `external_l1_max`):
- Budget 4: +0.175000
- Budget 6: +0.133333
- Budget 8: +0.175000
- Mean delta across budgets: +0.161111

Result: **`strict_f3` remains ahead at all tested budgets (4/6/8).**

Main-paper-ready budget table source:
- `budget_curve_table.csv`
- `head_to_head_budget_table.csv`

Appendix detail source:
- `budget_curve_by_dataset.csv`

## 2) Multi-run / multi-seed stability
Artifacts: `outputs/multi_seed_stability/20260422T045249Z/`.

Aggregate stability:
- `strict_f3`: mean 0.658333, std 0.035355, range [0.633333, 0.683333], seeds=2
- `external_l1_max`: mean 0.497222, std 0.058926, range [0.455556, 0.538889], seeds=2

Per-dataset trend: `strict_f3` mean exceeds `external_l1_max` on all three included datasets.

Result: **Ordering is stable under available repeated evaluation runs; `strict_f3` remains first.**

Important honesty note:
- This substrate exposes 2 seeds (11, 23), so this is a **limited repeated-evaluation stability check**, not a full 3-5 seed training-variation study.

Main-paper-ready stability table source:
- `seed_stability_table.csv`

Appendix detail source:
- `seed_stability_by_dataset.csv`

## 3) Failure-mechanism robustness across budgets
Artifacts: `outputs/failure_mechanism_robustness/20260422T045249Z/`.

Comparison definition:
- Strict loss set = cases where `strict_f3` is wrong and `external_l1_max` is correct.

Core findings:
- Loss count: **56**
- Overall dominant mechanism: **`absent_from_tree`**
- Overall rates:
  - `absent_from_tree`: 0.857143
  - `present_not_selected`: 0.142857
- By-budget dominant mechanism:
  - Budget 4: absent_from_tree
  - Budget 6: absent_from_tree
  - Budget 8: absent_from_tree

Result: **The mechanism story is robust across tested budgets; absent_from_tree stays dominant, with present_not_selected secondary.**

Main-paper-ready failure table source:
- `failure_mechanism_by_budget.csv`

Appendix detail sources:
- `failure_mechanism_by_dataset.csv`
- `feature_summary.json`

## Manuscript-safe claim wording
Use the following text (claim-bounded):

1. **Budget robustness claim**
   - "Across matched budgets 4/6/8 on the canonical near-direct substrate, `strict_f3` remains above `external_l1_max` at every budget (mean delta +0.161111)."

2. **Stability claim**
   - "Under repeated evaluation on available seeds (11, 23), ranking order is stable: `strict_f3` has higher mean accuracy than `external_l1_max`; this is evaluation-seed stability, not training-seed variation."

3. **Failure mechanism claim**
   - "In the strict-loss slice versus `external_l1_max` (n=56), `absent_from_tree` remains the dominant failure mechanism across all tested budgets, with `present_not_selected` as the secondary mechanism."

4. **Boundary caveat**
   - "This robustness pass is limited to datasets currently present in the canonical surface (`gsm8k`, `MATH-500`, `aime_2024`); a gpqa_diamond science-anchor robustness readout remains future work once that dataset is integrated on the same matched substrate."

## Main paper vs appendix recommendation
Main paper:
- One budget robustness table from `head_to_head_budget_table.csv`.
- One stability table from `seed_stability_table.csv`.
- One failure-mechanism table from `failure_mechanism_by_budget.csv`.

Appendix:
- Per-dataset budget curves (`budget_curve_by_dataset.csv`).
- Per-dataset stability (`seed_stability_by_dataset.csv`).
- Failure mechanism breakdown by dataset and additional feature summary (`failure_mechanism_by_dataset.csv`, `feature_summary.json`).

## Output bundle index
- `outputs/budget_sweep_robustness/20260422T045249Z/`
- `outputs/multi_seed_stability/20260422T045249Z/`
- `outputs/failure_mechanism_robustness/20260422T045249Z/`

All artifacts in this pass are text-only (`.json`, `.md`, `.csv`, `.txt`).
