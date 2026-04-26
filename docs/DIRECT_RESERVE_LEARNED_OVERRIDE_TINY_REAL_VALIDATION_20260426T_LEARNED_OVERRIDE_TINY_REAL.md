# Direct-reserve learned override tiny real validation

Timestamp: `20260426T_LEARNED_OVERRIDE_TINY_REAL`

## Scope

This was a diagnostic-only Cursor run of `direct_reserve_strong_plus_diverse_learned_override_v1` on a fresh 10-case GSM8K plan. It did not modify canonical `strict_f3`, did not make the learned override default, did not use HGB, did not call OpenAI, and did not regenerate paper artifacts.

## Inputs and outputs

- Fresh plan: `outputs/fresh_gsm8k_learned_override_runtime_plan_20260426T_LEARNED_OVERRIDE_TINY_REAL/`
- Real validation: `outputs/cohere_direct_reserve_validation_learned_override_tiny_real_20260426T_LEARNED_OVERRIDE_TINY_REAL/`
- Runtime eval: `outputs/direct_reserve_learned_override_runtime_eval_20260426T_LEARNED_OVERRIDE_TINY_REAL/`
- Model path used by runtime default: `outputs/direct_reserve_candidate_scorer_train_20260426T150000Z/selected_model.joblib`
- Margin threshold: `0.05`

## Results

| Question | Answer |
|---|---:|
| Was Cohere API used? | yes |
| How many fresh examples were evaluated? | 10 |
| Was overlap with prior validation zero? | yes, total overlap = 0 |
| Base plus-diverse selected-gold rate | 0.80 |
| Learned override method selected-gold rate | 0.50 |
| Overrides triggered | 0 |
| Improvements vs base | 0 |
| Method-level degradations vs base | 3 |
| Selector-triggered degradations | 0 |
| Control degradation | 0 |
| Missing model/features | 0 |
| Override available but not triggered | 10 |
| Learned override margin distribution | min 0.0167, mean 0.2233, max 0.4333 |

The learned override runtime path loaded the model and extracted features on every case. Reasons were `learned_matches_base` for 7 cases and `below_margin_threshold` for 3 cases, so no actual override was applied at threshold `0.05`.

## Interpretation

This validates that the learned-override code path is reachable in the real Cohere runtime and that the safe fallback path is active: no missing model, missing feature, HGB, or load failure occurred. It does not validate a successful runtime intervention because no override triggered.

The learned-override method underperformed the separately run base plus-diverse method on this tiny sample. The three method-level degradations are cases where the learned-override method's own runtime candidate set selected a worse final answer than the independently run base plus-diverse method; the learned selector itself did not trigger in those cases, so selector-triggered degradation is 0.

## Recommendation

Do not proceed to non-math or broader diagnostic validation yet. Keep `direct_reserve_strong_plus_diverse_learned_override_v1` diagnostic-only. The next validation should first debug the runtime evaluation design and candidate-pairing behavior, then rerun a tiny paired runtime check that can actually observe an override trigger before any 20-30 case diagnostic expansion.
