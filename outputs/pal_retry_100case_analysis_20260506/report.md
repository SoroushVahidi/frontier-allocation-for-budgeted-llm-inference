# PAL+retry fresh 100-case analysis (no API)

- Output path: `/home/soroush/research-next-wt/outputs/pal_retry_100case_analysis_20260506`
- Statistical conclusion: PAL+retry and external_l1_max are statistically indistinguishable on this sample (gap -1 pp; discordants 8 vs 9; exact p=1.0000; bootstrap CI includes 0).
- Retry effect conclusion: retry is beneficial when triggered (net +2 on triggered subset) but had limited global impact because it ran in only 4/100 cases.
- Metric consistency issue: no integrity failures; low corrected_gold_in_tree (7) and Discovery3 (2) are mostly field-definition/threshold effects, not a raw metric bug.
- Exact recommended next action: **A. larger paired validation** (API required).
- API should remain paused: **yes**, until explicit approval.
