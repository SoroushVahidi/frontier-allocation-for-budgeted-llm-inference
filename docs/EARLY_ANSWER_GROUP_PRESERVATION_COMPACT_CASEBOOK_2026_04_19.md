# Early divergence compact casebook (2026-04-19)

Source artifact: `outputs/early_answer_group_preservation_bounded_eval_20260419/compact_casebook_early_divergence.json`.

## Focus slices required by plan
- Base method absent at first split: 90
- Base method present then collapsed: 0

## What changed under early-preservation
- Previously wrong cases fixed by early-preservation: 61
- Previously wrong cases still wrong: 23
- Previously correct cases harmed: 2

## Representative rows
- openai/gsm8k / openai_gsm8k_4 (budget=6, seed=11): base_type=absent_after_first_split, base_correct=False, early_correct=True
- openai/gsm8k / openai_gsm8k_17 (budget=6, seed=11): base_type=absent_after_first_split, base_correct=False, early_correct=False
- openai/gsm8k / openai_gsm8k_18 (budget=6, seed=11): base_type=absent_after_first_split, base_correct=False, early_correct=False
- openai/gsm8k / openai_gsm8k_1 (budget=8, seed=11): base_type=absent_after_first_split, base_correct=False, early_correct=True
- openai/gsm8k / openai_gsm8k_4 (budget=8, seed=11): base_type=absent_after_first_split, base_correct=False, early_correct=True
- openai/gsm8k / openai_gsm8k_5 (budget=8, seed=11): base_type=absent_after_first_split, base_correct=False, early_correct=False
- openai/gsm8k / openai_gsm8k_7 (budget=8, seed=11): base_type=absent_after_first_split, base_correct=False, early_correct=True
- openai/gsm8k / openai_gsm8k_11 (budget=8, seed=11): base_type=absent_after_first_split, base_correct=False, early_correct=False
- openai/gsm8k / openai_gsm8k_19 (budget=8, seed=11): base_type=absent_after_first_split, base_correct=False, early_correct=True
- openai/gsm8k / openai_gsm8k_4 (budget=6, seed=23): base_type=absent_after_first_split, base_correct=False, early_correct=True
- openai/gsm8k / openai_gsm8k_6 (budget=6, seed=23): base_type=absent_after_first_split, base_correct=False, early_correct=True
- openai/gsm8k / openai_gsm8k_10 (budget=6, seed=23): base_type=absent_after_first_split, base_correct=False, early_correct=True

## Conservative takeaway
- Most problematic rows in this bounded run were first-split absence rather than later collapse.
- Early-preservation changes part of that slice, but harms remain; keep this line active with tighter gating, not as final promoted default yet.
