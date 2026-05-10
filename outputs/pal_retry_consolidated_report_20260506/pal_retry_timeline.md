# PAL + Retry Timeline (no-API consolidation)

1. **Fresh paired benchmark (100-case):** `cohere_paired_pal_vs_external_l1_100case_20260506T025806Z` and analysis in `paired_pal_external_100case_analysis_20260506`.
2. **External-only mining expansion:** cumulative external-only losses grew to 31 through completed + round2 + round3 collections and audits.
3. **Root-cause concentration established:** code-absence became the leading actionable category across external-only losses.
4. **Retry patch readiness (offline):** `offline_pal_empty_code_retry_readiness_20260506` identified 16/31 retry-eligible, including 14/14 L1_P1 cases.
5. **Live retry smoke (5-case):** retry triggered appropriately and produced net fixes without breaks.
6. **Live retry follow-up (remaining 11 cases):** additional net fixes without breaks; cap respected.
7. **Current state:** retry-on-empty-code is useful for targeted losses, but robustness gaps remain; global superiority claim is still premature.
