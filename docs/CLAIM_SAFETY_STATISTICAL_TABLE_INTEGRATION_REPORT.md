# Claim-Safety Statistical Table Integration Report

Date: 2026-04-24 (UTC)

## Scope
Integrated the claim-safety statistical table builder into the canonical NeurIPS artifact regeneration workflow and validated end-to-end execution.

## Files modified/created

### Code / tests
- `tests/test_paper_artifact_runner_claim_safety_integration.py` (new)

### Dependency declarations
- `requirements.txt`
- `pyproject.toml`

### Documentation
- `docs/NEURIPS_PAPER_ARTIFACTS.md`
- `docs/PAPER_ARTIFACT_MAP.md`
- `docs/PAPER_REPRODUCTION_CHECKLIST.md`
- `outputs/paper_tables/README.md`
- `outputs/paper_plot_data/README.md`
- `docs/CLAIM_SAFETY_STATISTICAL_TABLE_INTEGRATION_REPORT.md` (this report)

## Commands run

1. `python -m pip install matplotlib>=3.8`
2. `python scripts/paper/build_claim_safety_statistical_table.py`
3. `python scripts/paper/run_all_neurips_paper_artifacts.py`
4. `pytest tests/test_unified_claim_safety_statistical_audit.py tests/test_claim_safety_statistical_table.py tests/test_paper_artifact_runner_claim_safety_integration.py`
5. `python scripts/check_repo_health.py`

## Regeneration result

- Full canonical artifact regeneration via `python scripts/paper/run_all_neurips_paper_artifacts.py` succeeded in this environment.
- The runner explicitly includes and executes `build_claim_safety_statistical_table.py` in the canonical sequence.

## Dependency update result

- `matplotlib` was genuinely missing from declared dependencies and was required by canonical plot scripts.
- Added `matplotlib>=3.8` to both:
  - `requirements.txt`
  - `pyproject.toml` project dependencies.

## Safe manuscript wording (final)

Use wording aligned with the claim-safety table and note:

- `strict_f3` is **not statistically established** as decisively better than `strict_gate1_cap_k6` on matched-surface slices.
- The safe claim is that leading frontier-allocation variants form a close top cluster and the exact winner is surface-dependent.
- External-baseline comparisons are slice-specific under matched action-budget/substrate constraints; they are not universal dominance evidence.

## Explicit forbidden wording

- “Strict-F3 statistically dominates Gate1.”
- “Frontier allocation universally dominates external baselines.”
