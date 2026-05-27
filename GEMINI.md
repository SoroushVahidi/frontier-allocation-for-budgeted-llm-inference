# Gemini CLI Project Instructions

You are helping with the repository:
frontier-allocation-for-budgeted-llm-inference

Main rule:
Work autonomously on safe, explicitly scoped engineering tasks. Do not ask repeated confirmation questions when the requested action is safe and within scope.

Project constraints:
- Long jobs and all training/evaluation/generation jobs must run in tmux.
- Do not run API calls unless the user explicitly authorizes API use in the prompt.
- Do not delete existing outputs.
- Do not overwrite existing artifacts.
- Do not stage, commit, or push unless explicitly requested.
- Do not print or log API keys or secrets.
- Use corrected fixed-policy baselines only.
- Do not use row-wise max over candidate correctness as a baseline.
- Oracle is only an upper bound.
- Gold/correctness labels may be used only for offline training/evaluation, never as runtime-visible features.
- D6 bucket labels such as rescue/regression-check are diagnostic only and must not be runtime selector features.

Verification rule:
Never claim a job is complete from plans, assumptions, simulated counts, or conceptual updates.
Final status must be based only on real evidence:
- real file counts,
- real generation_outputs.jsonl rows,
- real generation_errors.jsonl rows,
- real tmux status,
- real logs,
- real evaluation outputs,
- real ledger/backlog changes.

Current research direction (updated 2026-05-27):
The canonical paper result is FTA / FIX-2+FIX-4 (Failure-Trace Allocator):
- Final-300: 86.67% (260/300, seed=71, Cohere × GSM8K, budget=6) — verified
- Aggregate-720: 80.69% (581/720) — verified; leakage audit PASS

D6/D9 multi-provider work is complete and supporting:
- D6 creates risky but useful extra frontier candidates (standalone negative; D9 gate required)
- D9 learns when to use D6; CV 50.18%±2.52% vs frontier 34.36% (+15.82pp); 550 pools; 3 providers; 0 false overrides
- Mistral D6 retrain: COMPLETE (D9_MISTRAL_RETRAIN_USE_D6_AS_GATED_MODULE)
- Cloudrift extraction repair: COMPLETE (98.8% coverage via lenient extractor)

Current priority: paper finalization (no API calls needed).
Secondary: fix Cloudrift/Qwen prompt before new generation; targeted Mistral rescue-bucket D6 generation.

Required paper disclosures:
1. CI vs pooled ensemble includes zero (must disclose, do not claim statistical superiority)
2. Full pool generation = 4×B=6 = 24 calls per example (FTA post-generation = 0)
3. Evaluation: Cohere × GSM8K only
4. Seed=61 (59.17%) is failure-enriched in aggregate-720

See docs/CURRENT_CANONICAL_STATE_20260527.md for the full canonical state.
