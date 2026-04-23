# Quickstart

This is the shortest reliable entry point for the current repository.

## What this repository is about now

The current project studies **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

The canonical question is:

> Which active branch should receive the next unit of compute, and when should the controller continue versus commit?

This repository is **not** currently centered on the older binary revise-routing story.

## Read in this order

1. `docs/CANONICAL_START_HERE.md`
2. `docs/PAPER_START_HERE.md`
3. `docs/PAPER_SOURCE_OF_TRUTH.md`
4. `docs/INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
5. `docs/MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`
6. `docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
7. `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
8. `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
9. `docs/PAPER_ARTIFACT_MAP.md`
10. `docs/PAPER_REPRODUCTION_CHECKLIST.md`
11. `scripts/CANONICAL_START_HERE.md`

## Canonical first-run command block

For a reproducible first pass through the current broad default evidence path:

```bash
make setup
python scripts/run_broader_strict_phased_default_decision_eval.py
```

Then review:
- `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- `outputs/final_strict_phased_default_decision_eval_20260421T042913Z/`

## Canonical method-status clarification

- Manuscript-facing internal winner on the canonical manuscript-facing matched surface: `strict_f3`
- Broader operational default on the broader strict-phased surface: `strict_gate1_cap_k6`

## Use these artifact families first

### Current canonical broad comparison
- `docs/CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_2026_04_20.md`
- `docs/CURRENT_RANKING_AND_COMPETITIVE_STATUS_2026_04_20.md`
- `outputs/current_full_method_comparison_bundle_20260420/`

### Current exact failure surface
- `docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md`
- `outputs/twenty_exact_current_full_vs_best_fresh_20260420/`

### Current targeted method-development surfaces
- `docs/TWENTY_CASE_CURRENT_FULL_IMPROVEMENT_REPORT_20260420T181131Z.md`
- `docs/TARGETED_FAILURE_BUNDLE_REPORT_20260420T183801Z.md`
- `docs/NEAR_MISS_CORRECTION_EVAL_REPORT_20260420T184849Z.md`

## Do not treat these as the default current ranking source

These are valid but historically bounded:
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/`
- `outputs/paper_plot_data/`

Use them only with explicit scope labeling.

## Most relevant current scripts

### Broad comparison / current evidence
- `scripts/run_full_method_comparison_bundle.py`
- `scripts/build_twenty_exact_current_full_vs_best_fresh.py`

### Focused failure analysis / method-development
- `scripts/run_fresh_twenty_current_full_improvement_eval_20260420.py`
- `scripts/build_targeted_failure_bundle_from_fresh_loss_surface_20260420.py`
- `scripts/run_near_miss_correction_bundle_eval_20260420.py`

## Rule of thumb

- Start from canonical docs, not arbitrary outputs.
- Use the current April 20–21 bundles for current claims.
- Treat older derived plot folders as bounded historical surfaces unless explicitly stated otherwise.


## Manuscript-safe paper writing path

Use this minimal sequence before drafting claims or plotting final paper tables:
- `docs/PAPER_START_HERE.md`
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
- `docs/PAPER_ARTIFACT_MAP.md`
- `docs/PAPER_FIGURES_AND_TABLES_PLAN.md`
- `docs/PAPER_BASELINE_HONESTY_STATUS.md`
- `docs/PAPER_OPEN_GAPS_AND_RISKS.md`
