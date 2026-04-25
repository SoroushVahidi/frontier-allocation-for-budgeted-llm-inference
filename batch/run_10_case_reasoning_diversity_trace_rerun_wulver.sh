#!/usr/bin/env bash
set -euo pipefail
TS="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
python scripts/run_10_case_reasoning_diversity_trace_rerun.py \
  --timestamp "$TS" \
  --max-cases 10 \
  --case-package outputs/ten_case_loss_deep_dive_20260425T221500Z/ \
  --case-report docs/TEN_CASE_LOSS_DEEP_DIVE_20260425T221500Z.md \
  --provider cohere \
  --cohere-model command-r-plus-08-2024 \
  --methods strict_f3,strict_f3_reasoning_diversity_bonus_v1,external_l1_max \
  --skip-real-api-if-no-key \
  --emit-full-traces \
  --temperature 0.2 \
  --max-output-tokens 180 \
  --timeout-seconds 45
