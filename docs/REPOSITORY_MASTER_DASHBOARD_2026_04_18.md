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
- provenance-aware outputs and method notes.

## What has worked so far

### Framing and project identity
- The fixed-budget frontier-allocation framing is stronger and more honest than the older binary-routing story.
- The repo now has a clearer canonical identity.

### Mechanism and evaluation
- Anti-collapse design matters.
- Branch ranking / next-step allocation is the right conceptual center.
- Pairwise branch comparison remains one of the strongest active learned directions.
- Hard-case feature representation improvements helped materially on difficult slices.
- Tie-aware post-hoc deferral improved controller cleanliness and gave a more honest ambiguity-handling scaffold.

### Research process
- The repository is good at provenance.
- The repo is strong at bounded experiment notes and safe-claims discipline.
- The repo is already ready for serious paper planning and collaborator onboarding.

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

### What this means
The problem is not primarily lack of infrastructure, another controller family, or just more scale. The harder issue is still supervision semantics and selective control on ambiguous hard cases.

## Main unresolved bottleneck

The current primary bottleneck is:

> **supervision target quality / proxy-label mismatch for the next-step branch-allocation decision**

More concretely, the bottleneck is now concentrated in:

> **principled selective pairwise control and supervision design for ambiguous hard cases.**

This includes:
- noisy branch-comparison targets,
- low-margin ambiguity,
- shallow comparator semantics,
- imperfect opportunity-cost modeling,
- and unresolved confidence/defer design.

## Best current method scaffold

The current strongest supported scaffold is:

> **pairwise default + tie-aware post-hoc deferral + specialist pointwise fallback**

This should currently be treated as the strongest default hard-case scaffold unless new evidence clearly displaces it.

## Most important current research direction

The most promising next target-design direction is:

> **budget-conditioned selective marginal allocation using branch-level continuation-value signals, softer or structured supervision on ambiguous pairs, and explicit defer/unresolved handling rather than forcing all hard comparisons into binary winner labels.**

## What should happen next

### Immediate next step
- improve supervision target design,
- improve opportunity-cost-aware comparator semantics,
- strengthen selective pairwise accept/defer control,
- and test branch-level value + uncertainty style supervision in bounded auditable form.

### Near-term next layer
- reuse current data more intelligently,
- keep provenance explicit,
- use disagreement- and near-tie-focused exact relabeling,
- and compare new target designs against the current strongest scaffold.

### Later, after target-quality improvement
- broaden datasets in new ambiguity regimes,
- expand stronger external baselines fairly,
- and scale to heavier evidence only after target semantics are sharper.

## Best reading path

If you are new to the repo, read:
1. `README.md`
2. `docs/PROJECT_MASTER_PLAN.md`
3. `docs/CURRENT_PROJECT_STATUS.md`
4. `docs/CURRENT_BOTTLENECKS.md`
5. `docs/CURRENT_SAFE_CLAIMS.md`
6. `docs/EXPERIMENT_LEDGER_2026_04_18.md`
7. `docs/CONTINUATION_PLAN_2026_04_18.md`
8. `docs/REFERENCES_ORGANIZATION_2026_04_18.md`

## Best code path

If you want the strongest current code path for hard-case branch-allocation work, start with:
- `scripts/run_bruteforce_branch_label_generator.py`
- `scripts/build_bruteforce_target_regimes.py`
- `scripts/train_bruteforce_branch_allocator.py`
- `scripts/run_target_fidelity_regime_experiment.py`
- `scripts/run_ternary_or_abstain_branch_comparison_experiment.py`
- `scripts/run_structured_ambiguity_experiment.py`
- `scripts/run_defer_fallback_experiment.py`

## Safe high-level summary

A safe repository-facing summary is:

> The repository is already a strong platform for fixed-budget branch allocation in LLM reasoning. The main remaining challenge is not understanding the problem or building more infrastructure, but designing better supervision targets and selective ambiguity handling for hard next-step branch-allocation decisions.
