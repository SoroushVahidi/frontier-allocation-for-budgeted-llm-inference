# Diverse Anchor No-API Audit (2026-05-10)

## Executive summary

This audit checked the diverse-anchor scaffolding before any live/API diagnostic. It used only mocked and simulated generators and wrote reproducible text artifacts under `docs/project_handoff_20260510/`.

**Result:** the diverse-anchor method is registered, builds without API keys, runs in simulated/mocked mode, emits the required diversity/collapse metadata, preserves Direct L1 Anchor behavior, and leaves a measurable remaining frontier budget after the early anchor phase in the forced-frontier smoke case.

No paid/API calls were made.

## Exact method ID

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor
```

The method is registered through the normal `build_frontier_strategies(...)` path as a `DirectReserveDiverseRootFrontierV1GuardedController` with:

- `enable_direct_hybrid_seed=True`
- `enable_diverse_prompt_anchors=True`
- `diverse_prompt_anchor_budget_actions=1`

## Audit command and artifacts

Command:

```bash
python3 scripts/audit_diverse_anchor_scaffolding_no_api_20260510.py
```

Artifacts:

- JSON: `docs/project_handoff_20260510/diverse_anchor_no_api_audit_20260510.json`
- CSV: `docs/project_handoff_20260510/diverse_anchor_no_api_audit_20260510.csv`

The script temporarily removes common API-key environment variables for the registration check and uses `use_openai_api=False`, mocked generators, and simulated generators only.

## Questions answered

### Is the new diverse-anchor method fully registered?

Yes. The registry check confirms the exact method ID is present in `build_frontier_strategies(...)` output and builds as `DirectReserveDiverseRootFrontierV1GuardedController`.

### Does it run without API keys?

Yes. The audit removed these API environment variables for the registration/simulated-run check:

- `OPENAI_API_KEY`
- `COHERE_API_KEY`
- `CO_API_KEY`
- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`

The simulated run completed without error and reported `simulated_run_without_api_keys=true`.

### Does it produce all required metadata?

Yes. All 4 mocked audit cases reported the required metadata fields:

- `diverse_prompt_anchor_metadata`
- `per_anchor_support`
- `candidate_pool_answer_group_count`
- `answer_group_entropy`
- `frontier_collapse_detected`
- `direct_l1_anchor_present`
- `selector_candidate_pool`
- `answer_group_support_counts`

The audit also records `gold_in_pool` in the artifact to demonstrate that future live runs can measure gold-in-pool rate from the candidate pool.

### Does it increase answer-group diversity in mocked/simulated cases?

Yes in the configured diversity smoke cases. The mocked cases used the five configured anchors:

- `direct_l1_anchor`
- `equation_first_anchor`
- `unit_ledger_money_anchor`
- `ratio_percentage_anchor`
- `backward_check_anchor`

Observed candidate answer-group counts:

| case_id | candidate groups | entropy | collapse detected |
|---|---:|---:|---|
| `diverse_groups` | 6 | 1.7917594692280547 | false |
| `duplicate_merge` | 2 | 0.45056120886630463 | false |
| `frontier_collapse` | 1 | 0.0 | true |
| `frontier_budget_preservation` | 7 | 1.945910149055313 | false |

The `frontier_collapse` case intentionally returns one repeated wrong answer to verify that the low-diversity flag fires.

### Does it preserve Direct L1 Anchor behavior?

Yes. All 4 mocked cases reported `direct_l1_anchor_present=true`. The duplicate-merge case confirmed that duplicate anchor answers merge into the same normalized answer group rather than creating duplicate groups: answer `20` accumulated support 5 from the Direct L1 Anchor plus four additional anchors, while candidate answer-group count remained 2.

### Does it preserve PAL/frontier protection behavior?

The existing targeted tests still pass, including the focused selector/commitment/PAL/frontier-tiebreak test selection. The diverse-anchor test suite also includes a direct assertion that strong PAL conflict protection still blocks takeover against a supported peer group.

### Is it ready for a small live diagnostic later?

Yes, with caveats. The method is ready for a small **approved** live/API diagnostic to measure candidate-pool diversity and gold-in-pool rate. This audit does not prove live accuracy and makes no claim against `external_l1_max`.

## Key audit metrics

Aggregate metrics from `diverse_anchor_no_api_audit_20260510.json`:

- Cases: 4
- Registered in normal method builder: true
- Builds without API keys: true
- Simulated run without API keys: true
- All required metadata present: true
- Direct L1 Anchor present in all mocked cases: true
- Duplicate merge case passed: true
- Collapse case detected: true
- Frontier budget preservation case passed: true
- Minimum candidate answer-group count: 1
- Maximum candidate answer-group count: 7
- API calls made: 0

## Frontier budget preservation check

The forced-frontier smoke case used a mock action budget of 12. It spent:

- 1 action on direct reserve;
- 1 action on the Direct L1/hybrid seed;
- 4 actions on the remaining configured anchors.

Expected frontier budget after anchors: `12 - 1 - 1 - 4 = 6`.

Observed frontier factory budget: `6`.

Therefore the audit confirms the early anchor phase preserves the expected remaining frontier budget in the forced-frontier mocked path.

## Caveats

- This is a no-API mocked/simulated audit, not a live model result.
- The diversity gains in the mocked cases are constructed to verify instrumentation behavior, not to estimate real accuracy.
- `answer_group_entropy` is a simple support-count entropy metric; it is useful for collapse diagnostics but is not a semantic diversity classifier.
- More anchors reduce remaining frontier depth under a fixed budget, so live diagnostics should report both diversity and remaining frontier budget.

## Recommended later live diagnostic — do not run without approval

Run a matched, failure-focused live diagnostic only after explicit API approval:

- Cases: 30 to 50 cases sampled from the latest gold-absent/frontier-collapse casebook, stratified across money/cost/revenue, multi-step arithmetic, and ratio/proportion/percentage.
- Methods: compare the current direct-hybrid or production-equivalent line against `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor` on the same examples.
- Anchor budget: 5 anchors per case at one action each.
- Expected incremental anchor calls: 150 to 250 calls for anchor generation (`30–50 cases × 5 anchors`), plus the matched baseline/controller calls needed by the existing evaluation contract.
- Report: gold-in-pool rate, candidate answer-group count, answer-group entropy, collapse rate, Direct L1 Anchor present rate, remaining frontier budget, and exact match under the existing selector/tiebreak contract.

No such live/API diagnostic was run in this audit.
