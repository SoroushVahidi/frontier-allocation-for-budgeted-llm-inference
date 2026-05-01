# Current evidence ledger — 2026-05-01

This ledger separates **claim-eligible evidence**, **diagnostic evidence**, and **tooling/scaffold artifacts** after the recent selector, literature-baseline, Cohere-comparison, and L1-loss-decomposition work.

It is meant to prevent future work from mistaking dry-run packages, blocked runs, or one-case diagnostics for final evidence.

## One-line status

The repository has a strong audited recovery-track selector result, a usable self-consistency literature baseline, a CMV literature-baseline scaffold, and new Cohere/L1-loss-decomposition tooling. It does **not** yet have a clean 100-case real-Cohere result showing our best selected method beating `external_l1_max`, nor a clean 100-case L1-loss decomposition for the best selector/reranker.

## Evidence classes

| Class | Meaning | Manuscript use |
|---|---|---|
| `claim_eligible_current` | Current, audited, and scoped evidence that may support a narrow claim. | Allowed with exact scope/caveats. |
| `diagnostic_current` | Useful engineering evidence, but incomplete, cache-limited, small, or not full-coverage. | Appendix/internal only unless promoted by source-of-truth docs. |
| `tooling_scaffold` | Scripts/tests/output skeletons exist, but no real or sufficient result yet. | Do not cite as performance evidence. |
| `blocked_or_non_evidence` | Execution failed, zero real calls, or no completed paired rows. | Do not cite as results. |
| `historical_provenance` | Older outputs/docs kept to explain path taken. | Cite only for history/failure analysis. |

## Current selector evidence

| Artifact / doc | Classification | What it supports | What it does not support |
|---|---|---|---|
| `configs/selected_selector_current.json` | `claim_eligible_current` | The current selected recovery-track selector config. | Runtime promotion or L1 defeat. |
| `docs/CURRENT_SELECTOR_DECISION.md` | `claim_eligible_current` | Canonical recovery-track selector decision and caveats. | Broad real-model dominance. |
| `outputs/final_selector_decision_20260501T175547Z/` | `claim_eligible_current` | Final recovery-track selector decision. | Fully scored paired external comparison. |
| `outputs/selected_selector_audit_20260501T181608Z/` | `claim_eligible_current` | Audit of selected-selector reproducibility/leakage/scope. | Runtime/current-correct safety. |
| `outputs/outcome_verifier_answer_group_selector_repro_linkage_20260501T181534Z/` | `claim_eligible_current` | Selected selector reproduces 47-case recovery metrics. | External-baseline superiority. |
| `outputs/outcome_verifier_scores_cohere_smoke10_20260501T162328Z/` | `claim_eligible_current` for recovery package | Completed 94/94 Cohere score cache for recovery selector evidence. | Coverage of arbitrary paired DR-v2/L1 candidate pools. |

### Recovery-track headline

On the 47-case recovery selector-evidence package, the selected Cohere cached verifier selector produced:

- `fixes = 21`
- `breaks = 0`
- `net_fixes_minus_breaks = +21`
- `accuracy = 0.4468`
- among gold-terminal cases: `21 / 29` recovered, leaving `8 / 29` gold-present-but-not-selected.

This is a useful selector result, but its scope is **recovery selector evidence**, not full runtime deployment.

## Literature selector baselines

| Baseline | Classification | Status |
|---|---|---|
| `self_consistency_majority_selector_v1` | `diagnostic_current` / literature baseline | Complete and usable no-API selector baseline over existing candidate pools. |
| `self_verification_cmv_selector_v1` | `tooling_scaffold` / literature baseline | Implemented, but the committed pilot was non-informative or not full-coverage; do not use as performance evidence. |

Self-consistency is the cleanest current literature selector baseline. CMV should remain documented as a literature-baseline scaffold unless a future bounded run produces real full-coverage comparison evidence.

## External-baseline comparison evidence

| Artifact / doc | Classification | Notes |
|---|---|---|
| `outputs/best_selector_vs_external_l1_comparison_*/` | `diagnostic_current` | 100-case bounded comparison exists, but selected-verifier application is cache-limited; missing selector scores remain. |
| `docs/METHOD_EVIDENCE_AND_FAILURE_SUMMARY_20260429.md` | `diagnostic_current` | Summarizes existing Cohere evidence: no internal method has clearly beaten `external_l1_max` in meaningful broad real-model comparison. |
| `docs/SELECTOR_COMPARISON_30CASE_COHERE_20260429.md` | `diagnostic_current` | 30-case selector comparison; useful but not final evidence. |
| `outputs/cohere_100case_ours_vs_external_20260501T000000Z/` | `blocked_or_non_evidence` | PR #343 scaffold/dry-run package; actual calls were zero. Do not cite as results. |

The current safe statement is: existing Cohere evidence remains unfavorable or incomplete for claiming dominance over `external_l1_max`.

## L1-loss decomposition evidence

| Artifact / doc | Classification | Notes |
|---|---|---|
| `scripts/run_l1_loss_decomposition_for_best_selector.py` | `tooling_scaffold` | Useful wrapper/tooling for the requested L1-loss decomposition. |
| `outputs/l1_loss_decomposition_best_selector_20260501T000000Z/` | `blocked_or_non_evidence` | Initial blocker package; Cohere SDK was missing in that environment. |
| `outputs/l1_loss_decomposition_best_selector_20260501T010000Z/` | `blocked_or_non_evidence` | Cohere readiness passed but complete paired artifacts were missing. |
| `outputs/l1_loss_decomposition_best_selector_20260501T023500Z/` | `diagnostic_current` only | Real JSONL output exists, but only `total_paired_cases = 1`; no L1-correct/ours-wrong losses occurred. |
| `docs/L1_LOSS_DECOMPOSITION_BEST_SELECTOR_RESULT.md` | `diagnostic_current` | Should be read as status/blocker/diagnostic documentation until a larger paired run exists. |

The exact statistic the project still needs is **not complete**:

> For our best selected DR-v2 selector/reranker versus `external_l1_max`, among L1-correct/ours-wrong cases, how many are gold-absent-from-tree versus gold-present-but-not-selected?

The latest known real diagnostic output has only one paired case and therefore cannot answer the scientific bottleneck question.

## Main-table external baselines

The current fully paper-ready external baseline family remains the three MODE-A adapter comparators:

1. `l1_length_control_rl` / runtime mapping `external_l1_max`
2. `tale_token_budget_aware_reasoning` / runtime mapping `tale`
3. `s1_simple_test_time_scaling` / runtime mapping `s1`

Claim boundary: these are **MODE-A adapter comparators on a matched substrate, not official full-stack reproductions**.

## Current best next action

Do not add another selector baseline. The most useful next action is one of:

1. Complete the L1-loss decomposition run at the largest feasible paired case count under a clear call cap, preferably 100 paired cases.
2. If full selector/reranker coverage is too expensive, run a smaller clearly marked diagnostic and report the exact cap/coverage blocker.
3. Use the decomposition to decide whether the dominant remaining bottleneck is:
   - discovery/coverage: gold absent from candidate tree;
   - selection: gold present but not chosen;
   - instrumentation: candidate/trace evidence missing.

## Do-not-claim list

Do not claim:

- our selected selector beats `external_l1_max`;
- the selected selector is runtime-promoted;
- CMV is competitive;
- the 100-case Cohere ours-vs-external scaffold is evidence-bearing;
- the 1-case L1-loss-decomposition diagnostic answers the bottleneck question;
- gold is absent from tree when candidate traces are missing.

## Safe current wording

Safe:

> The selected Cohere cached outcome-verifier selector substantially improves recovery on a controlled 47-case selector-evidence package, reducing gold-present-but-not-selected terminal-node failures from 29 to 8. However, broader paired real-model comparison against `external_l1_max` remains incomplete or unfavorable, and the repository does not yet contain a full 100-case L1-loss decomposition for the selected method.

Unsafe:

> Our selector solves the L1 gap or proves our method beats the external baseline.
