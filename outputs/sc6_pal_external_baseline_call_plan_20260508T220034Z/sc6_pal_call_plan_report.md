# SC6 / PAL external baseline call plan

## Decision
- **chosen_live_plan**: `ten_case_calibration_only`
- **reason**: Expected full-50 workload 350 logical calls for both methods exceeds decision threshold 250 (50*6 + 50*1 = 350). PAL path variability and SC6 decode diversity (temp=0) add risk; run 10-case calibration first with cap 80 (expected 70 calls).

## Estimates
| Plan | Cases / method | SC6 calls | PAL calls | Total |
|------|----------------|-----------|-----------|------|
| A calibration | 10 | 60 | 10 | 70 |
| B full | 50 | 300 | 50 | 350 |

Caps: calibration max **80**; full hypothetical max **300** (would be insufficient for 350 — full 50 both methods requires raising cap or running methods in separate budgeted slices).

## Per-method
- **SC6**: `n_samples=6` with controller `budget=6` (aligned with core4 SC4@4 pattern).
- **PAL**: Single Cohere JSON code-gen call + local sandbox in `APIBranchGenerator.generate_program_of_thought_answer`.

## Risks
{
  "sc6_temperature_0": "Independent samples at temperature 0 may collapse diversity vs paper-style sampling; caveated in manifests.",
  "pal_executor": "Restricted Python execution may fail or return unparseable stdout; method_execution_error or parsing_failure.",
  "method_execution_error": "Branch generator must expose PoT path; rare RuntimeError from API cap.",
  "parsing_failure": "Empty normalized answer after self-consistency vote or missing PAL numeric extraction."
}
