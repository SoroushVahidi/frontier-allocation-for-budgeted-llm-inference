# Current Artifacts Index Supplement (2026-05-11)

This supplement points to the current evidence hierarchy and separates canonical summaries from heavy provenance.

## Canonical / Current Reading Order

1. [docs/CURRENT_STATE_SUMMARY_20260511.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/CURRENT_STATE_SUMMARY_20260511.md)
2. [README.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/README.md)
3. [START_HERE_CURRENT.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/START_HERE_CURRENT.md)

## Main Evidence Artifacts

| Artifact | Role | Tracked / provenance |
|---|---|---|
| [outputs/pal_retry_300case_analysis_20260506/](/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/pal_retry_300case_analysis_20260506/) | Main 300-case PAL+retry vs `external_l1_max` evidence | Canonical summary bundle; representative docs tracked |
| [outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/](/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/) | Raw paired run backing the 300-case headline | Heavy provenance; do not cite raw JSONL alone |
| [outputs/cohere_pal_retry_vs_3_external_baselines_30case_20260507T152735Z/](/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/cohere_pal_retry_vs_3_external_baselines_30case_20260507T152735Z/) | 30-case four-way pilot | Local-heavy diagnostic bundle |
| [outputs/direct_l1_strong_seed_15case_live_20260511T202624Z/](/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/direct_l1_strong_seed_15case_live_20260511T202624Z/) | 15-case Direct L1 strong-seed follow-up diagnostic | Local-heavy diagnostic bundle |

## Diagnostic / Proxy Artifacts

| Artifact | Role | Tracked / provenance |
|---|---|---|
| [docs/DIRECT_L1_ANCHOR_PATCH_EFFECT_AUDIT_20260510.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/DIRECT_L1_ANCHOR_PATCH_EFFECT_AUDIT_20260510.md) | Direct L1 Anchor proxy audit | Curated doc; proxy only |
| [docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_summary_20260510.json](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_summary_20260510.json) | Proxy summary for the anchor patch effect | Curated summary; proxy only |
| [docs/PAL_157_DEEP_PATTERN_MINING_20260511.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/PAL_157_DEEP_PATTERN_MINING_20260511.md) | 157 PAL-still-failing covered cases | Curated no-API mining note |
| [docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl) | Exact-case input slice for the strong-seed diagnostic | Provenance input, not evidence by itself |

## Historical / Reference Artifacts

| Artifact | Role | Status |
|---|---|---|
| [docs/CURRENT_EXTERNAL_BASELINE_GAP.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/CURRENT_EXTERNAL_BASELINE_GAP.md) | Narrow strict-method diagnostic vs `external_l1_max` | Historical reference, not PAL headline evidence |
| [outputs/failure_case_corpus_20260507/](/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/failure_case_corpus_20260507/) | Failure corpus used for PAL mining | Curated diagnostic corpus |
| [outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/](/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/) | Selected-failure collection + 247-ID replay bundle | Heavy local provenance |
| [docs/project_handoff_20260510/](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/project_handoff_20260510/) | Local handoff package and curated summaries | Local-only curated bundle |

## Tracked vs Heavy

- Canonical summaries should be cited from `docs/*.md` and small JSON/CSV summaries.
- Heavy `outputs/*.jsonl` files are provenance and should be used only when a summary or manifest requires verification.
- The 300-case bundle is the main evidence; the 30-case pilot and 15-case strong-seed run are diagnostics only.
