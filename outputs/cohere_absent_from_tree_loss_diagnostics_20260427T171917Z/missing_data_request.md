# Missing data request

- Existing artifacts were used only; no new expensive run was triggered.
- Missing requested datasets in available Cohere artifacts: ['natural_plan', 'gpqa_diamond']
- Missing requested methods in available Cohere artifacts: ['strict_f3_anti_collapse_weak_v1', 's1', 'tale']

## Minimal additional Cohere run needed
```bash
python scripts/run_real_model_ours_vs_external_validation.py --timestamp 20260427T171917Z_MISSING_MIN --providers cohere --datasets openai/gsm8k,natural_plan,gpqa_diamond --subset-size 20 --seeds 11,23 --budgets 4,6,8 --methods strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,external_l1_max,external_tale_prompt_budgeting,external_s1_budget_forcing --resume
```
