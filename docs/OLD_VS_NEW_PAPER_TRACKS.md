# Old vs New Paper Tracks (Repository Grounding)

This note is a **navigation and naming guardrail** for the repository.

## 1) Current submitted manuscript track (old track)

- Working title line: **When to Revise: Cost-Aware Adaptive Routing for LLM Reasoning**.
- Core problem: query-level **binary** routing (cheap route vs revise route).
- Canonical question: **"When should we revise?"**

Typical artifacts in this track:
- Manuscript-support notes in `docs/*manuscript*` and conservative claim notes.
- Heavy routing script: `scripts/run_heavy_real_routing_eval.sh`.

## 2) Emerging next-paper track (new track)

- Core problem: budgeted allocation across a frontier of controllers.
- Canonical question: **"Where should the next unit of compute go?"**
- Preferred naming: **cross-controller frontier allocation**.

Typical artifacts in this track:
- `scripts/run_cross_strategy_frontier_allocation.py` (legacy filename; conceptually cross-controller frontier allocation).
- `scripts/run_multi_action_allocation_pass.sh`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`
- `docs/NEXT_PAPER_SUMMARY_AND_GOALS.md`

## 3) Terminology policy

Use these terms in docs for the new track:

- Preferred:
  - **cross-controller frontier allocation**
  - **controller allocation under fixed budget**
  - **frontier headroom / oracle frontier headroom**
  - **anti-collapse controller design**

- Use with caution:
  - **cross-strategy** (acceptable only as legacy naming if script/file names already use it)

- Avoid overclaiming:
  - Do not claim strong heterogeneity when current strategy sets are still mostly controller/search variants.

## 4) What stays intentionally unchanged in this cleanup

- Existing script filenames are mostly preserved for reproducibility.
- Existing dated notes are retained (no artifact deletion in this pass).
- Existing `output/` and `outputs/` paths are preserved; see `docs/REPO_MAP.md` for usage guidance.
