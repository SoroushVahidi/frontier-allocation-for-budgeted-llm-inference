# Asset audit and current working set (2026-04-17)

## Purpose

This note records which repository assets currently matter most for continuation work and how they should be interpreted.

It is designed to answer three practical questions quickly:
1. what assets are currently strongest,
2. what assets are still useful but secondary,
3. and what assets should not define the next iteration.

## Current highest-value working set

### A. Canonical interpretation docs
These should define the default project understanding.

- `docs/CURRENT_PROJECT_STATUS.md`
- `docs/CURRENT_BOTTLENECKS.md`
- `docs/CURRENT_SAFE_CLAIMS.md`
- `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
- `docs/WHAT_IS_NOT_WORKING_NOW.md`
- `docs/RESEARCH_UPGRADE_NOTE_2026_04_17.md`
- `docs/PAPER_POSITIONING_NOTE.md`
- `docs/REPO_MAP.md`

### B. Current strongest method-status docs
These are the most useful method-specific status notes right now.

- `docs/HARD_CASE_FEATURE_REPRESENTATION_STATUS.md`
- `docs/TARGET_FIDELITY_BRANCH_COMPARISON_STATUS.md`
- `docs/NEAR_TIE_POINTWISE_EXPERT_STATUS.md`
- `docs/STRICT_COUPLED_NEAR_TIE_CONTROLLER_STATUS.md`
- `docs/STRICT_COUPLED_TIE_AWARE_POSTHOC_DEFERRAL_STATUS.md`
- `docs/STRICT_COUPLED_TIE_AWARE_DEFERRED_EXPERT_IMPROVEMENT_STATUS.md`
- `docs/STRICT_COUPLED_TIE_AWARE_LEARNED_TWO_STAGE_DEFERRAL_STATUS.md`
- `docs/imported_methodology_frontier_integration_report.md`

### C. Current strongest code working set
These are the main scripts/modules for current continuation work.

- `scripts/run_near_tie_pointwise_expert_experiment.py`
- `scripts/run_imported_methodology_frontier_eval.py`
- `scripts/run_near_tie_policy_experiment.py`
- `scripts/run_target_fidelity_regime_experiment.py`
- `scripts/train_bruteforce_branch_allocator.py`
- `experiments/bruteforce_branch_allocator.py`

### D. Current highest-value artifact families
These are the output families most likely to matter for paper-quality continuation.

- `outputs/branch_label_bruteforce_merged/`
- `outputs/branch_label_bruteforce_targets/`
- `outputs/branch_label_bruteforce_learning/`
- `outputs/imported_methodology_frontier_eval/`
- `outputs/external_baseline_completeness/`
- `outputs/external_baseline_runnability/`

## Assets that are useful but not currently central

- older stop-vs-act-specific notes,
- broad exploratory BT variants not clearly promoted,
- one-off ambiguity/fallback variants that did not improve the strongest scaffold,
- historical manuscript-support wrappers.

These remain useful for provenance and comparison, but they should not drive the next method step.

## Assets that should not define the next pass

- old binary revise-routing material,
- generic model-class swaps without stronger supervision/decision logic,
- narrower specialist-subset variants that already failed bounded tests,
- evaluation layers that ignore current strongest pairwise/tie-aware checkpoints.

## Current interpretation of the best scaffold

The current best scaffold is:

> pairwise default comparator + `v2` hard-case representation + tie-aware / strict-coupled ambiguity handling + specialist pointwise fallback + imported manuscript-style evaluation layer.

This is not yet a final winning method, but it is the right scaffold to improve from.

## Most useful unresolved asset gap

The main remaining asset gap is not another large code family.
It is a cleaner and more compact bridge from:
- the strongest current controller,
- to manuscript-facing evaluation,
- to the final paper framing.

That is why the imported-methodology frontier evaluation layer and the new continuation notes are now part of the working set.

## Practical collaborator rule

If starting a new bounded pass, read in this order:
1. `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
2. `docs/WHAT_IS_NOT_WORKING_NOW.md`
3. `docs/RESEARCH_UPGRADE_NOTE_2026_04_17.md`
4. the most relevant current method-status note
5. the relevant script entry point in `scripts/`

## Practical writing rule

For manuscript work, prefer citing or summarizing from:
- the canonical docs,
- the strongest current method-status docs,
- and the imported frontier evaluation artifacts,
not from older exploratory notes unless provenance specifically requires it.
