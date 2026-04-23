# GPQA-Diamond science-anchor robustness repeat (broader seeds, appendix-only) — 2026-04-23

## 1) Existing science-anchor run inspection (before repeat)

Inspected sources:
- Prior robustness notes:
  - `docs/SCIENCE_ANCHOR_ROBUSTNESS_GPQA_2026_04_23.md`
  - `docs/SCIENCE_ANCHOR_ROBUSTNESS_GPQA_DIAMOND_20260423.md`
- Existing appendix plot-data snapshots:
  - `outputs/paper_plot_data/appendix_science_anchor_gpqa_per_budget_summary.csv`
  - `outputs/paper_plot_data/appendix_science_anchor_gpqa_per_method_summary.csv`

Established prior run contract:
- Dataset: `Idavidrein/gpqa` (`gpqa_diamond`).
- Methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`, plus already-supported near-direct externals (`external_s1_budget_forcing`, `external_tale_prompt_budgeting`, `external_l1_max`, `external_l1_exact`).
- Budgets: `4,6,8,10,12,14`.
- Seeds: `11,23` (small-seed slice).
- Subset-size / matched-style contract: subset-size `20`, same matched-style substrate runner.

Prior ranking/mechanism behavior (from existing note + appendix CSV snapshots):
- On that first GPQA-Diamond slice, manuscript-surface preference for `strict_f3` was weakened.
- `strict_gate1_cap_k6` beat `strict_f3` on the science-anchor slice.
- `strict_f2` was highly competitive / often stronger.
- Failure mix remained dominated by `absent_from_tree` + `present_not_selected`, with near-zero `output_layer_mismatch`.

Prior output family and manifest path (as documented in prior note):
- Output family: `outputs/science_anchor_robustness_20260423T_science_anchor_gpqa_diamond/`
- Manifest path: `outputs/science_anchor_robustness_20260423T_science_anchor_gpqa_diamond/manifest.json`

## 2) Broader-seed repeat (this run)

Command executed:

```bash
python scripts/run_science_anchor_robustness.py \
  --run-id 20260423T_science_anchor_gpqa_diamond_broader_seeds \
  --datasets Idavidrein/gpqa \
  --budgets 4,6,8,10,12,14 \
  --seeds 11,23,37,41,53,67,79,97 \
  --subset-size 20
```

Seed expansion used (explicit):
- Previous: `11,23`.
- Broader repeat: `11,23,37,41,53,67,79,97`.
- Net expansion: +6 seeds, 4x the original seed count.

New output family (separate; no overwrite):
- `outputs/science_anchor_robustness_20260423T_science_anchor_gpqa_diamond_broader_seeds/`

Artifacts produced:
- `per_case_outcomes.csv`
- `comparison_table.csv`
- `per_budget_summary.csv`
- `per_method_summary.csv`
- `per_seed_summary.csv`
- `per_dataset_summary.csv`
- `pairwise_mechanism_head_to_head.csv`
- `manifest.json`
- `conservative_interpretation_note.md`

## 3) Artifact-backed findings from broader seeds

Internal overall mean-accuracy ranking (`per_method_summary.csv`):
1. `strict_f2`: `0.6510`
2. `strict_gate1_cap_k6`: `0.6323`
3. `strict_f3`: `0.6271`

Matched manuscript-facing 4/6/8 aggregate (sum of per-budget means):
- `strict_f2`: `1.8125`
- `strict_f3`: `1.7688`
- `strict_gate1_cap_k6`: `1.7625`

High-budget 10/12/14 aggregate:
- `strict_f2`: `2.0938`
- `strict_gate1_cap_k6`: `2.0312`
- `strict_f3`: `1.9938`

Per-budget internal winners:
- Budget 4: `strict_f3`
- Budget 6: `strict_f2`
- Budget 8: `strict_gate1_cap_k6`
- Budget 10: `strict_f2`
- Budget 12: tie (`strict_f2`, `strict_gate1_cap_k6`)
- Budget 14: `strict_f3`

Mechanism stability:
- In pairwise head-to-head rows, `delta_output_layer_mismatch_rate` stays ~0 for most budgets and remains small overall.
- Accuracy deltas continue to co-move mainly with `absent_from_tree` and `present_not_selected` deltas.
- Overall mechanism narrative remains: tree-entry + selection dominate, not output-layer mismatch.

## 4) Direct answers to the research questions

1. Does GPQA-Diamond weakening of `strict_f3` persist under broader seeds?
- **Yes, it persists overall**. `strict_f3` is not the top internal method on the broader-seed GPQA run (overall and in 4/6/8 aggregate).

2. Does `strict_gate1_cap_k6` become the stable science-anchor winner?
- **No (not as a stable overall winner).** It is stronger than `strict_f3` on the 10/12/14 aggregate and at some budgets (notably 8), but `strict_f2` remains the strongest overall internal method.

3. Does `strict_f2` remain genuinely competitive on the science anchor?
- **Yes.** It remains highly competitive and is the strongest internal method on overall mean accuracy and both 4/6/8 and 10/12/14 aggregate sums.

4. Do the same mechanisms still dominate (`absent_from_tree` + `present_not_selected`)?
- **Yes.** The broader-seed repeat keeps the same dominant mechanism profile; `output_layer_mismatch` remains near-zero / non-dominant.

5. Should this force a manuscript framing rethink now?
- **Not yet.** Keep this as appendix/robustness evidence and preserve the two-surface distinction:
  - manuscript-facing matched internal winner: `strict_f3`
  - broader operational default: `strict_gate1_cap_k6`

## 5) Positioning and claim discipline

- This is a stronger GPQA robustness check than the first small-seed pass and increases confidence that the initial weakening signal for `strict_f3` is real on this science anchor.
- Still, it is one science-anchor family; do not silently override canonical manuscript 4/6/8 positioning from this alone.
- Treat this as appendix stress-test evidence with clearer stability than before, but still bounded in scope.

## 6) Appendix-only refresh

Refreshed natural appendix plot-data path (science-anchor only):
- `outputs/paper_plot_data/appendix_science_anchor_gpqa_per_budget_summary.csv`
- `outputs/paper_plot_data/appendix_science_anchor_gpqa_per_method_summary.csv`

Canonical main-paper figure/table artifacts were not modified.
