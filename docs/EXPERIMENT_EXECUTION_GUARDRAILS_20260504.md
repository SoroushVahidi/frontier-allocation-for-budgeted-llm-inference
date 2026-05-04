# Experiment execution guardrails — 2026-05-04

Purpose: prevent expensive or misleading runs by making the current method target, old-script traps, and API approval rules explicit.

## Current merged state

- PR #351 is merged: diverse-root frontier v1, guarded held-out evaluation, API parsing hardening, and candidate extraction diagnostics are on `main`.
- PR #353 is merged: cached verifier selector replay tooling is on `main`.
- The old strict-F3 diagnostic tooling remains useful as reference history, but it is not the current-best comparison target.

## Current method target for new real-model comparisons

When testing against `external_l1_max`, the internal target should be the newest live-runnable method stack, not the old manuscript-facing strict-F3 anchor.

Primary target:

```text
direct_reserve_diverse_root_frontier_v1_guarded
```

Optional supporting targets:

```text
direct_reserve_diverse_root_frontier_v1
cached verifier selector replay at tau ~= 0.05, only when score coverage is complete and runtime-legal
```

Reference anchors only:

```text
strict_f3
strict_gate1_cap_k6
strict_f2
```

These older methods may be useful for historical continuity, but they do not answer the question “does our current best method close the `external_l1_max` gap?”

## Known script trap

The following script is intentionally old-scope:

```text
scripts/run_cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic.py
```

It is hardwired around `strict_f3`, `external_l1_max`, and optionally `strict_gate1_cap_k6`. Do not use it as the decisive current-best comparison. If it is used, label the result as an old strict-F3 reference diagnostic.

## Diverse-root guarded runners

Simulator/no paid API held-out comparison:

```text
scripts/run_gsm8k_held_out_dr_comparison.py
```

Real-generation capable guarded diverse-root runner:

```text
scripts/run_diverse_root_frontier_v1_66_eval_with_guarded.py
```

This runner supports:

```text
--real-generation
--api-provider cohere
--cohere-model command-a-03-2025
--max-total-api-calls N
```

It was built around the 66-case diagnostic path, so a 100-case fair comparison against `external_l1_max` should first perform a dry-run and verify the exact case-list adapter before any Cohere calls.

## API approval rule

No paid/API run should begin until a dry-run report states:

1. exact case set;
2. exact method IDs;
3. whether completed `external_l1_max` outputs can be reused;
4. new Cohere call count required;
5. HF access needed or not;
6. output directory;
7. abort conditions.

The operator must explicitly approve the call budget before any Cohere calls.

## Stop rule during runs

If a run starts an unintended method, stop before the next method begins. Prefer graceful termination:

```bash
kill -INT <pid>
sleep 10
kill -TERM <pid>   # only if still running
```

Do not use `kill -9` unless the process refuses to stop and partial artifacts are already acceptable.

## Corrected fair-comparison plan template

A corrected dry-run should compare:

```text
external_l1_max
vs direct_reserve_diverse_root_frontier_v1_guarded
```

Optionally add:

```text
direct_reserve_diverse_root_frontier_v1
guarded + cached verifier selector tau ~= 0.05, only if fully score-covered
```

Do not include old strict methods as the main target.

## Output hygiene

- Timestamped `outputs/` directories are provenance; do not delete them during cleanup.
- Do not commit caches, raw API responses, logs, token files, `.env`, or provider secrets.
- For new diagnostic outputs, write manifest, planned-calls file, and report before executing paid calls.

## Concise status phrase

Use this when handing off to another agent:

```text
Current goal: compare external_l1_max against direct_reserve_diverse_root_frontier_v1_guarded, not old strict_f3. PR #351 and PR #353 are merged. Produce a no-API dry-run and get call-budget approval before any Cohere calls.
```
