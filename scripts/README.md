# Scripts

Entry points for pilots, evaluation, and maintenance. All write ephemeral results under **`outputs/`** unless overridden.

| Script | Purpose |
|--------|---------|
| `run_pilot_gsm8k.py` | GSM8K pilot from `configs/pilot_gsm8k.yaml` |
| `evaluate_pilot_gsm8k.py` | Summarize a pilot run directory |
| `run_real_model_fixed_budget_pilot.py` | Real-API fixed-budget pilot (OpenAI / Gemini / optional Groq) |
| `run_cross_strategy_frontier_allocation.py` | Cross-controller frontier allocation track |
| `run_new_paper_frontier_matrix.py` | Multi-dataset frontier matrix + anti-collapse tables |
| `run_comparative_frontier_audit.py` | Matched-budget audit: primary adaptive vs baselines → `main_drawbacks_report.md` |
| `run_new_paper_prm_branch_scoring.py` | PRM-style partial-branch scoring + early-rejection audit (new-paper track) |
| `run_new_paper_external_warmstart_branch_scorer.py` | External warm-start vs internal-only branch-scorer comparison (new-paper track) |
| `smoke_frontier_methods.py` | Simulator-only smoke for frontier methods |
| `verify_hf_dataset_access.py` | HF dataset access check → `outputs/hf_dataset_access` (default) |
| `dataset_smoke_sample.py` | Small dataset smoke samples |
| `generate_dataset_integration_report.py` | `outputs/dataset_integration_report.{json,md}` |
| `verify_external_reasoning_datasets.py` | Verify access + schema preview for PRM800K / Math-Shepherd / UltraInteract datasets |
| `generate_external_reasoning_dataset_integration_report.py` | Run-id report artifacts under `outputs/external_reasoning_datasets/<run_id>/` |
| `prepare_external_reasoning_datasets.py` | Readiness scoring + lightweight normalized previews under `outputs/prepared_reasoning_datasets/<run_id>/` |
| `generate_external_baseline_integration_report.py` | `outputs/external_baseline_integration_report.{json,md}` |
| `list_external_baselines.py` | Print `configs/external_baselines_registry.json` |
| `smoke_test.py` | Minimal repo smoke test |

Training and branch-scorer workflows: `build_v3_ranking_dataset.py`, `train_branch_scorer_v3.py`, `evaluate_branch_scorer_controller.py`, `evaluate_branch_scorer_robustness.py`, and shell helpers `run_*.sh` as needed.
