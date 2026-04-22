# Internal method final decision package (2026-04-22)

## Scope and intent
This note resolves the internal-method ambiguity across prior surfaces by selecting one **manuscript-facing internal main method** using one unified, matched, reproducible surface and explicit tie-break rules.

The decision package is in:
- `outputs/internal_method_final_decision_bundle_20260422T201427Z/`

It preserves historical provenance rather than rewriting it:
- broad matched bundle context,
- strict-phased default-decision context,
- cap-refinement context,
- canonical full manuscript-facing matched ranking context.

## A) Serious internal method families
1. **Broad diversity / anti-collapse family**
   - Includes the strong broad line and anti-collapse + repeat-expansion refinement variants.
2. **Strict-phased force/gate/cap family**
   - `strict_f2`, `strict_f3`, `strict_gate1`, `strict_gate2`, and capped gate variants (`strict_gate1_cap_k6/k7/k8`).
3. **Internal reasoning baselines**
   - `reasoning_beam2`, `reasoning_greedy`, `self_consistency_3`.
4. **Verifier-guided internal baseline**
   - `verifier_guided_search`.
5. **Earlier repo-line allocation methods**
   - `adaptive_min_expand_*`.
6. **Integrated/full/repair line**
   - Current integrated full broad+repair path and strict integrated variants.

Inventory artifact:
- `outputs/internal_method_final_decision_bundle_20260422T201427Z/internal_method_inventory.csv`

## B) Strongest fair manuscript-relevant internal surface and winner
Unified decision surface:
- `outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv`
- matched datasets: GSM8K, MATH-500, AIME-2024, OlympiadBench
- matched budgets: 6 and 8
- matched seeds: 11 and 23

Internal-only finalist + anchor comparison winner by explicit rule is:
- **`strict_f3`**

Top two on this surface:
- `strict_f3`: accuracy 0.658333
- `strict_gate1_cap_k6`: accuracy 0.652778
- margin: +0.005556 for `strict_f3`

See:
- `internal_unified_summary_table.csv`
- `head_to_head_finalists.csv`
- `dataset_wise_comparison.csv`

## C) Is that already the manuscript-centered method?
Yes. The selected manuscript-facing winner is already `strict_f3`.

## D) Re-center manuscript on a method or a family?
Recommendation:
- Keep manuscript main-method center on **`strict_f3`**,
- while explicitly presenting it as one member of the strict-phased family,
- and clearly separating:
  - manuscript-facing matched winner (`strict_f3`), vs
  - broader strict-phased operational default (`strict_gate1_cap_k6`) on its own decision surface.

## E) Final method name/alias for manuscript
Use alias:
- **`strict_f3`**

Runtime long-form identifier remains the strict depth-3 forced variant with deterministic output-layer repair (as already used in canonical ranking artifacts).

## F) Strongest supporting ablations / variants
Support package (already present):
- strict-phased default/cap refinement showing why `strict_gate1_cap_k6` became broad default on a different surface.
- internal cross-family unified comparison (this package) showing manuscript-facing internal winner remains `strict_f3`.
- strict_f3 component ablations on manuscript surface:
  - `outputs/component_ablation_strict_f3_paper_surface/20260422T180445Z/`
- strict_gate1_cap_k6 component ablations:
  - `outputs/integrated_controller_component_ablation_20260422T170256Z/`

## G) Remaining uncertainty
1. The winner margin between `strict_f3` and `strict_gate1_cap_k6` is modest on this bounded matched surface.
2. Surface-dependence remains real: strict default-decision and manuscript-facing surfaces do not pick the same winner.
3. Stability should be periodically re-checked on expanded seeds/datasets and independent reruns.

## Explicit conservative claim boundary
Safe claim:
- On the canonical matched manuscript-facing internal comparison surface, `strict_f3` is the strongest internal method among current serious internal contenders.

Not claimed:
- universal superiority across all budgets, all future datasets, or all controller-policy surfaces.

## Provenance and surface limitations summary
See machine-readable surface summary:
- `outputs/internal_method_final_decision_bundle_20260422T201427Z/comparison_surfaces_summary.csv`

This file records different historical winners and why each prior surface alone was insufficient for final manuscript method selection.
