#!/usr/bin/env bash
#SBATCH --job-name=oracle-label-pilot-v1
#SBATCH --output=outputs/slurm/%x-%j.out
#SBATCH --error=outputs/slurm/%x-%j.err
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G

# Optional (cluster-specific):
# SBATCH --partition=...
# SBATCH --gres=gpu:1

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
cd "$REPO_ROOT"
mkdir -p outputs/slurm

# TODO: replace this placeholder with the real heavy generator entrypoint.
# Interface smoke-test example (testing only, not real oracle labels):
# GENERATOR_PLACEHOLDER='python3 scripts/run_oracle_label_generator_interface_stub.py --pilot-config "$ORACLE_PILOT_CONFIG" --state-manifest "$ORACLE_STATE_MANIFEST" --output-dir "$ORACLE_OUTPUT_DIR" --mock-mode --seed 7 --max-states 24'
# Prototype real-rollout example (limited subset, still not full production scale):
# GENERATOR_PLACEHOLDER='python3 scripts/run_oracle_label_generator_prototype.py --pilot-config "$ORACLE_PILOT_CONFIG" --selection-config configs/stop_vs_act_oracle_pilot_state_selection_v1.json --state-manifest "$ORACLE_STATE_MANIFEST" --output-dir "$ORACLE_OUTPUT_DIR" --max-states 64 --seed 7 --paired-rollouts 16'
# It must consume ORACLE_* env vars exported by the wrapper and write:
# - $ORACLE_LABELS_JSONL
# - $ORACLE_LABEL_MANIFEST
GENERATOR_PLACEHOLDER='python3 -c "import sys; raise SystemExit(9)"'

scripts/run_oracle_label_pilot_hpc.sh \
  --build-state-manifest \
  --generator-cmd "$GENERATOR_PLACEHOLDER"
