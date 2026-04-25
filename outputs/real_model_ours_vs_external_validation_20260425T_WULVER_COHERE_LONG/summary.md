# Real-model ours-vs-external validation summary

## Provider execution status
- cohere: attempted=True completed=True partial=False shards=6/6 reason=

## Ours vs external headline (OpenAI)
- Did best ours beat best external overall? NO
- Best ours method: N/A (0.0000)
- Best external method: N/A (0.0000)
- Ours minus external gap: +0.0000
- Evaluated rows: 0
- API/runtime error rows: 0
- Claim safety status: not safe

## Slice support (dataset-budget)
- No OpenAI dataset-budget slices available yet.

## Conservative interpretation
- Headline claim remains ours-family vs external baselines under a shared substrate.
- Internal ordering among strict_f3/strict_gate1_cap_k6/strict_f2 is non-headline.
- This smoke run is OpenAI-only and small; it cannot be main-paper-safe.

## Next prepared run
- python scripts/run_real_model_ours_vs_external_validation.py --timestamp 20260424T_OPENAI_REAL_MAIN --providers openai --datasets openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024 --subset-size 20 --seeds 11,23 --budgets 4,6,8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,external_l1_exact,external_tale_prompt_budgeting,external_s1_budget_forcing,self_consistency_3 --resume
