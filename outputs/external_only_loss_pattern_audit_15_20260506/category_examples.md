# Category examples

## L1_P9_external_trace_advantage_unknown (7)
- `openai_gsm8k_162`: gold absent from PAL candidate pool while external found correct target path; PAL=`60`, gold=`50`
- `openai_gsm8k_180`: gold absent from PAL candidate pool while external found correct target path; PAL=`25`, gold=`8`
- `openai_gsm8k_183`: gold absent from PAL candidate pool while external found correct target path; PAL=`5760`, gold=`40`

## L1_P1_code_absent (3)
- `openai_gsm8k_125`: code omitted final executable snippet/answer payload; PAL=`1`, gold=`32`
- `openai_gsm8k_166`: code omitted final executable snippet/answer payload; PAL=`1`, gold=`15`
- `openai_gsm8k_31`: code omitted final executable snippet/answer payload; PAL=`6`, gold=`12`

## L1_P5_correct_candidate_not_selected (2)
- `openai_gsm8k_204`: gold-equivalent candidate exists but selector/tiebreak picked another answer; PAL=`-240`, gold=`4`
- `openai_gsm8k_81`: gold-equivalent candidate exists but selector/tiebreak picked another answer; PAL=`1000`, gold=`750`

## L1_P3_exec_failed (1)
- `openai_gsm8k_127`: PAL code accepted but execution failed before producing a valid final answer; PAL=`0.8`, gold=`6`

## L1_P4_exec_succeeded_wrong (1)
- `openai_gsm8k_168`: PAL execution succeeded but computed numerically wrong final result; PAL=`40`, gold=`35`

## L1_P2_unsafe_code (1)
- `openai_gsm8k_95`: PAL code blocked by sandbox safety checks; PAL=`1`, gold=`6`

