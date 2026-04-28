# Direct Reserve v2 Thresholded+Ordered Cohere API Issue (20260428T173311Z)

## Cohere readiness
- COHERE_API_KEY: absent
- readiness_passed: no
- failure_class: missing_env_var

## Sanitized error tail
- No COHERE_API_KEY environment variable was available in the execution environment, so live Cohere diagnostics were not attempted.

## Live diagnostic command that would have been run
```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp 20260428T173311Z \
  --mode cohere \
  --run-live-cohere \
  --selection-profile expanded-loss-pool \
  --max-cases 8 \
  --allow-duplicate-example-fallback \
  --methods external_l1_max,strict_f3,direct_reserve_semantic_frontier_v1,direct_reserve_semantic_frontier_v2_thresholded_ordered \
  --budgets 4,6,8 \
  --emit-full-traces \
  --dataset-name openai/gsm8k
```

## Fix / rerun instructions
1. Export a valid key in the shell before running diagnostics:
   - `export COHERE_API_KEY=...`
2. Re-run a minimal readiness smoke check (without printing the key):
   - `python - <<'PY'\nimport os\nprint('COHERE_API_KEY: present' if os.getenv('COHERE_API_KEY') else 'COHERE_API_KEY: absent')\nPY`
3. Re-run the small diagnostic command above (max 8 selected cases).
4. Run offline analysis:
   - `python scripts/analyze_semantic_diversity_diagnostic_run.py --timestamp 20260428T173311Z`

## Notes
- No live Cohere calls were executed in this pass.
- This remains diagnostic-only and does not affect manuscript claims.
