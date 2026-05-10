# Main-Table External Baselines Implementation Report

## Added now
- external_l1_max_fair_v1
- external_self_consistency_4_fair_v1
- external_self_consistency_6_fair_v1
- external_pal_pot_fair_v1
- external_s1_budget_forcing_faithful_v1
- external_tale_ep_prompt_budgeting_faithful_v1

## Live-ready vs dry-run-only
- Live-ready in registry/runtime: all six IDs resolve via build_frontier_strategies and validate-methods-only.
- Caveat: PAL/PoT fair depends on generator capability (`generate_program_of_thought_answer`); otherwise returns explicit metadata error path.

## Known deviations
- TALE-EP remains EP-only style adapter (not TALE-PT).
- S1 remains behavior-level adapter (not full official stack parity).
- L1 fair is transparent comparator, not official reproduction.

## Recommended rerun ladder
1. Run no-API call-plan + method resolution checks (done).
2. Run small budget-4/6 live baseline-only sanity run.
3. Run matched 50-case baseline rerun and refresh claim tables.
4. Re-evaluate wording for stronger claims only if parity evidence improves.
