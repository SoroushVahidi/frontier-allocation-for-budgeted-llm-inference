# REPRODUCTION_CHECKLIST

## 1) Environment setup
- Use Python 3.10+ (recommended 3.11 if available).
- Create and activate a virtual environment.
- Install dependencies from project requirements (if using local workflow, use existing project setup commands documented in README/scripts).

Suggested bootstrap:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Smoke and health checks
```bash
python scripts/check_repo_health.py
python -m py_compile scripts/build_10_case_loss_deep_dive.py
python -m py_compile scripts/run_family_normalized_rerank_eval.py
python -m py_compile scripts/run_typed_strategy_seeded_eval.py
python -m py_compile scripts/run_direction_combinatorics_guard_eval.py
```

## 3) Tests (lightweight/local)
```bash
python -m pytest tests/test_ten_case_loss_deep_dive.py \
  tests/test_family_normalized_rerank.py \
  tests/test_typed_strategy_seeded.py \
  tests/test_direction_combinatorics_guard.py
```

## 4) Canonical paper table regeneration
```bash
python scripts/run_broader_strict_phased_default_decision_eval.py
python scripts/run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py
python scripts/build_paper_facing_baseline_tables.py
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Expected canonical outputs:
- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

## 5) Real-model validation requirements (optional, non-canonical for headline claims)
- Requires provider API credentials configured in environment variables.
- Do not print keys in logs or scripts.
- Do not run expensive real-API sweeps unless explicitly planned.
- Real-model outputs are diagnostic/supporting evidence unless promoted by canonical claim policy.

## 6) Wulver batch script locations
- `batch/*.sbatch` (primary batch launchers)
- `jobs/*.sbatch` (extended job entrypoints)
- `logs/slurm/*.out|*.err` (cluster run evidence)

## 7) API key handling
- Keep keys in environment variables only.
- Never commit `.env` with secrets.
- Never include secrets in docs, logs, or artifact JSON/CSV.

## 8) Known limitations to document in any reproduction report
- Real-model comparisons are diagnostic and can show external baseline wins.
- Diagnostic variants are not final methods unless promoted.
- Some historical runs lack complete branch traces.
- Loss-case closure remains incomplete (present-not-selected and absent-from-tree remain active failure modes).
