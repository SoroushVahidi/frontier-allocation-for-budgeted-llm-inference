# Conditional early intervention follow-up on manuscript-relevant hard slice (2026-04-23)

## Why this is the next surgical experiment

This follow-up is explicitly scoped as a narrow next step after prior broad controls:

- Hard max family cap studies showed broad fixed caps reduce collapse proxies but often hurt accuracy on matched surfaces.
- Strict phased early coverage studies improved entry on hard slices but acted as blunt forcing barriers.
- Deterministic output-layer repair is retained but no longer treated as the main bottleneck.

The active bottleneck remains upstream tree entry under fixed budget (especially absent-from-tree with early same-family monopolization), so this pass tests **conditional early anti-collapse only when risk is present**, rather than always-on global forcing.

## Surface and comparison contract

- Source surface: `outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv`.
- Surface scope replayed here: datasets `{gsm8k, MATH-500, AIME-2024}`, budgets `{4,6,8}`, seeds `{11,23}`, total 360 strict_f3 rows.
- Anchor method (manuscript-facing internal winner runtime):
  - `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1`
- Interventions:
  1. `strict_f3_conditional_early_risk_cap_k2_v1`
  2. `strict_f3_conditional_early_risk_cap_k2_rival_maturation_v1`

## Intervention definitions

Both interventions add a **conditional cap mode** to the existing hard-family-cap mechanism (no new controller family):

- Base early cap: `K=2`.
- Relax cap: `K=6`.
- Early window: first 6 actions.
- Risk trigger: active only when either
  - max consecutive same-family run >= 3, or
  - top support share >= 0.60.
- Outside early-risk regime, cap relaxes to `K=6`.

Variant differences:

1. **conditional_early_risk_cap**
   - Tightens only during early-risk; otherwise immediately relaxes.
2. **conditional_early_risk_cap_rival_maturation**
   - Same, but keeps tight cap until at least one rival family reaches minimum maturity (`>=2` expansions).

## Machine-readable outputs

- `outputs/manuscript_slice_conditional_early_intervention_eval_20260423T194504Z/eval_manifest.json`
- `outputs/manuscript_slice_conditional_early_intervention_eval_20260423T194504Z/per_case_results.csv`
- `outputs/manuscript_slice_conditional_early_intervention_eval_20260423T194504Z/method_summary.csv`
- `outputs/manuscript_slice_conditional_early_intervention_eval_20260423T194504Z/aggregate_summary.json`
- `outputs/manuscript_slice_conditional_early_intervention_eval_20260423T194504Z/target_slice_summary.json`

## Aggregate matched-surface results (360 strict_f3 rows)

From `method_summary.csv`:

- Anchor `strict_f3`:
  - accuracy **0.6306**
  - absent-from-tree **102**
  - present-not-selected **31**
  - repeated same-family present **319**
  - gold in tree **258**
- `conditional_early_risk_cap`:
  - accuracy **0.6389** (**+0.0083** vs anchor)
  - absent-from-tree **99** (**-3**)
  - present-not-selected **31** (no change)
  - repeated same-family present **314** (**-5**)
  - gold in tree **261** (**+3**)
  - H2H vs anchor: improved 81 / worsened 78 / unchanged 201
- `conditional_early_risk_cap_rival_maturation`:
  - accuracy **0.5917** (**-0.0389**)
  - absent-from-tree **102** (no gain)
  - present-not-selected **45** (worse)
  - repeated same-family present **305** (lower, but with accuracy cost)
  - gold in tree **258** (no gain)
  - H2H vs anchor: improved 77 / worsened 91 / unchanged 192

## Targeted hard slice results

Slice definition (from anchor canonical surface rows):

- anchor failures
- absent-from-tree
- repeated same-family present

Slice size: **91** rows.

From `target_slice_summary.json`:

- `conditional_early_risk_cap` on this slice:
  - accuracy 0.7143 vs anchor 0.6264 on replay
  - absent-from-tree 20 vs 29
  - repeated same-family present 77 vs 80
  - gold in tree 71 vs 62
  - H2H improved 23 / worsened 15 / unchanged 53
- `conditional_early_risk_cap_rival_maturation`:
  - accuracy 0.6154 (below anchor replay on this slice)
  - absent-from-tree 29 (no gain)
  - repeated same-family present 78 (small drop)
  - H2H improved 20 / worsened 21 / unchanged 50

## Upstream interpretation

Core question:

> On the current manuscript-relevant hard failure slice, can a conditional early anti-collapse / alternative-entry intervention reduce absent-from-tree and same-family monopolization without reducing overall matched-surface accuracy?

Answer from this pass:

- **Yes, partially, for one narrow variant** (`conditional_early_risk_cap`).
  - It reduced absent-from-tree and repeated same-family counts while slightly improving overall matched-surface accuracy.
  - Improvement appears upstream (gold-in-tree increased; present-not-selected did not inflate).
- **No for the rival-maturation extension** in this parameterization.
  - It reduced some collapse proxy counts but paid a broad accuracy and selection cost.

## Decision status

**Overall result: mixed (one positive narrow variant, one negative extension).**

Recommendation:

- Keep `strict_f3_conditional_early_risk_cap_k2_v1` as **exploratory/supportive** evidence for mechanism-level improvement.
- Do **not** promote to canonical paper evidence without confirmation on the canonical matched manuscript bundle and additional seed stability checks.
- Do **not** advance the rival-maturation version in current form.

## Next experiment (if continuing this line)

A minimal next pass should remain surgical:

1. Hold the successful conditional-risk template fixed.
2. Run a very small threshold sensitivity check only around risk triggers (family-share and run-length), not a broad K sweep.
3. Re-evaluate on the same manuscript-relevant surface and the same hard slice definitions.
4. Require non-negative aggregate accuracy plus absent-from-tree reduction before promotion.

