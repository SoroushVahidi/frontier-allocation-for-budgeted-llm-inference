# Coverage then scorer diagnostic (20260426T004641Z)

## Setup
- Provider/model: Cohere `command-r-plus-08-2024`.
- Dataset: `openai/gsm8k`.
- Slice: 9 examples, budget=4, seed=11.
- Compared methods: `strict_f3`, `external_l1_max`, `strict_f3_direct_reserve_gate_rerank_v1`, `direct_reserve_strong_plus_diverse_v1` (proxy for external-style direct internal candidate).

## Answers to required questions
1. **Did correct answers appear in the candidate pool?** In the trace-level learned-scorer dataset, no: gold-present was 0 for all methods.
2. **Which method produced the most gold-present cases?** Tie at 0 (all methods).
3. **Is budget 4 too tight?** Budget 4 appears too tight or structurally mismatched for trace-extracted candidate coverage on this slice.
4. **Does external_l1_max solve cases that our internal direct branch misses?** external_l1_max had higher selected-gold than strict_f3, but trace-extracted candidate pools still showed zero gold-present, indicating prompt/interface mismatch rather than selector weakness.
5. **Was scorer training run or skipped?** Skipped.
6. **If scorer training ran, did it improve final answer selection among gold-present cases?** Not run.
7. **Recommended next engineering step?** Coverage improvement / prompt-interface repair first; then budget-6 ablation if budget-4 remains all-zero after repair.

## Stage-1 metrics (trace-level dataset view)
| method | candidate_branches | answer_groups | gold_present | selected_gold | extraction_success |
|---|---:|---:|---:|---:|---:|
| direct_reserve_strong_plus_diverse_v1 | 18 | 9 | 0/9 | 0/9 | 0.000 |
| external_l1_max | 9 | 9 | 0/9 | 0/9 | 0.000 |
| strict_f3 | 22 | 9 | 0/9 | 0/9 | 0.000 |
| strict_f3_direct_reserve_gate_rerank_v1 | 9 | 9 | 0/9 | 0/9 | 0.000 |
