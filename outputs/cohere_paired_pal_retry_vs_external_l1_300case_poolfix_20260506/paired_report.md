# Paired pilot: external_l1_max vs PAL (fresh allowlist)

- Planned allowlist cohort: larger than `300` pairs; finalized **full pairs `300`** after global logical-call cap behavior (see manifest / `paired_summary.json`).

- Paired rows: **300**
- External exact: **0.813**
- PAL exact: **0.840**
- Gap (external − PAL, percentage points): **-2.67**
- Total logical API calls (sum of `cohere_logical_api_calls`, per-example counters): **1865**
- Logical API budget cap consumed (infer from RuntimeError): **None**

## Pair outcomes
- both_correct: **223**
- both_wrong: **27**
- external_correct_pal_wrong: **21**
- pal_correct_external_wrong: **29**

## PAL quality
- gold_in_tree: **263/300**
- discovery3 gold in augmented norms: **266/300**
- present-not-selected: **11/300**
- gold-absent proxy: **34/300**

### PAL subsystem rates
- pal_seed_ran: **100.0% of paired rows**
- pal_code_present: **99.3% of paired rows**
- pal_json_answer_present: **99.3% of paired rows**
- pal_confidence_present: **100.0% of paired rows**
- pal_parse_ok: **99.3% of paired rows**
- pal_safety_ok: **99.0% of paired rows**
- pal_exec_ok: **98.7% of paired rows**
- pal_stdout_present: **98.7% of paired rows**
- pal_candidate_strong: **96.0% of paired rows**
- pal_overlay_triggered: **95.7% of paired rows**
- pal_integration_fix_triggered: **0.0% of paired rows**
- PAL exact | exec_ok: **0.851**
- PAL exact | candidate_strong: **0.854**

## Interpretation
- **PAL matches/beats external exact rate?** True
- **Head-to-head “close race” |gap|≤5pp?** True
- **More paired sampling justified (narrow remaining uncertainty)?** False
- Proposed next cap: **≥360** remains optional for confirmation only; larger caps only if widening evaluation.

- External `discovery3` column is **unavailable** (no PAL-style augmented pool in external metadata).
