# Repository master dashboard (2026-04-18)

## Purpose

This note is the shortest repository-facing answer to the following questions:
- What is this repository about now?
- Where did the project start from?
- What has been built so far?
- What has worked?
- What has not worked?
- What should happen next?

This file is intended to be the best single-page collaborator dashboard for the repository.

## Project identity

The repository is currently the canonical home for the project on:

> **fixed-budget adaptive test-time compute allocation for LLM reasoning, centered on which active branch should receive the next unit of compute.**

This repository is **not** the old binary revise-routing paper.

## Where the project started from

The current project evolved from earlier routing-oriented work, but the canonical project question is now different.

Old local story:
- should we revise or not?
- should we escalate or not?

Current canonical story:
- given multiple active branches under a fixed budget,
- which branch should receive the next unit of compute,
- and when should the system explicitly avoid forced commitment?

## What the repository already has

The repo already contains a strong research platform with:
- frontier/controller experimentation scaffold,
- anti-collapse controller design and audits,
- branch-scorer experimentation paths,
- stop-vs-act as a bounded helper formulation,
- brute-force / near-brute-force label generation,
- exact-vs-approx audits,
- hard-case feature representations,
- tie-aware / abstention / defer experiments,
- fallback-policy experiments,
- dataset and baseline integration readiness,
- provenance-aware outputs and method notes,
- fresh observability-enabled branch-semantic capture,
- bounded worst-failure semantic casebooks,
- bounded final-answer recovery on contested states,
- bounded oracle mismatch comparison studies.

## What has worked so far

### Framing and project identity
- The fixed-budget frontier-allocation framing is stronger and more honest than the older binary-routing story.
- The repo now has a clearer canonical identity.

### Mechanism and evaluation
- Anti-collapse design matters.
- Branch ranking / next-step allocation is the right conceptual center.
- The multistep family remains the strongest bounded method lead.
- Fresh observability-enabled runs now allow real semantic diagnosis of worst failure cases.
- Completion-aware evidence appears to matter in a small disagreement region even though it is not a global replacement signal.

### Research process
- The repository is good at provenance.
- The repo is strong at bounded experiment notes and safe-claims discipline.
- The repo is already ready for serious paper planning and collaborator onboarding.
- The repo is now closer to a target-definition decision point than a broad exploration point.

## What has not worked well enough

### Not enough as full solutions
- More model class alone.
- More labels alone.
- Exact hard-region promotion alone.
- Pure threshold tweaking alone.
- Generic fallback policies.
- Deferred-only specialist training.
- Broad hard-pair replacement.
- Broadening scope too early.
- Recent nearby target/control refinements as broad successors to multistep-k3.

### What this means
The problem is not primarily lack of infrastructure, another controller family, or just more scale.

The harder issue is now narrower:
- how the target/oracle should be defined in hard close-branch states,
- especially when continuation value and visible semantic completion diverge.

## Main unresolved bottleneck

The current primary bottleneck is:

> **target-definition clarity for hard next-step branch-allocation disagreements**

More concretely, the bottleneck is now concentrated in:

> **whether continuation value should remain the sole oracle/target, or whether bounded completion-aware correction should apply in near-tie disagreement states.**

This includes:
- semantic/objective mismatch on a small disagreement slice,
- near-tie branch comparisons,
- answer-completion evidence versus immediate continuation value,
- and the exact definition of a bounded hybrid oracle/controller.

## Best current target/oracle stance

The current strongest repository-supported stance is:

> **keep continuation value as the core oracle/target, and augment it with bounded completion-aware evidence only in disagreement slices, especially near-ties.**

This should currently be treated as the strongest default stance unless new evidence clearly displaces it.

## Most important current research direction

The most important current direction is:

> **freeze and validate the hybrid target/oracle definition for hard disagreement states, rather than continuing broad nearby target/controller sweeps.**

## What should happen next

### Immediate next step
- consolidate the current target-definition decision,
- use the fresh semantic failure cases plus recovered final answers to manually and programmatically adjudicate the contested disagreement slice,
- and write the repository-facing decision memo/rule that governs what should count as the next admissible experiment.

### Near-term next layer
- keep continuation value as the base object,
- formalize bounded completion-aware correction only where disagreement is real,
- and avoid broad new families until the target-definition memo changes.

### Later, only after target-definition consolidation
- broaden datasets in new ambiguity regimes,
- expand stronger external baselines fairly,
- and scale to heavier evidence only after the hybrid target/oracle stance is stable.

## Best reading path

If you are new to the repo, read:
1. `README.md`
2. `docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`
3. `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
4. `docs/PROJECT_MASTER_PLAN.md`
5. `docs/CURRENT_PROJECT_STATUS.md`
6. `docs/CURRENT_BOTTLENECKS.md`
7. `docs/CURRENT_SAFE_CLAIMS.md`
8. `docs/EXPERIMENT_LEDGER_2026_04_18.md`
9. `docs/CONTINUATION_PLAN_2026_04_18.md`
10. `docs/REFERENCES_ORGANIZATION_2026_04_18.md`

## Best code path

If you want the strongest current code path for semantic target-definition work, start with:
- `scripts/run_worst_real_failure_casebook_with_reasoning.py`
- `scripts/run_completion_aware_decision_experiment.py`
- `scripts/run_oracle_mismatch_study.py`
- `scripts/run_branch_observability_smoke.py`

If you specifically want the strongest current bounded method line, start with:
- `scripts/run_multistep_branch_utility_target_experiment.py`
- `scripts/build_bruteforce_target_regimes.py`
- `scripts/train_bruteforce_branch_allocator.py`

## Safe high-level summary

A safe repository-facing summary is:

> The repository is already a strong platform for fixed-budget branch allocation in LLM reasoning. The main remaining challenge is no longer broad method exploration, but freezing the right target/oracle definition for hard close-branch decisions now that fresh semantic failure analysis is available.
