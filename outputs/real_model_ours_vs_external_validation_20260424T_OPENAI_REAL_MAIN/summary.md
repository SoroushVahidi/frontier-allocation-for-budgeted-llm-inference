# Real-model ours-vs-external validation summary

## Provider execution status
- openai: attempted=True completed=True partial=False shards=18/18 reason=

## Ours vs external headline (OpenAI)
- Did best ours beat best external overall? NO
- Best ours method: strict_f3 (0.4833)
- Best external method: external_l1_max (0.5417)
- Ours minus external gap: -0.0583
- Evaluated rows: 1799
- API/runtime error rows: 1
- Claim safety status: not safe

## Slice support (dataset-budget)
- HuggingFaceH4/MATH-500 @ budget 4: gap=+0.0250
- HuggingFaceH4/MATH-500 @ budget 6: gap=-0.0750
- HuggingFaceH4/MATH-500 @ budget 8: gap=-0.0500
- HuggingFaceH4/aime_2024 @ budget 4: gap=-0.0500
- HuggingFaceH4/aime_2024 @ budget 6: gap=-0.1250
- HuggingFaceH4/aime_2024 @ budget 8: gap=+0.0000
- openai/gsm8k @ budget 4: gap=+0.0250
- openai/gsm8k @ budget 6: gap=-0.2750
- openai/gsm8k @ budget 8: gap=+0.0000

## Failure decomposition
- Best ours (strict_f3): absent_from_tree=186, present_not_selected=0, output_layer_mismatch=0
- Best external (external_l1_max): absent_from_tree=165, present_not_selected=0, output_layer_mismatch=0

## Conservative interpretation
- Headline claim remains ours-family vs external baselines under a shared substrate.
- Internal ordering among strict_f3/strict_gate1_cap_k6/strict_f2 is non-headline.
- This smoke run is OpenAI-only and small; it cannot be main-paper-safe.

## Next prepared run
- python scripts/run_real_model_ours_vs_external_validation.py --timestamp 20260424T_OPENAI_REAL_MAIN --providers openai --datasets openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024 --subset-size 20 --seeds 11,23 --budgets 4,6,8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,external_l1_exact,external_tale_prompt_budgeting,external_s1_budget_forcing,self_consistency_3 --resume
