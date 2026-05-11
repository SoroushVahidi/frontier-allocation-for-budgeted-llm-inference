# Direct L1 Strong Seed 15-Case Live Preflight (2026-05-11)

## Purpose

This preflight prepares a future 15-case live diagnostic for the opt-in Direct L1 strong seed method.

It is intentionally **no-API**:

- no Cohere/OpenAI/Anthropic calls
- no live diagnostic execution
- no runtime default change
- no external-baseline claim

## Slice

Tracked exact-case artifact:

- [docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl)

The preflight uses the tracked 15-case slice already present in the repository and validates it deterministically before any future live run is considered.

## Method Comparison

- Baseline: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid`
- Treatment: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1`
- Optional comparator: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`

## What the Preflight Writes

When run without `--dry-run`, the script writes:

- `summary.json`
- `direct_l1_strong_seed_15case_live_preflight_report.md`
- `future_live_command.sh`

The `future_live_command.sh` file contains the exact live command that should be used later if a separate approval is granted.

## Validation Ladder

1. Load and validate the tracked exact-case JSONL.
2. Check method registration and runtime availability without API calls.
3. Build the future live command, but do not run it in this PR.
4. Write a concise summary and markdown report for reviewer inspection.

## Claim Boundaries

- This is a preflight, not a result.
- The live diagnostic is not run here.
- The slice is diagnostic-only.
- No broad method promotion is implied.
