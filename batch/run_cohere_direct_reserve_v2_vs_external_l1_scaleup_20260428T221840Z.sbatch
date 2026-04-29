#!/bin/bash
#SBATCH --job-name=coh-dr2-vs-l1
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=outputs/slurm_logs/cohere_direct_reserve_v2_vs_external_l1_scaleup_%j.out
#SBATCH --error=outputs/slurm_logs/cohere_direct_reserve_v2_vs_external_l1_scaleup_%j.err
set -euo pipefail
REPO_ROOT="/workspace/frontier-allocation-for-budgeted-llm-inference"
cd "$REPO_ROOT"
mkdir -p outputs/slurm_logs
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUTDIR="outputs/cohere_direct_reserve_v2_vs_external_l1_scaleup_${TS}"
REALDIR="outputs/cohere_real_model_cost_normalized_validation_${TS}"
METHODS="direct_reserve_semantic_frontier_v2,external_l1_max,strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,tale,s1"
DATASETS="openai/gsm8k,HuggingFaceH4/MATH-500"
BUDGETS="4,6,8"
SEEDS="11,23"
TARGET=100
MAXE=100
GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
if [ -f ".venv/bin/activate" ]; then source .venv/bin/activate; fi
python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp "$TS" --providers cohere --cohere-model command-r-plus-08-2024 --datasets "$DATASETS" --budgets "$BUDGETS" --seeds "$SEEDS" --methods "$METHODS" --target-scored-per-slice "$TARGET" --max-examples "$MAXE" --resume
python scripts/build_real_model_cost_validation_outputs.py --output-dir "$REALDIR"
python scripts/postprocess_cohere_scaleup_outputs.py --output-dir "$REALDIR"
mkdir -p "$OUTDIR"
cp "$REALDIR"/per_case_results.csv "$OUTDIR"/
cp "$REALDIR"/method_summary.csv "$OUTDIR"/
cp "$REALDIR"/unique_example_method_summary.csv "$OUTDIR"/
cp "$REALDIR"/paired_vs_external_l1_max.csv "$OUTDIR"/
cp "$REALDIR"/paired_vs_best_external.csv "$OUTDIR"/
cp "$REALDIR"/token_latency_cost_summary.csv "$OUTDIR"/
cp "$REALDIR"/cost_normalized_leaderboard.csv "$OUTDIR"/
cp "$REALDIR"/coverage_gap_report.csv "$OUTDIR"/
cp "$REALDIR"/methods_excluded.csv "$OUTDIR"/
cp "$REALDIR"/run_status.json "$OUTDIR"/
python - <<PY
import json, os
from pathlib import Path
p=Path('$OUTDIR/manifest.json')
p.write_text(json.dumps({
'timestamp':'$TS','git_commit':'$GIT_COMMIT','command':'run_cohere_real_model_cost_normalized_validation + postprocess','env_key_presence':{'COHERE_API_KEY':bool(os.getenv('COHERE_API_KEY')),'HF_TOKEN':bool(os.getenv('HF_TOKEN'))},'datasets':'$DATASETS'.split(','),'methods':'$METHODS'.split(','),'budgets':[4,6,8],'seeds':[11,23],'provider':'cohere','model':'command-r-plus-08-2024','example_cap':$MAXE
},indent=2)+'\n')
PY
