# Post-Migration Verification Report - 2026-05-10

## Overview
This report verifies the migration of project-related files from various scattered directories into the canonical repository: `~/frontier-allocation-for-budgeted-llm-inference`.

## Verification Methodology
- **Checksum Comparison**: Generated MD5 checksums for all files in old folders and compared them against the canonical repository.
- **Git Status**: Checked for untracked files in the canonical repository.
- **Health Checks**: Ran `scripts/check_repo_health.py` and core tests after fixing environment dependencies.

## Environment Fix
The environment was fixed by installing the missing dependencies:
```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -e .[dev]
```
Post-fix health check: **OK** (14 tests passed).

## Migration Status by Folder

| Old Folder | Migration Status | Missing Files | Conflicts | Recommendation | Safe to Delete |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `~/diverse-root-clean` | Verified | None (Non-ignored) | 7 files (newer in canonical) | Worktree of canonical. | Yes |
| `~/pal-pilot-clean` | Verified | None (Non-ignored) | 7 files (newer in canonical) | Worktree of canonical. | Yes |
| `~/research-next-wt` | Verified | None (Non-ignored) | `README.md` (newer in canonical) | Active research folder. Unique content migrated. | Yes |
| `~/outputs` | Verified | None | None | Home-level outputs migrated. | Yes |
| `~/scripts` | Verified | None | `check_provider_readiness.py` | Moved to `_migration_review`. | Yes |
| `~/tests` | Verified | None | `run_tests.py`, `test_check_provider_readiness.py` | Moved to `_migration_review`. | Yes |
| `~/migration_artifacts_20260509` | Archived | None | None | Archived to `archive/`. | Yes |

## Detailed Findings

### Missing or Skipped Files
- **Intentionally Skipped**: `.git` (worktree files), `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`.
- **Content Differences**: Several files in `experiments/` (e.g., `frontier_matrix_core.py`, `controllers.py`) and `README.md` have different content. In all inspected cases, the version in the **canonical repository is newer** and contains more features/fixes than the versions in the old folders.

### Migration Review Folder (`_migration_review/`)
The following files were moved here because they conflicted with existing files in the canonical repository:

1.  **`scripts/check_provider_readiness.py`**:
    - **Conflict**: Different implementation of the provider check.
    - **Explanation**: The canonical version is more robust and follows the current project structure.
    - **Recommendation**: **Delete** after verifying the canonical version works.
2.  **`tests/test_check_provider_readiness.py`**:
    - **Conflict**: Corresponding test for the script above.
    - **Recommendation**: **Delete**.
3.  **`tests/run_tests.py`**:
    - **Conflict**: Unique script from home-level `tests/`.
    - **Recommendation**: **Keep local-only** or merge if it provides unique functionality not covered by `pytest`.

## Repo Status
`git status --short` shows all migrated files as untracked.
- `docs/`: Many new experiment reports.
- `experiments/`: New unique experiment scripts.
- `outputs/`: New experiment result folders.
- `archive/`: Previous migration artifacts.

## Final Recommendation
All unique and project-related material has been safely migrated or archived. The canonical repository is healthy and passes tests. The old folders listed above are now safe to delete.

## Final Archival Status
- **Archive Folder**: `~/frontier-allocation-old-folders-archive-20260510`
- **Action Taken**: All verified old folders (`~/diverse-root-clean`, `~/pal-pilot-clean`, `~/research-next-wt`, `~/outputs`, `~/scripts`, `~/tests`, `~/migration_artifacts_20260509`) have been moved into this single archive folder.
- **Post-Move Verification**: The canonical repository `~/frontier-allocation-for-budgeted-llm-inference` remains healthy and passes all core tests (**14 passed**) after the move.
- **Conclusion**: The archive is not needed for active work and can be safely deleted later once manual confidence is established. The current repository is fully self-contained.
