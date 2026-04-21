# Outputs directory guide

This directory stores generated artifacts from scripts and evaluation passes.

## Current-canonical output families

Use these first for current claims:

### 1. Final strict-phased default-decision bundle
- `final_strict_phased_default_decision_eval_20260421T042913Z/`

This is the current primary output family for the broad default-model claim.
Current conclusion: `strict_gate1_cap_k6` is the repository's broad default promoted model on the evaluated surface.

### 2. Current exact loss surfaces and larger direct-adversary failure statistics
- `twenty_exact_current_full_vs_best_fresh_20260420/`
- `hundred_current_full_vs_best_failure_statistics_20260420T220416Z/`
- `new_hundred_newest_vs_best_failure_statistics_20260421T032711Z/`

### 3. Current strict-phased hard-coverage and gate-comparison stack
- `hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421T020917Z/`
- `hundred_three_gate_design_eval_strict_phased_20260421T022459Z/`

### 4. Current learned and capped alternatives
- `learned_f2_to_f3_gate_<timestamp>/`
- `hard_max_family_expansions_k456_eval_20260421T041916Z/`

### 5. Current output-layer repair analysis
- `current_failure_output_layer_repair_20260420/`

## Historical or bounded paper-facing output families

These are still useful, but they are not the default current source for the finalized default-model story:
- `imported_methodology_frontier_eval/`
- `paper_plot_data/`
- older `full_method_comparison_bundle/` runs that predate the current April 20 broad comparison path
- older bounded targeted-eval bundles that predate the strict-phased law

## Interpretation rule

- Do not use an output folder as a headline evidence source unless it is linked from the current canonical docs.
- Check `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`, `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`, and `docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md` before using a folder for manuscript claims.

## Practical rule of thumb

- Use the final strict-phased default-decision bundle for the current broad default-model claim.
- Use the newest-vs-best exact-loss families for direct-adversary failure statistics.
- Use the strict-phased force/gate families for why the default emerged from the strict-phased family.
- Use the learned-gate and hard-cap output families as controlled alternatives and supporting evidence, not as the default source unless the canonical docs explicitly promote them.
