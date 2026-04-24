# Manuscript Claim-Safety Revision Report

Date: 2026-04-24 (UTC)

## Manuscript files modified

- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/abstract_safe_revision.txt`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/claim_box.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/statistical_strength_insert.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/experimental_scope_and_claim_boundaries_insert.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/limitations_rewrite.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/claim_safety_summary_table.csv`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/claim_safety_summary_table.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/README.md`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/main_results_claim_safety_table_insert.tex` (new)
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/appendix_claim_boundary_insert.tex` (new)
- `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`

## Exact claim changes made

1. Replaced Strict-F3-centered winner language with top-cluster language:
   - now states `strict_f3` and `strict_gate1_cap_k6` are statistically close on matched-surface paired/bootstrap/permutation evidence.
2. Declared winner identity as surface-dependent, and made Strict-F3 a representative-for-continuity choice rather than a decisive winner claim.
3. Added explicit family-level positive claim:
   - branch-level frontier allocation affects budget use;
   - absent-from-tree / early tree-shape control remains the core failure bottleneck signal.
4. Kept real-model evidence appendix/supportive only.
5. Bounded external comparisons to action-budget-matched, matched-substrate, slice-specific evidence.

## Table/reference added

- Added a main-results paragraph explicitly referencing the integrated claim-safety statistical table:
  - `outputs/paper_tables/table_claim_safety_statistical_tests.tex`
  - label target: `tab:claim_safety_statistical_tests`
- Added an appendix claim-boundary paragraph reiterating that no central claim depends on a decisive Strict-F3 vs Gate1 ranking.

## Forbidden wording removal check

Executed targeted grep for:
- `Strict-F3 statistically dominates`
- `Strict-F3 decisively outperforms`
- `frontier allocation universally dominates`
- `universal dominance`
- `best internal method`

No forbidden claim strings remain in the revised manuscript claim text artifacts (excluding explicit forbidden-phrase checklist files used for editorial guardrails).

## Commands run and results

1. `rg -n "Strict-F3 statistically dominates|Strict-F3 decisively outperforms|frontier allocation universally dominates|universal dominance|best internal method" manuscript_integration/neurips_claim_safe_revision_20260424T234500Z docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`
2. `python scripts/paper/run_all_neurips_paper_artifacts.py` ✅ succeeded.
3. `pytest tests/test_unified_claim_safety_statistical_audit.py tests/test_claim_safety_statistical_table.py tests/test_paper_artifact_runner_claim_safety_integration.py` ✅ all passed.
4. `python scripts/check_repo_health.py` ✅ succeeded.

No dedicated manuscript LaTeX build command is currently documented in this repository; manuscript-integration assets are maintained as insertion snippets and table fragments.

## Final reviewer-facing response recommendation

We have revised the manuscript so that no central claim depends on Strict-F3 being a decisive internal winner. The paper now states that leading frontier-allocation variants form a statistically close matched-surface top cluster, with surface-dependent winner identity between Strict-F3 and Strict-Gate1-Cap-K6. We still make a positive, stable contribution claim: frontier-allocation is a useful budgeted inference-control formulation with reproducible diagnostics, and failure decomposition consistently identifies absent-from-tree / early tree-shape control as the key bottleneck. External baseline and real-model evidence are now explicitly bounded to matched action-budget, matched-substrate, and appendix-level contexts.
