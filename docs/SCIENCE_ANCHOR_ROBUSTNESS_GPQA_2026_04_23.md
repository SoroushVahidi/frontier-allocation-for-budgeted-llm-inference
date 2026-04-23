# Science-anchor robustness extension (GPQA Diamond, 2026-04-23)

## Feasibility check

GPQA-Diamond was feasible on the same matched-style substrate in this environment.

- Access check command:
  - `python scripts/verify_hf_dataset_access.py --output-dir outputs/hf_dataset_access_science_anchor_check --datasets Idavidrein/gpqa,HuggingFaceH4/aime_2024,HuggingFaceH4/MATH-500,openai/gsm8k`
- Result: `Idavidrein/gpqa` loaded with `config=gpqa_diamond`, loader-path verdict true.

## Experiment design (narrow and controlled)

- Dataset: `Idavidrein/gpqa` (GPQA Diamond)
- Methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2` + near-direct externals used in manuscript-facing comparisons (`external_l1_max`, `external_l1_exact`, `external_tale_prompt_budgeting`, `external_s1_budget_forcing`)
- Budgets: `4,6,8,10,12,14`
  - Rationale: include canonical budgets (4/6/8) and appendix-only higher budgets (10/12/14) in one pass so we can test both manuscript-facing and high-budget claims on the same science anchor without changing canonical paper artifacts.
- Seeds: `11,23`
- Subset size: `20`
- Runner:
  - `python scripts/run_science_anchor_robustness.py --run-id 20260423Tscience_anchor_gpqa_v1`

Output family:

- `outputs/science_anchor_robustness_20260423Tscience_anchor_gpqa_v1/`

## Research-facing answers

1. **Does science anchor preserve manuscript-facing strict_f3 preference?**
   - **Weakened / unresolved** on this GPQA run. `strict_f3` is not the top internal method on 4/6/8 as a set.

2. **Does strict_gate1_cap_k6 become stronger on harder science substrate?**
   - Relative to `strict_f3`, often yes at multiple budgets; however at high budgets (10/12/14) `strict_f2` is strongest overall on this run.

3. **Does strict_f2 remain competitive?**
   - **Yes**, and on this run it is the strongest internal method overall and across 10/12/14 aggregate.

4. **Is dominant failure still absent_from_tree + present_not_selected?**
   - For `strict_f3` vs `strict_gate1_cap_k6` at higher budgets, the deltas are still dominated by tree-entry/selection terms (`absent_from_tree`, `present_not_selected`) with near-zero `output_layer_mismatch`.
   - Mechanism mix is somewhat budget-dependent, but output-layer mismatch is not the primary driver here either.

5. **Should paper strategy change now?**
   - No. Keep this science-anchor extension as appendix/robustness evidence only.
   - Keep canonical main manuscript positioning unchanged (4/6/8 contract and existing two-surface distinction).

## Conservative interpretation

This is one narrow GPQA slice (single science anchor, two seeds, subset size 20), so it is informative but not sufficient for a main-story rewrite.
Treat as robustness signal and future-promotion input, not immediate manuscript replacement evidence.
