# Commands / assumptions / caveats
- Command run: `python scripts/run_natural_language_failure_casebook_dominant_group.py`.
- Leading-mode selection is based on latest validation aggregate summary under `multistep_branch_utility_target_validation_eval_20260417`.
- Taxonomy is rule-based from available fields (`multistep_delta_vs_onestep`, `branch_vs_outside_gap`, `near_tie`, `oracle_gap`, `k3_pred_margin_top2`).
- Full free-text branch reasoning traces are not present in inspected artifacts; branch explanations are reconstructed from stored branch-level signals, followup allocation mass, and feature proxies.
- Because dominant-group strict failures were fewer than 4, two backfill controls were included and explicitly labeled.
