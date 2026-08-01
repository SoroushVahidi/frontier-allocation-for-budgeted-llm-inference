# Integrated allocator audit result note (new-paper track)

This note records a single integrated lightweight method experiment that combines:

1. controller-family routing,
2. difficulty-adaptive two-level budget allocation (`B-1` / `B+1`, fixed mean budget),
3. anti-collapse-aware guarded-controller override.

## Audit of existing lightweight paths before integration

- **Router path (implementation audit):** `experiments/frontier_router.py` and `scripts/run_cross_strategy_frontier_allocation.py` provide a lightweight text router (TF-IDF + logistic regression with constant fallback) over in-repo controller families.
- **Difficulty-adaptive path (implementation audit):** `scripts/run_new_paper_difficulty_adaptive_allocation.py` provides two-level allocation from a cheap hardness proxy learned on calibration outcomes.
- **Anti-collapse path (implementation + prior result):** `scripts/run_new_paper_anti_collapse_audit.py` and `docs/new_paper_anti_collapse_audit_note_2026-04-13.md` report reduced collapse-like behavior for `adaptive_budget_guarded`, but no clear win over best fixed-k in that pilot.
- **Real-model comparative frontier path (prior result):** `docs/new_paper_real_model_comparative_frontier_report_2026-04-14.md` + `outputs/comparative_frontier_audit/*` report that `adaptive_min_expand_1` remains weak on GSM8K real-model pilots versus several simpler baselines.

## Integrated method implementation

- Script: `scripts/run_integrated_allocator_audit.py`
- Method tag: `integrated_router_difficulty_anticollapse`
- Output pattern: `outputs/integrated_allocator_audit/<run_id>/`

## Real-model run executed

```bash
python scripts/run_integrated_allocator_audit.py \
  --datasets openai/gsm8k,EleutherAI/hendrycks_math \
  --subset-size 2 \
  --budget 8 \
  --adaptive-min-expand-grid 1 \
  --api-backend openai \
  --model gpt-4.1-mini \
  --timeout-seconds 25
```

- Completed run: `outputs/integrated_allocator_audit/20260414T005849Z/`
- Files written:
  - `method_metrics.csv`
  - `comparison_summary.csv`
  - `oracle_gap_summary.csv`
  - `integrated_method_report.md`
  - `run_manifest.json`

## Honesty on evidence strength

This run is **real-model** but **very pilot-scale** (`subset_size=2`, one eval item per dataset after calibration split). It is useful as an integration smoke test and method wiring check, not as publication-strength evidence.
