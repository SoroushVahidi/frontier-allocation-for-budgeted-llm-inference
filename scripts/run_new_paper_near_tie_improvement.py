#!/usr/bin/env python3
"""Bounded near-tie hard-pair improvement run (new-paper, cheap/text-only)."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.controllers import AdaptiveController
from experiments.frontier_matrix_core import build_frontier_strategies, evaluate_strategies_on_examples, generator_factory_for_mode, load_pilot_examples
from experiments.scoring import LearnedBTBranchScorer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run near-tie targeted lightweight improvement")
    p.add_argument("--output-root", default="outputs/new_paper/near_tie_improvement")
    p.add_argument("--near-tie-output-root", default="outputs/new_paper/near_tie_pairs")
    p.add_argument("--run-id", default=None)
    p.add_argument("--seed", type=int, default=61)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=420)
    p.add_argument("--subset-size", type=int, default=32)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--hard-oversample-factor", type=int, default=3)
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _pair_key(episode_id: int, decision_id: int, a: str, b: str) -> tuple[int, int, str, str]:
    x, y = sorted([str(a), str(b)])
    return (int(episode_id), int(decision_id), x, y)


def _score(model: dict[str, Any], features: dict[str, float]) -> float:
    s = float(model.get("intercept", 0.0))
    for n, w in model.get("weights", {}).items():
        s += float(w) * float(features.get(n, 0.0))
    return s


def _pair_acc(rows: list[dict[str, Any]], model: dict[str, Any]) -> float:
    if not rows:
        return 0.0
    ok = 0
    for r in rows:
        pred = 1 if (_score(model, r["features_a"]) - _score(model, r["features_b"])) >= 0 else 0
        ok += int(pred == int(r.get("a_preferred", 0)))
    return ok / len(rows)


def _oracle_accuracy(rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    if not by_ex:
        return 0.0
    return sum(1 for rr in by_ex.values() if any(bool(r["is_correct"]) for r in rr)) / len(by_ex)


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ranking_dataset = run_dir / "branch_scorer_v3_dataset.jsonl"
    pairwise_dataset = run_dir / "pairwise_dataset.jsonl"
    baseline_model_path = run_dir / "adaptive_learned_branch_score_v7_bt_baseline.json"
    improved_dataset = run_dir / "pairwise_dataset_hard_oversampled.jsonl"
    improved_model_path = run_dir / "adaptive_learned_branch_score_v7_bt_near_tie.json"

    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"),
        "--output-dir",
        str(run_dir),
        "--episodes",
        str(args.ranking_episodes),
        "--budget",
        str(args.budget),
        "--seed",
        str(args.seed),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/build_bt_pairwise_branch_dataset.py"),
        "--ranking-dataset",
        str(ranking_dataset),
        "--output",
        str(pairwise_dataset),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pairwise_dataset),
        "--output",
        str(baseline_model_path),
        "--seed",
        str(args.seed),
    ])

    # Optional cheap oracle-ish join for disagreement signals.
    oracle_root = run_dir / "oracle_labels"
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/run_new_paper_oracle_branch_label_generation.py"),
        "--output-root",
        str(oracle_root),
        "--episodes",
        str(min(args.ranking_episodes, 60)),
        "--decision-budget",
        str(args.budget),
        "--max-decisions-per-episode-to-label",
        "3",
        "--max-branches-per-decision",
        "3",
        "--rollouts-per-policy",
        "2",
        "--seed",
        str(args.seed),
    ])
    oracle_dirs = sorted([p for p in oracle_root.glob("*") if p.is_dir()])
    oracle_pairwise = oracle_dirs[-1] / "pairwise_oracle_preferences.jsonl" if oracle_dirs else None

    near_tie_root = Path(args.near_tie_output_root)
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/run_new_paper_near_tie_pair_pipeline.py"),
        "--pairwise-dataset",
        str(pairwise_dataset),
        "--bt-model",
        str(baseline_model_path),
        "--oracle-pairwise",
        str(oracle_pairwise) if oracle_pairwise else "",
        "--output-root",
        str(near_tie_root),
        "--run-id",
        run_id,
        "--min-signals",
        "1",
    ])

    near_pairs = _load_jsonl(near_tie_root / run_id / "near_tie_pairs.jsonl")
    hard_train_keys = {
        tuple(x.split("|"))
        for x in [r["pair_key"] for r in near_pairs if r.get("split") == "train"]
    }
    hard_test_keys = {
        tuple(x.split("|"))
        for x in [r["pair_key"] for r in near_pairs if r.get("split") == "test"]
    }

    base_pairs = _load_jsonl(pairwise_dataset)
    improved_rows: list[dict[str, Any]] = []
    for r in base_pairs:
        key = tuple(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"])))
        improved_rows.append(r)
        if r.get("split") == "train" and key in hard_train_keys:
            for _ in range(max(0, int(args.hard_oversample_factor) - 1)):
                improved_rows.append(dict(r))

    _write_jsonl(improved_dataset, improved_rows)

    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(improved_dataset),
        "--output",
        str(improved_model_path),
        "--seed",
        str(args.seed),
        "--weighting",
        "confidence",
        "--soft-uncertain-target",
    ])

    baseline_model = json.loads(baseline_model_path.read_text(encoding="utf-8"))
    improved_model = json.loads(improved_model_path.read_text(encoding="utf-8"))
    test_rows = [r for r in base_pairs if r.get("split") == "test"]
    hard_test_rows = [
        r
        for r in test_rows
        if tuple(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"]))) in hard_test_keys
    ]

    failure_rows = [
        {
            "slice": "all_test_pairs",
            "n_pairs": len(test_rows),
            "baseline_pair_accuracy": _pair_acc(test_rows, baseline_model),
            "near_tie_pair_accuracy": _pair_acc(test_rows, improved_model),
            "delta_accuracy": _pair_acc(test_rows, improved_model) - _pair_acc(test_rows, baseline_model),
        },
        {
            "slice": "near_tie_test_pairs",
            "n_pairs": len(hard_test_rows),
            "baseline_pair_accuracy": _pair_acc(hard_test_rows, baseline_model),
            "near_tie_pair_accuracy": _pair_acc(hard_test_rows, improved_model),
            "delta_accuracy": _pair_acc(hard_test_rows, improved_model) - _pair_acc(hard_test_rows, baseline_model),
        },
    ]

    rng = random.Random(args.seed)
    examples = load_pilot_examples(args.dataset, args.subset_size, args.seed)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
    strategies = build_frontier_strategies(
        gen_factory,
        args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        bt_pairwise_model_path=str(baseline_model_path),
    )
    strategies["adaptive_bt_pairwise_near_tie"] = AdaptiveController(
        gen_factory(),
        LearnedBTBranchScorer(improved_model_path, max_actions_per_problem=args.budget),
        args.budget,
        high_threshold=0.72,
        low_threshold=0.42,
        max_branches=3,
        allow_verify=True,
        min_expansions_before_prune=1,
        method_name="adaptive_bt_pairwise_near_tie",
    )

    metrics, rows = evaluate_strategies_on_examples(examples, strategies)
    selected = ["adaptive_bt_pairwise", "adaptive_bt_pairwise_near_tie", "adaptive_min_expand_1", "reasoning_greedy"]
    eval_rows = [r for r in rows if r["strategy"] in selected]
    oracle_acc = _oracle_accuracy(eval_rows)

    method_rows: list[dict[str, Any]] = []
    for m in selected:
        if m not in metrics:
            continue
        method_rows.append(
            {
                "method": m,
                "accuracy": float(metrics[m]["accuracy"]),
                "avg_actions": float(metrics[m]["avg_actions"]),
                "gap_to_oracle": float(oracle_acc) - float(metrics[m]["accuracy"]),
            }
        )
    by_method = {r["method"]: r for r in method_rows}

    near_comp = [
        {
            "comparison": "near_tie_oversample_vs_baseline",
            "baseline_accuracy": by_method.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0),
            "near_tie_accuracy": by_method.get("adaptive_bt_pairwise_near_tie", {}).get("accuracy", 0.0),
            "delta_accuracy": by_method.get("adaptive_bt_pairwise_near_tie", {}).get("accuracy", 0.0)
            - by_method.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0),
            "baseline_gap": by_method.get("adaptive_bt_pairwise", {}).get("gap_to_oracle", 0.0),
            "near_tie_gap": by_method.get("adaptive_bt_pairwise_near_tie", {}).get("gap_to_oracle", 0.0),
            "near_tie_test_pair_delta": failure_rows[1]["delta_accuracy"],
        }
    ]

    _write_csv(run_dir / "method_metrics.csv", method_rows)
    _write_csv(run_dir / "near_tie_comparison.csv", near_comp)
    _write_csv(run_dir / "failure_slice_summary.csv", failure_rows)

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "dataset": args.dataset,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "subset_size": args.subset_size,
        "hard_oversample_factor": args.hard_oversample_factor,
        "near_tie_pair_artifacts": str(near_tie_root / run_id),
        "artifacts": {
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "near_tie_comparison": str(run_dir / "near_tie_comparison.csv"),
            "failure_slice_summary": str(run_dir / "failure_slice_summary.csv"),
            "run_manifest": str(run_dir / "run_manifest.json"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    delta_overall = float(near_comp[0]["delta_accuracy"])
    delta_slice = float(near_comp[0]["near_tie_test_pair_delta"])
    interp = [
        f"# Near-tie targeted improvement ({run_id})",
        "",
        "All artifacts are text-based and produced with bounded cheap runs only.",
        "",
        "## Dominant failure mode check",
        f"- Near-tie pair test slice delta (improved - baseline): {delta_slice:+.4f}.",
        "- Near-tie slice is treated as dominant only if this slice is both large and materially lower-accuracy than all-test.",
        "",
        "## Targeted improvement",
        "- Cheap hard-pair oversampling: duplicate near-tie training pairs before BT training.",
        f"- Oversample factor: {args.hard_oversample_factor}.",
        "",
        "## Outcome",
        f"- Overall controller delta (near-tie model - baseline BT): {delta_overall:+.4f}.",
        f"- Near-tie test pair delta: {delta_slice:+.4f}.",
        "",
        "If deltas are flat/negative, keep near-tie diagnostics as main result and avoid larger model complexity next.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "delta_overall": delta_overall, "delta_slice": delta_slice}, indent=2))


if __name__ == "__main__":
    main()
