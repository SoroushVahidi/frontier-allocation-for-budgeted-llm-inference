# Cohere direct reserve validation (20260426T_COHERE_DIRECT_RESERVE_CONFIRM)

## Setup
- Provider/model: `cohere` / `command-r-plus-08-2024`.
- Dataset: `openai/gsm8k`.
- Slice target: 12 cases (4 absent, 4 present-not-selected, 4 control), budget=4, seed=23.
- Methods: `strict_f3`, `external_l1_max`, `direct_reserve_strong_v1`, `direct_reserve_strong_plus_diverse_v1`.

## Required answers
1. **Did Cohere API actually run?** Yes (`real_api_enabled=1`).
2. **How many examples were evaluated?** 12 unique examples (48 case-method rows).
3. **How much overlap with previous 9-case run?** 0 overlapping example IDs (0 in planned-case exclusion tracking).
4. **Gold-present and selected-gold rates** (per method):
| method | gold-present rate | selected-gold rate |
|---|---:|---:|
| direct_reserve_strong_plus_diverse_v1 | 0.9167 | 0.8333 |
| direct_reserve_strong_v1 | 0.7500 | 0.7500 |
| external_l1_max | 0.8333 | 0.0000 |
| strict_f3 | 0.6667 | 0.0000 |

5. **Did `direct_reserve_strong_plus_diverse_v1` beat `external_l1_max`?** Yes on selected-gold (0.8333 vs 0.0000).
6. **Did it beat `strict_f3`?** Yes on selected-gold (0.8333 vs 0.0000).
7. **Did it preserve control cases?** Not fully: control degradation count=1 (control selected-gold rate 0.7500).
8. **What were the loss cases?** 3 cases (see `loss_cases_for_manual_inspection.md`).
9. **What failure modes appeared?** {'all_wrong': 1, 'gold_absent': 1, 'present_not_selected': 1}.
10. **Stable enough for 30–50 case validation?** Not yet under conservative rule due control-stratum degradation.
11. **Debug or modify first?** Debug first: investigate control degradation and the two non-control failures (`gold_absent`, `present_not_selected`).

## Decision rule outcome
- Promote to larger validation: **NO**.
- Reason: conservative rule requires no serious control degradation; this run had a control degradation case.

## Key artifact paths
- Output package: `outputs/cohere_direct_reserve_validation_20260426T_COHERE_DIRECT_RESERVE_CONFIRM/`
- Loss manual inspection: `outputs/cohere_direct_reserve_validation_20260426T_COHERE_DIRECT_RESERVE_CONFIRM/loss_cases_for_manual_inspection.md`
- Difference manual inspection: `outputs/cohere_direct_reserve_validation_20260426T_COHERE_DIRECT_RESERVE_CONFIRM/difference_cases_for_manual_inspection.md`
