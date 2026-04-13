# Cross-provider pilot summary

- Run: `20260413T162139Z`
- Providers attempted: openai, gemini, groq
- Datasets: openai/gsm8k, EleutherAI/hendrycks_math, Idavidrein/gpqa

## Provider/dataset outcomes
- gemini | EleutherAI/hendrycks_math: ok_methods=0, failed_methods=4, raw_top=n/a, calibrated_top=n/a, ranking_changed=False
- gemini | Idavidrein/gpqa: ok_methods=0, failed_methods=4, raw_top=n/a, calibrated_top=n/a, ranking_changed=False
- gemini | openai/gsm8k: ok_methods=0, failed_methods=4, raw_top=n/a, calibrated_top=n/a, ranking_changed=False
- groq | EleutherAI/hendrycks_math: ok_methods=0, failed_methods=4, raw_top=n/a, calibrated_top=n/a, ranking_changed=False
- groq | Idavidrein/gpqa: ok_methods=0, failed_methods=4, raw_top=n/a, calibrated_top=n/a, ranking_changed=False
- groq | openai/gsm8k: ok_methods=0, failed_methods=4, raw_top=n/a, calibrated_top=n/a, ranking_changed=False
- openai | EleutherAI/hendrycks_math: ok_methods=4, failed_methods=0, raw_top=best_of_n, calibrated_top=adaptive_relative_rank, ranking_changed=True
- openai | Idavidrein/gpqa: ok_methods=3, failed_methods=1, raw_top=adaptive_relative_rank, calibrated_top=adaptive_relative_rank, ranking_changed=False
- openai | openai/gsm8k: ok_methods=4, failed_methods=0, raw_top=best_of_n, calibrated_top=adaptive_relative_rank, ranking_changed=True

## Notable failures
- openai | Idavidrein/gpqa | best_of_n: http_error_other (RuntimeError: OpenAI API HTTPError 503: upstream connect error or disconnect/reset before headers. reset reason: connection termination)
- gemini | openai/gsm8k | adaptive_relative_rank: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | openai/gsm8k | adaptive_score_plus_progress: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | openai/gsm8k | adaptive_learned_branch_score_v4: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | openai/gsm8k | best_of_n: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | EleutherAI/hendrycks_math | adaptive_relative_rank: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | EleutherAI/hendrycks_math | adaptive_score_plus_progress: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | EleutherAI/hendrycks_math | adaptive_learned_branch_score_v4: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | EleutherAI/hendrycks_math | best_of_n: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | Idavidrein/gpqa | adaptive_relative_rank: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | Idavidrein/gpqa | adaptive_score_plus_progress: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | Idavidrein/gpqa | adaptive_learned_branch_score_v4: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- gemini | Idavidrein/gpqa | best_of_n: quota_or_rate_limit (RuntimeError: Gemini API HTTPError 429: {)
- groq | openai/gsm8k | adaptive_relative_rank: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | openai/gsm8k | adaptive_score_plus_progress: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | openai/gsm8k | adaptive_learned_branch_score_v4: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | openai/gsm8k | best_of_n: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | EleutherAI/hendrycks_math | adaptive_relative_rank: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | EleutherAI/hendrycks_math | adaptive_score_plus_progress: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | EleutherAI/hendrycks_math | adaptive_learned_branch_score_v4: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | EleutherAI/hendrycks_math | best_of_n: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | Idavidrein/gpqa | adaptive_relative_rank: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | Idavidrein/gpqa | adaptive_score_plus_progress: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | Idavidrein/gpqa | adaptive_learned_branch_score_v4: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
- groq | Idavidrein/gpqa | best_of_n: http_error_other (RuntimeError: Groq API HTTPError 403: error code: 1010)
