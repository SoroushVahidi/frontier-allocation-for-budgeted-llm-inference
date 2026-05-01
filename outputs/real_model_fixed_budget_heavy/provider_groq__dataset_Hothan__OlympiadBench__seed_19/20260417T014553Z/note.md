# Real-model fixed-budget pilot note

- Run id: `20260417T014553Z`
- Providers: groq
- Datasets: Hothan/OlympiadBench
- Subset size per provider/dataset: 60
- Fixed budget (max actions/problem): 8
- Min expansions before prune: 0
- Learned scorer path preference: `outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v4.json`

## Provider/dataset summary
- No successful provider/dataset/method runs were recorded.

## Skipped/failed combinations
- groq | Hothan/OlympiadBench | adaptive_relative_rank: status=method_failed, reason=http_error_other, error=RuntimeError: Groq API HTTPError 403: error code: 1010
- groq | Hothan/OlympiadBench | adaptive_score_plus_progress: status=method_failed, reason=http_error_other, error=RuntimeError: Groq API HTTPError 403: error code: 1010
- groq | Hothan/OlympiadBench | adaptive_learned_branch_score_v4: status=method_failed, reason=http_error_other, error=RuntimeError: Groq API HTTPError 403: error code: 1010
- groq | Hothan/OlympiadBench | best_of_n: status=method_failed, reason=http_error_other, error=RuntimeError: Groq API HTTPError 403: error code: 1010

## Diagnostics included
- branch diversity / collapse from unique branch ids touched per example
- branch-score variance across action-trace score updates
- budget usage over time from remaining_budget in action trace
- semantic redundancy proxy as mean token-overlap (Jaccard) between recorded steps/predictions
- provider/method failure reasons via lightweight error categorization
