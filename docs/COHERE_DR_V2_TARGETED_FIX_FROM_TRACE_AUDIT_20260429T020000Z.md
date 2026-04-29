# COHERE_DR_V2_TARGETED_FIX_FROM_TRACE_AUDIT_20260429T020000Z

1. **Trace-audit dominant bottleneck**
   - `selection_failure_present_not_selected`.

2. **Exact fix implemented**
   - Added diagnostic controller `direct_reserve_semantic_frontier_v2_selection_fix_v1`.
   - It keeps DR-v2 proposal/generation unchanged and only changes final selection if frontier answer-group support is strictly higher than direct-reserve support by at least 1.

3. **Why this matches bottleneck**
   - The trace audit indicated DR-v2 losses where candidate evidence existed but the final selection did not pick it.

4. **Test commands**
   - `python scripts/check_repo_health.py`
   - `python -m pytest -q tests/test_frontier_router.py tests/test_check_repo_health_paths.py tests/test_cohere_dr_v2_trace_loss_audit.py`

5. **Rerun command**
   - `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260429T020000Z --providers cohere --datasets openai/gsm8k --budgets 4 --seeds 11 --methods direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max --max-examples 20 --target-scored-per-slice 20 --emit-trace-audit --resume`

6. **Before/after on same 20-case slice**
   - DR-v2 original accuracy: **0.60**
   - Selection-fix accuracy: **0.60**
   - external_l1_max accuracy: **0.70**
   - Paired delta vs external_l1_max:
     - DR-v2 original: **-0.10**
     - Selection-fix: **-0.10**
   - Mean total tokens/example:
     - DR-v2 original: **1066.15**
     - Selection-fix: **1088.80**
     - external_l1_max: **528.60**
   - Bottleneck shift:
     - Selection-fix applied in 2/20 cases, but no net exact-match gain in this slice.

7. **Recommendation**
   - **keep diagnostic only** (do not claim improvement yet; no gain on matched slice).
