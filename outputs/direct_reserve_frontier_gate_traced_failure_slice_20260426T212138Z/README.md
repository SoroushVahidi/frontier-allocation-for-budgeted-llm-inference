# Direct Reserve Frontier Gate Traced Failure Slice Attempt

- Diagnostic type: `not_evaluable_missing_traced_candidate_pool`
- Matched cached examples: 30
- Existing `external_l1_max` accuracy: 0.8
- Existing `strict_f3` accuracy: 0.5333333333333333
- `direct_reserve_frontier_gate_v1` accuracy: NA_not_run_no_cached_traces_or_api
- Override count: NA_not_run
- Support/maturity coverage: 0/30 matched cases; 0 trace tables present

## Outcome

A `paired_candidate_pool_diagnostic` cannot be produced offline from the current Cohere Stage-1 artifacts. The matched 30-row source has no branch trace tables, no `result_metadata`, no `final_nodes`, and no final answer fields for the matched rows. Creating trace JSONs from these files would invent candidate pools, so this report does not do that.

## Smallest real API rerun needed

Run the exact 30-cell replay with branch traces enabled for the two incumbent/frontier methods plus the new controller:

`.venv-test/bin/python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN --providers cohere --datasets openai/gsm8k --budgets 4,6,8 --seeds 11,23 --methods strict_f3,external_l1_max,direct_reserve_frontier_gate_v1 --target-scored-per-slice 5 --max-examples 5 --save-branch-traces`

That rerun should produce `candidate_branch_table.csv`, `answer_group_table.csv`, `per_case_trace_index.csv`, and `traces/*.json`, after which `scripts/run_direct_reserve_frontier_gate_failure_slice_diagnostic.py --source-dir <rerun-output>` can classify the diagnostic as `paired_candidate_pool_diagnostic`.

## Interpretation

No larger real-model pilot is justified yet. The next step is only the minimal traced replay above. The unfavorable Cohere Stage-1 result remains unchanged and diagnostic-only.
