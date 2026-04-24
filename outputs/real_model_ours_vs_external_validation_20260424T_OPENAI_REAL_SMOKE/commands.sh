python scripts/run_real_model_ours_vs_external_validation.py --timestamp 20260424T_OPENAI_REAL_SMOKE

# Next larger OpenAI run (prepared)
python scripts/run_real_model_ours_vs_external_validation.py --timestamp 20260424T_OPENAI_REAL_MAIN --providers openai --datasets openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024 --subset-size 20 --seeds 11,23 --budgets 4,6,8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,external_l1_exact,external_tale_prompt_budgeting,external_s1_budget_forcing,self_consistency_3 --resume
