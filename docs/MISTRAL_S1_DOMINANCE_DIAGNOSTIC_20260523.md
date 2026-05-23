# MISTRAL S1 DOMINANCE DIAGNOSTIC (2026-05-23)

- Source run: `outputs/mistral_frozen_agreement_only_2of3_validation_20260523T145416Z/cohere_real_model_cost_normalized_validation_20260523T145416Z`
- Diagnostic outputs: `outputs/mistral_s1_dominance_diagnostic_20260523`
- Cases analyzed: 300

## Accuracy snapshot
- Frontier: 235/300 = 78.33%
- L1: 217/300 = 72.33%
- S1: 269/300 = 89.67%
- TALE: 189/300 = 63.00%
- Agreement-only 2-of-3: 256/300 = 85.33%
- Pooled-4 fallback: 251/300 = 83.67%

## Why S1 is stronger on Mistral (evidence)
- `only_s1_correct`: 9 cases.
- `s1_correct_frontier_wrong`: 42 cases.
- `s1_correct_l1_and_tale_wrong`: 30 cases.
- `s1_wrong_others_correct`: 3 cases.
- This pattern indicates genuine correctness advantage on this run, not only tie-breaking luck.

## Parseability / formatting
- No parse_extraction failures detected for any of the four methods.
- Differences are more consistent with answer-quality/style behavior than hard parser failure spikes.
- Response-style table shows whether S1 emits cleaner numeric outputs relative to L1/TALE (see response_style_by_method.csv).

## Why agreement-only underperforms S1
- Agreement-only is wrong while S1 is correct in 19 cases.
- It keeps frontier while S1 is correct and frontier is wrong in 8 cases.
- Therefore, fallback-to-frontier and external-majority constraints prevent exploiting S1 dominance fully.

## Cross-provider context (available artifacts only)
- Cohere completed run (non-active artifact): S1=220/300 (73.33%), Frontier=223/300 (74.33%), L1=216/300 (72.00%), TALE=205/300 (68.33%).
- Mistral run: S1=269/300 (89.67%), Frontier=235/300 (78.33%), L1=217/300 (72.33%), TALE=189/300 (63.00%).
- S1 appears uniquely dominant on Mistral relative to this completed Cohere artifact.
- Cerebras comparison deferred because the Cerebras run is active/incomplete.

## Diagnostic-only rule consideration (not promoted)
- A provider-specific diagnostic rule like “prefer S1 on Mistral” could increase this run’s accuracy, but this is **diagnostic only** and not promoted evidence without broader, contract-matched replication.

## Checks before using Mistral as cross-provider evidence
- Reproduce on contract-matched example set(s) and multiple seeds/providers.
- Confirm no hidden formatting/parser artifacts by auditing raw outputs for S1/L1/TALE.
- Compare with completed contract-matched Cohere run once finished and with completed Cerebras run.
