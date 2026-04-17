# Outputs interpretation guide

## Purpose

This note explains how to interpret the main output families without having to reverse-engineer them each time.

## Main output families

### 1. `outputs/branch_label_bruteforce_merged/`
Use this family when the question is about:
- merged supervision scale,
- dataset / budget / seed coverage,
- exact-vs-approx provenance,
- learner training inputs.

### 2. `outputs/branch_label_bruteforce_targets/`
Use this family when the question is about:
- target-construction regimes,
- exact promotion,
- hard-region mining,
- tie-aware / abstention-aware target variants,
- supervision-quality audits.

### 3. `outputs/branch_label_bruteforce_learning/`
Use this family when the question is about:
- learned-controller results,
- near-tie / adjacent hard-slice metrics,
- fallback or deferral policy comparisons,
- specialist expert variants,
- bounded matched method comparisons.

### 4. `outputs/imported_methodology_frontier_eval/`
Use this family when the question is about:
- fixed vs adaptive vs oracle comparison,
- budget-frontier views,
- gap-to-oracle reporting,
- signal-slice summaries,
- manuscript-style evaluation artifacts adapted from the old manuscript workflow.

### 5. `outputs/external_baseline_completeness/` and `outputs/external_baseline_runnability/`
Use these when the question is about:
- what external baselines are runnable,
- what is only adjacent/import-validated,
- what is blocked,
- and what comparison claims are currently safe.

## Which outputs are most paper-facing right now

Most paper-facing output families currently are:
- `outputs/imported_methodology_frontier_eval/`
- `outputs/branch_label_bruteforce_learning/`
- `outputs/external_baseline_completeness/`

## Which outputs are more diagnostic / research-internal

More diagnostic or method-development-oriented output families include:
- most target-regime and hard-region mining folders under `outputs/branch_label_bruteforce_targets/`,
- intermediate supervision-building folders,
- one-off bounded exploratory runs not promoted in the canonical docs.

## Practical rule

When presenting results externally:
- prefer outputs that already connect clearly to canonical docs and comparison notes,
- and avoid using a one-off diagnostic folder as if it were the canonical evidence source.

## Neighbor docs

- `docs/ASSET_AUDIT_AND_WORKING_SET_2026_04_17.md`
- `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
- `docs/imported_methodology_frontier_integration_report.md`
