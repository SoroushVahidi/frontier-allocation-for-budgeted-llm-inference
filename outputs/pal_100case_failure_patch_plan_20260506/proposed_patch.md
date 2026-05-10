# Proposed minimal patch (implemented)

## Decision
Implement exactly one low-risk runtime-gold-free patch:

- **Patch:** allow safe builtin numeric casts `int` and `float` in PAL executor.
- **File:** `experiments/pal_executor.py`
- **Why first:** matches preferred order and directly addresses `P2_code_rejected_for_safe_but_needed_construct` observed in actionable case `openai_gsm8k_95`.

## What changed
- Added `int` and `float` to `_ALLOWED_BUILTINS`.
- Added executor test for safe conversion acceptance in `tests/test_pal_executor.py`.

## Not changed yet
- No prompt rewrite yet (P1 still design follow-up).
- No selection policy changes.
- No runtime use of gold/eval fields.

## Expected impact
- Directly unblocks safe cast patterns in PAL code.
- Could recover a subset of unsafe-code failures where only numeric casts were blocked.
