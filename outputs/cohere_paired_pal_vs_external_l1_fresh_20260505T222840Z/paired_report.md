# Paired pilot: external_l1_max vs PAL (fresh allowlist)

- Planned allowlist cohort: larger than `43` pairs; finalized **full pairs `43`** after global logical-call cap behavior (see manifest / `paired_summary.json`).

- Paired rows: **43**
- External exact: **0.837**
- PAL exact: **0.930**
- Gap (external − PAL, percentage points): **-9.3**
- Total logical API calls (sum of `cohere_logical_api_calls`, per-example counters): **250**
- Logical API budget cap consumed (infer from RuntimeError): **360**

## Pair outcomes
- both_correct: **34**
- both_wrong: **1**
- external_correct_pal_wrong: **2**
- pal_correct_external_wrong: **6**

## PAL quality
- gold_in_tree: **40/43**
- discovery3 gold in augmented norms: **40/43**
- present-not-selected: **0/43**
- gold-absent proxy: **3/43**

### PAL subsystem rates
- pal_seed_ran: **100.0% of paired rows**
- pal_code_present: **100.0% of paired rows**
- pal_json_answer_present: **100.0% of paired rows**
- pal_confidence_present: **100.0% of paired rows**
- pal_parse_ok: **100.0% of paired rows**
- pal_safety_ok: **97.7% of paired rows**
- pal_exec_ok: **97.7% of paired rows**
- pal_stdout_present: **97.7% of paired rows**
- pal_candidate_strong: **97.7% of paired rows**
- pal_overlay_triggered: **95.3% of paired rows**
- pal_integration_fix_triggered: **0.0% of paired rows**
- PAL exact | exec_ok: **0.929**
- PAL exact | candidate_strong: **0.929**

## Interpretation
- **PAL matches/beats external exact rate?** True
- **Head-to-head “close race” |gap|≤5pp?** False
- **More paired sampling justified (narrow remaining uncertainty)?** True
- Proposed next logical-call cap if tightening head-to-head mass (≈≥80 pairs feasible): **720**.

- External `discovery3` column is **unavailable** (no PAL-style augmented pool in external metadata).
