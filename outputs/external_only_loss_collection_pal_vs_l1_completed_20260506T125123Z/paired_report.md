# Paired pilot: external_l1_max vs PAL (fresh allowlist)

- Planned allowlist cohort: larger than `140` pairs; finalized **full pairs `140`** after global logical-call cap behavior (see manifest / `paired_summary.json`).

- Paired rows: **140**
- External exact: **0.779**
- PAL exact: **0.857**
- Gap (external − PAL, percentage points): **-7.86**
- Total logical API calls (sum of `cohere_logical_api_calls`, per-example counters): **1123**
- Logical API budget cap consumed (infer from RuntimeError): **1500**

## Pair outcomes
- both_correct: **99**
- both_wrong: **10**
- external_correct_pal_wrong: **10**
- pal_correct_external_wrong: **21**

## PAL quality
- gold_in_tree: **122/140**
- discovery3 gold in augmented norms: **123/140**
- present-not-selected: **2/140**
- gold-absent proxy: **17/140**

### PAL subsystem rates
- pal_seed_ran: **100.0% of paired rows**
- pal_code_present: **95.0% of paired rows**
- pal_json_answer_present: **95.0% of paired rows**
- pal_confidence_present: **100.0% of paired rows**
- pal_parse_ok: **95.0% of paired rows**
- pal_safety_ok: **95.0% of paired rows**
- pal_exec_ok: **94.3% of paired rows**
- pal_stdout_present: **94.3% of paired rows**
- pal_candidate_strong: **92.9% of paired rows**
- pal_overlay_triggered: **92.1% of paired rows**
- pal_integration_fix_triggered: **0.0% of paired rows**
- PAL exact | exec_ok: **0.886**
- PAL exact | candidate_strong: **0.885**

## Interpretation
- **PAL matches/beats external exact rate?** True
- **Head-to-head “close race” |gap|≤5pp?** False
- **More paired sampling justified (narrow remaining uncertainty)?** False
- Proposed next cap: **≥360** remains optional for confirmation only; larger caps only if widening evaluation.

- External `discovery3` column is **unavailable** (no PAL-style augmented pool in external metadata).
