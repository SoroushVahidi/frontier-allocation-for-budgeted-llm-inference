#!/usr/bin/env python3
"""Cheap calibration sweep for two-stage near-tie tie-breakers (new-paper track)."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_scorer_v3 import V7_FEATURE_NAMES
from experiments.controllers import AdaptiveController
from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)
from experiments.scoring import LearnedBTBranchScorer, TwoStageNearTieBTBranchScorer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded calibration sweep for two-stage tie-breaker")
    p.add_argument("--output-root", default="outputs/new_paper/near_tie_tiebreaker_calibration")
    p.add_argument("--near-tie-output-root", default="outputs/new_paper/near_tie_pairs")
    p.add_argument("--run-id", default=None)
    p.add_argument("--seed", type=int, default=61)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=220)
    p.add_argument("--subset-size", type=int, default=30)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--hard-oversample-factor", type=int, default=3)
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _score(model: dict[str, Any], features: dict[str, float]) -> float:
    s = float(model.get("intercept", 0.0))
    for n, w in model.get("weights", {}).items():
        s += float(w) * float(features.get(n, 0.0))
    return s


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _pair_key(episode_id: int, decision_id: int, a: str, b: str) -> tuple[int, int, str, str]:
    x, y = sorted([str(a), str(b)])
    return (int(episode_id), int(decision_id), x, y)


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


def _feature_names(feature_set: str) -> list[str]:
    if feature_set == "compact":
        keys = [
            "parent_relative_score",
            "node_2_score",
            "node_3_score",
            "node_3_distance_to_terminal_est",
            "edge_1_score_delta",
            "edge_2_score_delta",
            "stalled_steps",
            "verify_count",
        ]
        names = [f"diff::{k}" for k in keys]
        names.extend([f"abs_diff::{k}" for k in ["node_3_score", "parent_relative_score", "edge_2_score_delta"]])
        return names
    if feature_set == "diff_only":
        return [f"diff::{k}" for k in V7_FEATURE_NAMES]
    if feature_set == "diff_abs":
        names = [f"diff::{k}" for k in V7_FEATURE_NAMES]
        names.extend([f"abs_diff::{k}" for k in ["node_3_score", "node_2_score", "parent_relative_score", "edge_2_score_delta", "verify_count", "stalled_steps"]])
        return names
    raise ValueError(f"unknown feature_set={feature_set}")


def _tie_features(row: dict[str, Any], feature_names: list[str]) -> dict[str, float]:
    a = row["features_a"]
    b = row["features_b"]
    out: dict[str, float] = {}
    for name in feature_names:
        if name.startswith("diff::"):
            base = name.split("::", 1)[1]
            out[name] = float(a.get(base, 0.0)) - float(b.get(base, 0.0))
        elif name.startswith("abs_diff::"):
            base = name.split("::", 1)[1]
            out[name] = abs(float(a.get(base, 0.0)) - float(b.get(base, 0.0)))
    return out


def _train_logistic(
    train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], feature_names: list[str], l2: float, seed: int
) -> dict[str, Any]:
    w = {k: 0.0 for k in feature_names}
    b = 0.0
    rng = random.Random(seed)
    epochs = 45
    lr = 0.03

    for _ in range(epochs):
        rng.shuffle(train_rows)
        for r in train_rows:
            x = _tie_features(r, feature_names)
            y = float(r.get("a_preferred", 0.0))
            z = b + sum(w[k] * x[k] for k in feature_names)
            p = _sigmoid(z)
            g = p - y
            for k in feature_names:
                w[k] -= lr * (g * x[k] + l2 * w[k])
            b -= lr * g

    def acc(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        ok = 0
        for r in rows:
            x = _tie_features(r, feature_names)
            z = b + sum(w[k] * x[k] for k in feature_names)
            pred = 1 if _sigmoid(z) >= 0.5 else 0
            ok += int(pred == int(r.get("a_preferred", 0)))
        return ok / len(rows)

    top = sorted(((k, abs(v)) for k, v in w.items()), key=lambda x: x[1], reverse=True)[:10]
    return {
        "model_type": "logistic_regression",
        "feature_names": feature_names,
        "weights": {k: float(v) for k, v in w.items()},
        "intercept": float(b),
        "train_pair_accuracy": acc(train_rows),
        "test_pair_accuracy": acc(test_rows),
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "top_abs_weight_features": [{"feature": k, "abs_weight": float(v)} for k, v in top],
        "l2": float(l2),
    }


def _train_decision_stump(train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], feature_names: list[str]) -> dict[str, Any]:
    if not train_rows:
        return {
            "model_type": "decision_stump",
            "feature_names": feature_names,
            "stump_feature": feature_names[0],
            "threshold": 0.0,
            "left_prob_a": 0.5,
            "right_prob_a": 0.5,
            "train_pair_accuracy": 0.0,
            "test_pair_accuracy": 0.0,
            "n_train": 0,
            "n_test": len(test_rows),
        }

    best: dict[str, Any] | None = None

    def _acc(rows: list[dict[str, Any]], feature: str, threshold: float, left_prob: float, right_prob: float) -> float:
        if not rows:
            return 0.0
        ok = 0
        for r in rows:
            x = _tie_features(r, [feature])[feature]
            prob = left_prob if x <= threshold else right_prob
            pred = 1 if prob >= 0.5 else 0
            ok += int(pred == int(r.get("a_preferred", 0)))
        return ok / len(rows)

    for feature in feature_names:
        vals = [_tie_features(r, [feature])[feature] for r in train_rows]
        if not vals:
            continue
        qs = sorted(vals)[:: max(1, len(vals) // 6)]
        candidates = sorted(set(qs + [0.0]))
        for t in candidates:
            left = [int(r.get("a_preferred", 0)) for r in train_rows if _tie_features(r, [feature])[feature] <= t]
            right = [int(r.get("a_preferred", 0)) for r in train_rows if _tie_features(r, [feature])[feature] > t]
            left_prob = sum(left) / max(1, len(left))
            right_prob = sum(right) / max(1, len(right))
            train_acc = _acc(train_rows, feature, t, left_prob, right_prob)
            cand = {
                "model_type": "decision_stump",
                "feature_names": feature_names,
                "stump_feature": feature,
                "threshold": float(t),
                "left_prob_a": float(left_prob),
                "right_prob_a": float(right_prob),
                "train_pair_accuracy": float(train_acc),
                "test_pair_accuracy": float(_acc(test_rows, feature, t, left_prob, right_prob)),
                "n_train": len(train_rows),
                "n_test": len(test_rows),
            }
            if best is None or cand["train_pair_accuracy"] > best["train_pair_accuracy"]:
                best = cand

    assert best is not None
    return best


def _pair_acc_two_stage(rows: list[dict[str, Any]], base_model: dict[str, Any], tie_model: dict[str, Any], margin: float) -> float:
    if not rows:
        return 0.0
    feature_names = list(tie_model.get("feature_names", []))
    ok = 0
    for r in rows:
        sa = _score(base_model, r["features_a"])
        sb = _score(base_model, r["features_b"])
        pred = 1 if sa >= sb else 0
        if abs(sa - sb) <= margin:
            oriented = r if pred == 1 else {
                **r,
                "features_a": r["features_b"],
                "features_b": r["features_a"],
                "a_preferred": 1 - int(r.get("a_preferred", 0)),
            }
            x = _tie_features(oriented, feature_names)
            model_type = str(tie_model.get("model_type", "logistic_regression"))
            if model_type == "decision_stump":
                feature = str(tie_model.get("stump_feature", feature_names[0]))
                threshold = float(tie_model.get("threshold", 0.0))
                keep_top_prob = (
                    float(tie_model.get("left_prob_a", 0.5))
                    if float(x.get(feature, 0.0)) <= threshold
                    else float(tie_model.get("right_prob_a", 0.5))
                )
                keep_top = 1 if keep_top_prob >= 0.5 else 0
            else:
                z = float(tie_model.get("intercept", 0.0))
                for k, v in tie_model.get("weights", {}).items():
                    z += float(v) * float(x.get(k, 0.0))
                keep_top = 1 if _sigmoid(z) >= 0.5 else 0
            pred = pred if keep_top == 1 else (1 - pred)
        ok += int(pred == int(r.get("a_preferred", 0)))
    return ok / len(rows)


def _select_train_rows(
    base_pairs: list[dict[str, Any]], hard_train_keys: set[str], base_model: dict[str, Any], subset_mode: str, strict_margin: float
) -> list[dict[str, Any]]:
    rows = []
    for r in base_pairs:
        if r.get("split") != "train":
            continue
        key = "|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"])))
        if key not in hard_train_keys:
            continue
        if subset_mode == "strict_margin":
            sa = _score(base_model, r["features_a"])
            sb = _score(base_model, r["features_b"])
            if abs(sa - sb) > strict_margin:
                continue
        rows.append(r)
    return rows


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ranking_dataset = run_dir / "branch_scorer_v3_dataset.jsonl"
    pairwise_dataset = run_dir / "pairwise_dataset.jsonl"
    baseline_model_path = run_dir / "adaptive_learned_branch_score_v7_bt_baseline.json"
    oversampled_dataset = run_dir / "pairwise_dataset_hard_oversampled.jsonl"
    oversampled_model_path = run_dir / "adaptive_learned_branch_score_v7_bt_near_tie_oversample.json"

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
    near_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/run_new_paper_near_tie_pair_pipeline.py"),
        "--pairwise-dataset",
        str(pairwise_dataset),
        "--bt-model",
        str(baseline_model_path),
        "--output-root",
        str(near_tie_root),
        "--run-id",
        run_id,
        "--min-signals",
        "1",
    ]
    if oracle_pairwise:
        near_cmd.extend(["--oracle-pairwise", str(oracle_pairwise)])
    _run(near_cmd)

    base_pairs = _load_jsonl(pairwise_dataset)
    baseline_model = json.loads(baseline_model_path.read_text(encoding="utf-8"))
    near_pairs = _load_jsonl(near_tie_root / run_id / "near_tie_pairs.jsonl")
    hard_train_keys = {r["pair_key"] for r in near_pairs if r.get("split") == "train"}
    hard_test_keys = {r["pair_key"] for r in near_pairs if r.get("split") == "test"}

    oversampled_rows: list[dict[str, Any]] = []
    for r in base_pairs:
        key = "|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"])))
        oversampled_rows.append(r)
        if r.get("split") == "train" and key in hard_train_keys:
            for _ in range(max(0, int(args.hard_oversample_factor) - 1)):
                oversampled_rows.append(dict(r))
    _write_jsonl(oversampled_dataset, oversampled_rows)
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(oversampled_dataset),
        "--output",
        str(oversampled_model_path),
        "--seed",
        str(args.seed),
        "--weighting",
        "confidence",
        "--soft-uncertain-target",
    ])

    oversampled_model = json.loads(oversampled_model_path.read_text(encoding="utf-8"))
    test_rows = [r for r in base_pairs if r.get("split") == "test"]
    hard_test_rows = [
        r
        for r in test_rows
        if "|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"]))) in hard_test_keys
    ]

    sweep = [
        {"variant": "logistic", "near_tie_margin": 0.04, "subset_mode": "all_near_tie", "feature_set": "compact", "l2": 1e-3},
        {"variant": "logistic", "near_tie_margin": 0.06, "subset_mode": "all_near_tie", "feature_set": "diff_abs", "l2": 1e-4},
        {"variant": "logistic", "near_tie_margin": 0.08, "subset_mode": "strict_margin", "feature_set": "diff_abs", "l2": 1e-4},
        {"variant": "logistic", "near_tie_margin": 0.10, "subset_mode": "strict_margin", "feature_set": "compact", "l2": 1e-3},
        {"variant": "logistic", "near_tie_margin": 0.06, "subset_mode": "all_near_tie", "feature_set": "diff_only", "l2": 1e-4},
        {"variant": "decision_stump", "near_tie_margin": 0.06, "subset_mode": "all_near_tie", "feature_set": "compact", "l2": 0.0},
    ]

    method_rows: list[dict[str, Any]] = []
    sweep_rows: list[dict[str, Any]] = []
    near_slice_rows: list[dict[str, Any]] = []

    rng = random.Random(args.seed)
    examples = load_pilot_examples(args.dataset, args.subset_size, args.seed)
    base_factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
    base_strategies = build_frontier_strategies(
        base_factory,
        args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        bt_pairwise_model_path=str(baseline_model_path),
        bt_pairwise_oracle_model_path=str(baseline_model_path),
    )
    base_strategies["adaptive_bt_pairwise_oversample"] = AdaptiveController(
        base_factory(),
        LearnedBTBranchScorer(oversampled_model_path, max_actions_per_problem=args.budget),
        args.budget,
        high_threshold=0.72,
        low_threshold=0.42,
        max_branches=3,
        allow_verify=True,
        min_expansions_before_prune=1,
        method_name="adaptive_bt_pairwise_oversample",
    )
    base_selected = ["adaptive_bt_pairwise", "adaptive_bt_pairwise_oversample", "adaptive_bt_pairwise_oracle"]
    base_metrics, base_eval_rows = evaluate_strategies_on_examples(examples, {k: base_strategies[k] for k in base_selected})
    base_oracle_acc = _oracle_accuracy(base_eval_rows)
    for m in base_selected:
        method_rows.append(
            {
                "method": m,
                "config_id": "base",
                "accuracy": float(base_metrics[m]["accuracy"]),
                "avg_actions": float(base_metrics[m]["avg_actions"]),
                "gap_to_oracle": float(base_oracle_acc) - float(base_metrics[m]["accuracy"]),
            }
        )

    for idx, cfg in enumerate(sweep):
        config_id = f"cfg_{idx+1:02d}_{cfg['variant']}_{cfg['near_tie_margin']:.2f}_{cfg['feature_set']}_{cfg['subset_mode']}"
        feature_names = _feature_names(str(cfg["feature_set"]))
        train_rows = _select_train_rows(
            base_pairs,
            hard_train_keys,
            baseline_model,
            subset_mode=str(cfg["subset_mode"]),
            strict_margin=float(cfg["near_tie_margin"]),
        )
        test_rows_for_tie = [
            r
            for r in base_pairs
            if r.get("split") == "test"
            and "|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"]))) in hard_test_keys
        ]

        if str(cfg["variant"]) == "decision_stump":
            tie_model = _train_decision_stump(train_rows, test_rows_for_tie, feature_names)
        else:
            tie_model = _train_logistic(
                train_rows,
                test_rows_for_tie,
                feature_names,
                l2=float(cfg["l2"]),
                seed=args.seed + idx,
            )

        two_stage_model = {
            "model_type": "two_stage_near_tie_bt",
            "base_model": {
                "intercept": float(baseline_model.get("intercept", 0.0)),
                "weights": baseline_model.get("weights", {}),
            },
            "tie_break_model": tie_model,
            "near_tie_margin": float(cfg["near_tie_margin"]),
            "config": cfg,
        }
        model_path = run_dir / f"two_stage_model_{config_id}.json"
        model_path.write_text(json.dumps(two_stage_model, indent=2), encoding="utf-8")

        pair_all = _pair_acc_two_stage(test_rows, baseline_model, tie_model, float(cfg["near_tie_margin"]))
        pair_hard = _pair_acc_two_stage(hard_test_rows, baseline_model, tie_model, float(cfg["near_tie_margin"]))

        local_rng = random.Random(args.seed)
        local_factory = generator_factory_for_mode(False, local_rng, "gpt-4.1-mini", 0.2, 180, 45)
        local_strategies = {
            "adaptive_bt_pairwise": build_frontier_strategies(
                local_factory,
                args.budget,
                adaptive_min_expand_grid=[1],
                rng=local_rng,
                use_openai_api=False,
                bt_pairwise_model_path=str(baseline_model_path),
            )["adaptive_bt_pairwise"],
            f"adaptive_bt_pairwise_two_stage_{config_id}": AdaptiveController(
                local_factory(),
                TwoStageNearTieBTBranchScorer(model_path, max_actions_per_problem=args.budget),
                args.budget,
                high_threshold=0.72,
                low_threshold=0.42,
                max_branches=3,
                allow_verify=True,
                min_expansions_before_prune=1,
                method_name=f"adaptive_bt_pairwise_two_stage_{config_id}",
            ),
        }
        local_metrics, _ = evaluate_strategies_on_examples(examples, local_strategies)
        base_acc = float(local_metrics["adaptive_bt_pairwise"]["accuracy"])
        two_stage_key = f"adaptive_bt_pairwise_two_stage_{config_id}"
        two_stage_acc = float(local_metrics[two_stage_key]["accuracy"])

        sweep_rows.append(
            {
                "config_id": config_id,
                "variant": cfg["variant"],
                "near_tie_margin": cfg["near_tie_margin"],
                "subset_mode": cfg["subset_mode"],
                "feature_set": cfg["feature_set"],
                "l2": cfg["l2"],
                "n_tie_train": len(train_rows),
                "n_tie_test": len(test_rows_for_tie),
                "tie_model_test_pair_accuracy": tie_model.get("test_pair_accuracy", 0.0),
                "controller_baseline_accuracy": base_acc,
                "controller_two_stage_accuracy": two_stage_acc,
                "controller_delta_vs_baseline": two_stage_acc - base_acc,
                "pair_all_delta_vs_baseline": pair_all - _pair_acc(test_rows, baseline_model),
                "pair_near_tie_delta_vs_baseline": pair_hard - _pair_acc(hard_test_rows, baseline_model),
            }
        )
        near_slice_rows.append(
            {
                "config_id": config_id,
                "variant": cfg["variant"],
                "near_tie_margin": cfg["near_tie_margin"],
                "subset_mode": cfg["subset_mode"],
                "feature_set": cfg["feature_set"],
                "near_tie_pair_accuracy": pair_hard,
                "near_tie_pair_delta_vs_baseline": pair_hard - _pair_acc(hard_test_rows, baseline_model),
                "all_test_pair_accuracy": pair_all,
                "all_test_pair_delta_vs_baseline": pair_all - _pair_acc(test_rows, baseline_model),
            }
        )

    sweep_sorted = sorted(sweep_rows, key=lambda r: (float(r["controller_delta_vs_baseline"]), float(r["pair_near_tie_delta_vs_baseline"])), reverse=True)
    best = sweep_sorted[0] if sweep_sorted else {}

    _write_csv(run_dir / "method_metrics.csv", method_rows)
    _write_csv(run_dir / "tiebreaker_sweep_results.csv", sweep_sorted)
    _write_csv(run_dir / "near_tie_slice_results.csv", near_slice_rows)

    margin_bins: dict[str, list[dict[str, Any]]] = {}
    for r in sweep_rows:
        m = f"{float(r['near_tie_margin']):.2f}"
        margin_bins.setdefault(m, []).append(r)
    margin_summary = {
        k: {
            "mean_controller_delta": sum(float(x["controller_delta_vs_baseline"]) for x in v) / len(v),
            "mean_near_tie_delta": sum(float(x["pair_near_tie_delta_vs_baseline"]) for x in v) / len(v),
        }
        for k, v in margin_bins.items()
    }

    interp = [
        f"# Two-stage tie-breaker calibration ({run_id})",
        "",
        "Bounded calibration sweep across margin/subset/features/model while keeping two-stage architecture fixed.",
        "",
        "## Answers",
        f"- Previous two-stage gain robust or fragile? {'fragile' if any(float(r['controller_delta_vs_baseline']) <= 0 for r in sweep_rows) else 'robust on this sweep'}.",
        f"- Best config by controller delta: {best.get('config_id', 'n/a')} (delta={float(best.get('controller_delta_vs_baseline', 0.0)):+.4f}).",
        f"- Best near-tie slice delta found: {max([float(r['pair_near_tie_delta_vs_baseline']) for r in sweep_rows] or [0.0]):+.4f}.",
        f"- Near-tie slice fully resolved? {'yes' if max([float(r['pair_near_tie_delta_vs_baseline']) for r in sweep_rows] or [0.0]) > 0 else 'no'}.",
        "",
        "## Margin region summary (mean deltas)",
    ]
    for m, s in sorted(margin_summary.items()):
        interp.append(f"- margin={m}: mean controller delta={s['mean_controller_delta']:+.4f}, mean near-tie delta={s['mean_near_tie_delta']:+.4f}")
    interp.extend(
        [
            "",
            "## Conservative conclusion",
            "- Keep two-stage as the best lightweight branch only if positive controller deltas repeat across margins/seeds.",
            "- If near-tie slice gains stay non-positive, treat diagnostics as stronger than method gain and continue small calibration only.",
        ]
    )
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "dataset": args.dataset,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "subset_size": args.subset_size,
        "near_tie_pair_artifacts": str(near_tie_root / run_id),
        "artifacts": {
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "tiebreaker_sweep_results": str(run_dir / "tiebreaker_sweep_results.csv"),
            "near_tie_slice_results": str(run_dir / "near_tie_slice_results.csv"),
            "run_manifest": str(run_dir / "run_manifest.json"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
        "sweep_size": len(sweep_rows),
        "best_config": best,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "best_config": best}, indent=2))


if __name__ == "__main__":
    main()
