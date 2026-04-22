# Component Ablation Strict-F3 Paper Surface (20260422T180445Z)

## Scope and non-duplication
This report performs a packaging-only consolidation of an existing strict_f3 manuscript-surface component ablation.
No evaluation was rerun and no outcomes were altered.

## Source-of-truth artifacts
- `docs/MANUSCRIPT_SURFACE_COMPONENT_ABLATION_REPORT_2026_04_22.md`
- `docs/MANUSCRIPT_SURFACE_COMPONENT_ABLATION_20260422T172218Z.md`
- `outputs/manuscript_surface_component_ablation_20260422T172218Z`

## Exact manuscript surface used
- Canonical matched surface: `outputs/canonical_full_method_ranking_20260421T212948Z`
- Method lock: `strict_f3`
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- Seeds: `11`, `23`
- Budgets: `4`, `6`, `8`
- Subset size: `20` per `(dataset, seed)`

## Exact ablation variants
- `full_method`
- `no_answer_support_aggregation`
- `no_anti_collapse`
- `no_repeat_expansion_control`
- `no_output_repair`
- `upstream_only_core`
- `strongest_reduced_variant` = `no_anti_collapse`

## Mapping from manuscript components to implementation
- Answer-support aggregation:
  - `experiments/controllers.py`: `_group_support_summary`, `_final_prediction_from_groups`
  - Toggles: `answer_support_weight`, `value_weight`
- Anti-collapse control:
  - `experiments/controllers.py`: `_anti_collapse_priority_adjustments`
  - Toggle: `enable_anti_collapse_answer_group_refinement`
- Repeated same-family expansion moderation:
  - `experiments/controllers.py`: repeat penalties and cooldown controls
  - Toggles include `repeat_expand_penalty_weight`, `repeat_expand_family_penalty_weight`, `repeated_same_branch_penalty`, `enable_low_marginal_gain_family_cooldown`
- Bounded deterministic output-layer repair:
  - `experiments/output_layer_repair.py`: `choose_repair_answer(..., enable_rescue=...)`

## Main findings from existing results
- Full strict_f3 accuracy: `0.6250`
- No repeat-expansion control accuracy: `0.5833` (largest drop)
- No output repair accuracy: `0.6222` (small change vs full)
- No anti-collapse accuracy: `0.6694` (improves on this bounded surface)

Failure decomposition signals:
- `absent_from_tree` is worst for `no_repeat_expansion_control` (`123` vs `97` for full).
- `present_not_selected` differences are smaller and mixed across variants.
- `output_layer_mismatch` remains a narrower slice.

## Which component matters most
Within this strict_f3 manuscript surface, repeated same-family expansion moderation has the strongest marginal contribution: removing it causes the largest accuracy drop and largest `absent_from_tree` increase.

## Is output repair secondary?
Yes on this bounded surface. Disabling output repair causes only a small aggregate accuracy change (`0.6250` to `0.6222`), consistent with a secondary/residual role.

## Manuscript narrative status
Partially supported. The upstream-allocation narrative is supported by the sensitivity to repeat-expansion moderation and `absent_from_tree`, but not every component removal is uniformly harmful (`no_anti_collapse` improves aggregate accuracy here). Claims should remain conservative and component-specific.

## Safe wording for manuscript
- Safe: "On the matched strict_f3 manuscript surface, repeat-expansion moderation is the most critical ablated component for preserving accuracy and reducing absent-from-tree failures."
- Safe: "Output-layer repair has a secondary effect relative to upstream allocation controls on this bounded evaluation."
- Weaken: "All anti-collapse mechanisms are uniformly beneficial across this surface."
- Weaken: "Every strict_f3 subcomponent contributes positively in isolation."

## Manuscript-use guidance
- Use this table in the paper: `outputs/component_ablation_strict_f3_paper_surface/20260422T180445Z/component_summary_table.csv`
- Use this figure in the appendix: `outputs/component_ablation_strict_f3_paper_surface/20260422T180445Z/budget_performance_frontier.csv`
- Safe claims: repeat-expansion moderation is the strongest contributor; output repair is secondary on this surface.
- Claims to weaken: universal anti-collapse benefit and universal monotonic benefit of every subcomponent.
