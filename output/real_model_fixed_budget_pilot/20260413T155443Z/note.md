# Real-model fixed-budget pilot note

- Run id: `20260413T155443Z`
- Providers: openai, gemini
- Datasets: openai/gsm8k, EleutherAI/hendrycks_math
- Subset size per provider/dataset: 1
- Fixed budget (max actions/problem): 4
- Learned scorer path preference: `outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v4.json`

## Provider/dataset summary
- openai | openai/gsm8k | adaptive_relative_rank: acc=0.000, avg_actions=1.00, budget_exhaustion=0.00
- openai | openai/gsm8k | adaptive_score_plus_progress: acc=0.000, avg_actions=1.00, budget_exhaustion=0.00
- openai | openai/gsm8k | adaptive_learned_branch_score_v4: acc=0.000, avg_actions=1.00, budget_exhaustion=0.00
- openai | openai/gsm8k | best_of_n: acc=1.000, avg_actions=4.00, budget_exhaustion=1.00
- openai | EleutherAI/hendrycks_math | adaptive_relative_rank: acc=0.000, avg_actions=1.00, budget_exhaustion=0.00
- openai | EleutherAI/hendrycks_math | adaptive_score_plus_progress: acc=0.000, avg_actions=1.00, budget_exhaustion=0.00
- openai | EleutherAI/hendrycks_math | adaptive_learned_branch_score_v4: acc=0.000, avg_actions=1.00, budget_exhaustion=0.00
- openai | EleutherAI/hendrycks_math | best_of_n: acc=0.000, avg_actions=4.00, budget_exhaustion=1.00

## Skipped/failed combinations
- gemini | openai/gsm8k | adaptive_relative_rank: status=method_failed, error=RuntimeError: Gemini API HTTPError 429: {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_con
- gemini | openai/gsm8k | adaptive_score_plus_progress: status=method_failed, error=RuntimeError: Gemini API HTTPError 429: {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_input_token_count, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/gen
- gemini | openai/gsm8k | adaptive_learned_branch_score_v4: status=method_failed, error=RuntimeError: Gemini API HTTPError 429: {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_con
- gemini | openai/gsm8k | best_of_n: status=method_failed, error=RuntimeError: Gemini API HTTPError 429: {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_con
- gemini | EleutherAI/hendrycks_math | adaptive_relative_rank: status=method_failed, error=RuntimeError: Gemini API HTTPError 429: {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_con
- gemini | EleutherAI/hendrycks_math | adaptive_score_plus_progress: status=method_failed, error=RuntimeError: Gemini API HTTPError 429: {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_con
- gemini | EleutherAI/hendrycks_math | adaptive_learned_branch_score_v4: status=method_failed, error=RuntimeError: Gemini API HTTPError 429: {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_con
- gemini | EleutherAI/hendrycks_math | best_of_n: status=method_failed, error=RuntimeError: Gemini API HTTPError 429: {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_input_token_count, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/gen

## Pilot signal
- This real-API pilot is intentionally small; use trends as directional only, not benchmark claims.
- Mean method accuracy across successful rows: 0.125
