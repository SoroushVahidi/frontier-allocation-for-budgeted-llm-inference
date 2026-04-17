#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

TRAIN_ROOT="${TRAIN_ROOT:-outputs/branch_scorer_v3_heavy_ml}"
MODEL_DIR="${MODEL_DIR:-$TRAIN_ROOT/training/models}"
SELECT_FROM_DIR="${SELECT_FROM_DIR:-$TRAIN_ROOT/controller_eval}"
OUT_ROOT="${OUT_ROOT:-outputs/branch_scorer_v3_final_eval}"
mkdir -p "$OUT_ROOT"

if [[ ! -d "$MODEL_DIR" ]]; then
  echo "Missing trained model directory: $MODEL_DIR"
  exit 1
fi

python - <<'PY'
from __future__ import annotations

import csv
import json
from pathlib import Path
import random
import statistics

from experiments.branch_scorer_v3 import load_model, simulate_controller

train_root = Path("outputs/branch_scorer_v3_heavy_ml")
model_dir = train_root / "training" / "models"
selection_dir = train_root / "controller_eval"
out_root = Path("outputs/branch_scorer_v3_final_eval")
out_root.mkdir(parents=True, exist_ok=True)

learned_methods = [
    "adaptive_learned_branch_score",
    "adaptive_learned_branch_score_v4",
    "adaptive_learned_branch_score_v5",
    "adaptive_learned_branch_score_v6",
]
baseline_methods = [
    "adaptive_relative_rank",
    "adaptive_score_plus_progress",
    "adaptive_raw_score",
    "adaptive_eptree_baseline",
]

model_map = {
    "adaptive_learned_branch_score": load_model(model_dir / "adaptive_learned_branch_score.json"),
    "adaptive_learned_branch_score_v4": load_model(model_dir / "adaptive_learned_branch_score_v4.json"),
    "adaptive_learned_branch_score_v5": load_model(model_dir / "adaptive_learned_branch_score_v5.json"),
    "adaptive_learned_branch_score_v6": load_model(model_dir / "adaptive_learned_branch_score_v6.json"),
}

scores: dict[str, list[float]] = {m: [] for m in learned_methods}
for p in sorted(selection_dir.glob("controller_eval_seed*_b*_i*.json")):
    obj = json.loads(p.read_text(encoding="utf-8"))
    res = obj.get("results", {})
    for m in learned_methods:
        acc = res.get(m, {}).get("accuracy")
        if isinstance(acc, (int, float)):
            scores[m].append(float(acc))

if not any(scores.values()):
    best_learned = "adaptive_learned_branch_score_v6"
    selection_meta = {"fallback_used": True, "reason": "no prior controller_eval files", "best_learned": best_learned}
else:
    mean_scores = {m: (statistics.mean(v) if v else float("-inf")) for m, v in scores.items()}
    best_learned = max(mean_scores, key=mean_scores.get)
    selection_meta = {
        "fallback_used": False,
        "source_dir": str(selection_dir),
        "mean_accuracy_by_learned_method": mean_scores,
        "n_settings_by_learned_method": {m: len(v) for m, v in scores.items()},
        "best_learned": best_learned,
    }

(out_root / "selected_best_learned_model.json").write_text(json.dumps(selection_meta, indent=2), encoding="utf-8")

methods = baseline_methods + [best_learned]
heldout_seeds = [29, 31, 37, 41, 43]
budgets = [8, 10, 12, 14]
init_branches = [3, 5, 7]
episodes = 3000

settings_dir = out_root / "per_setting"
settings_dir.mkdir(parents=True, exist_ok=True)

rows: list[dict[str, float | int | str]] = []
for seed in heldout_seeds:
    for budget in budgets:
        for init_b in init_branches:
            setting_file = settings_dir / f"heldout_seed{seed}_b{budget}_i{init_b}.json"
            if setting_file.exists():
                setting_obj = json.loads(setting_file.read_text(encoding="utf-8"))
                result = setting_obj["results"]
            else:
                rng = random.Random(seed)
                result: dict[str, dict[str, float]] = {}
                for method in methods:
                    episode_metrics = []
                    for _ in range(episodes):
                        episode_metrics.append(
                            simulate_controller(
                                method=method,
                                rng=rng,
                                budget=budget,
                                n_init_branches=init_b,
                                max_depth=7,
                                finish_prob_base=0.16,
                                answer_noise=0.12,
                                model_map=model_map,
                            )
                        )
                    n = max(1, len(episode_metrics))
                    result[method] = {
                        "accuracy": sum(1 for r in episode_metrics if r["is_correct"]) / n,
                        "solve_rate": sum(1 for r in episode_metrics if r["solved_any"]) / n,
                        "avg_actions": sum(float(r["actions_used"]) for r in episode_metrics) / n,
                    }
                setting_obj = {
                    "seed": seed,
                    "budget": budget,
                    "init_branches": init_b,
                    "episodes": episodes,
                    "methods": methods,
                    "best_learned": best_learned,
                    "results": result,
                }
                setting_file.write_text(json.dumps(setting_obj, indent=2), encoding="utf-8")

            rr = float(result["adaptive_relative_rank"]["accuracy"])
            spp = float(result["adaptive_score_plus_progress"]["accuracy"])
            raw = float(result["adaptive_raw_score"]["accuracy"])
            ept = float(result["adaptive_eptree_baseline"]["accuracy"])
            bl = float(result[best_learned]["accuracy"])
            rows.append(
                {
                    "seed": seed,
                    "budget": budget,
                    "init_branches": init_b,
                    "best_learned_method": best_learned,
                    "best_learned_accuracy": bl,
                    "adaptive_relative_rank_accuracy": rr,
                    "adaptive_score_plus_progress_accuracy": spp,
                    "adaptive_raw_score_accuracy": raw,
                    "adaptive_eptree_baseline_accuracy": ept,
                    "margin_vs_relative_rank": bl - rr,
                    "margin_vs_score_plus_progress": bl - spp,
                    "margin_vs_raw_score": bl - raw,
                    "margin_vs_eptree": bl - ept,
                }
            )

if not rows:
    raise RuntimeError("No rows produced for final held-out evaluation")

summary = {
    "best_learned_method": best_learned,
    "heldout_seeds": heldout_seeds,
    "budgets": budgets,
    "init_branches": init_branches,
    "episodes_per_setting": episodes,
    "n_settings": len(rows),
    "mean_best_learned_accuracy": statistics.mean(float(r["best_learned_accuracy"]) for r in rows),
    "mean_relative_rank_accuracy": statistics.mean(float(r["adaptive_relative_rank_accuracy"]) for r in rows),
    "mean_score_plus_progress_accuracy": statistics.mean(float(r["adaptive_score_plus_progress_accuracy"]) for r in rows),
    "mean_raw_score_accuracy": statistics.mean(float(r["adaptive_raw_score_accuracy"]) for r in rows),
    "mean_eptree_accuracy": statistics.mean(float(r["adaptive_eptree_baseline_accuracy"]) for r in rows),
    "mean_margin_vs_relative_rank": statistics.mean(float(r["margin_vs_relative_rank"]) for r in rows),
    "mean_margin_vs_score_plus_progress": statistics.mean(float(r["margin_vs_score_plus_progress"]) for r in rows),
    "mean_margin_vs_raw_score": statistics.mean(float(r["margin_vs_raw_score"]) for r in rows),
    "mean_margin_vs_eptree": statistics.mean(float(r["margin_vs_eptree"]) for r in rows),
    "win_rate_vs_relative_rank": sum(1 for r in rows if float(r["margin_vs_relative_rank"]) > 0) / len(rows),
    "win_rate_vs_score_plus_progress": sum(1 for r in rows if float(r["margin_vs_score_plus_progress"]) > 0) / len(rows),
    "win_rate_vs_raw_score": sum(1 for r in rows if float(r["margin_vs_raw_score"]) > 0) / len(rows),
    "win_rate_vs_eptree": sum(1 for r in rows if float(r["margin_vs_eptree"]) > 0) / len(rows),
}

(out_root / "final_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

csv_path = out_root / "final_per_setting.csv"
with csv_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

budget_sweep: dict[int, dict[str, float]] = {}
for b in budgets:
    sub = [r for r in rows if int(r["budget"]) == b]
    budget_sweep[b] = {
        "best_learned_accuracy": statistics.mean(float(r["best_learned_accuracy"]) for r in sub),
        "relative_rank_accuracy": statistics.mean(float(r["adaptive_relative_rank_accuracy"]) for r in sub),
        "score_plus_progress_accuracy": statistics.mean(float(r["adaptive_score_plus_progress_accuracy"]) for r in sub),
        "raw_score_accuracy": statistics.mean(float(r["adaptive_raw_score_accuracy"]) for r in sub),
        "eptree_accuracy": statistics.mean(float(r["adaptive_eptree_baseline_accuracy"]) for r in sub),
        "margin_vs_relative_rank": statistics.mean(float(r["margin_vs_relative_rank"]) for r in sub),
    }

budget_csv = out_root / "budget_sweep_table.csv"
with budget_csv.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "budget",
            "best_learned_accuracy",
            "relative_rank_accuracy",
            "score_plus_progress_accuracy",
            "raw_score_accuracy",
            "eptree_accuracy",
            "margin_vs_relative_rank",
        ],
    )
    writer.writeheader()
    for b in budgets:
        writer.writerow({"budget": b, **budget_sweep[b]})

note = out_root / "manuscript_eval_note.md"
note_lines = [
    "# Final held-out controller evaluation note",
    "",
    f"- Selected best learned method from training job outputs: `{best_learned}`",
    f"- Held-out seeds: {heldout_seeds}",
    f"- Budgets: {budgets}",
    f"- Initial branches: {init_branches}",
    f"- Episodes per setting: {episodes}",
    "",
    "## Main aggregate results",
    f"- Mean best-learned accuracy: {summary['mean_best_learned_accuracy']:.4f}",
    f"- Mean adaptive_relative_rank accuracy: {summary['mean_relative_rank_accuracy']:.4f}",
    f"- Mean margin vs adaptive_relative_rank: {summary['mean_margin_vs_relative_rank']:.4f}",
    f"- Win rate vs adaptive_relative_rank: {summary['win_rate_vs_relative_rank']:.3f}",
    "",
    "## Comparator baselines included",
    "- adaptive_relative_rank (strong heuristic ranker)",
    "- adaptive_score_plus_progress (adaptive heuristic)",
    "- adaptive_raw_score (fixed-policy style score ordering)",
    "- adaptive_eptree_baseline (strong uncertainty/instability heuristic baseline)",
    "",
    "## Files",
    "- `final_summary.json`: aggregate headline metrics",
    "- `final_per_setting.csv`: full per-regime table",
    "- `budget_sweep_table.csv`: budget-sweep figure/table data",
    "- `selected_best_learned_model.json`: selection provenance from job 914308 outputs",
]
note.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

print(f"Best learned selected: {best_learned}")
print(f"Wrote: {out_root / 'selected_best_learned_model.json'}")
print(f"Wrote: {out_root / 'final_summary.json'}")
print(f"Wrote: {csv_path}")
print(f"Wrote: {budget_csv}")
print(f"Wrote: {note}")
PY

echo "Final manuscript evaluation run complete."
