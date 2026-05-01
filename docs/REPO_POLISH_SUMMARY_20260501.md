# Repository polish summary — 2026-05-01

This note records the documentation-only repository polish after the selector-decision and external-baseline comparison work.

## What changed

- Refreshed `README.md` so the repository front door reflects the current selected selector instead of stale trace-recovery blockers.
- Refreshed `docs/CURRENT_PROJECT_STATUS.md` so day-to-day status points to selected-selector validation and literature-baseline comparison.
- Added this short summary document to make the polish scope explicit.

## Current canonical selector

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

Canonical decision and audit artifacts:

```text
outputs/final_selector_decision_20260501T175547Z/
outputs/selected_selector_audit_20260501T181608Z/
```

## Current claim boundary

Safe to say:

- A recovery-track selector decision exists and is audited.
- The selected Cohere cached outcome-verifier selector outperformed the tested conservative and trace-quality selector baselines on the recovery selector-evidence package.
- The repository contains tooling for bounded paired comparison against `external_l1_max`.

Not safe to say yet:

- The selected selector is runtime-promoted.
- The selected selector robustly beats `external_l1_max`.
- Cache-limited paired comparisons are equivalent to fully scored paired comparisons.

## Next recommended work

1. Finish and compare literature selector baselines, starting with self-consistency majority vote.
2. Run apples-to-apples fully scored comparisons on the same pilot cases for self-consistency and the Cohere outcome-verifier selector.
3. If the selected selector remains best, shift focus to discovery/coverage: getting correct answers into the candidate tree.
