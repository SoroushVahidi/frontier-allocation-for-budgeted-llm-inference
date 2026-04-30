# Current project status

This document is the short, current orientation note for the repository. It supersedes older broad-status notes for day-to-day work, while preserving dated documents as provenance.

## Current project identity

This repository studies **frontier allocation for budgeted LLM inference** under explicit compute/action-budget contracts.

The current paper-facing frame is not the old binary revise-routing story. The central question is:

> Given a fixed inference budget and multiple active reasoning/candidate paths, where should the next unit of compute go, and how should the final answer be selected from the explored frontier?

The older `-adaptive-llm-inference` project is now treated as prior internal background and diagnostic inspiration, not as the runtime center of this project. Its useful ideas have been absorbed as headroom/oracle analysis, cost-aware framing, answer-error features, and risk diagnostics.

## Current development goal

The active engineering goal is to defeat `external_l1_max` honestly with completed, paired, trace-complete evidence.

The current subgoal is no longer basic trace-schema validation. We now have a usable real paired 30-case trace artifact and need to convert the observed selector headroom into a deployable selector improvement.

## Current key artifact

Primary current diagnostic artifact:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/
```

Important diagnostics under this artifact:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/offline_selector_variants/
```

## Current evidence snapshot

On the paired 30-example Cohere GSM8K budget-4 seed-11 slice:

| Quantity | Value |
|---|---:|
| `external_l1_max` accuracy | 0.8000 |
| current DR-v2 accuracy | 0.6333 |
| oracle selector ceiling over DR-v2 candidate pool | 0.8667 |
| corrected selector gap over DR-v2 | 0.2333 |
| L1-correct / DR-v2-wrong cases | 7 |
| gold-present among those losses | 5 |
| gold-absent among those losses | 2 |
| candidate_count mean/median/max | 2 / 2 / 2 |
| answer_group_count mean/median/max | 1.6 / 2 / 2 |

Interpretation:

- The candidate pool has meaningful hidden headroom.
- Most L1>DR-v2 losses on this slice are **present-but-not-selected**, not pure coverage failures.
- Simple deployable offline selectors did **not** produce a net gain: support-only fixed some failures but broke a comparable number of currently correct cases.
- Therefore the next selector should be a **conservative outcome-verifier / correctness-estimator override**, not another broad support heuristic.

## Current phase

**Phase:** conservative answer-verifier selector design.

Current priority order:

1. Analyze the 5 gold-present-but-not-selected cases and the support-only break cases.
2. Build a narrow override rule that keeps current DR-v2 by default.
3. Override only when a candidate answer has stronger correctness evidence than the current selected answer.
4. Test the rule offline on the real 30-case artifact.
5. If it shows positive net gain without breaking many current-correct cases, implement it as a runtime method.
6. Then run a 50-case paired trace-complete validation.

## Current known blocker

The blocker is no longer lack of trace-complete artifact support. The blocker is:

> Simple support/confidence/consistency selectors do not distinguish safe overrides from unsafe overrides well enough.

The next method must estimate candidate correctness more directly:

```text
score(problem, candidate answer, optional reasoning trace, source/support/error features)
  -> estimated probability candidate is correct
```

This is an outcome-verifier framing. PRM/process-verifier work remains useful later, but the immediate deployable target is an outcome-level conservative override.

## Current safe claim boundary

Safe:

- The repository implements a fixed-budget frontier-allocation framework with trace-complete selector and coverage diagnostics.
- A real 30-case paired diagnostic shows oracle-selector headroom over DR-v2 candidate pools.
- The current evidence supports selector/commit-rule work as the primary next direction, with coverage repair secondary.

Not safe yet:

- Do **not** claim robust or broad superiority over `external_l1_max`.
- Do **not** claim DR-v2/OV/PRM variants defeat L1 without completed paired rows.
- Do **not** promote a selector to runtime until it improves offline on real trace artifacts and passes focused tests.
- Do **not** treat mock-backed verifier results as real verifier evidence.

## Current method interpretation

- `strict_f3` remains the manuscript-facing matched-surface representative under the older canonical paper surface.
- `strict_gate1_cap_k6` remains a broader operational default on a different surface.
- DR-v2 and its selector/rerank variants are the active L1-defeat development family.
- The immediate method target is a conservative outcome-verifier-style selector/override for DR-v2 candidate groups.

## Current next action

The next non-circular task is:

1. Build a focused casebook for:
   - gold-present but DR-v2-selected-wrong cases;
   - support-only break cases.
2. Derive exactly one conservative override rule.
3. Test it offline on the existing 30-case real artifact.
4. Add small focused tests for any implemented logic.
5. Promote to runtime only if it gives positive net gain offline.

## Important documents

- `docs/CANONICAL_START_HERE.md` — canonical reviewer/collaborator orientation.
- `docs/DOCS_INDEX.md` — active vs diagnostic vs historical document map.
- `docs/SELECTOR_START_HERE.md` — current selector/L1-defeat track.
- `docs/OUTCOME_VERIFIER_SELECTOR_ROADMAP.md` — current verifier-selector roadmap.
- `docs/OUTPUTS_SELECTOR_TRACE_INDEX.md` — selector trace artifact index and usability policy.
- `docs/FINAL_ADAPTIVE_LLM_INFERENCE_TRANSFER_AUDIT_20260430T034801Z.md` — final transfer audit from the old project.
- `docs/PAPER_SOURCE_OF_TRUTH.md` — claim-eligible evidence rules.
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md` — safe vs unsafe claim map.
- `docs/PAPER_OPEN_GAPS_AND_RISKS.md` — known open gaps.

## One-sentence status

The repository now has real paired evidence that DR-v2 often finds the correct answer but fails to commit to it; the next step is a conservative outcome-verifier override that recovers present-not-selected cases without breaking current correct answers.
