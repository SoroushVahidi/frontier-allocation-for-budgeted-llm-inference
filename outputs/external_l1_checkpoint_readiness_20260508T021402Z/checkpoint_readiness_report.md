# External L1 checkpoint readiness (no-API)

## Considered case sets
- A: 100-case paired band (100 cases) with reusable external_l1 outputs.
- B: 300-case paired band (300 cases) with reusable external_l1 outputs.
- C: 71-case known-loss bank (71 cases), mechanism-focused not population-clean.
- D: Fresh held-out fixed slice not currently available in artifacts.

## Recommended first checkpoint
- Recommended set: Stage-1 40-case slice from the 100-case paired band (excluding integrated live-pilot seen IDs).
- Why: clean pairing vs `external_l1_max`, bounded cost, and better generalization check than the 15-case allowlist pilot.
- Estimated new Cohere calls: 2 (targeted-retry expected 2; structural extra 0).

## Reusable baseline and fresh generation
- Reusable external baseline artifacts:
  - `/home/soroush/research-next-wt/outputs/cohere_paired_pal_retry_vs_external_l1_100case_20260506T185133Z/external_l1_results.csv`
  - `/home/soroush/research-next-wt/outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/external_l1_results.csv`
  - `/home/soroush/research-next-wt/outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/all_results.jsonl`
- Must be generated fresh for approved run: integrated method outputs on selected checkpoint cases.

## Readiness status
- Ready for staged execution once approved and preflight gates pass.
- Abort if API key missing, method validation fails, prompt no-gold check fails, planned calls exceed cap, or early-call error/parse rate is high.

## Commands
- Method-only no-API validation:
  `python scripts/run_cohere_real_model_cost_normalized_validation.py --provider cohere --datasets openai/gsm8k --budgets 4 --seeds 11 --methods direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1,external_l1_max --validate-methods-only`
- No-API call-plan dry run:
  `python scripts/run_cohere_real_model_cost_normalized_validation.py --provider cohere --datasets openai/gsm8k --budgets 4 --seeds 11 --methods direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1,external_l1_max --allowed-example-ids-file outputs/cohere_paired_pal_retry_vs_external_l1_100case_20260506T185133Z/allowed_example_ids.jsonl --dry-run-call-plan`
- If approved for live run (not executed in this step), use the same selector and set `--max-total-api-calls 50`.

## Claim boundaries
- This bundle is checkpoint planning only; no Cohere calls were run.
- Stage-1 conclusions should be treated as preliminary until Stage-2 (100-case) confirms paired outcomes.
