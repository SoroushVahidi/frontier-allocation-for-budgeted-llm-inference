# Latest Method Fully Tracked Failure Cases — 2026-05-10

This report identifies and categorizes the failure test cases for the current latest method, as requested.

## Latest Method Identification

The current primary method is:
**`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak`**

Superseding variants and aliases include:
- `..._pal`: Includes PAL execution seed and overlay logic (PR #357).
- `..._direct_hybrid`: Includes an L1-style direct reasoning seed.
- `production_equiv_v1`: The consolidated method incorporating structural commitment and latest surfacing repairs (PR #368).

## Failure Case Inventory

Based on the exhaustive failure audit (`docs/project_handoff_20260510/exhaustive_failure_audit/audit_summary.json`), we have:

| Category | Count | Definition |
|----------|-------|------------|
| **Fully Tracked Failures** | **215** | FULL evidence: case ID, gold, prediction, and diagnostic metadata (trace/candidate/commitment) available. |
| **Partially Tracked Failures** | **464** | PARTIAL evidence: wrong case known, but metadata incomplete. |
| **Untracked Aggregate Failures** | **480** | ID_ONLY: only aggregate accuracy/correct_count known or ID-only records. |
| **Unique FULL Case IDs** | **174** | Unique problem IDs with at least one FULL evidence failure record. |

### Regression-Test Failures (Encoded in Tests)

The following cases are explicitly referenced or mocked in the test suite:

- `openai_gsm8k_59`: Verified fixed by commitment-gate patch.
- `openai_gsm8k_1177`: Verified fixed by commitment-gate patch.
- `openai_gsm8k_30`: Likely fixed by commitment-gate patch (abstains from incorrect overlay).
- `openai_gsm8k_24`: Mocked in `tests/test_output_layer_frontier_surfacing.py` (two-branch wrong incumbent).
- `openai_gsm8k_17`: Used in `tests/test_detailed_loss_case_package.py`.
- `openai_gsm8k_42`: Used in `tests/test_ten_case_loss_deep_dive.py`.

## Detailed Failure Table (Sample of Key Diagnostic Cases)

| case_id | failure type | gold_answer | predicted_answer | tracking status | artifact path | has trace? | has candidate pool? | has commitment metadata? | still failing? |
|---------|--------------|-------------|------------------|-----------------|---------------|------------|---------------------|--------------------------|----------------|
| `openai_gsm8k_30` | PAL override regression | 109 | 121 | full | `target_audit_diagnostic_cases.jsonl` | yes | yes | yes | **No** (Likely fixed) |
| `openai_gsm8k_59` | structural-commit regression | 187 | 287 | full | `target_audit_diagnostic_cases.jsonl` | yes | yes | yes | **No** (Fixed) |
| `openai_gsm8k_1177` | PAL override regression | 320 | 150 | full | `target_audit_diagnostic_cases.jsonl` | yes | yes | yes | **No** (Fixed) |
| `openai_gsm8k_118` | gold absent | 1300 | 200 | full | `wrong_casebook.csv` | yes | yes | yes | Yes |
| `openai_gsm8k_800` | gold absent | 315 | 1 | full | `wrong_casebook.csv` | yes | yes | yes | Yes |
| `openai_gsm8k_297` | gold absent | 114 | 20 | full | `wrong_casebook.csv` | yes | yes | yes | Yes |
| `openai_gsm8k_324` | parse/surfacing | 76 | 1 | full | `wrong_casebook.csv` | yes | yes | yes | Yes |
| `openai_gsm8k_1180` | wrong supported consensus | 1520 | 720 | full | `target_audit_diagnostic_cases.jsonl` | yes | yes | yes | Yes |
| `openai_gsm8k_1218` | wrong supported consensus | 120 | 180 | full | `target_audit_diagnostic_cases.jsonl` | yes | yes | yes | Yes |

## Direct Answers

- **How many fully tracked failure cases exist for the latest/current method?**
  **215** records (covering **174** unique case IDs).
- **How many partially tracked failures exist?**
  **464**.
- **How many regression-test failure cases are encoded in tests?**
  **6** (referenced or mocked in `tests/`).
- **Which cases are known to have been fixed by the latest commitment-gate patch?**
  `openai_gsm8k_59`, `openai_gsm8k_1177`, and likely `openai_gsm8k_30`.
- **Which cases remain unresolved?**
  `openai_gsm8k_118`, `openai_gsm8k_800`, `openai_gsm8k_297`, `openai_gsm8k_324`, `openai_gsm8k_1180`, `openai_gsm8k_1218`, and the majority of the 174 unique FULL cases (mostly gold-absent or wrong-reasoning).
- **Which artifact is the best source of truth for the failure case list?**
  `docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv` for the broad list; `docs/project_handoff_20260510/target_audit_diagnostic_cases.jsonl` for deep diagnostic metadata.
- **Are there enough fully tracked failures to mine patterns, or do we need a new no-API casebook generation run?**
  **Yes**, there are plenty (174 unique FULL cases) for pattern mining. A new run is not strictly necessary but could be useful to verify the recent patches at scale.

## No-API Casebook Generation Plan (If needed)

If a fresh consolidated casebook is required from existing outputs:

```bash
# Combine latest method failures from multiple sources into a single diagnostic JSONL
python3 scripts/build_frontier_pipeline_loss_casebook.py \
  --artifacts \
    outputs/cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506/pal_results.csv \
    outputs/local_latest_method_failure_inventory_20260509T205100Z/latest_method_failures.csv \
    outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/cumulative_with_previous_casebook.csv \
  --output-dir docs/LATEST_METHOD_CONSOLIDATED_CASEBOOK_20260510/ \
  --method production_equiv_v1
```
