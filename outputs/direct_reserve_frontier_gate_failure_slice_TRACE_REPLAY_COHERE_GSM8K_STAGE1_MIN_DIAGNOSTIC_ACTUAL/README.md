# Direct Reserve Frontier Gate Traced Replay Diagnostic

- Source replay: `outputs/cohere_real_model_cost_normalized_validation_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN/`
- Diagnostic type: `paired_candidate_pool_diagnostic`
- Matched examples: 30
- Support/maturity coverage: 30/30
- `external_l1_max` accuracy: 0.7000
- `strict_f3` accuracy: 0.5667
- `direct_reserve_frontier_gate_v1` accuracy: 0.6667
- Paired delta vs `external_l1_max`: -0.0333
- Override count: 3
- Helpful overrides: 1
- Harmful overrides: 2
- Direct-solved preserved: 16
- Direct-solved harmed: 5
- Reserve-use rate: 0.9000
- Override rate: 0.1000

## Token/cost/latency

| method | total tokens | estimated cost | mean latency seconds | mean tokens/example |
| --- | ---: | ---: | ---: | ---: |
| `external_l1_max` | 15872 | $0.083136 | 2.6843 | 529.1 |
| `strict_f3` | 31153 | $0.157815 | 4.2754 | 1038.4 |
| `direct_reserve_frontier_gate_v1` | 32798 | $0.168822 | 12.4827 | 1093.3 |

## Override audit

Helpful overrides:
- openai_gsm8k_2 seed=11 budget=8: reserve `350` -> frontier `475`.

Harmful overrides:
- openai_gsm8k_1 seed=23 budget=6: reserve `27` -> frontier `27`.
- openai_gsm8k_3 seed=23 budget=8: reserve `160` -> frontier `80`.

## Interpretation

The controller does not close the gap versus `external_l1_max` on this traced failure slice. It triggers 3 overrides, but 2 are harmful and only 1 is helpful. A larger real-model pilot is not justified until the guard is tightened and revalidated on this exact slice without harmful overrides. This remains diagnostic-only and does not promote the controller as canonical evidence.
