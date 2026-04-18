# Commands, assumptions, and caveats

## Commands run
- python scripts/run_light_all_methods_comparison.py --dataset openai/gsm8k --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/run_light_all_methods_comparison.py --dataset HuggingFaceH4/MATH-500 --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/run_light_all_methods_comparison.py --dataset HuggingFaceH4/aime_2024 --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/run_light_all_methods_comparison.py --dataset olympiadbench --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/build_full_method_comparison_status_20260418.py
- python scripts/run_self_consistency_advantage_casebook_20260418.py

## Assumptions and caveats
- This is a targeted diagnostic pass, not a broad rerun claim.
- Rich self-consistency reasoning traces are not recoverable from the light controller artifacts used here.
- multistep_k3_current and best_bounded_learned_branch_score_current are included as aggregate context methods from existing repository artifacts, but per-example answer traces for those methods are not available in this pass.
