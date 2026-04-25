# Recommended Manuscript Changes (Cohere Stage-1 Decision Update)

## 1) Abstract sentence changes

### Replace/avoid
- Any sentence claiming or implying that frontier allocation (`strict_f3`) **outperforms** `external_l1_max` under real-model API execution.
- Any sentence implying cross-provider real-model dominance.

### Use instead
- "Real-model evidence is currently **bounded and diagnostic**; in a Cohere Stage-1 matched GSM8K slice, frontier allocation is **not superior** to `external_l1_max`."
- "We present the method contribution as a formulation and controlled evaluation framework, with real-model comparisons reported conservatively."

## 2) Results-section wording changes

- Add explicit sentence: "On the current matched Cohere GSM8K Stage-1 diagnostic (n=30 matched examples), `strict_f3` trails `external_l1_max` (paired delta -0.2667, 95% bootstrap CI [-0.4667, -0.0667])."
- Add explicit scope caveat: "These results are diagnostic and incomplete, not universal across providers/tasks."
- Add explicit budget consistency note: "Observed deltas are negative at budgets 4/6/8."

## 3) Limitations wording changes

- Add: "Current real-model evidence is incomplete and includes unfavorable comparisons for the manuscript-facing frontier method against `external_l1_max` on a Cohere Stage-1 slice."
- Add: "We therefore do not claim real-model dominance; conclusions are restricted to bounded diagnostic interpretation."

## 4) Appendix real-model wording

- Add subsection "Cohere Stage-1 adverse diagnostic" with:
  - matched count,
  - overall paired delta and CI,
  - per-budget and per-seed deltas,
  - cost-normalized metrics,
  - runner-correctness status and matched-ID warning.
- Add subsection "What this does and does not establish":
  - does establish: adverse signal under this bounded setting,
  - does not establish: universal method inferiority across providers/tasks.

## 5) Forbidden phrases to remove

- "real-model dominance"
- "frontier allocation beats external_l1_max" (without strict scope + caveat)
- "state-of-the-art under real API execution"
- "consistent superiority across budgets/providers"
- "robustly outperforms external baselines in real-model tests"

## 6) Safe replacement style guide

- Prefer: "competitive/mixed/diagnostic" over "better/superior/dominant".
- Always pair real-model statements with scope tuple (provider, dataset, seed set, budget set, matched n).
- Keep real-model comparison in appendix unless and until materially larger confirmatory evidence overturns current adverse result.
