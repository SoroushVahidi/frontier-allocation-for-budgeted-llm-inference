# Repository Map (Tracks, Paths, and Canonical Entry Points)

This map clarifies where things live without changing core experiment logic.

## Top-level layout

- `scripts/`: runnable entry points and orchestration scripts.
- `experiments/`: controller/search/data/scoring implementation modules and result notes.
- `docs/`: manuscript notes, direction notes, and reproducibility/status notes.
- `configs/`: experiment configs.
- `jobs/`: cluster job wrappers.
- `output/` and `outputs/`: generated artifacts (both exist; historical path inconsistency retained for compatibility).

## Track mapping

### A) Old manuscript track (binary revise-routing)

Primary scripts:
- `scripts/run_heavy_real_routing_eval.sh`

Supporting docs/examples:
- `docs/safe_manuscript_claims_2026-04-13.md`
- `docs/manuscript_support_index_2026-04-13.md`

Typical output roots:
- `outputs/real_model_fixed_budget_heavy/` (from heavy matrix script defaults)

### B) New frontier/controller-allocation track

Primary scripts:
- `scripts/run_cross_strategy_frontier_allocation.py`  
  (legacy filename; used for cross-controller frontier allocation scaffold)
- `scripts/run_multi_action_allocation_pass.sh`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`
- `scripts/build_v3_ranking_dataset.py`
- `scripts/train_branch_scorer_v3.py`

Supporting code:
- `experiments/controllers.py`
- `experiments/branch_scorer_v3.py`
- `experiments/branching.py`
- `experiments/scoring.py`

Typical output roots:
- `outputs/branch_scorer_v3/`
- `outputs/multi_action_allocation_pass/`
- `outputs/branch_scorer_v3_final_eval/`

## Docs organization guidance

### Canonical orientation docs

- `README.md` (top-level navigation)
- `docs/OLD_VS_NEW_PAPER_TRACKS.md` (track split + naming policy)
- `docs/NEXT_PAPER_SUMMARY_AND_GOALS.md` (new-paper framing)
- `docs/REPO_MAP.md` (this map)

### Historical / dated notes

Many files in `docs/` are timestamped working notes (e.g., `*_2026-04-13.md`).
They are retained for provenance and should not be treated as single-source canonical navigation docs.

## Known intentional messiness left untouched

- `output/` and `outputs/` both exist.
  - Kept intact to avoid breaking prior commands and references.
- Some script names include `cross_strategy` while docs now prefer `cross-controller frontier allocation`.
  - Kept for backward compatibility; naming clarification is handled in docs.
