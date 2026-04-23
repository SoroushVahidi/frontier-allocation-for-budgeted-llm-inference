# Extended budget robustness contract and results (2026-04-23)

## 1) Pre-change budget contract (recorded before extension)

Canonical manuscript-facing and paper artifact contract before this change:

- Main paper frontier and table package is built from `outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/20260422T175142Z/` and `outputs/component_ablation_strict_f3_paper_surface/20260422T180445Z/` via `scripts/paper/run_all_neurips_paper_artifacts.py`.
- The current main/frontier budget scope in this paper-facing path is budgets **4, 6, 8**.
- The manuscript-facing internal winner contract is `strict_f3` on the matched manuscript-facing internal surface.
- The broader operational default on its own broader strict-phased surface remains `strict_gate1_cap_k6`.
- Canonical manuscript method decision surface note (`docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`) is explicitly based on matched budgets **6 and 8** for the final internal winner decision package.

Current compared methods on the paper-facing matched bundle include:

- in-house: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`
- near-direct external anchors: `external_l1_max`, `external_l1_exact`, `external_tale_prompt_budgeting`, `external_s1_budget_forcing`

Canonical artifacts that must not be silently overwritten include:

- `outputs/paper_plot_data/figure2_main_frontier.csv`
- `outputs/paper_figures/figure2_main_frontier.{pdf,png}`
- `outputs/paper_tables/table2_main_frontier.{csv,tex}`
- and all other outputs produced by `scripts/paper/run_all_neurips_paper_artifacts.py` under `outputs/paper_plot_data/`, `outputs/paper_figures/`, and `outputs/paper_tables/`.

## 2) New extended-budget robustness surface

New extension run (appendix/robustness-only; does not replace canonical 4/6/8 paper artifacts):

- Run command:
  - `python scripts/run_extended_budget_frontier_robustness.py --run-id 20260423Textended101214`
- Output directory:
  - `outputs/extended_budget_frontier_20260423Textended101214/`
- Extended budgets:
  - `10, 12, 14`
- Matched evaluation contract retained:
  - datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
  - seeds: `11, 23`
  - subset size: `20`
- Methods evaluated:
  - `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`, `external_l1_max`, `external_l1_exact`, `external_tale_prompt_budgeting`, `external_s1_budget_forcing`

Produced machine-readable outputs:

- `per_case_outcomes.csv`
- `comparison_table.csv`
- `per_budget_summary.csv`
- `per_dataset_summary.csv`
- `per_seed_summary.csv`
- `budget_performance_frontier.csv`
- `method_ranking_by_budget.csv`
- `head_to_head_summary.csv`
- `method_budget_trends.csv`
- `manifest.json`
- `stability_note.md`

## 3) Conservative interpretation for manuscript decision stability

### Extended-budget leaderboard snapshot (mean accuracy)

- Budget 10: `strict_gate1_cap_k6` 0.7250, `strict_f2` 0.7000, `strict_f3` 0.6750.
- Budget 12: `strict_f3` 0.6833, `strict_f2` 0.6167, `strict_gate1_cap_k6` 0.6167.
- Budget 14: `strict_f2` 0.7000, `strict_gate1_cap_k6` 0.7000, `strict_f3` 0.6667.

Head-to-head deltas (`strict_f3 - strict_gate1_cap_k6`):

- Budget 10: `-0.0500`
- Budget 12: `+0.0667`
- Budget 14: `-0.0333`


Direct answers requested:

1. **Do budgets 10/12/14 preserve the existing manuscript story?**
   - Mixed evidence. The result is **not uniformly stable** in favor of `strict_f3` at higher budgets; leadership alternates by budget slice.

2. **Does `strict_f3` remain manuscript-facing best internal method when budgets are extended?**
   - Not consistently on this extension slice. `strict_f3` leads at budget 12, but not at 10 or 14.

3. **Does `strict_gate1_cap_k6` strengthen or weaken as budget grows?**
   - Non-monotonic. It is strongest at budget 10, drops at 12, and partially recovers at 14.

4. **Do methods plateau, saturate, or revert?**
   - Internal methods show non-monotonic behavior between 10/12/14. This is consistent with saturation/reversion risk at higher budgets under this bounded simulator-backed contract.

5. **Should higher budgets remain appendix-only, or force a main-story revision now?**
   - Conservative recommendation: keep higher budgets as **appendix/robustness-only** for now. The extension adds useful stress-test evidence but does not provide a clean, single-direction winner replacement signal.

## 4) Appendix support path (optional)

Added optional appendix plot-data packager (not wired into canonical paper runner by default):

- Script:
  - `scripts/paper/build_appendix_extended_budget_frontier_plot_data.py`
- Example command:
  - `python scripts/paper/build_appendix_extended_budget_frontier_plot_data.py --extended-bundle-dir outputs/extended_budget_frontier_20260423Textended101214`
- Generated appendix plot-data files:
  - `outputs/paper_plot_data/appendix_extended_budget_frontier.csv`
  - `outputs/paper_plot_data/appendix_extended_budget_method_ranking.csv`
  - `outputs/paper_plot_data/appendix_extended_budget_head_to_head.csv`

This preserves canonical main-paper artifacts while enabling appendix-level rendering and table integration for the extended-budget robustness surface.
