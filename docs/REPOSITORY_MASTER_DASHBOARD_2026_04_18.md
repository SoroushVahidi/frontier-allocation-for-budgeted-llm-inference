# Repository master dashboard (2026-04-18)

## Purpose

This note is the shortest repository-facing answer to the following questions:
- What is this repository about now?
- What has already worked?
- What is currently the main method family?
- What is the current bottleneck?
- What should happen next?

This file is intended to be the best single-page collaborator dashboard for the repository.

## Project identity

The repository is currently the canonical home for the project on:

> **fixed-budget adaptive test-time compute allocation for LLM reasoning, centered on which active branch should receive the next unit of compute and when the system should continue versus commit.**

This repository is **not** the old binary revise-routing paper.

## Canonical project story now

The current project no longer centers on only a local target/oracle-definition question.

The current strongest repository-backed story is:
- allocate fixed inference budget across active reasoning branches,
- encourage useful diversity rather than redundant paths,
- aggregate evidence at the answer-group level,
- and make commit decisions only when the leading answer group is strong enough relative to the value of further expansion.

## Current main method family

The leading serious method family in the repository is now:

> **broad diversity-aware branch allocation with answer-support aggregation**

Recent repository evidence supports the following interpretation:
- earlier local target/oracle refinements were useful diagnostics, but not the final broad method answer,
- bounded self-consistency-style local rescue was directionally useful but too weak,
- a broader diversity/aggregation family was the first branch-allocation family to behave like a serious broad competitor,
- stricter simulator confirmation held up for that family,
- and bounded real-model confirmation kept the family alive as plausible but still underconfirmed.

### Current method-status shorthand
- Main family: `broad_diversity_aggregation_*`
- Strong simulator-side candidate: `broad_diversity_aggregation_strong_v1`
- Stronger real-model follow-up candidate so far: `broad_diversity_aggregation_v1`
- Strong recent refinement: `marginal_coverage_diversity_v1`
- Best broad baseline to beat: `self_consistency_3`

## What the repository already has

The repo already contains a strong research platform with:
- frontier/controller experimentation scaffold,
- broad diversity-aware controller implementations,
- answer-support aggregation mechanisms,
- branch observability and semantic-failure capture,
- bounded real failure casebooks,
- comparative mistake audits against the best baseline,
- simulator and bounded real-model confirmation runners,
- provider-backed evaluation paths,
- provenance-aware outputs and safe-claim notes,
- canonical method/objective notes,
- grouped repository navigation and interpretation rules.

## What has worked so far

### Framing and project identity
- The fixed-budget branch-allocation framing is stronger and more honest than the old binary-routing story.
- The repo now has a clear main family rather than many equally plausible stories.

### Mechanism and evaluation
- Diversity-aware branch allocation is the right broad direction.
- Self-consistency-style strengths were diagnosed correctly as broader search, stronger answer support, and reduced premature commitment.
- Marginal coverage plus semantic overlap is a strong improvement inside the current family.
- Fresh observability-enabled runs now allow real semantic diagnosis of failure cases.
- Comparative mistake grouping now identifies dominant failure modes rather than only reporting score gaps.

### Research process
- The repository is strong at provenance and machine-readable output bundles.
- Notes are increasingly honest about what is simulator-backed versus real-model-backed.
- The repo is good at narrowing experiments to a concrete next bottleneck.

## What has not worked well enough

### Not enough as full solutions
- Earlier local target/oracle-only refinements by themselves.
- Generic fallback or defer-policy tweaks.
- Small hard-case rescue without broader family implications.
- Duplicate-aware aggregation alone as a decisive improvement.
- Broad dominance claims from simulator evidence alone.

### What this means
The problem is not primarily lack of infrastructure or lack of ideas.

The harder issue is now narrower and more concrete:
- making useful diversity actually materialize under realistic generation noise,
- using that diversity well once it exists,
- and confirming the current family more strongly under real-model evaluation.

## Main unresolved bottlenecks

The current primary bottlenecks are:

> **reliable diversity realization, ranking/aggregation quality after diversity exists, and stronger real-model confirmation.**

More concretely, the leading residuals are now best described as:
- insufficient diversity realized,
- bad diversity realized,
- ranking error despite diversity,
- aggregation concentration failure,
- and unstable commit-selection under real generation noise.

## Best current repository stance

The strongest current repository-supported stance is:

> **keep the broad diversity/aggregation family as the main line, strengthen it through useful-diversity and branch-quality improvements, and prioritize larger but still cost-controlled real-model confirmation over opening a new method family.**

## Most important current research direction

The most important current direction is:

> **make diversity compete for budget through expected decision value, not through raw distance alone, and harden the family under real provider noise.**

Practically, this means:
- better realized answer-distinct branching,
- better scoring of diverse branches after they exist,
- dependence-aware answer-group aggregation,
- and more trustworthy real-model validation.

## What should happen next

### Immediate next step
- keep the broad diversity/aggregation family frozen as the main family,
- improve the quality of realized diversity and downstream branch scoring,
- and run larger but still controlled real-model confirmation using available providers.

### Near-term next layer
- use comparative mistake audits to drive method refinement,
- strengthen answer-group scoring and commit logic only when they solve a diagnosed residual,
- and keep simulator gains tied to real-model plausibility rather than letting the family drift.

### What should not be the default next move
- opening another unrelated controller family,
- another simulator-only broad campaign without realism follow-up,
- another local tweak that does not target the dominant residual groups,
- or broad paper-level claims that exceed current real-model evidence.

## Best reading path

If you are new to the repo, read:
1. `README.md`
2. `docs/CANONICAL_START_HERE.md`
3. `docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`
4. `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
5. `docs/MARGINAL_COVERAGE_DIVERSITY_STATUS_2026_04_18.md`
6. `docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md`
7. `docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md`
8. `docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md`

## Best code path

If you want the strongest current code path for the main family, start with:
- `experiments/controllers.py`
- `experiments/frontier_matrix_core.py`
- `experiments/objective_function_stack.py`
- `scripts/run_marginal_coverage_diversity_pass_20260418.py`
- `scripts/run_broad_diversity_aggregation_real_model_confirmation_20260418.py`
- `scripts/run_broad_diversity_aggregation_cohere_gemini_confirmation_20260418.py`
- `scripts/run_full_comparative_mistake_audit_vs_best_method_20260418.py`

## Safe high-level summary

A safe repository-facing summary is:

> The repository is now a strong platform for fixed-budget branch allocation in LLM reasoning. The leading direction is a broad diversity/aggregation family, the main remaining challenge is making useful diversity reliably materialize and be scored correctly, and the next major step is stronger real-model confirmation rather than a new method-family search.
