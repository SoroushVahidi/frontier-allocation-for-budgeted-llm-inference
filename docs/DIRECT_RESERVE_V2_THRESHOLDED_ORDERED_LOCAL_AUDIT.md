# Direct-Reserve v2 Thresholded-Ordered Local Audit (2026-04-28)

## Scope
Lightweight local sanity/audit only. No Cohere calls. No Slurm submission. No expensive experiment execution.

## Current git status summary
- Branch: `work`
- `git status --short`: clean (no uncommitted files found for `direct_reserve_semantic_frontier_v2_thresholded_ordered`)
- Recent commits:
  - `28a35a0 Add diagnostic direct_reserve_semantic_frontier_v2_thresholded_ordered controller`
  - `9759ca0 Document direct-reserve v2 threshold and ordering ideas`
  - `ca37a24 Submit long direct-reserve-v2 Cohere diagnostic on Wulver.`

## Files inspected
- `experiments/controllers.py`
- `experiments/semantic_diversity_diagnostic_strategies.py`
- `experiments/frontier_matrix_core.py`
- `experiments/semantic_family_clustering.py`
- `tests/test_semantic_diversity_direct_reserve_v2_thresholded_ordered.py`
- `docs/DIRECT_RESERVE_V2_THRESHOLDED_ORDERED_IMPLEMENTATION_NOTE.md`
- `docs/DIRECT_RESERVE_V2_THRESHOLD_AND_ORDERING_IDEAS.md`

## Diagnostic-only verification
- Registry method name is exactly:
  - `direct_reserve_semantic_frontier_v2_thresholded_ordered`
- Method appears in diagnostic semantic-diversity strategy registry.
- No canonical registry rewiring was found for:
  - `strict_f3`
  - `strict_f2`
  - `strict_gate1_cap_k6`
  - `external_l1_max`

## Behavior summary verified
- Direct incumbent is produced first and protected as default source.
- Route decisions exist and are wired:
  - `stop_with_incumbent`
  - `one_more_direct_continuation`
  - `limited_frontier_challenge`
- Early-stop path exists for parseable/low-uncertainty incumbent.
- Lower challenger cap than v1 budget usage is enforced in v2-thresholded diagnostics.
- Thresholds exist:
  - continuation threshold,
  - commit threshold,
  - replacement threshold.
- Replacement policy is stricter than v1-style simple support replacement (parseability/support/family-support/cheap-verifier checks).
- Ordering policy labels exist for early novelty and later support/challenger-focused ordering.
- No additional gold-answer-derived heuristic is used in route/continuation/replacement decisions (gold is only passed through shared simulator/controller interfaces and used for post-hoc correctness accounting).

## Threshold + ordering logic summary
- Continuation proxy:
  - `continuation_value = quality + novelty + challenge_value - redundancy - cost` (+ uncertainty bonus term)
- Configured thresholds:
  - `continuation_threshold=0.42`
  - `commit_threshold=0.62`
  - `replacement_threshold=0.55`
- Ordering stages logged:
  1. direct incumbent first,
  2. layer-1 semantic novelty/setup diversity,
  3. layers 2-3 uncertainty-adjusted continuation,
  4. post-layer-3 support/challenger/proxy exploitation.

## Metadata fields confirmed
Confirmed in method metadata (when available):
- `route_decision`
- `route_reason`
- `incumbent_parseable`
- `incumbent_confidence_proxy`
- `frontier_opened`
- `direct_actions_used`
- `frontier_actions_used`
- `semantic_family_count`
- `family_redundancy_ratio`
- `families_matured_count`
- `continuation_threshold`
- `commit_threshold`
- `replacement_threshold`
- `top_challenger_answer`
- `final_source`
- `incumbent_replacement_reason`
- `actions_used`

## Lightweight checks run
1. `python -m compileall experiments scripts` ✅
2. `pytest -q tests/test_semantic_diversity_direct_reserve_v2_thresholded_ordered.py` ✅ (5 passed)
3. Tiny registry inspection snippet ✅ (method exists)
4. Tiny offline synthetic smoke snippet ✅ (`route_decision` and `final_source` present)

## Job 1011746 local output availability
- Checked for: `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/`
- Result: **not present locally**.
- Therefore no offline run analysis was executed for that timestamp.

## Remaining risks before Cohere run
- Current validations are simulation/offline only; real-provider cost-accuracy tradeoff remains unverified locally.
- Family maturation/cap behavior should be re-checked on real uncertainty slices.
- Replacement thresholds may still under/over-switch without real Cohere disagreement patterns.

## Recommended next Wulver command (do not run here)
```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --mode cohere \
  --run-live-cohere \
  --timestamp 20260428T_DR_V2_THRESHOLDED_ORDERED_NEXT \
  --methods external_l1_max,strict_f3,direct_reserve_semantic_frontier_v1,direct_reserve_semantic_frontier_v2_thresholded_ordered \
  --budgets 4,6,8
```
