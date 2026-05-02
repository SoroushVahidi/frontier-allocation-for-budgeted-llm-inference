# Open experiments and evidence gaps

This is the canonical living backlog for scientific questions that are not yet answered by the repository.

Use this file when a question comes up and the current answer is: **tooling exists or partial evidence exists, but the completed experiment is missing**. Update one row when a run finishes, fails, or is superseded.

## Status labels

| Label | Meaning |
|---|---|
| `todo` | Needed experiment has not been run. |
| `running` | Experiment has been submitted or started but has no final result yet. |
| `diagnostic_partial` | Some data exists, but it is too small, cache-limited, or incomplete for the scientific claim. |
| `blocked` | Cannot run until a concrete blocker is fixed. |
| `complete_claim_eligible` | Completed and may support a scoped claim. |
| `complete_diagnostic_only` | Completed but should not be used as headline evidence. |
| `deprioritized` | Tooling exists or idea is valid, but it is not worth current effort. |

## Open high-priority experiments

| Experiment ID | Scientific question | Why it matters | Current status | Next action | Minimum success condition | Claim enabled if successful |
|---|---|---|---|---|---|---|
| `EXP-L1-DECOMP-100` | After applying the best DR-v2 selector/reranker, when we still lose to `external_l1_max`, are losses mostly gold-absent-from-tree or gold-present-but-not-selected? | Decides whether to focus on discovery/coverage or selection. | `running` / `diagnostic_partial`: tooling exists; one-case diagnostic exists; Wulver diagnostic job submitted with small cap; full 100-case result missing. | Run largest feasible real-Cohere paired decomposition, preferably 100 paired cases. | `l1_loss_decomposition_summary.json` with `total_paired_cases = 100`, or a hard failure report after attempting full run. | A bottleneck claim: discovery/coverage dominant, selection dominant, mixed, or inconclusive. |
| `EXP-ABSENT-CLOSENESS` | For gold-absent-from-tree losses, how close were candidates to the correct answer? | Tells whether absent-from-tree means near miss, collapsed wrong group, or search went far away. | `todo` / partially scripted: `scripts/build_external_baseline_loss_casebook.py` computes nearest numeric/edit-distance features, but no final latest-selector summary exists. | Run closeness casebook on the completed L1-decomposition artifact. | Casebook with candidate answers, nearest numeric error, edit distance, answer-group count, and distance category for every absent loss. | Determines whether to improve local arithmetic repair, branching/seeding, or global exploration. |
| `EXP-COHERE-OURS-3-VS-EXT-3` | On a real Cohere slice, how do our best three algorithms compare with the three main-table external adapter baselines? | Decides whether Cohere results should be added to the manuscript. | `diagnostic_partial`: scaffold package exists with zero calls; no evidence-bearing result. | Run local/cloud or Wulver real-Cohere comparison only if expected calls/cost are acceptable. | Same 100 cases for all six lanes, real calls, no missing rows, comparison summary and pairwise matrix. | Add bounded Cohere validation to manuscript only if best ours beats all three external baselines fairly. |
| `EXP-FULL-SCORED-SELECTOR-VS-L1` | Does the selected Cohere verifier selector improve DR-v2 against `external_l1_max` when all needed selector scores are present? | Current 100-case selected-selector vs L1 pilot is cache-limited and mostly falls back to DR-v2. | `todo` / `diagnostic_partial`: cache-limited 100-case package exists with missing selector scores. | Build missing verifier call plan for that paired slice, score all missing candidates under cap, rerun comparison. | Missing selector scores = 0; fallback due to missing scores = 0; selected-candidate-not-in-pool = 0. | A fair selector-impact claim against L1 on that paired slice. |
| `EXP-SC-VS-OV-SAME-SLICE` | Is self-consistency or the Cohere outcome-verifier selector better on the same candidate pools? | Provides a clean literature-baseline comparison. | `todo`: self-consistency exists; OV exists; same-slice full comparison still needed. | Run both selectors on the same paired candidate slice with full score coverage for OV. | Same cases/candidates for SC and OV; no gold leakage; paired fixes/breaks/net table. | Decide whether paid verifier selection is worth the cost compared with no-API self-consistency. |

## Medium / low-priority experiments

| Experiment ID | Scientific question | Why it matters | Current status | Next action | Minimum success condition | Claim enabled if successful |
|---|---|---|---|---|---|---|
| `EXP-CMV-PILOT` | Is self-verification / CMV competitive as a selector baseline? | Provides another paper-based selector baseline. | `deprioritized`: CMV tooling exists; committed pilot was non-informative / zero-call or incomplete. | Only rerun if reviewer pressure requires another literature baseline. | Nonzero call plan, full CMV coverage, comparison against DR-v2, SC, OV, and L1. | Appendix baseline result, not selector promotion unless surprisingly strong. |
| `EXP-PRM-RERANK-100` | Does PRM/step-verifier reranking beat OV or selection-fix on a full real-Cohere paired run? | Could be a stronger selector/reranker lane. | `diagnostic_partial`: 30-case evidence exists; broad 100-case completed evidence is not final. | Run only if L1 decomposition says selection remains dominant. | Full paired run, real verifier backend, no mock rows. | Choose PRM over OV if it improves fixes without break risk. |
| `EXP-DISCOVERY-COVERAGE-V1` | If gold-absent losses dominate, can a new discovery/coverage controller get gold into the tree more often? | Likely next algorithmic direction if selector is no longer main bottleneck. | `todo`: depends on `EXP-L1-DECOMP-100` and `EXP-ABSENT-CLOSENESS`. | Design after absent-loss casebook is available. | New method reduces gold-absent loss rate at comparable or justified cost. | New method contribution beyond selector work. |

## Maintenance rule

When any experiment runs, update this file with:

- timestamp / output directory;
- exact method list;
- dataset / split / seed / budget;
- planned and actual call count;
- completed paired case count;
- claim safety status;
- one-line result;
- next action.

If an experiment only creates scaffolding, readiness checks, or a tiny smoke test, keep the status as `diagnostic_partial` or `blocked`; do **not** mark it complete.

## Current top priority

The highest-priority missing experiment is:

```text
EXP-L1-DECOMP-100
```

because it answers the immediate strategic question:

> If the best selector/reranker still loses to L1, is the remaining gap mainly because the correct answer is absent from our tree, or because the correct answer is present but not selected?

Until this is answered, do not keep adding selector baselines as the main path forward.
