# PAL 100-case failure patch plan

## Actionable 5-case table
See `actionable_failure_casebook.csv`.

Patch-category mapping:
- `openai_gsm8k_125` -> `P1_prompt_no_code_emitted`
- `openai_gsm8k_31` -> `P1_prompt_no_code_emitted`
- `openai_gsm8k_95` -> `P2_code_rejected_for_safe_but_needed_construct`
- `openai_gsm8k_127` -> `P3_code_runtime_error_fixable_by_executor` (practically prompt/code-quality)
- `openai_gsm8k_81` -> `P5_code_executes_but_wrong_operation`

## Chosen patch vs design-only
Chosen patch: **implemented** minimal P2 executor change (allow `int`/`float`).

## Files changed
- `experiments/pal_executor.py`
- `tests/test_pal_executor.py`

## Tests
- Ran requested no-API suite subset: **74 passed, 0 failed**.

## Estimated help from patch
- Directly likely to help: **1 case** (safe cast blocked).
- Additional gains likely require prompt-compliance and code-target fixes (P1/P3/P5).

## Recommended immediate next step
- **Patch replay** (targeted/offline or small controlled rerun) before larger validation.
- Keep API paused until explicit approval.
