# Commands, assumptions, caveats

## Commands run
- python scripts/run_full_comparative_mistake_audit_vs_best_method_20260418.py --datasets openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench --sim-subset-size 16 --sim-seeds 11,23 --sim-budgets 4,6,8 --real-subset-size 1 --real-seeds 11 --real-budgets 4 --real-providers ''

## Assumptions
- Main comparison pair is fixed as self_consistency_3 vs broad_diversity_aggregation_v1 from current repo evidence and real-slice instability note.
- strong_v1 is kept as sibling context only for instability annotation.
- Fresh real-provider runs were skipped in this pass to keep the audit bounded and reproducible in the available runtime window.

## Caveats
- This pass's machine-readable mistake counts are simulator-backed.
- Real-model evidence referenced in the note comes from prior repository artifacts and remains tiny-slice directional evidence.
- Some internal traces are not recoverable from self-consistency outputs.
