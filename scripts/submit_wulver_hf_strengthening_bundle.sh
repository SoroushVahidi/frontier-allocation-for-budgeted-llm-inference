#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

mkdir -p logs/slurm

echo "Submitting Wulver HF strengthening jobs from: ${REPO_ROOT}"

jid1="$(sbatch --parsable jobs/wulver_when_solve_verify_hf_smoke.sbatch)"
echo "wsv_hf_smoke job_id=${jid1}"

jid2="$(sbatch --parsable jobs/wulver_when_solve_verify_hf_import_pipeline.sbatch)"
echo "wsv_hf_import job_id=${jid2}"

jid3="$(sbatch --parsable jobs/wulver_hf_adjacent_baseline_refresh.sbatch)"
echo "hf_adj_refresh job_id=${jid3}"

jid4="$(sbatch --parsable jobs/wulver_hf_access_gap_audit.sbatch)"
echo "hf_gap_audit job_id=${jid4}"

cat <<EOF
{
  "submitted": true,
  "jobs": {
    "when_solve_verify_hf_smoke": "${jid1}",
    "when_solve_verify_hf_import_pipeline": "${jid2}",
    "hf_adjacent_baseline_refresh": "${jid3}",
    "hf_access_gap_audit": "${jid4}"
  }
}
EOF
