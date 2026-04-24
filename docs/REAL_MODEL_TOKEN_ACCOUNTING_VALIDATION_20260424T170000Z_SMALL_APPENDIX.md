# REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION_SMALL_APPENDIX

Timestamp: `20260424T170000Z`.
Primary artifact: `outputs/real_model_token_accounting_validation_20260424T170000Z_SMALLAPPX_S1/`.

## Scope and positioning

- This is **small appendix evidence**, not main headline manuscript evidence.
- The primary comparison contract remains **action-budget matched**.
- Token and latency fields are **diagnostic accounting fields**.
- Cost is reported as `NA` when pricing is not configured (as in this run).
- `strict_f3` vs `strict_gate1_cap_k6` should **not** be treated as statistically decisive unless stronger/larger evidence supports it.
- Compare `strict_f3` and `strict_gate1_cap_k6` primarily as internal representatives; compare frontier-allocation family vs `external_l1_max` cautiously.

## Contract run

- Provider/model: `openai/gpt-4.1-mini`
- Methods: `strict_f3`, `strict_gate1_cap_k6`, `external_l1_max`
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- Budgets: `4, 6, 8`
- Seeds: `11, 23`

## Subset-size progression

- Attempted subset-size 5 run (`20260424T170000Z_SMALLAPPX_S5`) but did not complete cleanly within practical runtime limits in this environment.
- subset-size 10 was therefore not launched.
- Completed fallback small appendix run with subset-size 1 (`20260424T170000Z_SMALLAPPX_S1`) to produce auditable real-model accounting artifacts.

## Small-appendix summary (subset-size 1)

Rows scored: `54`.

By method and budget (accuracy / mean actions / mean estimated total tokens / mean latency sec):

- **external_l1_max**
  - b4: `0.5000 / 3.1667 / 444.6667 / 7.5582`
  - b6: `0.6667 / 3.8333 / 561.3333 / 11.8601`
  - b8: `0.6667 / 3.8333 / 522.1667 / 9.6502`
- **strict_f3**
  - b4: `0.5000 / 3.8333 / 502.5000 / 6.6206`
  - b6: `0.3333 / 6.0000 / 710.5000 / 12.5225`
  - b8: `0.6667 / 7.0000 / 819.5000 / 15.0162`
- **strict_gate1_cap_k6**
  - b4: `0.0000 / 4.0000 / 508.3333 / 7.9378`
  - b6: `0.3333 / 6.0000 / 706.0000 / 12.9021`
  - b8: `0.6667 / 7.0000 / 848.6667 / 14.9224`

## Interpretation guardrail

This package is **appendix-only** and should be treated as directional accounting/robustness evidence under a small sample, not as headline-safe ranking evidence.
