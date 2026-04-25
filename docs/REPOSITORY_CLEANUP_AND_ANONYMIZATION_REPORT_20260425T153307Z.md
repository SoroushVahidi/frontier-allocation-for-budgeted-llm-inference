# REPOSITORY_CLEANUP_AND_ANONYMIZATION_REPORT_20260425T153307Z

## Files inspected
Repository-wide text files (excluding `.git`) using scripted scans for identity/path/API/link and claim-risk phrases.

## Files changed
See `outputs/repository_cleanup_and_anonymization_20260425T153307Z/files_changed.csv`.

## Identity leaks found and fixed
- Canonical reviewer-facing docs rewritten to remove identity-bearing wording and enforce anonymous framing.
- Residual leaks in legacy/historical content are listed in anonymization audit CSVs with status labels.

## Claim-safety issues found and fixed
- Added explicit claim-boundary policy and safe wording in canonical docs.
- Real-model results constrained to supporting/diagnostic status.

## Artifact organization changes
- Clarified four-way hierarchy: canonical, appendix/supporting, exploratory/provenance-only, non-review/private-local.

## Canonical reproduction path
```bash
python scripts/check_repo_health.py
python -m ruff check
python -m pytest
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Python-only validation path
Documented in README and reviewer quickstart; no `make` dependency required for anonymous review flow.

## Exploratory artifacts retained and why
Negative and exploratory artifacts were retained for provenance integrity and clearly labeled as non-headline evidence.

## Remaining risks
See `outputs/repository_cleanup_and_anonymization_20260425T153307Z/remaining_risks.csv` and `outputs/anonymization_audit_20260425T153307Z/remaining_risks.csv`.

## Exact tests/checks run
- `python scripts/check_repo_health.py`
- `python -m ruff check`
- `python -m pytest`
- `python scripts/paper/run_all_neurips_paper_artifacts.py`
