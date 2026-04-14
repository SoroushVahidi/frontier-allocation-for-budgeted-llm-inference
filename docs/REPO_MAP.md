# Repository map (tracks, paths, and status labels)

This map is for navigation and interpretation, not for changing experiments.

## Top-level structure

- `scripts/`: runnable entry points and orchestration.
- `experiments/`: core implementation modules + compact result notes.
- `docs/`: navigation docs, status notes, historical memos.
- `configs/`: registries/configs for pilots, baselines, and datasets.
- `datasets/`: dataset policy and controlled manifests.
- `outputs/`: generated artifacts (gitignored).

## Two-track mapping (do not mix)

### A) Old manuscript track — binary revise-routing

- Research question: **when should we revise?**
- Status: **canonical for existing submitted manuscript support**.
- Main script: `scripts/run_heavy_real_routing_eval.sh`
- Main docs: `docs/safe_manuscript_claims_2026-04-13.md`, `docs/manuscript_support_index_2026-04-13.md`

### B) New paper track — cross-controller frontier allocation

- Research question: **where should the next unit of compute go?**
- Status: **canonical active research track**.
- Main scripts:
  - `scripts/run_cross_strategy_frontier_allocation.py` (legacy filename)
  - `scripts/run_multi_action_allocation_pass.sh`
  - `scripts/evaluate_branch_scorer_controller.py`
  - `scripts/evaluate_branch_scorer_robustness.py`
- Main docs:
  - `docs/NEW_PAPER_CURRENT_STATUS.md`
  - `docs/NEW_PAPER_CURRENT_BOTTLENECKS.md`
  - `docs/BRANCH_SCORER_STATUS.md`

## Branch-scorer and dataset layers in the new-paper track

- Branch-scorer family notes in `experiments/*branch_scorer*_result_note.md` are mostly **exploratory result notes**.
- External reasoning datasets and baseline registries in `configs/*registry*.json` are **integration/preparation resources**, not final-method evidence by themselves.
- Pairwise diagnostics and reliability-weighted BT are **promising but not default** until robustness and transfer evidence is stronger.

## Historical conventions intentionally preserved

- Some script names use `cross_strategy` for backward compatibility; docs use “cross-controller frontier allocation”.
- Dated notes remain in place for provenance and should be interpreted via `docs/README.md`.
