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

# Production-leaning heavy generator command (single-manifest mode).
# For sharded pilot runs, prefer pre-splitting state manifests and submitting
# one job per shard with shard-specific ORACLE_STATE_MANIFEST + output-dir.
GENERATOR_CMD='python3 scripts/run_oracle_label_generator_heavy.py --pilot-config "$ORACLE_PILOT_CONFIG" --selection-config configs/stop_vs_act_oracle_pilot_state_selection_v1.json --state-manifest "$ORACLE_STATE_MANIFEST" --output-dir "$ORACLE_OUTPUT_DIR" --seed 7 --resume --progress-every 50'

scripts/run_oracle_label_pilot_hpc.sh \
  --build-state-manifest \
  --generator-cmd "$GENERATOR_CMD"
