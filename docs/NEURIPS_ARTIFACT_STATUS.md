# NeurIPS Artifact Status

## What was successfully built

A reproducible text-only pipeline now generates:

- all requested paper tables under `outputs/paper_tables/`,
- all requested plot-source CSVs under `outputs/paper_plot_data/`,
- a single runner script `scripts/paper/run_all_neurips_artifacts.py`,
- canonical-input validation and conservative missing-data handling.

No binary files were added.

## Current strongest NeurIPS narrative supported by this repo

The strongest repository-consistent manuscript story remains:

1. Under fixed inference budgets, heterogeneous controller families exhibit distinct frontier behavior.
2. Oracle frontier rows show non-trivial remaining headroom over strongest non-oracle baselines.
3. Anti-collapse evidence (via oracle winner-share diversity diagnostics) indicates that broad family coverage can matter under fixed budgets.
4. Existing adaptive variants (`adaptive_min_expand_*`, `adaptive_budget_guarded`) provide meaningful ablation handles, but broad-best claims remain conditional on missing canonical baselines/policies.

## Missing experiments that would most strengthen submission

Highest-priority missing pieces (for this manuscript direction):

- canonical explicit **uniform allocation baseline** artifacts,
- canonical explicit **learned cross-controller allocation policy** artifacts in the same multi-dataset/seed evaluation bundle,
- paper-grade feature-toggle ablations for:
  - family-aware features,
  - difficulty-aware features,
  - oracle-inspired target supervision.

## Blockers and caveats found

- Imported frontier canonical run currently provides two budgets (`8`, `10`) rather than a full low/medium/high grid.
- Some requested ablation axes are not available in canonical outputs and are reported as missing.
- Anti-collapse metrics are conservative composition diagnostics derived from per-example canonical outcomes, not direct policy-trace entropy from a dedicated learned allocator run.
- Pipeline intentionally does not claim cross-strategy/binary revise-routing results beyond cross-controller frontier allocation evidence.
