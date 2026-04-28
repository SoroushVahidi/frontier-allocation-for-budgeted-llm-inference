# Cohere API Readiness Issue — direct_reserve_semantic_frontier_v2_thresholded_ordered (small diagnostic)

- Timestamp (UTC): 20260428T175246Z
- Readiness pass: **failed**
- Failure class: `missing_env_var`
- COHERE_API_KEY: `absent`

## Sanitized error tail

```
COHERE_API_KEY environment variable is not set in this shell session.
```

## Live diagnostic command that would have been run

```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp 20260428T175246Z \
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

## How to fix / rerun

1. Export a valid Cohere API key in the same shell/session running the command:
   ```bash
   export COHERE_API_KEY='***'
   ```
2. Re-run readiness check and print only key presence:
   ```bash
   python - <<'PY'
   import os
   print('COHERE_API_KEY: present' if os.getenv('COHERE_API_KEY') else 'COHERE_API_KEY: absent')
   PY
   ```
3. Re-run the small diagnostic command above (max 8 selected cases).
4. Run offline analysis:
   ```bash
   python scripts/analyze_semantic_diversity_diagnostic_run.py --timestamp 20260428T175246Z
   ```

## Notes

- No live Cohere diagnostic was executed.
- This is diagnostic-only and should not be treated as manuscript evidence.
