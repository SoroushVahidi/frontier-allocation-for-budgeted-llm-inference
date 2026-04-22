# Outputs directory guide

This directory stores generated artifacts from scripts and evaluation passes.

## Current-canonical output families

Use these first for current claims.

### 1. Final strict-phased default-decision bundle
- `final_strict_phased_default_decision_eval_20260421T042913Z/`

This is the current primary output family for the broad promoted-default claim on its own surface.
Current conclusion on that surface: `strict_gate1_cap_k6` is the repository's broad promoted default.

### 2. Current explicit in-house winner decision bundle
- `final_inhouse_method_decision_20260422T001521Z/`

This is the current primary output family for the question “what is our method?”
Current conclusion: `strict_f3` is the repository’s single canonical in-house winner.

### 3. Current our-method vs external-baselines comparison bundle
- `full_our_method_vs_external_baselines_comparison/20260422T230000Z/`

This is the current primary bundle for our-method (`strict_f3`) vs external-baseline ranking and strongest-external-baseline identification.

### 4. Current strongest-external loss-analysis bundle
- `our_method_vs_strongest_external_loss_analysis/20260422T230000Z/`

This is the current primary loss-analysis bundle against the strongest fair external baseline.

### 5. Current paper-facing baseline table package
- `paper_facing_baseline_tables/20260422T231500Z/`

This package contains the reviewer-facing separation into:
- near-direct ranking,
- published adjacent baselines,
- discussion-only recent papers.

### 6. Current fairness-audit package for direct baselines
- `fairness_audit_direct_baselines/20260422T235900Z/`

This package contains the direct-baseline fairness audit, claim-safety matrix, and main-vs-appendix recommendation.

### 7. Current simple-scaling-axis coverage audit
- `simple_scaling_baseline_coverage_audit/20260422T235959Z/`

This package records the decision that the current direct package already covers the simple inference-time scaling axis and that no extra direct baseline was added.

### 8. Current official-adjacent external baseline canonical families
- `best_route_runtime_stabilization/<run_id>/`
- `when_solve_when_verify_adjacent_integration/<run_id>/`
- `lets_verify_step_by_step_adjacent_integration/<run_id>/`
- `rest_mcts_adjacent_integration/<run_id>/`
- `tree_plv_adjacent_integration/<run_id>/`
- `external_adjacent_baseline_bundle/<run_id>/`

### 9. Current unofficial but explicitly caveated comparator families
- `qstar_style_adapter/<run_id>/`

These should be interpreted using their companion docs and caveat language, not as official reproductions.

## Historical or bounded paper-facing output families

These are still useful, but they are not the default current source for the paper-facing comparison story:
- `imported_methodology_frontier_eval/`
- `paper_plot_data/`
- older `full_method_comparison_bundle/` runs that predate the current our-method comparison path
- older bounded targeted-eval bundles that predate the current paper-facing baseline package

## Interpretation rule

- Do not use an output folder as a headline evidence source unless it is linked from the current canonical docs.
- Check `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`, `docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`, `docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`, and `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md` before using a folder for manuscript claims.

## Practical rule of thumb

- Use `final_inhouse_method_decision_20260422T001521Z/` when you need the canonical answer to “what is our method?”
- Use `full_our_method_vs_external_baselines_comparison/20260422T230000Z/` for our-method vs external ranking and strongest-external-baseline identification.
- Use `our_method_vs_strongest_external_loss_analysis/20260422T230000Z/` for current loss mechanisms against the strongest fair external baseline.
- Use `paper_facing_baseline_tables/20260422T231500Z/` for manuscript tables.
- Use `fairness_audit_direct_baselines/20260422T235900Z/` and `simple_scaling_baseline_coverage_audit/20260422T235959Z/` for claim-boundary and reviewer-defense wording.
