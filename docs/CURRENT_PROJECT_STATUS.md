# Current project status

This document is the short, current orientation note for day-to-day work. It supersedes older broad-status notes for navigation purposes, while dated documents remain provenance.

## Current navigation (2026-05-02 cleanup)

For a **short** entry point and claim guardrails, read [`../START_HERE_CURRENT.md`](../START_HERE_CURRENT.md). Method IDs: [`METHOD_STATUS_TABLE.md`](METHOD_STATUS_TABLE.md). Major `outputs/` folders: [`ARTIFACT_STATUS_TABLE.md`](ARTIFACT_STATUS_TABLE.md). Commands: [`../scripts/CURRENT_RUNBOOK.md`](../scripts/CURRENT_RUNBOOK.md). Audit log: [`REPOSITORY_HYGIENE_AUDIT_20260502.md`](REPOSITORY_HYGIENE_AUDIT_20260502.md). **Recent Wulver diagnostics / last-10 job audit:** [`LAST_10_WULVER_JOBS_AUDIT_20260502.md`](LAST_10_WULVER_JOBS_AUDIT_20260502.md) (`outputs/last_10_wulver_jobs_audit_20260502T220857Z/artifact_summary.md`).

Interpretation aides: **`external_l1_max` gap** → [`CURRENT_EXTERNAL_BASELINE_GAP.md`](CURRENT_EXTERNAL_BASELINE_GAP.md). **Negative / superseded indexing** → [`FAILED_AND_NEGATIVE_RESULTS_INDEX.md`](FAILED_AND_NEGATIVE_RESULTS_INDEX.md). **Discovery vocabulary** → [`DISCOVERY_FAILURE_TAXONOMY.md`](DISCOVERY_FAILURE_TAXONOMY.md). **Git retention** → [`OUTPUT_RETENTION_POLICY_CURRENT.md`](OUTPUT_RETENTION_POLICY_CURRENT.md). **Workspace-only cleanup brainstorming** → [`LOCAL_ONLY_CLEANUP_CANDIDATES_20260502.md`](LOCAL_ONLY_CLEANUP_CANDIDATES_20260502.md).

## Bounded external-loss diagnostics (2026-05-02)

Slurm job **1018248** completed a **zero-missing** verifier score fill and selected-selector rerun on the **88** paired external-loss slice (`outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/`). **`summary.json`:** `evaluated_cases = 88`, `correct_count = 19`, `still_lost_count` / `wrong_count = 69`, `missing_score_count = 0`, `fallback_due_to_missing_score_count = 0`, `selected_candidate_not_in_pool_count = 0`, `discovery_failure_count` / `gold_absent_count = 66`, `gold_present_but_not_selected_count = selector_recoverable_count = 22`. **`comparison_vs_previous_run.json`** reports **no correctness flips versus 1018219** after score merge. **Claim-safety:** intentional external-loss subset only—not broad superiority over **`external_l1_max`** or runtime promotion claims.

Slurm **1018287** produced the **preferred** gold-absent path-gap diagnostic with a tightened premature-commit heuristic (`outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/`; supersedes `...215820Z` / **1018285**).

Slurm **1018203** finished cleanly in artifact terms (`outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/summary.json` reports `status:"ok"`). Caveated headline on the recorded **narrow 100-case** GSM8K slice (seed **`20260501`**, budget **6** vs prior last-10 audit freeze): **`external_l1_max` = 0.92**, best internal **`strict_gate1_cap_k6` = 0.57**, gap **≈ −0.35**. **Not** a universal GSM8k claim — use only with manifests + bounded framing; strengthens **diagnostic** evidence that curated internal headline **rails below `external_l1_max`** on this pairing.

Slurm **1018304** ran the **`strategy_seeded_semantic_diversity_frontier_v1`** pilot on the intentional **66** gold-absent diagnostic (`outputs/strategy_seeded_discovery_on_66_gold_absent_20260502T222129Z/` — curated summaries tracked in Git). Produced summary counts show **fewer gold-present outcomes vs cached DR‑v2 baseline** on that diagnostic definition; treat as **method pilot + alignment caveat** — **baseline alignment / implementation auditing** unfinished; **repeat / final audit** recommended before narrative closure.

Code and batch entry points: `scripts/diagnose_gold_absent_path_gap.py`, `experiments/gold_absent_path_gap.py`, `batch/run_gold_absent_path_gap_diagnostic_wulver.sbatch`, `batch/run_strategy_seeded_discovery_on_66_gold_absent_wulver.sbatch`, `scripts/run_strategy_seeded_discovery_on_66_gold_absent.py`.

## Project identity

This repository studies **frontier allocation for budgeted LLM inference** under explicit compute/action-budget contracts.

The core question is:

> Given a fixed inference budget and multiple active reasoning/candidate paths, where should the next unit of compute go, and how should the final answer be selected from the explored frontier?

The active work is no longer the older binary cheap-vs-revise routing story. The current emphasis is final-answer selection from already-discovered candidate reasoning paths, followed by discovery/coverage improvements once selector baselines are sufficiently stable.

## Current phase

**Phase:** selected-selector validation, literature-baseline comparison, and fully scored paired comparison planning.

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

## Literature selector baseline status

The self-consistency majority-vote selector baseline has been added as a literature-grounded, no-API comparison family.

Canonical implementation/documentation:

```text
experiments/self_consistency_majority_selector.py
scripts/run_self_consistency_majority_selector.py
docs/LITERATURE_SELECTOR_BASELINES.md
```

Use self-consistency as a baseline over existing candidate pools. It is not a new method contribution and should be compared against the selected verifier selector only on matched paired slices.

## External-baseline comparison status

A bounded 100-case GSM8K comparison against `external_l1_max` was added under:

```text
outputs/best_selector_vs_external_l1_comparison_*/
```

That run is **cache-limited**: most paired-set candidates did not have verifier scores, so the selected selector mostly fell back to original DR-v2. Treat it as diagnostic until a fully scored paired comparison is available.

A fully scored pilot is the correct next step for claim-safe comparison because it must satisfy:

```text
missing_candidate_score_count = 0
fallback_to_incumbent_due_to_missing_scores = 0
selected_candidate_not_in_pool_count = 0
```

## Current bottleneck hypothesis

For selector work, distinguish three cases:

| Case type | Interpretation |
|---|---|
| gold present in candidate tree but not chosen | selector bottleneck |
| gold absent from candidate tree | discovery/coverage bottleneck |
| current answer correct but selector overrides wrongly | runtime safety / break-risk bottleneck |

The selected verifier selector reduced the recovery-track selector bottleneck. The next paired experiments should determine whether remaining wrong cases are now dominated by discovery/coverage or by selector mistakes.

## Current selector baselines

Because answer-quality selection is a broad research problem, the project should prefer published, defensible selector baselines rather than inventing complicated new selectors.

Current/near-term selector baselines:

1. Outcome-verifier / best-of-N verifier reranking — current selected family.
2. Self-consistency majority vote — implemented literature baseline.
3. Process-reward / step-verifier reranking — possible later baseline if needed.
4. Self-verification / backward verification — possible later baseline if needed.

The main project contribution should remain discovery/budget allocation, not a novel answer-quality selector.

## API-cost policy

Paid APIs are allowed only when the exact method, dataset, budget, seed, and expected call count are known.

For selector work:

1. Use existing candidate pools first.
2. Dry-run verifier-call count before paid scoring.
3. Cache every verifier score.
4. Do not regenerate answers merely to test selectors.
5. Keep verifier inputs gold/oracle/evaluation-only free.
6. Immediately report score coverage and fallback counts for paired comparisons.

## Safe claim boundary

Safe:

- The repository has an audited selected selector for the recovery selector-evidence track.
- The selected Cohere cached verifier selector beat conservative and trace-quality selector baselines on the recovery package.
- The self-consistency majority-vote literature baseline exists for matched-slice comparison.
- The 100-case external comparison script exists, but its first selected-verifier run is cache-limited and diagnostic.
- Narrow **1018203 main3-vs-best3** harness persists **`external_l1_max` ≫ best listed internal headline** (**see [`CURRENT_EXTERNAL_BASELINE_GAP.md`](CURRENT_EXTERNAL_BASELINE_GAP.md)**) without universality wording.
- The next claim-safe comparison requires full score coverage on paired candidate cases.

Not safe yet:

- Do not claim robust/universal superiority over `external_l1_max`.
- Do not claim runtime promotion of the selected selector.
- Do not treat cache-limited paired comparisons as real selected-selector comparisons.
- Do not compare selector families using unmatched slices as headline evidence.
- Do not claim selector errors are solved until fully scored paired pilots quantify gold-present-but-not-selected cases.
- Do not treat diagnostic/bug-revealing artifacts as paper-facing evidence without updating the source-of-truth docs.

## Next recommended action

1. Run a fully scored paired pilot/comparison against `external_l1_max` with zero missing selector scores.
2. Compare self-consistency and the Cohere outcome-verifier selector on the same paired cases.
3. If the verifier selector remains best, freeze selector work for the current paper track.
4. Move to discovery/coverage improvements if fully scored paired comparisons show most residual errors have gold absent from the candidate tree.

## Important documents

- `docs/CURRENT_EXTERNAL_BASELINE_GAP.md` — headline vs **`external_l1_max`** (**1018203**) with exact slice contract.
- `docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md` — cache-limited, superseded, and pilot regressions retained but bounded.
- `docs/DISCOVERY_FAILURE_TAXONOMY.md` — discovery vs selector decomposition vocabulary (**path-gap proxy warning** included).
- `docs/OUTPUT_RETENTION_POLICY_CURRENT.md` — **`outputs/`** commit vs `.gitignore` norms.
- `docs/REPO_ORGANIZATION_GUIDE_20260501.md` — clean navigation and cleanup rules.
- `docs/CURRENT_SELECTOR_DECISION.md` — selected selector config and caveats.
- `docs/LITERATURE_SELECTOR_BASELINES.md` — literature-grounded selector baselines.
- `docs/DOCS_INDEX.md` — active vs diagnostic vs historical document map.
- `docs/REPO_MAP.md` — repository structure and selector-phase reading path.
- `docs/SELECTOR_WORK_START_HERE_20260501.md` — selector artifact orientation.
- `docs/SELECTOR_CHOOSING_PLAYBOOK_20260501.md` — selector family decision checklist.
- `docs/FAST_SELECTOR_EXECUTION_POLICY.md` — cost-aware execution policy.
- `docs/PAPER_SOURCE_OF_TRUTH.md` — claim-eligible evidence rules.

## One-sentence status

The repository now has an audited recovery-track selected verifier selector and an implemented self-consistency literature baseline; the next useful work is an apples-to-apples fully scored paired pilot against `external_l1_max`, after which effort should shift to discovery/coverage if residual errors are mostly gold-absent-from-tree.
