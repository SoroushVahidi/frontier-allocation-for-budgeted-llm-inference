# Cohere Targeted No-Majority Fallback Rerun (2026-05-23)

## Motivation
Targeted diagnostic test for the Cohere-specific hypothesis: pooled-4 is generally strong, but on no-majority cases its frontier fallback may miss recoverable wins.

## Selected Case Sets
- A no-majority frontier-fallback wrong: 12
- B pooled4 wrong oracle-correct: 23
- C agreement wrong but pooled4 correct: 12
- D regression-check: 19
- E all-sources-wrong references: 5
- Union across sets: 53
- Paid rerun selected unique cases: 47

## Bias Warning
Failure-case rerun is intentionally biased and cannot prove overall improvement on the full Cohere distribution.

## Compact Paid Scope
- methods/case: 4
- expected logical calls: 188
- upper-bound hint with retries: 235
- no full Cohere 300-case rerun launched.

## Launch Status
- status: **running**
- tmux: `cohere_targeted_fallback_20260523T235741Z`
- output root: `outputs/cohere_targeted_no_majority_fallback_rerun_20260523`
- run output root: `outputs/cohere_targeted_no_majority_fallback_rerun_20260523/cohere_real_model_cost_normalized_validation_20260523T235741Z`
- log: `outputs/cohere_targeted_no_majority_fallback_rerun_20260523/cohere_targeted_live_20260523T235741Z.log`
- progress rows: 18
- unique examples touched: 18
- api retry http_429 events so far: 0

## Monitoring (Non-invasive)
- `tmux ls | rg cohere_targeted_fallback_20260523T235741Z`
- `tail -n 120 outputs/cohere_targeted_no_majority_fallback_rerun_20260523/cohere_targeted_live_20260523T235741Z.log`
- `wc -l outputs/cohere_targeted_no_majority_fallback_rerun_20260523/cohere_real_model_cost_normalized_validation_20260523T235741Z/per_example_records.jsonl`
- `tail -n 30 outputs/cohere_targeted_no_majority_fallback_rerun_20260523/cohere_real_model_cost_normalized_validation_20260523T235741Z/progress_heartbeat.jsonl`

## Guardrails
- Active Cerebras and Mistral runs were observed and left untouched.
- No policy promotion.
