#!/usr/bin/env bash
set -euo pipefail
.venv-test/bin/python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN --providers cohere --datasets openai/gsm8k --budgets 4,6,8 --seeds 11,23 --methods strict_f3,external_l1_max,direct_reserve_frontier_gate_v1 --target-scored-per-slice 5 --max-examples 5 --save-branch-traces
