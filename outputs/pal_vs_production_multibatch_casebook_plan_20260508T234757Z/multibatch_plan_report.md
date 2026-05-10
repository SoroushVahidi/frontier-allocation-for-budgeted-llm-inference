# PAL vs production_equiv multi-batch casebook plan

- **Eligible candidate pool size:** 135
- **Excluded (matched-50):** 50 ids
- **Excluded (prior nonoverlap 30):** 30 ids
- **Excluded (prior PAL casebook 30):** 30 ids
- **Screen batch size:** 50 PAL calls; **follow-up cap:** 25 production runs (budget 4 calls each, upper bound).
- **First batch estimated logical calls (upper bound):** 150 (<=200 preflight gate).
- **Global cap:** 900 logical Cohere calls; max screened 300.
- **Stop targets:** pal_only>=30, disagreement>=50, or caps.
- **ready_for_live_loop:** True

## Preflight before API

- Set `COHERE_API_KEY`.
- Run `scripts/run_pal_vs_production_multibatch_casebook_live.py --plan-dir <this_dir>`.
