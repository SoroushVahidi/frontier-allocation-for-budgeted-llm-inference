# adaptive-reasoning-budget-allocation

## External baseline code

A license-aware status summary for baseline code resources is available at [`external/README.md`](external/README.md).

## Main datasets

The current research-facing dataset package is documented in [`docs/main_datasets.md`](docs/main_datasets.md) and the practical access/setup workflow is in [`docs/datasets_access.md`](docs/datasets_access.md). Repository data-handling policy and placeholder structure are described in [`datasets/README.md`](datasets/README.md). These documents are conservative by design and explicitly mark uncertain details or access conditions for later manual verification.

Quick HF access check command (writes JSON/CSV/MD only, no raw dataset commits):

- `python scripts/verify_hf_dataset_access.py --output-dir outputs/hf_dataset_access`

Wired HF dataset identifiers:
- `openai/gsm8k`
- `EleutherAI/hendrycks_math`
- `Idavidrein/gpqa` (gated)
- `Hothan/OlympiadBench`
- `livecodebench/code_generation_lite` (optional)

## Pilot experiment

The repository now includes a lightweight GSM8K pilot scaffold for testing basic adaptive reasoning-branch allocation ideas against simple baselines.

- Pilot description: [`experiments/pilot_gsm8k.md`](experiments/pilot_gsm8k.md)
- Default config: [`configs/pilot_gsm8k.yaml`](configs/pilot_gsm8k.yaml)
- Run command:
  - `python scripts/run_pilot_gsm8k.py --config configs/pilot_gsm8k.yaml`
- Evaluate command:
  - `python scripts/evaluate_pilot_gsm8k.py outputs/pilot/<run_id>`

This pilot is intentionally provisional and research-friendly: it can run in local simulation mode when no external model API is wired, while keeping controller logic and outputs easy to inspect.

## Real-model fixed-budget pilot (OpenAI + Gemini + optional Groq)

Small real-API pilot runner using the existing branch-allocation controllers on HF subsets:

- `python scripts/run_real_model_fixed_budget_pilot.py --subset-size 2 --max-actions 6 --include-best-of-n`
- Groq can be included via `--providers openai,gemini,groq` (or `--providers groq` for a tiny provider-only smoke run).
- Outputs (JSON/CSV/Markdown) are written under `output/real_model_fixed_budget_pilot/<run_id>/`.
- Supports datasets:
  - `openai/gsm8k`
  - `EleutherAI/hendrycks_math`


## Branch scorer v3 (decision-point ranking)

New empirical scripts for learned branch allocation:

- Build dataset: `python scripts/build_v3_ranking_dataset.py --output-dir outputs/branch_scorer_v3 --episodes 1500 --budget 10 --n-init-branches 5 --seed 7`
- Train scorers (v1/v2/v3): `python scripts/train_branch_scorer_v3.py --dataset outputs/branch_scorer_v3/branch_scorer_v3_dataset.jsonl --output-dir outputs/branch_scorer_v3`
- Controller-level comparison (includes lightweight `adaptive_eptree_baseline`): `python scripts/evaluate_branch_scorer_controller.py --model-dir outputs/branch_scorer_v3/models --output outputs/branch_scorer_v3/controller_eval.json --episodes 1000 --seed 19 --budget 10 --n-init-branches 5`
- Robustness sweep: `python scripts/evaluate_branch_scorer_robustness.py --model-dir outputs/branch_scorer_v3/models --output-dir outputs/branch_scorer_v3/robustness --seeds 3,7,11,19,23 --budgets 8,10,12 --init-branches 3,5,7 --episodes 400 --include-score-plus-progress`

See result note (progress-style v3 target and controller-level comparison): `experiments/branch_scorer_v3_result_note.md`.
