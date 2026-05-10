# Suspicious / high-risk areas

## 1. `experiments/controllers.py` size (~+880 LOC in diff)

Not limited to PAL: the merged `DirectReserveFrontierGateController` now sequences **optional** pre-frontier seeds for **decomp_eq → opcheck → pal → unit_track → direct_hybrid** (when respective flags/budget/gate conditions hold).

- **Risk:** Any bug in shared `run()` (budget accounting, ordering, metadata keys) affects **all** guarded K1/tiebreak family controllers, not only `_pal`.
- **Mitigation evidence:** Offline suite previously reported **82/82** pass; spot-check **`test_baseline_k1_tiebreak_unchanged_without_pal_fields`** and **`test_external_l1_max_still_registered`** re-ran green in this review.
- **Conclusion:** Functionally corroborated, but reviewers should still skim `run()` around `remaining_budget` and seed blocks.

## 2. `gold_answer` threaded into `_run_pal_seed_attempt`

`generator.expand(branch, prompt, gold_answer)` matches the generator protocol used everywhere (including simulation). **`execute_pal_code` itself is gold-independent** (sandbox over model-produced `pal_code`).

Residual risk: accidental future use of `gold_answer` inside PAL scoring — **not observed** in `_run_pal_seed_attempt` beyond the expand call signature.

## 3. Evaluator-time PAL integration default **on** for `*_tiebreak_pal`

`--pal-residual-strong-integration-fix` defaults to **True** and applies in the runner when the method id contains **`tiebreak_pal`**.

- **Boundary:** Post-hoc repaired answer / diagnostics for scoring bundles — **not** the controller’s runtime branch expansion.
- **Risk:** Could surprise someone comparing raw `final_answer` vs repaired fields on historical JSONL if they did not expect evaluator-side alignment.

## 4. Duplicate / noisy untracked `outputs/` directories

Multiple `outputs/cohere_real_model_cost_normalized_validation_*` trees are present (validator side effects). **No secrets** matched a quick diff scan for credential-like tokens (empty result).

## 5. `branching.py` PAL field aliasing

`pal_json_answer` is taken from merge key `answer` (generic). Correct for PAL JSON schema; harmless for other prompts if those keys absent.
