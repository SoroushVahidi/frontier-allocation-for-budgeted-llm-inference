# Latest Method Failure Inventory Report - 2026-05-09

## SECTION 1 — Local branches/status searched
- **Current Branch**: `artifact-preservation-20260509`
- **Git Status**: 49 unique failure cases identified across untracked `outputs/` directories.
- **Search Scope**: All local branches, remote-tracking branches, untracked `outputs/`, `preserved_artifacts/`, and `manifests/`.

## SECTION 2 — Artifacts searched
The following artifacts were identified as containing failure evidence for the latest method:
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/relaxed_pal_vs_prod_casebook_new.csv`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/cumulative_pal_vs_prod_casebook.csv`
- `outputs/production_equiv_v1_50_live_failure_diagnosis_20260508T202315Z/row_level_diagnosis.csv`
- `outputs/production_equiv_v1_retry_commit_loss_audit_20260508T204005Z/production_equiv_loss_bank_detailed.csv`

## SECTION 3 — Which method is treated as best/latest
- **Method ID**: `production_equiv_v1`
- **Variants**: `structural_commit_v1`, `direct_reserve_diverse_root_frontier_v1`
- **Reasoning**: This is the most recent production-equivalent method used in the latest live runs (May 8-9, 2026).

## SECTION 4 — Total best/latest-method failure cases found locally
- **Total Unique Failures**: 49

## SECTION 5 — FULL/PARTIAL/ID_ONLY counts
- **FULL**: 28 (Has problem text, gold, prediction, and diagnostic metadata)
- **PARTIAL**: 1
- **ID_ONLY**: 20 (Primarily `cap_hit_incomplete` cases)

## SECTION 6 — Tracked vs untracked/local-only counts
- **Tracked**: 0
- **Untracked/Local-only**: 49
*Note: These are included in the `.tgz` archives pushed to GitHub, but do not exist as individual tracked files in the repo.*

## SECTION 7 — Latest-method failure table summary
| Case ID | Method | Family | Completeness |
|---------|--------|--------|--------------|
| openai_gsm8k_1121 | production_equiv_v1_loss_bank | retry_commit_miss | FULL |
| openai_gsm8k_1155 | production_equiv_v1_loss_bank | structural_commit_wrong | FULL |
| openai_gsm8k_1198 | production_equiv_v1_loss_bank | parsing_failure | FULL |
| openai_gsm8k_1077 | production_equiv_v1_loss_bank | structural_commit_wrong | FULL |
| openai_gsm8k_1081 | production_equiv_v1_diagnosis | cap_hit_incomplete | ID_ONLY |

## SECTION 8 — Largest failure families (FULL evidence only)
1. **structural_commit_wrong**: 9 cases
2. **final_target_mismatch**: 9 cases
3. **retry_commit_miss**: 4 cases
4. **parse_format**: 3 cases
5. **multi_step_computation**: 2 cases

## SECTION 9 — Older/diagnostic failure pools not counted
- **Total Older Failures**: 71 cases (from `latest_pal_external_loss_bank.csv`)
- These represent legacy PAL or external baseline losses and are not included in the 49 latest-method failures.

## SECTION 10 — Local-only failure artifacts likely missing from GitHub/Codex Web
The following directories contain the raw evidence and should be treated as the source of truth for these 49 failures:
- `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/`
- `outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z/`
- `outputs/production_equiv_v1_50_live_failure_diagnosis_20260508T202315Z/`
- `outputs/production_equiv_v1_retry_commit_loss_audit_20260508T204005Z/`

## SECTION 11 — Do we have enough failures to mine a meaningful next pattern?
**Yes.** We have 28 FULL failure cases for the latest method. The concentration in `final_target_mismatch` and `structural_commit_wrong` suggests clear areas for improvement in the commitment logic and frontier tiebreaking.

## SECTION 12 — Recommended next step
The current 49 cases are sufficient for an initial pattern mining session on Codex Web. However, to reach a more robust 100+ case failure bank, I recommend:
1. Running a 300-case "relaxed" sweep using Cohere to identify more `structural_commit_wrong` cases.
2. Expanding the `production_equiv_v1` validation to the full GSM8K test set (or a larger slice) to capture more `final_target_mismatch` diversity.
