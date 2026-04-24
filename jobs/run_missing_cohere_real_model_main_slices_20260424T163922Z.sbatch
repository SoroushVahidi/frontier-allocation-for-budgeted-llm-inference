#!/bin/bash
#SBATCH --job-name=cohere-real-main-missing
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail
REPO_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_DIR"
mkdir -p logs/slurm
if [[ -f /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh ]]; then
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh || true
  conda activate base >/dev/null 2>&1 || true
fi
if [[ -f "$HOME/.bashrc" ]]; then
  source "$HOME/.bashrc" || true
fi
echo "COHERE_API_KEY present: $( [[ -n "${COHERE_API_KEY:-}" ]] && echo true || echo false )"
if [[ -z "${COHERE_API_KEY:-}" ]]; then echo "Missing COHERE_API_KEY"; exit 1; fi
echo "python: $(command -v python3 || true)"
python3 --version || true

echo "Running slice: dataset=openai/gsm8k seed=11 budget=4"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_4_openai_gsm8k --provider cohere --model command-r-plus-08-2024 --datasets openai/gsm8k --subset-size 20 --seeds 11 --budgets 4 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=openai/gsm8k seed=11 budget=6"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_6_openai_gsm8k --provider cohere --model command-r-plus-08-2024 --datasets openai/gsm8k --subset-size 20 --seeds 11 --budgets 6 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=openai/gsm8k seed=11 budget=8"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_8_openai_gsm8k --provider cohere --model command-r-plus-08-2024 --datasets openai/gsm8k --subset-size 20 --seeds 11 --budgets 8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=openai/gsm8k seed=23 budget=4"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_23_4_openai_gsm8k --provider cohere --model command-r-plus-08-2024 --datasets openai/gsm8k --subset-size 20 --seeds 23 --budgets 4 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=openai/gsm8k seed=23 budget=6"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_23_6_openai_gsm8k --provider cohere --model command-r-plus-08-2024 --datasets openai/gsm8k --subset-size 20 --seeds 23 --budgets 6 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=openai/gsm8k seed=23 budget=8"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_23_8_openai_gsm8k --provider cohere --model command-r-plus-08-2024 --datasets openai/gsm8k --subset-size 20 --seeds 23 --budgets 8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/MATH-500 seed=11 budget=4"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_4_HuggingFaceH4_MATH-500 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/MATH-500 --subset-size 20 --seeds 11 --budgets 4 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/MATH-500 seed=11 budget=6"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_6_HuggingFaceH4_MATH-500 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/MATH-500 --subset-size 20 --seeds 11 --budgets 6 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/MATH-500 seed=11 budget=8"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_8_HuggingFaceH4_MATH-500 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/MATH-500 --subset-size 20 --seeds 11 --budgets 8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/MATH-500 seed=23 budget=4"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_23_4_HuggingFaceH4_MATH-500 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/MATH-500 --subset-size 20 --seeds 23 --budgets 4 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/MATH-500 seed=23 budget=6"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_23_6_HuggingFaceH4_MATH-500 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/MATH-500 --subset-size 20 --seeds 23 --budgets 6 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/MATH-500 seed=23 budget=8"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_23_8_HuggingFaceH4_MATH-500 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/MATH-500 --subset-size 20 --seeds 23 --budgets 8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/aime_2024 seed=11 budget=4"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_4_HuggingFaceH4_aime_2024 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/aime_2024 --subset-size 20 --seeds 11 --budgets 4 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/aime_2024 seed=11 budget=6"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_6_HuggingFaceH4_aime_2024 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/aime_2024 --subset-size 20 --seeds 11 --budgets 6 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/aime_2024 seed=11 budget=8"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_8_HuggingFaceH4_aime_2024 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/aime_2024 --subset-size 20 --seeds 11 --budgets 8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/aime_2024 seed=23 budget=4"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_23_4_HuggingFaceH4_aime_2024 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/aime_2024 --subset-size 20 --seeds 23 --budgets 4 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/aime_2024 seed=23 budget=6"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_23_6_HuggingFaceH4_aime_2024 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/aime_2024 --subset-size 20 --seeds 23 --budgets 6 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

echo "Running slice: dataset=HuggingFaceH4/aime_2024 seed=23 budget=8"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_23_8_HuggingFaceH4_aime_2024 --provider cohere --model command-r-plus-08-2024 --datasets HuggingFaceH4/aime_2024 --subset-size 20 --seeds 23 --budgets 8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3

