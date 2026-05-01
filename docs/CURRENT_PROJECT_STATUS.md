# Current project status

This document is the short, current orientation note for the repository. It supersedes older broad-status notes for day-to-day work, while preserving dated documents as provenance.

## Current project identity

This repository studies **frontier allocation for budgeted LLM inference** under explicit compute/action-budget contracts.

The current paper-facing frame is not the old binary revise-routing story. The central question is:

> Given a fixed inference budget and multiple active reasoning/candidate paths, where should the next unit of compute go, and how should the final answer be selected from the explored frontier?

The older `-adaptive-llm-inference` project is treated as prior internal background and diagnostic inspiration, not as the runtime center of this project.

## Current development goal

The active engineering goal is to defeat `external_l1_max` honestly with completed, paired, trace-complete evidence.

The current subgoal is to convert candidate-pool headroom into a deployable final-answer selector. Heuristic selectors have now been tested on a real 50-case compact tournament artifact and are not strong enough for runtime promotion.

## Current active artifact

Primary current real run:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/
```

Portable compact selector artifact:

```text
outputs/selector_tournament_compact_export_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/
```

Tournament diagnostics:

```text
outputs/selector_tournament_compact_export_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/diagnostics/selector_tournament/
```

## Current evidence snapshot

On the paired 50-example Cohere GSM8K budget-4 seed-11 slice:

| Method / diagnostic | Accuracy |
|---|---:|
| `external_l1_max` | 0.72 |
| current DR-v2 | 0.64 |
| best deployable heuristic selector | 0.66 |
| oracle selector ceiling | 0.84 |

Best deployable heuristic selector behavior:

| Quantity | Value |
|---|---:|
| fixes | 5 |
| breaks | 4 |
| net fixes-minus-breaks | +1 |
| overrides | 17 |
| override precision | 0.2941 |

Interpretation:

- DR-v2 candidate pools contain substantial hidden value: oracle selection reaches 0.84.
- Existing support/source/consistency heuristics recover only a small fraction of that value.
- Current heuristic selectors are too noisy and should **not** be promoted to runtime.
- The next selector must estimate candidate correctness more directly.

## Current phase

**Phase:** cached outcome-verifier selector test.

The next method should be framed as:

```text
score(question, candidate answer, optional reasoning trace)
  -> estimated probability that the candidate answer is correct
```

Then select the highest-scoring candidate, preferably with a margin that avoids breaking current correct answers.

## Execution policy from now on

We are using paid APIs. Avoid unnecessary cost.

Rules:

1. Do not run paid generation unless the exact method, dataset, budget, seed, and expected call count are known.
2. For selector work, use existing candidate pools whenever possible.
3. Cache every verifier score.
4. Before any paid verifier run, produce a dry-run count of required verifier calls and estimated cost.
5. Do not run more repository archaeology or broad diagnostics unless it directly enables a selector result.
6. After any paid run, immediately export a compact portable artifact and run the selector tournament.

## Current known blocker

The blocker is no longer artifact portability or lack of selector tournament infrastructure. The blocker is:

> Heuristic selectors cannot reliably distinguish safe overrides from unsafe overrides.

The next useful selector is an outcome-verifier-style candidate correctness estimator, not another support-only variant.

## Current safe claim boundary

Safe:

- The repository implements fixed-budget frontier-allocation diagnostics with portable selector-tournament artifacts.
- A real 50-case paired diagnostic shows substantial oracle-selector headroom over DR-v2 candidate pools.
- Simple deployable heuristic selectors are insufficient: they recover too little headroom and make too many unsafe overrides.
- These findings motivate outcome-verifier-based final-answer selection.

Not safe yet:

- Do **not** claim DR-v2 or any current selector beats `external_l1_max` robustly.
- Do **not** claim heuristic selectors solve final-answer commitment.
- Do **not** claim an outcome-verifier selector works before cached verifier scores are actually evaluated.
- Do **not** promote a selector to runtime without a focused offline result and then a paid validation.

## Current method interpretation

- `strict_f3` remains the manuscript-facing matched-surface representative under the older canonical paper surface.
- `strict_gate1_cap_k6` remains a broader operational default on a different surface.
- DR-v2 and its selector/rerank variants are the active L1-defeat development family.
- The immediate method target is a cached outcome-verifier selector over DR-v2 candidate answer groups.

## Current next action

The next non-circular task is:

1. Use the 50-case compact selector artifact.
2. Implement a cached outcome-verifier selector scaffold.
3. Dry-run and report verifier-call count before any paid verifier scoring.
4. Score only existing candidate groups, not regenerate answers.
5. Compare verifier selector against current DR-v2, best heuristic, L1, and oracle.
6. Promote to runtime only if the verifier selector gives a meaningful net gain.

## Important documents

- `docs/CANONICAL_START_HERE.md` — canonical reviewer/collaborator orientation.
- `docs/DOCS_INDEX.md` — active vs diagnostic vs historical document map.
- `docs/SELECTOR_START_HERE.md` — current selector/L1-defeat track.
- `docs/OUTCOME_VERIFIER_SELECTOR_ROADMAP.md` — current verifier-selector roadmap.
- `docs/FAST_SELECTOR_EXECUTION_POLICY.md` — cost-aware execution policy for selector work.
- `docs/OUTPUTS_SELECTOR_TRACE_INDEX.md` — selector trace artifact index and usability policy.
- `docs/FINAL_ADAPTIVE_LLM_INFERENCE_TRANSFER_AUDIT_20260430T034801Z.md` — final transfer audit from the old project.
- `docs/PAPER_SOURCE_OF_TRUTH.md` — claim-eligible evidence rules.
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md` — safe vs unsafe claim map.
- `docs/PAPER_OPEN_GAPS_AND_RISKS.md` — known open gaps.

## One-sentence status

The repository now has a reliable 50-case selector tournament showing that DR-v2 has large oracle headroom but heuristic selectors are too weak; the next step is a cached outcome-verifier selector over existing candidate groups, with strict API-cost control.
