# Paired pilot: external_l1_max vs PAL (fresh allowlist)

- Planned allowlist cohort: larger than `131` pairs; finalized **full pairs `131`** after global logical-call cap behavior (see manifest / `paired_summary.json`).

- Paired rows: **131**
- External exact: **0.832**
- PAL exact: **0.893**
- Gap (external − PAL, percentage points): **-6.11**
- Total logical API calls (sum of `cohere_logical_api_calls`, per-example counters): **1141**
- Logical API budget cap consumed (infer from RuntimeError): **1500**

## Pair outcomes
- both_correct: **104**
- both_wrong: **9**
- external_correct_pal_wrong: **5**
- pal_correct_external_wrong: **13**

## PAL quality
- gold_in_tree: **120/131**
- discovery3 gold in augmented norms: **120/131**
- present-not-selected: **3/131**
- gold-absent proxy: **11/131**

### PAL subsystem rates
- pal_seed_ran: **100.0% of paired rows**
- pal_code_present: **98.5% of paired rows**
- pal_json_answer_present: **98.5% of paired rows**
- pal_confidence_present: **100.0% of paired rows**
- pal_parse_ok: **98.5% of paired rows**
- pal_safety_ok: **97.7% of paired rows**
- pal_exec_ok: **97.7% of paired rows**
- pal_stdout_present: **97.7% of paired rows**
- pal_candidate_strong: **96.2% of paired rows**
- pal_overlay_triggered: **95.4% of paired rows**
- pal_integration_fix_triggered: **0.0% of paired rows**
- PAL exact | exec_ok: **0.906**
- PAL exact | candidate_strong: **0.913**

## Interpretation
- **PAL matches/beats external exact rate?** True
- **Head-to-head “close race” |gap|≤5pp?** False
- **More paired sampling justified (narrow remaining uncertainty)?** False
- Proposed next cap: **≥360** remains optional for confirmation only; larger caps only if widening evaluation.

- External `discovery3` column is **unavailable** (no PAL-style augmented pool in external metadata).
