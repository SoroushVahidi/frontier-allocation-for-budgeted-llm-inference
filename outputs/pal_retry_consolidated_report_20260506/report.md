# Consolidated PAL + Retry Research Status (No API)

- Output path: `/home/soroush/research-next-wt/outputs/pal_retry_consolidated_report_20260506`
- API status for this report: **paused** (no new API/model-eval runs)

## Headline results

1. **Paired 100-case PAL vs external_l1_max:** PAL 80/100 vs external 75/100 (**+5 pp**), with discordants 10 vs 5; p=0.3018 and bootstrap CI -2 to +13 pp. This is promising but **not statistically decisive**.
2. **External-only loss mining (31 cases):** dominant actionable issue is **code-absence** (`L1_P1_code_absent=14`), with top precise patterns concentrated on omitted executable payload/code blocks.
3. **Retry-on-empty-code evidence:** targeted live reevaluation over 16 retry-evaluated cases yields **6 fixes, 0 breaks, net +6**, but retry execution remains brittle (aggregate retry exec-OK 0.375).

## Claim boundaries

- No claim that PAL+retry beats external_l1_max globally yet.
- Current paired 100-case result is directionally favorable but not decisive.
- Retry results are targeted to external-only retry-eligible/code-absence losses, not a global unbiased estimate.

## Recommended next step

Stop new API for now and prepare a clean PR/report for the retry patch (no-API tests + 16-case live retry evidence). After merge/review, run a fresh paired PAL+retry vs external_l1_max validation.

## Should API remain paused?

**Yes.**
