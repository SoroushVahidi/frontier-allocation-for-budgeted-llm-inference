# Cleanup risk report

**Policy:** This report recommends only; **no deletions** were performed as part of this checkpoint.

## Likely temporary or scratch

| Path pattern | Risk | Recommendation |
|--------------|------|----------------|
| `outputs/_tmp_atlas_test/`, `outputs/_tmp_method_validate/` | Local scratch | **Keep** until owner confirms; optional manual archive after copying summaries. |
| `outputs/*_test/` (e.g. `production_equiv_v1_stage3_50_dry_run_test`) | Dry-run / pytest fixture outputs | **Keep** for reproducibility; do not treat as headline evidence. |
| `outputs/production_equiv_v1_runtime_wired_stage3_50_dry_run_test/` | Wiring test | **Keep**; low paper value. |
| `local_patches/`, `manifests/`, `prompts/` (untracked) | Workspace-local | **Hold** — commit only if sanitized and intentional. |

## Duplicate or superseded output folders

| Folder | Note |
|--------|------|
| `outputs/sc6_pal_external_baselines_10case_calibration_20260508T220037Z/` | **Superseded / ignore for headline calibration** — prefer `...220734Z` and the full fair-50 live folder `external_sc6_fair_50case_live_20260508T221625Z`. Earlier buggy calibration risk per handoff. |
| Multiple `pal_pot_advantage_loss_pattern_audit_*` timestamps | Newer timestamp usually supersedes analysis iteration — cite the latest used in paper text. |
| Multiple `production_equiv_v1_stage3_50_live_checkpoint_*` | **`...203036Z` rerun** is the checkpoint tied to suite aggregation. |

## One-off or pilot scripts (untracked)

Many `scripts/run_*` and `scripts/build_*` under untracked state are **one-off materializers**. **Keep** in repo when committed for reproducibility; until then they are **merge-risk** if they duplicate harness paths.

## Failed retry / schema outputs

**Flag:** **Negative diagnostic — preserve.** Folders matching `outputs/targeted_discovery_retry_*`, `outputs/schema_grounded_retry_v1_*` document what *not* to ship; do not delete for “cleanup.”

## Timestamped outputs (general)

**Do not delete** timestamped `outputs/*` directories unless you have explicitly copied summaries to canonical docs and completed a **manual** archival policy. Default **keep** indefinitely for provenance.

## delete/archive guidance (no action taken)

- **delete:** none automated.
- **archive (optional, manual):** old `_tmp*` after confirming empty or redundant.
- **keep:** all `outputs/*20260508T*` live run artifacts referenced in `artifact_index_update.md`.
