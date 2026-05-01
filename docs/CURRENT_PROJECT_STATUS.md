# Current project status

This document is the short, current orientation note for day-to-day work. It supersedes older broad-status notes for navigation purposes, while dated documents remain provenance.

## Project identity

This repository studies **frontier allocation for budgeted LLM inference** under explicit compute/action-budget contracts.

The core question is:

> Given a fixed inference budget and multiple active reasoning/candidate paths, where should the next unit of compute go, and how should the final answer be selected from the explored frontier?

The active work is no longer the older binary cheap-vs-revise routing story. The current focus is final-answer selection from already-discovered candidate reasoning paths.

## Current phase

**Phase:** selector evidence cleanup and outcome-verifier selector preparation.

The recent selector work established three important facts:

1. There are real **present-not-selected** failures: cases where the correct answer is present in discovered candidate groups/tree evidence but the runtime selector chooses another answer.
2. A conservative non-API selector baseline, `conservative_trace_support_selector_v1`, made zero overrides on the 50-case trace-recovered recovery benchmark, so support/source/trace-count features alone are too conservative for this setting.
3. The unified selector-evidence package builder exists, but the merged unified packages are **not yet selector-ready for the new-cap100 subset**, because that subset currently contributes zero candidate nodes in the unified summary.

## Current evidence packages

### Strongest recovery benchmark

```text
outputs/selector_evidence_trace_recovery_20260501T023200Z/
```

Recorded recovery metrics from the trace-recovery run:

| Metric | Value |
|---|---:|
| input cases | 50 |
| raw records matched | 50 |
| cases with candidate nodes | 50 |
| cases with at least one candidate trace | 50 |
| cases with all candidates traced | 50 |
| extracted candidate-node count | 142 |
| traced candidate-node count | 142 |
| gold present in aggregate answer buckets | 50 |
| gold present in extracted terminal node finals | 46 |
| selected answer present in extracted terminal node finals | 50 |
| Cohere calls used for recovery | 0 |

Important caveat: the committed `candidate_trace_enriched.jsonl` in this package has been observed to contain shell records with empty `candidate_nodes`. The summary claims 142 traced candidates, but the selector-unification path cannot currently recover those candidates from the committed package. Treat this as a source-package writing/retention issue to fix before using the package as unified selector input.

### Conservative selector negative baseline

```text
outputs/conservative_trace_support_selector_20260501T025615Z/
```

Result on the 50-case recovery package:

| Metric | Value |
|---|---:|
| total cases | 50 |
| current incumbent accuracy | 0.0 |
| oracle ceiling on package | 0.92 |
| recoverable trace-terminal cases | 46 |
| total overrides | 0 |
| fixes | 0 |
| gold-terminal failures not chosen | 46 |

Interpretation: `conservative_trace_support_selector_v1` is a valid deterministic no-API baseline, but it is a negative baseline. It shows that conservative support/source/trace gating does not recover the available headroom.

### Unified selector evidence packages

Unified packages were generated under:

```text
outputs/unified_selector_evidence_*/
```

Current caveat: the latest merged unified package family still shows the `new_cap100_trace_recovery` provenance with:

```text
candidate_nodes = 0
traced_candidate_nodes = 0
usable_for_trace_aware_selector = 0
```

Therefore the unified package is useful as a diagnostic artifact and builder scaffold, but **not yet the canonical selector-training/evaluation input** for outcome-verifier work.

## Current blocker

The immediate blocker is not the outcome-verifier selector itself. It is the source evidence retention issue:

> The trace-recovery summary reports 142 traced new-cap100 candidates, but the committed candidate-trace JSONL available to the unified builder contains empty candidate lists.

The next useful task is to fix `scripts/recover_selector_evidence_traces.py` or regenerate the source trace-recovery package so that `candidate_trace_enriched.jsonl` actually contains the recovered `candidate_nodes` and `verifier_input.candidates_for_verifier`.

## Next recommended action

1. Fix/regenerate the trace-recovery package so the committed JSONL contains the 142 recovered candidate nodes.
2. Rebuild unified selector evidence from the corrected trace-recovery package plus focused33.
3. Confirm the unified summary shows:

```text
new_cap100_trace_recovery candidate_nodes = 142
new_cap100_trace_recovery traced_candidate_nodes = 142
new_cap100_trace_recovery usable_for_trace_aware_selector = 50
```

4. Rerun `conservative_trace_support_selector_v1` on the corrected unified package.
5. Implement the outcome-verifier selector with a dry-run call plan before any paid API scoring.

## API-cost policy

Paid APIs are allowed only when the exact method, dataset, budget, seed, and expected call count are known.

For selector work:

1. Use existing candidate pools first.
2. Dry-run verifier-call count before paid scoring.
3. Cache every verifier score.
4. Do not regenerate answers merely to test selectors.
5. Keep verifier inputs gold/oracle-free.

## Safe claim boundary

Safe:

- The repository contains real selector-evidence artifacts and tools for present-not-selected recovery analysis.
- The 50-case recovery benchmark indicates substantial oracle headroom in discovered candidate sets.
- The conservative trace-support selector is a negative baseline and motivates outcome-verifier selection.
- The unified-evidence builder exists, but its current merged outputs expose a retention/schema problem for new-cap100 candidates.

Not safe yet:

- Do not claim a current selector beats `external_l1_max` robustly.
- Do not claim the merged unified packages are fully trace-aware for the new-cap100 subset.
- Do not claim outcome-verifier selection works until cached verifier scores are actually evaluated.
- Do not treat diagnostic/bug-revealing artifacts as paper-facing evidence without updating the source-of-truth docs.

## Important documents

- `docs/DOCS_INDEX.md` — active vs diagnostic vs historical document map.
- `docs/REPO_MAP.md` — repository structure and selector-phase reading path.
- `docs/SELECTOR_WORK_START_HERE_20260501.md` — selector artifact orientation.
- `docs/SELECTOR_CHOOSING_PLAYBOOK_20260501.md` — selector family decision checklist.
- `docs/SELECTOR_EVIDENCE_RETENTION_POLICY_20260501.md` — what to commit from selector evidence packages.
- `docs/FAST_SELECTOR_EXECUTION_POLICY.md` — cost-aware execution policy.
- `docs/PAPER_SOURCE_OF_TRUTH.md` — claim-eligible evidence rules.

## One-sentence status

The repository is ready for outcome-verifier selector work only after the new-cap100 trace-recovery package is corrected so its committed JSONL contains the 142 recovered candidate traces that its summary reports.
