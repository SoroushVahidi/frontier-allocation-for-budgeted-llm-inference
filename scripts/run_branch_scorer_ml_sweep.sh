#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_ROOT="${OUT_ROOT:-outputs/branch_scorer_v3_heavy_ml}"
mkdir -p "$OUT_ROOT"

DATASET_EPISODES="${DATASET_EPISODES:-6000}"
DATASET_BUDGET="${DATASET_BUDGET:-14}"
DATASET_INIT_BRANCHES="${DATASET_INIT_BRANCHES:-5}"
DATASET_MAX_DEPTH="${DATASET_MAX_DEPTH:-7}"
EVAL_EPISODES="${EVAL_EPISODES:-2500}"
ROBUST_EPISODES="${ROBUST_EPISODES:-1200}"
SEEDS=(7 19 23)

echo "Starting branch_scorer_v3 ML sweep."
echo "Output root: $OUT_ROOT"

# Step 1: build per-seed datasets (resumable by file existence).
for seed in "${SEEDS[@]}"; do
  seed_dir="$OUT_ROOT/datasets/seed_${seed}"
  dataset_file="$seed_dir/branch_scorer_v3_dataset.jsonl"
  if [[ -f "$dataset_file" ]]; then
    echo "Dataset exists, skipping build: seed=$seed"
    continue
  fi
  mkdir -p "$seed_dir"
  echo "Building dataset for seed=$seed"
  python scripts/build_v3_ranking_dataset.py \
    --output-dir "$seed_dir" \
    --episodes "$DATASET_EPISODES" \
    --budget "$DATASET_BUDGET" \
    --seed "$seed" \
    --n-init-branches "$DATASET_INIT_BRANCHES" \
    --max-depth "$DATASET_MAX_DEPTH"
done

# Step 2: pooled dataset assembly from committed pipeline outputs.
pooled_dir="$OUT_ROOT/pooled"
pooled_dataset="$pooled_dir/branch_scorer_v3_dataset.jsonl"
mkdir -p "$pooled_dir"
if [[ ! -f "$pooled_dataset" ]]; then
  : > "$pooled_dataset"
  for seed in "${SEEDS[@]}"; do
    cat "$OUT_ROOT/datasets/seed_${seed}/branch_scorer_v3_dataset.jsonl" >> "$pooled_dataset"
  done
  python - <<'PY'
import json
from pathlib import Path
root = Path("outputs/branch_scorer_v3_heavy_ml")
pooled = root / "pooled" / "branch_scorer_v3_dataset.jsonl"
rows = 0
train_rows = 0
test_rows = 0
with pooled.open("r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        rows += 1
        r = json.loads(line)
        if r.get("split") == "train":
            train_rows += 1
        elif r.get("split") == "test":
            test_rows += 1
meta = {
    "pooled_from_seeds": [7, 19, 23],
    "rows": rows,
    "train_rows": train_rows,
    "test_rows": test_rows,
}
(root / "pooled" / "dataset_meta_pooled.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print(json.dumps(meta, indent=2))
PY
else
  echo "Pooled dataset already exists, skipping assembly."
fi

# Step 3: train learned scorers on pooled dataset.
train_dir="$OUT_ROOT/training"
if [[ ! -f "$train_dir/training_meta.json" ]]; then
  mkdir -p "$train_dir"
  python scripts/train_branch_scorer_v3.py \
    --dataset "$pooled_dataset" \
    --output-dir "$train_dir"
else
  echo "Training artifacts already exist, skipping retrain."
fi

# Step 4: per-regime controller evaluation (canonical budgets/init branches).
regime_dir="$OUT_ROOT/controller_eval"
mkdir -p "$regime_dir"
for seed in "${SEEDS[@]}"; do
  for budget in 8 10 12; do
    for init_b in 3 5 7; do
      out_json="$regime_dir/controller_eval_seed${seed}_b${budget}_i${init_b}.json"
      if [[ -f "$out_json" ]]; then
        echo "Controller eval exists, skipping: seed=$seed budget=$budget init=$init_b"
        continue
      fi
      python scripts/evaluate_branch_scorer_controller.py \
        --model-dir "$train_dir/models" \
        --output "$out_json" \
        --episodes "$EVAL_EPISODES" \
        --seed "$seed" \
        --budget "$budget" \
        --n-init-branches "$init_b"
    done
  done
done

# Step 5: robustness summary sweep (includes heuristic comparator).
robust_dir="$OUT_ROOT/robustness"
if [[ ! -f "$robust_dir/robustness_summary.json" ]]; then
  python scripts/evaluate_branch_scorer_robustness.py \
    --model-dir "$train_dir/models" \
    --output-dir "$robust_dir" \
    --seeds "3,7,11,19,23" \
    --budgets "8,10,12" \
    --init-branches "3,5,7" \
    --episodes "$ROBUST_EPISODES" \
    --include-score-plus-progress
else
  echo "Robustness summary already exists, skipping."
fi

# Step 6: manuscript-facing aggregate table for regime results.
summary_csv="$OUT_ROOT/manuscript_controller_regime_table.csv"
python - <<'PY'
import csv
import json
import re
from pathlib import Path

root = Path("outputs/branch_scorer_v3_heavy_ml/controller_eval")
rows = []
for p in sorted(root.glob("controller_eval_seed*_b*_i*.json")):
    obj = json.loads(p.read_text(encoding="utf-8"))
    # Basename is controller_eval_seed{N}_b{B}_i{I} (five "_" segments, not six).
    m = re.match(r"^controller_eval_seed(\d+)_b(\d+)_i(\d+)$", p.stem)
    if not m:
        raise ValueError(f"unexpected controller_eval filename stem: {p.stem!r}")
    seed, budget, init_b = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    results = obj.get("results", {})
    rr = float(results.get("adaptive_relative_rank", {}).get("accuracy", 0.0))
    v4 = float(results.get("adaptive_learned_branch_score_v4", {}).get("accuracy", 0.0))
    v5 = float(results.get("adaptive_learned_branch_score_v5", {}).get("accuracy", 0.0))
    v6 = float(results.get("adaptive_learned_branch_score_v6", {}).get("accuracy", 0.0))
    rows.append(
        {
            "seed": seed,
            "budget": budget,
            "init_branches": init_b,
            "adaptive_relative_rank_acc": rr,
            "adaptive_learned_branch_score_v4_acc": v4,
            "adaptive_learned_branch_score_v5_acc": v5,
            "adaptive_learned_branch_score_v6_acc": v6,
            "v4_minus_relative_rank": v4 - rr,
            "v5_minus_relative_rank": v5 - rr,
            "v6_minus_relative_rank": v6 - rr,
            "v6_minus_v5": v6 - v5,
        }
    )

out_csv = Path("outputs/branch_scorer_v3_heavy_ml/manuscript_controller_regime_table.csv")
out_csv.parent.mkdir(parents=True, exist_ok=True)
with out_csv.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["seed"])
    writer.writeheader()
    writer.writerows(rows)
print(f"Wrote: {out_csv}")
PY

echo "Branch_scorer_v3 ML sweep complete."
