# adaptive-reasoning-budget-allocation

This repository now contains **two clearly separated research tracks**:

1. **Current submitted manuscript track**: binary adaptive routing / "when to revise".
2. **Emerging next-paper track**: cross-controller frontier allocation / controller-allocation under fixed budget.

The goal of this README is navigation clarity, not a redesign of experiments.

## Start here (high-value navigation)

- Track split and canonical terminology:
  - [`docs/OLD_VS_NEW_PAPER_TRACKS.md`](docs/OLD_VS_NEW_PAPER_TRACKS.md)
- Repository map (where scripts, docs, and outputs live):
  - [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
- Next-paper framing and goals:
  - [`docs/NEXT_PAPER_SUMMARY_AND_GOALS.md`](docs/NEXT_PAPER_SUMMARY_AND_GOALS.md)

## Track A: current submitted manuscript (binary revise-routing)

Use this track for the existing manuscript story:

- **Question**: *When should we revise?*
- **Core framing**: query-level binary adaptive routing (cheap route vs revise route)

Primary script entry point:
- `scripts/run_heavy_real_routing_eval.sh`

Related docs with manuscript-facing positioning:
- `docs/safe_manuscript_claims_2026-04-13.md`
- `docs/manuscript_support_index_2026-04-13.md`

## Track B: next paper (cross-controller frontier allocation)

Use this track for the emerging paper direction:

- **Question**: *Where should the next unit of compute go?*
- **Core framing**: cross-controller frontier allocation under fixed budget

Primary script entry points:
- `scripts/run_cross_strategy_frontier_allocation.py` (frontier scaffold; legacy filename retained)
- `scripts/run_multi_action_allocation_pass.sh`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`

## Datasets and access

Main dataset docs:
- [`docs/main_datasets.md`](docs/main_datasets.md)
- [`docs/datasets_access.md`](docs/datasets_access.md)
- [`datasets/README.md`](datasets/README.md)

Quick HF access check command (writes JSON/CSV/MD only, no raw dataset commits):

- `python scripts/verify_hf_dataset_access.py --output-dir outputs/hf_dataset_access`

Wired HF dataset identifiers:
- `openai/gsm8k`
- `EleutherAI/hendrycks_math`
- `Idavidrein/gpqa` (gated)
- `Hothan/OlympiadBench`
- `livecodebench/code_generation_lite` (optional)

## Pilot experiment scaffold

- Pilot description: [`experiments/pilot_gsm8k.md`](experiments/pilot_gsm8k.md)
- Default config: [`configs/pilot_gsm8k.yaml`](configs/pilot_gsm8k.yaml)
- Run: `python scripts/run_pilot_gsm8k.py --config configs/pilot_gsm8k.yaml`
- Evaluate: `python scripts/evaluate_pilot_gsm8k.py outputs/pilot/<run_id>`

## External baseline code

A license-aware status summary for baseline code resources is available at [`external/README.md`](external/README.md).
