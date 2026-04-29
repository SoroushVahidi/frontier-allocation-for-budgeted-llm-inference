# Trace-Complete External Loss Collection Results

## Run commands executed
1. `python scripts/plan_trace_complete_external_loss_collection.py`
2. Smoke (planned full set) failed on unresolved method:
   - `python scripts/run_cohere_real_model_cost_normalized_validation.py --providers cohere --datasets openai/gsm8k --budgets 4 --seeds 11 --methods strict_f3,strict_gate1_cap_k6,direct_reserve_semantic_frontier_v2,external_l1_max,tale,s1,self_consistency_3,tot_beam_matched_budget --target-scored-per-slice 2 --max-examples 2 --resume --save-branch-traces --emit-trace-audit --output-root outputs/external_baseline_loss_case_live_collection_20260429T030232`
3. Smoke rerun with resolved methods (excluded `tot_beam_matched_budget`).
4. Bounded continuation command (same scope, resume enabled):
   - `python scripts/run_cohere_real_model_cost_normalized_validation.py --providers cohere --datasets openai/gsm8k --budgets 4 --seeds 11 --methods strict_f3,strict_gate1_cap_k6,direct_reserve_semantic_frontier_v2,external_l1_max,tale,s1,self_consistency_3 --target-scored-per-slice 20 --max-examples 20 --resume --save-branch-traces --emit-trace-audit --output-root outputs/external_baseline_loss_case_live_collection_20260429T030232`

## Configuration
- Provider/model: Cohere / `command-r-plus-08-2024`
- Methods included: `strict_f3`, `strict_gate1_cap_k6`, `direct_reserve_semantic_frontier_v2`, `external_l1_max`, `tale`, `s1`, `self_consistency_3`
- Methods excluded: `tot_beam_matched_budget` (unknown method)
- Dataset/budget/seed/example cap: `openai/gsm8k`, budget `4`, seed `11`, max examples `20`, target scored per slice `20`

## Postprocessed corpus snapshot
- Updated collection output: `outputs/external_baseline_loss_case_collection_20260429T040000/`
- Updated decision output: `outputs/external_baseline_loss_corpus_decision_20260429T040000/`
- Paired real-LLM cases: `144`
- External-win cases: `37`
- Trace-complete external-win cases: `17`
- Dominant external baseline family: `direct_length_control`
- Dominant preliminary failure type: `external_direct_advantage`

## Interpretation
- Recommended bottleneck did **not** change yet: continue `collect_trace_complete_losses` until family/trace thresholds are met.
- Algorithm change is **not yet justified** because `tale_or_s1`, `self_consistency_or_tot`, and trace-complete wins remain below plan thresholds.

## Claim guardrails
- Do not claim cross-family bottleneck certainty yet.
- Do not claim algorithm superiority changes from this partial continuation.
- Keep results diagnostic until threshold-complete trace-backed evidence is collected.
