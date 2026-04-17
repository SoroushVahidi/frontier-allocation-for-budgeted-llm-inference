# Full repository audit and polish summary (2026-04-18)

## Purpose

This note provides a compact, repository-facing summary of the current state of `adaptive-reasoning-budget-allocation` after the recent branch-allocation, ambiguity-handling, penalized-marginal, and Cohere-bounded passes.

It is intended to answer four practical questions for future collaborators and paper work:
1. What is this repository actually about now?
2. What is already organized and working well?
3. What is still noisy, overloaded, or easy to misread?
4. What is the best continuation path from the current state?

## Repository identity

The canonical project is:

> **fixed-budget adaptive test-time compute allocation for LLM reasoning, centered on which active branch should receive the next unit of compute.**

This repository is **not** the old binary revise-routing paper. It should be interpreted primarily through branch allocation, frontier allocation, anti-collapse control, target fidelity, and ambiguity-aware supervision.

## What is already in good shape

### 1. The repository identity is now clear

The top-level README, canonical docs, and scripts index all point to the same current project identity.

### 2. Canonical vs exploratory vs historical interpretation is explicit

The repo now has a usable interpretation structure:
- **canonical** docs for current project truth,
- **exploratory** notes for active but non-default lines,
- **historical** material for provenance only.

### 3. The hard-case supervision bottleneck is honestly documented

The repo is unusually strong on bottleneck clarity. It does not pretend the main problem is merely larger models or more data. The strongest current wording is that the bottleneck is principled treatment of hard ambiguous branch-comparison supervision.

### 4. The runnable code path is substantial

This is not only a documentation repo. There is a real experiment stack for:
- frontier/controller comparisons,
- brute-force label generation,
- target-regime construction,
- ambiguity / defer / fallback experiments,
- exact-vs-approx audits,
- hard-case feature passes,
- and bounded external/Cohere comparison paths.

### 5. Provenance discipline is good

The repo already records many analyses through:
- dated method-status notes,
- manifest-backed scripts,
- outputs written under `outputs/`,
- safe-claims discipline,
- and bounded-result interpretation.

## What is still noisy or easy to misread

### 1. The repo still has high surface area

The docs are much cleaner than before, but the repository remains large and method-rich. A new collaborator can still be overwhelmed by the number of active hard-case lines.

### 2. The scripts index is informative but dense

`scripts/README.md` is usable, but it still functions more as a comprehensive index than as a very short “do these three things first” operator guide.

### 3. Several method passes remain bounded rather than settled

The recent hard-pair, defer-target, penalized-marginal, and Cohere-related passes are valuable, but most should still be treated as **bounded evidence**, not final canonical wins.

### 4. The current best method story is still supervision-centered rather than winner-centered

The repo now supports a strong paper direction, but not yet a simple “this one learned allocator is the robust universal winner” claim.

### 5. There is still a risk of accidental old-track drift

Despite strong README language, future contributors could still drift into stop-vs-act or old revise-routing framing if they skip the canonical docs.

## Best reading path today

If you need the shortest reliable understanding path, use:

1. `docs/CANONICAL_START_HERE.md`
2. `docs/CURRENT_PROJECT_STATUS.md`
3. `docs/CURRENT_BOTTLENECKS.md`
4. `docs/CURRENT_SAFE_CLAIMS.md`
5. `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
6. `docs/STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md`
7. `docs/REPOSITORY_AUDIT_AND_NEXT_STEP_2026_04_18.md`
8. `scripts/CANONICAL_START_HERE.md`
9. `scripts/README.md`

## Best code path today

For current branch-allocation work, the highest-value runnable core is:
- `scripts/run_bruteforce_branch_label_generator.py`
- `scripts/build_bruteforce_target_regimes.py`
- `scripts/train_bruteforce_branch_allocator.py`
- `scripts/run_target_fidelity_regime_experiment.py`
- `scripts/run_ternary_or_abstain_branch_comparison_experiment.py`
- `scripts/run_structured_ambiguity_experiment.py`
- `scripts/run_defer_fallback_experiment.py`

These are the most useful entry points for understanding how supervision and selective control are currently being studied.

## Current strongest repository-level interpretation

The best current one-paragraph interpretation is:

> This repository is a strong research platform for fixed-budget branch allocation in LLM reasoning. Its main open problem is not missing infrastructure, but learning better supervision and selective control for ambiguous hard branch comparisons. The hardest close-call states should increasingly be interpreted as structured ambiguity objects that may require defer / unresolved treatment rather than forced binary commitment.

## Organization recommendations

### Keep doing
- maintain the canonical/exploratory/historical distinction,
- record bounded experiment summaries in `docs/`,
- write machine-readable summaries in `outputs/`,
- preserve manifest-backed runs and explicit caveats.

### Prefer more of
- short continuation-oriented audit notes,
- method-status summaries that explain what changed and what did not,
- explicit notes on whether a pass is canonical, exploratory, or bounded.

### Avoid
- presenting bounded passes as default truth,
- mixing old revise-routing framing into new branch-allocation docs,
- adding more method families without equally clear interpretation notes.

## Practical next repository-cleanup step

The next highest-value polish step is:

> **keep the code structure mostly stable, but continue adding compact continuation-oriented audit notes and summary artifacts whenever a bounded method pass changes the interpretation of the repo.**

This repo is already intellectually well organized; the most useful polish now is not a massive file move, but keeping the continuation path explicit and easy to recover.

## Safe repo-facing conclusion

A conservative but accurate summary is:

> The repository is now well enough organized to support serious collaborator onboarding and paper planning. Its main remaining challenge is not understanding what the project is, but improving the supervision semantics and selective ambiguity handling at the heart of the branch-allocation problem.
