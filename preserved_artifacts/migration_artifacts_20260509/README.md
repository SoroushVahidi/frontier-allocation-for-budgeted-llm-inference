Migration artifacts preserved for Codex Web handoff on 2026-05-09.

Contents:
- `code_and_tests_target_staged_pal_and_validator.tgz`
- `external_baseline_and_selector_diagnostics.tgz`
- `local_patches_and_manifests.tgz`
- `pal_retry_vs_external_core_artifacts.tgz`
- `pal_vs_production_and_track_b.tgz`
- `git_status_final.txt`
- `recent_commits_final.txt`
- `untracked_files_final.txt`
- `_created_archives.txt`
- `_missing_skipped_paths.txt`

Purpose:
- Preserve local untracked code, prompts, manifests, patches, and selected high-value experiment artifacts in GitHub so Codex Web can access them after recloning.
- Keep the reviewed code/docs branch separate from raw preservation material.

Recommended use:
1. Open `git_status_final.txt`, `recent_commits_final.txt`, and `untracked_files_final.txt` for migration context.
2. Unpack the archives in a scratch directory, not over the repository root.

Example:

```bash
mkdir -p ~/migration_artifacts_20260509_unpacked
cd ~/migration_artifacts_20260509_unpacked
for f in /path/to/repo/preserved_artifacts/migration_artifacts_20260509/*.tgz; do
  tar -xzf "$f"
done
```

Notes:
- These archives are preservation snapshots, not reviewed source-of-truth replacements.
- Raw `outputs/` trees were intentionally not bulk-added to normal Git history.
