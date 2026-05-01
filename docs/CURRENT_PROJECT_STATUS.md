# Current project status

This document is the short, current orientation note for day-to-day work. It supersedes older broad-status notes for navigation purposes, while dated documents remain provenance.

## Project identity

This repository studies **frontier allocation for budgeted LLM inference** under explicit compute/action-budget contracts.

The core question is:

> Given a fixed inference budget and multiple active reasoning/candidate paths, where should the next unit of compute go, and how should the final answer be selected from the explored frontier?

The active work is no longer the older binary cheap-vs-revise routing story. The current emphasis is final-answer selection from already-discovered candidate reasoning paths, followed by discovery/coverage improvements once selector baselines are sufficiently stable.

## Current phase

**Phase:** selected-selector validation, literature-baseline comparison, real-model comparison tooling, and L1-loss bottleneck diagnosis.

The recovery-track selector-choosing milestone is complete. The current selected working selector is the Cohere cached outcome-verifier answer-group selector:

```text
outcome_verifier_answer_group_selector_v1
scorer_mode = cached_jsonl
min_verifier_margin = 0.0
require_trace_for_override = true
dedupe_verifier_items = true
no_gold_features = true
```

Canonical config:

```text
configs/selected_selector_current.json
```

This selector is selected for the **recovery / selector-evidence track only**. It is not runtime-promoted.

For current evidence classification, read:

```text
docs/CURRENT_EVIDENCE_LEDGER_20260501.md
```

## Current selected-selector evidence

Final selector decision package:

```text
outputs/final_selector_decision_20260501T175547Z/
```

Passing selected-selector audit package:

```text
outputs/selected_selector_audit_20260501T181608Z/
```

The selected recovery-track result is:

| Selector | Cases | Overrides | Fixes | Breaks | Net | Accuracy | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| `conservative_trace_support_selector_v1` | 47 | 0 | 0 | 0 | 0 | 0.0000 | rejected fallback |
| outcome verifier + `trace_quality_heuristic` | 47 | 36 | 20 | 0 | +20 | 0.4255 | runner-up |
| outcome verifier + Cohere `cached_jsonl` | 47 | 42 | 21 | 0 | +21 | 0.4468 | selected |

The audit confirms that the selected config reproduces the expected metrics, uses a clean 94/94 cache join, keeps call-plan/score rows gold-free, and retains the explicit non-runtime-promotion scope boundary.

Important recovery fact: among gold-terminal cases in this package, the selected verifier recovered `21 / 29`, leaving `8 / 29` gold-present terminal cases still not chosen.

## Literature selector baseline status

The self-consistency majority-vote selector baseline has been added as a literature-grounded, no-API comparison family.

Canonical implementation/documentation:

```text
experiments/self_consistency_majority_selector.py
scripts/run_self_consistency_majority_selector.py
docs/LITERATURE_SELECTOR_BASELINES.md
```

Use self-consistency as a baseline over existing candidate pools. It is not a new method contribution and should be compared against the selected verifier selector only on matched paired slices.

The self-verification / condition-mask-verification baseline has also been implemented as a literature-baseline scaffold. The committed pilot/tooling should **not** be treated as performance evidence unless a future run has nonzero/full CMV coverage.

## External-baseline comparison status

A bounded 100-case GSM8K comparison against `external_l1_max` was added under:

```text
outputs/best_selector_vs_external_l1_comparison_*/
```

That run is **cache-limited**: most paired-set candidates did not have verifier scores, so the selected selector mostly fell back to original DR-v2. Treat it as diagnostic until a fully scored paired comparison is available.

A 100-case Cohere ours-vs-main-table-external comparison scaffold was also added under:

```text
outputs/cohere_100case_ours_vs_external_20260501T000000Z/
```

That package is **not evidence-bearing**: it was a dry-run/scaffold package with zero actual Cohere calls. Do not cite its accuracy or pairwise rows as results.

A fully scored pilot is the correct next step for claim-safe comparison because it must satisfy:

```text
missing_candidate_score_count = 0
fallback_to_incumbent_due_to_missing_scores = 0
selected_candidate_not_in_pool_count = 0
```

## L1-loss decomposition status

The repository now contains tooling for the exact bottleneck question:

```text
scripts/run_l1_loss_decomposition_for_best_selector.py
docs/L1_LOSS_DECOMPOSITION_BEST_SELECTOR_RESULT.md
```

Known output classes:

- `outputs/l1_loss_decomposition_best_selector_20260501T000000Z/` — blocked/non-evidence; initial readiness blocker.
- `outputs/l1_loss_decomposition_best_selector_20260501T010000Z/` — blocked/non-evidence; readiness passed, artifacts incomplete.
- `outputs/l1_loss_decomposition_best_selector_20260501T023500Z/` — real diagnostic plumbing output, but only `total_paired_cases = 1` and no L1-correct/ours-wrong losses.

The full statistic is **not complete yet**. The project still needs a larger paired run, preferably 100 paired real-Cohere cases, to answer whether remaining L1 losses are mostly gold-absent-from-tree or gold-present-but-not-selected.

## Current bottleneck hypothesis

For selector work, distinguish three cases:

| Case type | Interpretation |
|---|---|
| gold present in candidate tree but not chosen | selector bottleneck |
| gold absent from candidate tree | discovery/coverage bottleneck |
| current answer correct but selector overrides wrongly | runtime safety / break-risk bottleneck |

The selected verifier selector reduced the recovery-track selector bottleneck. The next paired experiments should determine whether remaining wrong cases are now dominated by discovery/coverage, selection mistakes, or missing instrumentation.

## Current selector baselines

Because answer-quality selection is a broad research problem, the project should prefer published, defensible selector baselines rather than inventing complicated new selectors.

Current/near-term selector baselines:

1. Outcome-verifier / best-of-N verifier reranking — current selected family.
2. Self-consistency majority vote — implemented literature baseline.
3. Self-verification / CMV — implemented scaffold, not evidence-complete.
4. Process-reward / step-verifier reranking — available as a development comparator where completed artifacts exist.

The main project contribution should remain discovery/budget allocation, not a novel answer-quality selector.

## API-cost policy

Paid APIs are allowed only when the exact method, dataset, budget, seed, and expected call count are known.

For selector and L1-loss-decomposition work:

1. Use existing candidate pools first.
2. Dry-run verifier-call count before paid scoring.
3. Cache every verifier score.
4. Do not regenerate answers merely to test selectors.
5. Keep verifier inputs gold/oracle/evaluation-only free.
6. Immediately report score coverage and fallback counts for paired comparisons.
7. If a run is blocked or cap-limited, label it diagnostic/non-evidence rather than writing fake accuracy rows.

## Safe claim boundary

Safe:

- The repository has an audited selected selector for the recovery selector-evidence track.
- The selected Cohere cached verifier selector beat conservative and trace-quality selector baselines on the recovery package.
- The self-consistency majority-vote literature baseline exists for matched-slice comparison.
- The 100-case external comparison script exists, but its first selected-verifier run is cache-limited and diagnostic.
- The L1-loss-decomposition tooling exists and has been smoke-validated on a one-paired-case real diagnostic, but the full statistic is not complete.

Not safe yet:

- Do not claim robust/universal superiority over `external_l1_max`.
- Do not claim runtime promotion of the selected selector.
- Do not treat cache-limited paired comparisons as real selected-selector comparisons.
- Do not compare selector families using unmatched slices as headline evidence.
- Do not claim selector errors are solved until fully scored paired pilots quantify gold-present-but-not-selected cases.
- Do not treat dry-run or blocked Cohere packages as results.
- Do not treat the one-case L1-loss-decomposition diagnostic as answering the bottleneck question.
- Do not treat diagnostic/bug-revealing artifacts as paper-facing evidence without updating the source-of-truth docs.

## Next recommended action

1. Complete a paired L1-loss-decomposition run at the largest feasible real-Cohere case count, preferably 100 paired cases.
2. Use that decomposition to decide whether the dominant remaining bottleneck is gold absent from the tree, gold present but not selected, or missing traces/instrumentation.
3. Run a fully scored paired selector comparison against `external_l1_max` with zero missing selector scores.
4. Compare self-consistency and the Cohere outcome-verifier selector on the same paired cases.
5. If selector errors are no longer dominant, move effort to discovery/coverage.

## Important documents

- `docs/CURRENT_EVIDENCE_LEDGER_20260501.md` — current evidence vs diagnostic/scaffold ledger.
- `docs/REPO_ORGANIZATION_GUIDE_20260501.md` — clean navigation and cleanup rules.
- `docs/CURRENT_SELECTOR_DECISION.md` — selected selector config and caveats.
- `docs/LITERATURE_SELECTOR_BASELINES.md` — literature-grounded selector baselines.
- `docs/L1_LOSS_DECOMPOSITION_BEST_SELECTOR_RESULT.md` — current L1-loss-decomposition status.
- `docs/DOCS_INDEX.md` — active vs diagnostic vs historical document map.
- `docs/REPO_MAP.md` — repository structure and selector-phase reading path.
- `docs/SELECTOR_WORK_START_HERE_20260501.md` — selector artifact orientation.
- `docs/SELECTOR_CHOOSING_PLAYBOOK_20260501.md` — selector family decision checklist.
- `docs/FAST_SELECTOR_EXECUTION_POLICY.md` — cost-aware execution policy.
- `docs/PAPER_SOURCE_OF_TRUTH.md` — claim-eligible evidence rules.

## One-sentence status

The repository has an audited recovery-track selected verifier selector and several comparison/bottleneck tools, but it still lacks the clean larger paired real-Cohere decomposition needed to know whether the remaining L1 gap is mainly discovery/coverage or selection.
