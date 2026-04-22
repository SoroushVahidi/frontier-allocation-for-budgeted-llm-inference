# Integrated Controller Component Ablation Report (2026-04-22)

## Canonical protocol used

- Surface: the same strict-phased broader matched default-decision surface used in `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`.
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`, `olympiadbench`.
- Seeds: `11`, `23`.
- Budgets: `6`, `8`.
- Subset size: `20` per `(dataset, seed)` slice.

This run is stored under:
- `outputs/integrated_controller_component_ablation_20260422T170256Z/`

## Exact variants evaluated

- `full_integrated`
- `no_answer_support`
- `no_anti_collapse`
- `no_repeat_expansion_control`
- `no_output_repair`
- `allocation_only_core`
- `best_reduced_variant` (chosen post-hoc from reduced variants by accuracy then failure tie-breaks)

Operational notes:
- `no_output_repair` disables the bounded rescue mode in `choose_repair_answer(..., enable_rescue=False)`.
- `no_answer_support` uses a value-only final scoring blend (`answer_support_weight=0.0`, `value_weight=1.0`).
- `no_anti_collapse` disables anti-collapse refinement and low-marginal-gain cooldown.
- `no_repeat_expansion_control` keeps anti-collapse enabled but zeros repeat-expansion penalties and disables low-marginal-gain cooldown.

## Main findings (aggregate)

From `aggregate_summary.csv`:

- `full_integrated`: accuracy `0.6281`
- `no_answer_support`: accuracy `0.5844` (largest degradation; introduces output-layer mismatches)
- `no_anti_collapse`: accuracy `0.5906`
- `no_repeat_expansion_control`: accuracy `0.6312` (best reduced variant in this run)
- `no_output_repair`: accuracy `0.6281` (no aggregate delta vs full integrated on this surface run)
- `allocation_only_core`: accuracy `0.6125`

## Which components appear to matter most here

- **Answer-support aggregation** shows the strongest negative impact when removed (`0.6281 -> 0.5844`) and increased output-layer mismatch count (`13`).
- **Anti-collapse refinement** also appears important for aggregate accuracy (`0.6281 -> 0.5906`) and absent-from-tree failures (`86 -> 100`).
- **Repeat-expansion moderation** did not improve this run when enabled; the ablated variant slightly outperformed full integrated (`0.6312` vs `0.6281`) with fewer present-not-selected failures.
- **Bounded output-layer repair** produced no measured delta on this run’s aggregate metrics.

## Failure and compute-pattern interpretation

- Primary failure movement across variants is in:
  - `absent_from_tree`
  - `present_not_selected`
  - and, for `no_answer_support`, `output_layer_mismatch`.
- Realized compute allocation patterns changed with toggles:
  - `avg_actions`, `avg_expansions`, and `avg_verifications` shift across variants.
  - `repeated_same_family_present` counts also shift, but should be interpreted cautiously as simulation-surface proxies.
- Anti-collapse diagnostics tied to low-marginal-gain triggering are captured in:
  - `outputs/integrated_controller_component_ablation_20260422T170256Z/anti_collapse_diagnostics.csv`

## Manuscript-claim implication

Current evidence supports a nuanced update:
- The integrated story is **partly supported** (answer-support and anti-collapse matter materially),
- but the current implementation does **not** support a blanket claim that every integrated component is strictly beneficial on the canonical surface.

Recommended wording discipline:
- keep claims component-specific,
- avoid overclaiming repeat-expansion moderation and output-layer repair as universally beneficial without broader confirmation runs.

## Paper-facing artifacts created

- Table: `outputs/paper_tables/table7_component_ablation.csv`
- Table TeX: `outputs/paper_tables/table7_component_ablation.tex`
- Figure: `outputs/paper_figures/figure8_component_ablation.{pdf,png}`

These were generated because the ablation produced meaningful variant spread on canonical-surface accuracy.
