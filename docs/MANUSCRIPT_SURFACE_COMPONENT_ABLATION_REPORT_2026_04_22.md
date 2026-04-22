# Manuscript-Surface Component Ablation Report (2026-04-22)

## Pre-check for duplication

A repository-wide check was performed before implementation across docs, scripts, and outputs.

- Existing canonical/exploratory ablation found: `outputs/integrated_controller_component_ablation_20260422T170256Z/`.
- That run is **not** equivalent to this request because it targets the strict-phased promoted default family (`strict_gate1_cap_k6` line), not the manuscript-facing fairness-locked method surface (`strict_f3` on canonical matched near-direct surface).
- No existing artifact matching all required conditions (strict_f3 lock + manuscript-facing canonical matched surface + requested component toggles) was found.

## Canonical manuscript-facing surface used

- Method lock: `strict_f3` (per manuscript-facing package/fairness docs).
- Surface: `outputs/canonical_full_method_ranking_20260421T212948Z/`.
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`.
- Seeds: `11`, `23`.
- Budgets: `4`, `6`, `8`.
- Subset size: `20` per `(dataset, seed)`.

## Code-path mapping for claimed components

- **Answer-support aggregation**
  - `experiments/controllers.py`: `_group_support_summary`, `_final_prediction_from_groups`
  - weights toggled via `answer_support_weight`, `value_weight`
- **Anti-collapse**
  - `experiments/controllers.py`: `_anti_collapse_priority_adjustments`
  - toggled via `enable_anti_collapse_answer_group_refinement`
- **Repeat-expansion moderation**
  - `experiments/controllers.py`: repeat penalties and low-marginal controls (`repeat_expand_*`, `enable_low_marginal_gain_family_cooldown`)
- **Bounded output-layer repair**
  - `experiments/output_layer_repair.py`: `choose_repair_answer(..., enable_rescue=...)`

## Variants evaluated

- `full_method`
- `no_answer_support_aggregation`
- `no_anti_collapse`
- `no_repeat_expansion_control`
- `no_output_repair`
- `upstream_only_core`
- `strongest_reduced_variant` (post-hoc selection from reduced variants)

## Main findings (from run `20260422T172218Z`)

- Full method accuracy: `0.6250`.
- `no_answer_support_aggregation`: `0.6222`.
- `no_anti_collapse`: `0.6694`.
- `no_repeat_expansion_control`: `0.5833`.
- `no_output_repair`: `0.6222`.
- `upstream_only_core`: `0.6694`.
- Strongest reduced variant: `no_anti_collapse` (tie-broken with lower `avg_actions`).

## Explicit required answers

1. **Which component contributes most to final accuracy?**  
   Removing repeat-expansion moderation causes the largest drop (`0.6250 -> 0.5833`), so repeat-expansion control appears most accuracy-critical on this surface.

2. **Which component most reduces `absent_from_tree` failures?**  
   Removing repeat-expansion moderation increases `absent_from_tree` most (`97 -> 123`), indicating this component contributes most to reducing `absent_from_tree`.

3. **Is output repair only a secondary effect on this canonical surface?**  
   Yes. `full_method` vs `no_output_repair` changes are small (`0.6250 -> 0.6222`) and mainly shift a small mismatch slice.

4. **Are current manuscript method claims empirically supported?**  
   Partially. Component behavior is not uniformly monotonic; some removals improved this bounded surface (`no_anti_collapse`, `upstream_only_core`), so claims should remain conservative and component-specific.

## Artifacts

- Output family:
  - `outputs/manuscript_surface_component_ablation_20260422T172218Z/`
- Key files:
  - `aggregate_summary.csv`
  - `aggregate_summary.json`
  - `per_dataset_summary.csv`
  - `per_seed_summary.csv`
  - `failure_decomposition.csv`
  - `compute_allocation_diagnostics.csv`
  - `per_case_results.csv`
  - `manifest.json`
  - `status.json`
- Run report:
  - `docs/MANUSCRIPT_SURFACE_COMPONENT_ABLATION_20260422T172218Z.md`
