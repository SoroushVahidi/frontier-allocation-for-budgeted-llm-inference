# Reasoning-Diversity Trace Rerun (10-case) Guide

## Safe dry-run/smoke
```bash
python scripts/run_10_case_reasoning_diversity_trace_rerun.py \
  --timestamp 20260426T000000Z \
  --max-cases 10 \
  --dry-run \
  --skip-real-api-if-no-key \
  --emit-full-traces
```

## Real Cohere 10-case command (strictly capped)
```bash
python scripts/run_10_case_reasoning_diversity_trace_rerun.py \
  --timestamp 20260426T000000Z \
  --max-cases 10 \
  --provider cohere \
  --cohere-model command-r-plus-08-2024 \
  --methods strict_f3,strict_f3_reasoning_diversity_bonus_v1,external_l1_max \
  --skip-real-api-if-no-key \
  --emit-full-traces \
  --temperature 0.2 \
  --max-output-tokens 180 \
  --timeout-seconds 45
```

If `COHERE_API_KEY` is missing and `--skip-real-api-if-no-key` is present, the run exits gracefully with a missing-key report and still writes a complete diagnostic package scaffold.

## Wulver batch submission
Use:
```bash
bash batch/run_10_case_reasoning_diversity_trace_rerun_wulver.sh
```

Outputs are written under:
`outputs/ten_case_reasoning_diversity_trace_rerun_<TIMESTAMP>/`.

All outputs are diagnostic/probe-labeled and do not modify canonical paper tables.
