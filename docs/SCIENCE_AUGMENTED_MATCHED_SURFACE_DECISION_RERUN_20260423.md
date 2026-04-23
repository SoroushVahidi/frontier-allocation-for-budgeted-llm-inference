# Science-augmented matched-surface decision rerun (appendix-only stress test) — 2026-04-23

## Scope and intent

This run is a decision-stability stress test that augments the manuscript-style matched 4/6/8 surface with GPQA-Diamond, while keeping the rest of the contract as close as practical to the current manuscript-facing matched comparison family.

This **does not** overwrite canonical paper artifacts and **does not** silently replace the current manuscript-facing contract.

## 1) Inputs inspected before the rerun

- `docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
- `docs/MATCHED_SURFACE_MULTI_SEED_MAIN_COMPARISON_20260423T235900Z.md`
- `docs/SCIENCE_ANCHOR_ROBUSTNESS_GPQA_DIAMOND_BROADER_SEEDS_20260423.md`
- broader-seed GPQA science-anchor output family contract (re-used as reference design):
  - `outputs/science_anchor_robustness_20260423T_science_anchor_gpqa_diamond_broader_seeds/`

## 2) Exact science-augmented matched-surface contract used

Canonical reference surface:
- `canonical_full_method_ranking_20260421T212948Z`

Science-augmented rerun contract:
- Datasets:
  - `openai/gsm8k`
  - `HuggingFaceH4/MATH-500`
  - `HuggingFaceH4/aime_2024`
  - `Idavidrein/gpqa` (`gpqa_diamond`)
- Budgets: `4,6,8`
- Seeds: `11,23,37,41,53,67,79,97,101,131`
- Subset size: `20` per dataset-seed
- Substrate and simulation setup: matched-style simulated substrate with deterministic output-layer repair, aligned to the current matched-style runners.

Method set:
- Internal focus methods:
  - `strict_f3`
  - `strict_gate1_cap_k6`
  - `strict_f2`
- Fair near-direct external anchors (same substrate; no contract drift):
  - `external_s1_budget_forcing`
  - `external_tale_prompt_budgeting`
  - `external_l1_max`
  - `external_l1_exact`

Alignment notes:
- Same matched-style budget contract (4/6/8), subset-size convention (20), and practical strong multi-seed list (10 seeds) as current matched-family practice.
- Main intended difference is dataset augmentation with GPQA-Diamond.

## 3) Command and output family

Run command:

```bash
python scripts/run_science_augmented_matched_surface.py \
  --run-id 20260423T_science_augmented_matched_surface_gpqa_addition
```

Output family:
- `outputs/science_augmented_matched_surface_20260423T_science_augmented_matched_surface_gpqa_addition/`

Produced artifacts:
- `per_case_outcomes.csv`
- `comparison_table.csv`
- `per_dataset_summary.csv`
- `per_budget_summary.csv`
- `per_seed_summary.csv`
- `head_to_head_summary.csv`
- `method_ranking_summary.csv`
- `manifest.json`
- `conservative_interpretation_note.md`

## 4) Main artifact-backed results

Internal overall mean accuracies on this science-augmented matched surface:
1. `strict_f3`: `0.6300`
2. `strict_gate1_cap_k6`: `0.5963`
3. `strict_f2`: `0.5950`

Per-budget internal winner pattern:
- Budget 4: `strict_f3`
- Budget 6: `strict_f3`
- Budget 8: `strict_f2` (narrowly)

Per-dataset (averaged across 4/6/8) internal ordering:
- `openai/gsm8k`: `strict_f3` > `strict_gate1_cap_k6` > `strict_f2`
- `HuggingFaceH4/MATH-500`: `strict_f3` > `strict_f2` > `strict_gate1_cap_k6`
- `HuggingFaceH4/aime_2024`: `strict_f3` > `strict_f2` > `strict_gate1_cap_k6`
- `Idavidrein/gpqa`: `strict_f3` > `strict_f2` > `strict_gate1_cap_k6`

Compact mechanism signal (internal head-to-head):
- Pairwise deltas remain mostly explained by `absent_from_tree` and `present_not_selected` movement.
- `output_layer_mismatch` deltas remain small / non-dominant.

## 5) Direct decision answers

1. Does `strict_f3` remain the manuscript-facing best internal method once GPQA-Diamond is added to matched 4/6/8?
- **Yes, on this science-augmented rerun it remains best overall among internal methods.**

2. Does `strict_gate1_cap_k6` become stronger on the science-augmented matched surface?
- **Not as the overall winner.** It trails `strict_f3` overall here.

3. Does `strict_f2` emerge as the more credible broader internal candidate?
- **Still credible and competitive**, but not overall winner on this specific science-augmented matched rerun.

4. Does adding GPQA materially change the strength of the current manuscript-facing claim?
- **Not in this rerun.** The manuscript-facing claim is not weakened by this specific science-augmented matched 4/6/8 test; `strict_f3` stays on top.

5. Should manuscript positioning remain unchanged, or is there enough evidence to reconsider now?
- **Remain unchanged for now.** Keep two-surface distinction and keep science augmentation as stress-test evidence, not an automatic canonical promotion.

## 6) Conservative interpretation boundary

- This result improves confidence that `strict_f3` can remain manuscript-facing robust on a cleaner science-augmented matched 4/6/8 surface.
- It does **not** invalidate prior appendix evidence that `strict_f3` can weaken on broader/high-budget/science-only robustness slices.
- Therefore: keep current manuscript vs operational split unchanged unless additional independent reruns overturn this pattern.

## 7) Optional appendix-only plot-data refresh

Created appendix-only plot-data snapshots for this science-augmented matched surface:
- `outputs/paper_plot_data/appendix_science_augmented_matched_surface_comparison_table.csv`
- `outputs/paper_plot_data/appendix_science_augmented_matched_surface_per_budget_summary.csv`
- `outputs/paper_plot_data/appendix_science_augmented_matched_surface_per_dataset_summary.csv`

Canonical main-paper figure/table artifacts were not modified.
