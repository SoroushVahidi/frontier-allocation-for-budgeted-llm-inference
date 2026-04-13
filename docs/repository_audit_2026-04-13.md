# Repository audit note (2026-04-13)

This note records the current state of the `main` branch after a live repository check.

## 1. What is clearly present on `main`

### Core pilot scaffold
The repository contains the lightweight GSM8K pilot scaffold and its associated controller/data/runner/evaluator code.

### Early merged PRs
The visible merged PR history on `main` clearly includes:
- dataset and baseline documentation
- lightweight GSM8K pilot scaffold
- API-backed branch generator and adaptive diagnostics
- minimum-expansions safeguard for the adaptive controller

### Manuscript-support notes
The repository also contains the internal manuscript-support notes in `docs/`, including the theory and citation-discipline memos.

## 2. What appears to be missing from `main`

A live file check indicates that later learned-scorer files discussed during project work are not currently present on `main`, including examples such as:
- `scripts/evaluate_branch_scorer_robustness.py`
- `experiments/branch_scorer_v3_result_note.md`

This suggests that some later v3 / robustness-sweep work may exist outside `main` (for example in a local branch, another branch, another repository, or only in conversation reports) but is not yet merged into the main repository branch.

## 3. README status

The top-level `README.md` is still the earlier pilot-oriented version and does not yet reflect the fuller learned-scorer and robustness-evaluation trajectory described in later project work.

## 4. Main practical implication

Before manuscript writing moves too far forward, the project should ensure that the code and results we intend to rely on are actually present in the canonical repository branch or are otherwise explicitly tracked.

## 5. Recommended follow-up

The repository should eventually be reconciled so that:
1. the canonical branch contains the intended learned-scorer pipeline and evaluation scripts,
2. the README reflects the current empirical state,
3. manuscript claims only rely on code and artifacts that are actually present and reproducible from the repo.

## 6. Status

This note is only an audit snapshot of `main` as checked on 2026-04-13. It should be updated or removed once the repository state is reconciled.