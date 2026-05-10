# Fair core4 loss pattern report

- Matched 50-case recap: our=39, best_core4=38, best_core4_only=2, both_wrong=9.
- Best_core4-only cases: openai_gsm8k_1124, openai_gsm8k_1198.
- Both-wrong cases indicate shared brittleness, often with parse overlap and ratio/state-update complexity.
- Main families (best_core4_only): {'final_target_mismatch': 1, 'format_parse': 1}
- Main families (both_wrong): {'format_parse': 3, 'final_target_mismatch': 2, 'ratio_setup': 1, 'state_update': 3}
- Proposed fixes: {'final-target verifier refinement': 3, 'improve robust extraction observability': 4, 'ratio scaffold with unit equations': 1, 'state-transition consistency checker': 3}
- Systematic gap signal: yes, especially final-target/parse robustness and ratio-state consistency checks.
- Recommendation: run a tiny micro-pilot on these 11 cases first, then prioritize production-equivalent validation for any accepted fix.
- Caveat: this is no-API retrospective labeling from saved outputs, not causal proof.
