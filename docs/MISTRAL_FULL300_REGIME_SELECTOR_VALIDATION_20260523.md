# Mistral Full-300 Regime Selector Validation (2026-05-23)

## Scope
- Diagnostic validation only (no policy promotion).
- Provider/model: mistral / `mistral-small-latest`.
- Dataset: `openai/gsm8k`.
- Budget: `B=6`.
- Methods: `direct_reserve_semantic_frontier_v2`, `external_l1_max`, `external_s1_budget_forcing`, `external_tale_prompt_budgeting`.

## Launch Status
- Status: **running**
- tmux session: `mistral_full300_regime_20260523T233843Z`
- Python PID: `2271445`
- Output root: `outputs/mistral_full300_regime_selector_validation_20260523`
- Run output root: `outputs/mistral_full300_regime_selector_validation_20260523/cohere_real_model_cost_normalized_validation_20260523T233843Z`
- Log path: `outputs/mistral_full300_regime_selector_validation_20260523/mistral_full300_live_20260523T233843Z.log`
- Case set: exact prior Mistral 300 replay (`mistral_original300_exact_cases.jsonl` + allowed IDs)
- Estimated API calls: ~1200 logical baseline calls (+ retries/backoff). Dry-run upper bound artifact reports up to 1800 logical calls.

## Current Progress Snapshot (2026-05-23T23:42:55Z)
- Rows written: 47
- Unique examples touched: 47
- Per-method row counts: {"direct_reserve_semantic_frontier_v2": 47}
- API retry http_429 events observed so far: 32
- Error/exception keyword mentions: 0

## Non-invasive Monitoring
- `tmux ls | rg mistral_full300_regime_20260523T233843Z`
- `tail -n 120 outputs/mistral_full300_regime_selector_validation_20260523/mistral_full300_live_20260523T233843Z.log`
- `wc -l outputs/mistral_full300_regime_selector_validation_20260523/cohere_real_model_cost_normalized_validation_20260523T233843Z/per_example_records.jsonl`
- `tail -n 30 outputs/mistral_full300_regime_selector_validation_20260523/cohere_real_model_cost_normalized_validation_20260523T233843Z/progress_heartbeat.jsonl`

## Guardrail Confirmation
- Active Cerebras run/session was observed and left untouched.
- Cohere paid rerun was not launched in this task.
- Frozen policy logic was not modified.
