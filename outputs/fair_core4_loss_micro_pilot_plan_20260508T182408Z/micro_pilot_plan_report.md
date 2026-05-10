# Fair core4 loss micro-pilot plan

- Selected cases: 11 (best_core4_only=2, both_wrong=9).
- Planned Cohere calls: 11.
- Scaffold distribution: {'tale_style_decomposition': 1, 'robust_extraction_observability': 4, 'final_target_extraction_repair': 2, 'ratio_unit_equation': 1, 'state_transition_consistency': 3}.
- Justification: targeted failure bank isolates known losses and shared-error cases for high-signal diagnostics.
- Expected information gain: whether targeted scaffolds recover final-target/state/ratio/format errors without broad runtime changes.
- Recommendation: run all 11 live in one capped micro-pilot (max 11 calls) since this is already a tightly filtered set.
- Caveats: prompts are heuristic scaffold assignments; no parser/runtime code changes are included in this planning step.
