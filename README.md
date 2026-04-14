# adaptive-reasoning-budget-allocation

This repository now contains **two clearly separated research tracks**:

1. **Current submitted manuscript track**: binary adaptive routing / "when to revise".
2. **Emerging next-paper track**: cross-controller frontier allocation / controller-allocation under fixed budget.

**Documentation index:** [`docs/README.md`](docs/README.md). **Runnable scripts:** [`scripts/README.md`](scripts/README.md).

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
- Overview and methods context: [`docs/cross_controller_frontier.md`](docs/cross_controller_frontier.md)

Primary script entry points:

- `scripts/run_cross_strategy_frontier_allocation.py` (frontier scaffold; legacy filename retained)
- `scripts/run_multi_action_allocation_pass.sh`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`

Frontier runner details: add `--use-openai-api` for a small real-model pilot. Registered families include **`verifier_guided_search`** (sample then verifier-ranked selection) and **`program_of_thought`** (code generation + local sandbox execution). Cheap simulator-only smoke: `python scripts/smoke_frontier_methods.py`.

**Real-model fixed-budget pilot** (OpenAI + Gemini + optional Groq), using branch-allocation controllers on HF subsets:

- `python scripts/run_real_model_fixed_budget_pilot.py --subset-size 2 --max-actions 6 --include-best-of-n`
- Groq: `--providers openai,gemini,groq` (or `--providers groq` for a tiny provider-only smoke run).
- Outputs: `outputs/real_model_fixed_budget_pilot/<run_id>/` (JSON/CSV/Markdown).

**Branch scorer v3** (decision-point ranking):

- Build dataset: `python scripts/build_v3_ranking_dataset.py --output-dir outputs/branch_scorer_v3 --episodes 1500 --budget 10 --n-init-branches 5 --seed 7`
- Train: `python scripts/train_branch_scorer_v3.py --dataset outputs/branch_scorer_v3/branch_scorer_v3_dataset.jsonl --output-dir outputs/branch_scorer_v3`
- Controller comparison: `python scripts/evaluate_branch_scorer_controller.py --model-dir outputs/branch_scorer_v3/models --output outputs/branch_scorer_v3/controller_eval.json --episodes 1000 --seed 19 --budget 10 --n-init-branches 5`
- Robustness sweep: `python scripts/evaluate_branch_scorer_robustness.py --model-dir outputs/branch_scorer_v3/models --output-dir outputs/branch_scorer_v3/robustness --seeds 3,7,11,19,23 --budgets 8,10,12 --init-branches 3,5,7 --episodes 400 --include-score-plus-progress`

Result note: `experiments/branch_scorer_v3_result_note.md`.

## Datasets and access

Main dataset docs:

- [`docs/main_datasets.md`](docs/main_datasets.md)
- [`docs/datasets_access.md`](docs/datasets_access.md)
- [`datasets/README.md`](datasets/README.md)

**Paper-priority HF keys** (see `experiments/hf_datasets.py`): `hendrycks/competition_math` / `EleutherAI/hendrycks_math` (MATH), `Idavidrein/gpqa` (GPQA Diamond), `HuggingFaceH4/aime_2024` (AIME 2024 slice), `Hothan/OlympiadBench` (OlympiadBench mirror). **NaturalPlan** is tracked in docs only (GitHub upstream). Generate a local integration report: `python scripts/generate_dataset_integration_report.py` → `outputs/dataset_integration_report.{json,md}`.

Quick HF access check command (writes JSON/CSV/MD only, no raw dataset commits):

- `python scripts/verify_hf_dataset_access.py --output-dir outputs/hf_dataset_access`

New-paper external reasoning-supervision integration report (PRM800K / Math-Shepherd / UltraInteract):

- `python scripts/generate_external_reasoning_dataset_integration_report.py`
  → `outputs/external_reasoning_datasets/<run_id>/dataset_integration_report.{json,md,csv}` + `dataset_access_status.json`

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

Machine-readable registry: `configs/external_baselines_registry.json`. Refresh the audited integration report: `python scripts/generate_external_baseline_integration_report.py` → `outputs/external_baseline_integration_report.{json,md}`.
