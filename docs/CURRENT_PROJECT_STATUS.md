# Current project status (canonical)

## Scope

This is the canonical status note for the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- budget-conditioned stop-vs-act control under a global compute budget.

## Core project goal

Learn and evaluate allocation policies that decide where the next unit of compute should go, while respecting a fixed budget and avoiding allocation collapse.

## Final paper goal

The final paper should show that:
1. budgeted test-time compute allocation is a meaningful and distinct problem,
2. a clean frontier / controller framing is more honest than a vague “more reasoning helps” story,
3. budget-conditioned stop-vs-act control is the strongest near-term controller family,
4. and the main methodological challenge is supervision-target quality.

## What has been built

The repo already contains:
- a runnable frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation stack,
- stop-vs-act dataset / train / eval machinery,
- dataset and baseline integration/readiness tooling,
- oracle-label pilot infrastructure,
- provenance-aware output and reporting patterns.

## What has been learned

1. The new project framing is sound and distinct from the old binary revise-routing track.
2. Anti-collapse controller design matters for realized budget use and frontier behavior.
3. Pairwise BT remains one of the strongest active learned directions.
4. The stop-vs-act controller family is the clearest next method direction.
5. Several bounded comparator variants improved understanding, but none has fully solved the ACT-vs-STOP target problem.
6. Larger scale alone is unlikely to fix the current weaknesses without better targets.

## Main unresolved issue

The main unresolved issue is **supervision target quality**:
- proxy-label mismatch,
- noisy or shallow ACT-vs-STOP comparisons,
- imperfect opportunity-cost modeling on the STOP side,
- uneven controller robustness across budgets / seeds / datasets.

## Current methodological interpretation

The project should currently be interpreted as:

> **a strong platform and paper direction whose main open problem is action-conditional supervision design, not missing infrastructure.**

## Current best next implementation direction

- Keep stop-vs-act as the canonical near-term controller family.
- Use uncertainty both as controller input and as data-policy signal.
- Continue matched bounded comparisons versus strong heuristics and BT baseline.
- Integrate the most important external paper baselines carefully and fairly.
- Treat oracle-label and selective-distillation work as high-value supporting lines, not replacements for clean baseline controller evaluation.

## Practical implication

The repo is already ready for serious paper planning, collaborator onboarding, and baseline integration work. The next phase should focus on sharpening the controller target and tightening the evaluation story, not on simply adding more scale.
