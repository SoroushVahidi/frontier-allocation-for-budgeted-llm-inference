# Selector Choosing Playbook (2026-05-01)

This is the decision checklist for choosing the next selector after the repository-polish pass. It complements `SELECTOR_WORK_START_HERE_20260501.md`; it does not replace the artifact index or evidence rules.

## Goal

Choose a selector that converts already-discovered DR-v2 candidate groups into a safer final answer decision, without regenerating answers and without using gold/oracle labels in the deployable rule.

## Current decision frame

The selector track should optimize for **safe override quality**, not raw override count.

A candidate selector is useful only if it can distinguish:

- recoverable present-not-selected cases, where the correct answer is present in candidate groups but not selected;
- current-correct cases, where an override would break a correct DR-v2 commitment;
- coverage failures, where the correct answer is not present in the trace-preserved candidate set and no selector can recover it.

## Candidate selector families to compare

| Priority | Family | Purpose | Promotion status |
|---:|---|---|---|
| 1 | Cached outcome verifier over answer groups | Estimate candidate correctness directly from problem + trace + final answer. | Current first serious candidate. |
| 2 | Conservative verifier override | Keep DR-v2 by default and override only with a clear verifier margin. | Preferred if verifier scoring is noisy. |
| 3 | Support/source/consistency heuristic | Cheap diagnostic baseline and ablation. | Do not promote unless it beats verifier variants on fixes/breaks. |
| 4 | Pairwise verifier selector | Compare incumbent vs challenger when absolute scores are poorly calibrated. | Next fallback after outcome verifier. |
| 5 | PRM / step verifier rerank | Diagnose trace quality and process errors. | Higher-cost follow-up, not first selector choice. |

## Minimum artifact inputs

Start with the focused trace-enriched selector artifact:

```text
outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enriched.jsonl
```

Also keep the 50-case compact tournament artifact in view for broader paired selector comparisons:

```text
outputs/selector_tournament_compact_export_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/
```

## Required run modes

Every selector runner should support these modes:

1. **Dry-run call plan** — no paid API calls; report candidate count, verifier-call upper bound, cache hits, missing traces, and expected cost.
2. **Cached scoring** — call only uncached verifier prompts; append stable cache records.
3. **Tournament export** — write compact CSV/JSON summaries suitable for selector tournament comparison.
4. **Casebook export** — write per-case fix/break/no-op decisions with human-readable reasons.

## Selector acceptance criteria

Do not choose a selector for runtime validation unless it satisfies all of the following on the current offline artifact:

- no gold/oracle fields in prompts or deployable decision features;
- positive net fixes-minus-breaks over current DR-v2;
- override precision materially above the best support/source heuristic;
- current-correct break count is bounded and inspectable;
- coverage failures are separated from selector failures;
- cache manifest and verifier backend are recorded;
- result is reproducible from a documented input artifact.

## Report table template

Every selector comparison should include:

| Selector | Accuracy | Δ vs DR-v2 | Δ vs external_l1_max | Overrides | Fixes | Breaks | Net | Override precision | Backend | Claim class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| current_dr_v2 |  |  |  |  |  |  |  |  | none | baseline |
| external_l1_max |  |  |  |  |  |  |  |  | external | baseline |
| support/source heuristic |  |  |  |  |  |  |  |  | none | diagnostic |
| cached outcome verifier |  |  |  |  |  |  |  |  | cohere/mock/etc. | diagnostic until promoted |
| conservative verifier override |  |  |  |  |  |  |  |  | cohere/mock/etc. | diagnostic until promoted |
| oracle selector |  |  |  |  |  |  |  |  | oracle | ceiling only |

## Immediate next work item

Run or adapt the cached outcome-verifier selector so it ingests `focused33_trace_enriched.jsonl` directly and emits:

- `verifier_call_plan.json` or `.jsonl`;
- `verifier_cache.jsonl`;
- `selector_summary.csv` and `.json`;
- `selector_casebook.csv` or `.jsonl`;
- `selector_choice_report.md`.

Only after the dry-run call plan is reviewed should a paid verifier backend be used.

## Guardrails

- Do not regenerate candidate answers merely to test selectors.
- Do not call answer-only verification Cobbe-style full-solution verification.
- Do not interpret mock-backed verifier scoring as real verifier evidence.
- Do not claim broad defeat of `external_l1_max` from focused33 alone.
- Do not delete, overwrite, or rename timestamped output artifacts during selector choosing.
