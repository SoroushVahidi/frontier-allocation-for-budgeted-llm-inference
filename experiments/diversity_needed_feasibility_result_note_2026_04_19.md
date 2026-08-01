# Diversity-Needed Predictor Feasibility Note (Bounded Pass)

Date: 2026-04-19
Run: `outputs/branch_label_bruteforce_learning/diversity_needed_feasibility_20260419`

## Scope and discipline
This pass is a bounded feasibility check only. It does **not** replace the current broad diversity-aware branch-allocation family.

## Operational target
For each frontier state `(s, b)`, we built:

- `Q_diverse_expand(s,b)`: value after one **diversity-seeking expansion**.
- `Q_best_nondiverse(s,b) = max(Q_exploit_expand(s,b), Q_commit(s,b))`.
- `Y_diversity_needed = Q_diverse_expand - Q_best_nondiverse`.
- Optional binary target: `needs_more_diversity = 1[Y_diversity_needed > 0]`.

Reliability/provenance fields are retained (`target_reliability_mean`, `target_stderr_mean`, `target_provenance`).

## Diversity-seeking expansion definition used
`diversity_action_definition = expand_plausible_undercovered_group_with_diversity_priority`.

Implementation details:
1. Branches are grouped by an auditable answer-group proxy key (`score bin`, `depth bin`, `verify bin`, `recent-delta sign`).
2. A branch is *plausible* if its score is within `diversity_plausibility_margin` of frontier top score.
3. Undercovered groups are groups with support count below the dominant group's support.
4. Diversity action picks the plausible undercovered branch with maximal diversity-aware priority:
   - continuation value + support-based diversity bonus - overlap penalty.
5. Exploit action picks the best branch within dominant group.

## Main bounded findings
- There is **some classification signal**, but small-sample instability is high.
  - Logistic baseline (held-out test): AUC `0.833`, accuracy `0.583`, F1 `0.545`.
  - GBT classifier (held-out test): AUC `0.444`, accuracy `0.417`.
- Regression signal for `Y_diversity_needed` is weak in this bounded run.
  - Ridge `R^2 ~ 0.013`; GBT regressor negative `R^2`.
- Feature importance (GBT) points at structure beyond a single tie flag (support margin, commit-readiness, semantic-overlap, continuation estimate), but the classifier itself is unstable in this sample.
- Ambiguity-only ablation is competitive (`AUC 0.708`), so this pass does **not yet** prove strong diversity-specific signal beyond near-tie style cues.
- Lightweight gate check is directionally neutral/weak in this run:
  - predictor-gated value equals always-diverse value (`0.812`), both above always-nondiverse (`0.725`), below oracle (`0.822`).

## Decision guidance
Current evidence is **promising but not yet strong** for immediate controller integration.

Recommended next bounded step before promotion to a serious new method line:
1. Increase matched held-out state count.
2. Re-run with stronger answer-group grounding from current broad-family traces.
3. Re-check whether performance remains above ambiguity-only baselines.

If those hold, the diversity-needed predictor is justified for deeper integration work; if not, prioritize failure-taxonomy refresh and data/target quality improvements first.
