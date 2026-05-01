# Cross-strategy frontier allocation note

This run evaluates a frontier of distinct existing strategy families and a simple budgeted selector.

Strategies used:
- reasoning_greedy (GreedyController)
- self_consistency_3 (BestOfNController with n=3)
- reasoning_beam2 (BeamController width=2)
- adaptive_min_expand_k (AdaptiveController variants for k in [1])
- verifier_guided_search (VerifierGuidedSearchController: expand candidates, verifier-ranked selection)
- program_of_thought (ProgramOfThoughtController: code generation + sandbox execution)

## Budgeted selector results
- budget=8: selected=self_consistency_3, selected_eval_acc=1.000, selected_eval_avg_actions=8.00, oracle_eval_acc=1.000

## Frontier gap signal
- Mean oracle-minus-selected accuracy gap across budgets: 0.000
- Positive gap implies headroom for richer cross-strategy frontier controllers (dynamic per-example or per-step allocation).
