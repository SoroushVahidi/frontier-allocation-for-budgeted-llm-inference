# Local-Only Artifacts to Preserve — 2026-05-10

| Path | Type | Recommendation | Reason |
| --- | --- | --- | --- |
| `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/` | Raw Run | Archive | Latest source for PAL-hybrid data; contains 542 raw rows. |
| `outputs/production_equiv_v1_50_live_failure_diagnosis_20260508T202315Z/` | Diagnosis | Archive | Detailed row-level diagnosis for `production_equiv_v1`. |
| `outputs/production_equiv_v1_retry_commit_loss_audit_20260508T204005Z/` | Loss Bank | Archive | Loss bank for retry commit behavior. |
| `outputs/structural_commit_v1_replay_20260508T120000Z/` | Replay | Archive | Counterfactual replay data for structural commitment. |
| `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/` | Collection | Archive | 4-way comparison bundle (PAL vs 3 Externals). |
| `outputs/local_latest_method_failure_inventory_20260509T234152Z/` | Inventory | Push Curated | Source of the handoff CSVs. |
| `preserved_artifacts/migration_artifacts_20260509/` | Archive | Preserve | Consolidated `.tgz` bundles for migration safety. |

## Action Definitions
- **Push Curated**: Include small summaries/CSVs in this handoff folder.
- **Archive**: Keep the full raw directory in a compressed archive outside of main Git history.
- **Left Local Only**: Do not push or archive (redundant or transient).
- **Ignore**: Standard `.gitignore` behavior.
