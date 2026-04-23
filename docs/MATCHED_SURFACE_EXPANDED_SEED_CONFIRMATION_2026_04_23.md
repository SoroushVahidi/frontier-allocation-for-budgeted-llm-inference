# Matched Surface Expanded-Seed Confirmation (2026-04-23)

## Contract used
- Canonical manuscript-facing matched-surface contract class: datasets `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`; budgets `4,6,8`; subset size `20` per dataset-seed.
- Internal focus methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`.
- Fair near-direct external baselines (already present in matched-surface runner): `external_s1_budget_forcing`, `external_tale_prompt_budgeting`, `external_l1_exact`, `external_l1_max`.
- New artifact bundle: `outputs/matched_surface_expanded_seed_confirmation_20260423T180003Z/`.

## What is new vs current manuscript-facing comparison
- Prior manuscript-facing decision used matched seeds `{11,23}`.
- This is one independent rerun with expanded seeds `{11,23,37,47,59}` on the same contract class and same budget range.
- No canonical paper-facing source-of-truth artifact was overwritten.

## Result
- Expanded-seed aggregate accuracy:
  - `strict_f3`: `0.622222`
  - `strict_gate1_cap_k6`: `0.585556`
  - delta (`strict_f3 - strict_gate1_cap_k6`): `+0.036667`
- `strict_f3` remains the manuscript-facing winner under this expanded-seed check.

## Evidence interpretation
- Relative to the prior narrow-margin manuscript-facing result, this rerun **strengthens** the manuscript-facing internal decision in favor of `strict_f3`.
- The broader operational/default distinction remains unchanged: this run does not redefine the broader operational surface decision for `strict_gate1_cap_k6`.

## Safe manuscript claim after this run
- Safe to claim: on the manuscript-facing matched-surface contract class, an expanded independent seed confirmation still selects `strict_f3` over `strict_gate1_cap_k6`.
- Still avoid universal claims outside this bounded contract (different surfaces, budgets, datasets, or future variants).
