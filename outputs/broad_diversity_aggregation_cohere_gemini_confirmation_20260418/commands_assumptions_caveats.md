# Commands, assumptions, and caveats

## Command provenance
- user_passed_command: `python scripts/run_broad_diversity_aggregation_cohere_gemini_confirmation_20260418.py --providers cohere,gemini --cohere-model command-r-plus-08-2024 --gemini-model gemini-2.0-flash --datasets openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench --subset-size 2 --seeds 11 --budgets 4 --adaptive-grid 1 --temperature 0.1 --max-output-tokens 140 --timeout-seconds 25 --output-dir outputs/broad_diversity_aggregation_cohere_gemini_confirmation_20260418`
- script: `scripts/run_broad_diversity_aggregation_cohere_gemini_confirmation_20260418.py`

## Explicit provider policy
- OpenAI API was not used in this pass.
- Providers are restricted to Cohere and Gemini only.

## Caveats
- This is bounded real-model evidence: larger than the tiny one-example pass, but still not paper-grade scale.
- Provider-level behaviors are not directly comparable as a pure model-quality ranking.
- Residual categories use deterministic heuristics from saved metadata; they are diagnostic rather than causal proof.

## Retry/timeout behavior
- Both Cohere and Gemini calls use timeout control and 4-attempt retry for transient HTTP/network failures.
