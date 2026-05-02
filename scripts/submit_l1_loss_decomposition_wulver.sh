#!/usr/bin/env bash
# Submit L1 loss decomposition batch job on Wulver with a fresh UTC stamp.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
export OUTDIR="${OUTDIR:-outputs/l1_loss_decomposition_best_selector_${STAMP}}"
export MAX_CALLS="${MAX_CALLS:-12400}"

mkdir -p logs/slurm

echo "Submitting with STAMP=${STAMP} OUTDIR=${OUTDIR}"
sbatch --export=ALL,STAMP,OUTDIR,MAX_CALLS batch/run_l1_loss_decomposition_best_selector_wulver_100case.sbatch
