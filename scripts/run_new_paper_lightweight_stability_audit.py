#!/usr/bin/env python3
"""Bounded multi-seed stability/variance audit for lightweight branch-scoring variants.

New-paper track only. Cheap/text-only artifacts.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
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


def _load_examples_with_retry(dataset: str, subset_size: int, seed: int, tries: int = 4):
    last_err: Exception | None = None
    for i in range(tries):
        try:
            return load_pilot_examples(dataset, subset_size, seed)
        except Exception as e:  # transient HF/network failures are expected occasionally
            last_err = e
            if i + 1 < tries:
                time.sleep(1.5 * (i + 1))
                continue
    if last_err is not None:
        raise last_err
    raise RuntimeError("failed to load examples")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded multi-seed stability audit (new-paper)")
    p.add_argument("--output-root", default="outputs/new_paper/lightweight_stability_audit")
    p.add_argument("--near-tie-output-root", default="outputs/new_paper/near_tie_pairs")
    p.add_argument("--run-id", default=None)
    p.add_argument("--seeds", default="61,62,63,64,65")
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=220)
    p.add_argument("--subset-size", type=int, default=30)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--hard-oversample-factor", type=int, default=3)
    p.add_argument("--near-tie-margin", type=float, default=0.06)
    p.add_argument("--include-oracle-reference", action="store_true")
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


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


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


def _tie_features_diff_abs() -> list[str]:
    names = [f"diff::{k}" for k in V7_FEATURE_NAMES]
    names.extend(
        [
            f"abs_diff::{k}"
            for k in [
                "node_3_score",
                "node_2_score",
                "parent_relative_score",
                "edge_2_score_delta",
                "verify_count",
                "stalled_steps",
            ]
        ]
    )
    return names


def _tie_features_compact() -> list[str]:
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


def _train_logistic(
    train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], feature_names: list[str], seed: int
) -> dict[str, Any]:
    w = {k: 0.0 for k in feature_names}
    b = 0.0
    rng = random.Random(seed)

    for _ in range(45):
        rng.shuffle(train_rows)
        for r in train_rows:
            x = _tie_features(r, feature_names)
            y = float(r.get("a_preferred", 0.0))
            z = b + sum(w[k] * x[k] for k in feature_names)
            p = _sigmoid(z)
            g = p - y
            for k in feature_names:
                w[k] -= 0.03 * (g * x[k] + 1e-4 * w[k])
            b -= 0.03 * g

    def _acc(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        ok = 0
        for r in rows:
            x = _tie_features(r, feature_names)
            z = b + sum(w[k] * x[k] for k in feature_names)
            pred = 1 if _sigmoid(z) >= 0.5 else 0
            ok += int(pred == int(r.get("a_preferred", 0)))
        return ok / len(rows)

    return {
        "model_type": "logistic_regression",
        "feature_names": feature_names,
        "weights": {k: float(v) for k, v in w.items()},
        "intercept": float(b),
        "train_pair_accuracy": _acc(train_rows),
        "test_pair_accuracy": _acc(test_rows),
        "n_train": len(train_rows),
        "n_test": len(test_rows),
    }


def _train_decision_stump(train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], feature_names: list[str]) -> dict[str, Any]:
    def _acc(rows: list[dict[str, Any]], feature: str, threshold: float, left_prob: float, right_prob: float) -> float:
        if not rows:
            return 0.0
        ok = 0
        for r in rows:
            val = _tie_features(r, [feature])[feature]
            prob = left_prob if val <= threshold else right_prob
            pred = 1 if prob >= 0.5 else 0
            ok += int(pred == int(r.get("a_preferred", 0)))
        return ok / len(rows)

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
    for feature in feature_names:
        vals = [_tie_features(r, [feature])[feature] for r in train_rows]
        candidates = sorted(set(sorted(vals)[:: max(1, len(vals) // 6)] + [0.0]))
        for t in candidates:
            left = [int(r.get("a_preferred", 0)) for r in train_rows if _tie_features(r, [feature])[feature] <= t]
            right = [int(r.get("a_preferred", 0)) for r in train_rows if _tie_features(r, [feature])[feature] > t]
            left_prob = sum(left) / max(1, len(left))
            right_prob = sum(right) / max(1, len(right))
            row = {
                "model_type": "decision_stump",
                "feature_names": feature_names,
                "stump_feature": feature,
                "threshold": float(t),
                "left_prob_a": float(left_prob),
                "right_prob_a": float(right_prob),
                "train_pair_accuracy": _acc(train_rows, feature, t, left_prob, right_prob),
                "test_pair_accuracy": _acc(test_rows, feature, t, left_prob, right_prob),
                "n_train": len(train_rows),
                "n_test": len(test_rows),
            }
            if best is None or (
                float(row["test_pair_accuracy"]),
                float(row["train_pair_accuracy"]),
            ) > (
                float(best["test_pair_accuracy"]),
                float(best["train_pair_accuracy"]),
            ):
                best = row
    return best or {
        "model_type": "decision_stump",
        "feature_names": feature_names,
        "stump_feature": feature_names[0],
        "threshold": 0.0,
        "left_prob_a": 0.5,
        "right_prob_a": 0.5,
        "train_pair_accuracy": 0.0,
        "test_pair_accuracy": 0.0,
        "n_train": len(train_rows),
        "n_test": len(test_rows),
    }


def _pair_acc_two_stage(rows: list[dict[str, Any]], base_model: dict[str, Any], tie_model: dict[str, Any], margin: float) -> float:
    if not rows:
        return 0.0
    feat_names = list(tie_model.get("feature_names", []))
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
            feats = _tie_features(oriented, feat_names)
            if str(tie_model.get("model_type", "logistic_regression")) == "decision_stump":
                feature = str(tie_model.get("stump_feature", ""))
                threshold = float(tie_model.get("threshold", 0.0))
                left_prob = float(tie_model.get("left_prob_a", 0.5))
                right_prob = float(tie_model.get("right_prob_a", 0.5))
                keep_top = 1 if (left_prob if float(feats.get(feature, 0.0)) <= threshold else right_prob) >= 0.5 else 0
            else:
                z = float(tie_model.get("intercept", 0.0))
                for k, v in tie_model.get("weights", {}).items():
                    z += float(v) * float(feats.get(k, 0.0))
                keep_top = 1 if _sigmoid(z) >= 0.5 else 0
            pred = pred if keep_top == 1 else (1 - pred)
        ok += int(pred == int(r.get("a_preferred", 0)))
    return ok / len(rows)


def _std(vals: list[float]) -> float:
    return statistics.stdev(vals) if len(vals) > 1 else 0.0


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    method_rows: list[dict[str, Any]] = []
    near_tie_rows: list[dict[str, Any]] = []

    for seed in seeds:
        seed_dir = run_dir / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)

        ranking_dataset = seed_dir / "branch_scorer_v3_dataset.jsonl"
        pairwise_dataset = seed_dir / "pairwise_dataset.jsonl"
        baseline_model_path = seed_dir / "adaptive_learned_branch_score_v7_bt_baseline.json"
        oversampled_model_path = seed_dir / "adaptive_learned_branch_score_v7_bt_near_tie_oversample.json"

        _run([
            sys.executable,
            str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"),
            "--output-dir",
            str(seed_dir),
            "--episodes",
            str(args.ranking_episodes),
            "--budget",
            str(args.budget),
            "--seed",
            str(seed),
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
            str(seed),
        ])

        near_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts/run_new_paper_near_tie_pair_pipeline.py"),
            "--pairwise-dataset",
            str(pairwise_dataset),
            "--bt-model",
            str(baseline_model_path),
            "--output-root",
            str(Path(args.near_tie_output_root)),
            "--run-id",
            f"{run_id}_seed_{seed}",
            "--min-signals",
            "1",
        ]
        _run(near_cmd)

        near_pairs = _load_jsonl(Path(args.near_tie_output_root) / f"{run_id}_seed_{seed}" / "near_tie_pairs.jsonl")
        hard_train_keys = {r["pair_key"] for r in near_pairs if r.get("split") == "train"}
        hard_test_keys = {r["pair_key"] for r in near_pairs if r.get("split") == "test"}
        base_pairs = _load_jsonl(pairwise_dataset)

        improved_rows: list[dict[str, Any]] = []
        for r in base_pairs:
            key = "|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"])))
            improved_rows.append(r)
            if r.get("split") == "train" and key in hard_train_keys:
                for _ in range(max(0, int(args.hard_oversample_factor) - 1)):
                    improved_rows.append(dict(r))

        improved_dataset = seed_dir / "pairwise_dataset_hard_oversampled.jsonl"
        _write_jsonl(improved_dataset, improved_rows)
        _run([
            sys.executable,
            str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
            "--dataset",
            str(improved_dataset),
            "--output",
            str(oversampled_model_path),
            "--seed",
            str(seed),
            "--weighting",
            "confidence",
            "--soft-uncertain-target",
        ])

        baseline_model = json.loads(baseline_model_path.read_text(encoding="utf-8"))
        oversampled_model = json.loads(oversampled_model_path.read_text(encoding="utf-8"))
        test_rows = [r for r in base_pairs if r.get("split") == "test"]
        hard_test_rows = [
            r
            for r in test_rows
            if "|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"]))) in hard_test_keys
        ]
        near_train_rows = [
            r
            for r in base_pairs
            if r.get("split") == "train"
            and "|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"]))) in hard_train_keys
        ]

        tie_log_model = _train_logistic(near_train_rows, hard_test_rows, _tie_features_diff_abs(), seed)
        tie_log_path = seed_dir / "near_tie_tiebreaker_logistic.json"
        tie_log_path.write_text(json.dumps(tie_log_model, indent=2), encoding="utf-8")

        tie_stump_model = _train_decision_stump(near_train_rows, hard_test_rows, _tie_features_compact())
        tie_stump_path = seed_dir / "near_tie_tiebreaker_stump_compact.json"
        tie_stump_path.write_text(json.dumps(tie_stump_model, indent=2), encoding="utf-8")

        two_stage_log_path = seed_dir / "adaptive_learned_branch_score_v7_bt_two_stage_logistic.json"
        two_stage_log_path.write_text(
            json.dumps(
                {
                    "model_type": "two_stage_near_tie_bt",
                    "base_model": {
                        "intercept": float(baseline_model.get("intercept", 0.0)),
                        "weights": baseline_model.get("weights", {}),
                    },
                    "tie_break_model": tie_log_model,
                    "near_tie_margin": float(args.near_tie_margin),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        two_stage_stump_path = seed_dir / "adaptive_learned_branch_score_v7_bt_two_stage_stump_calibrated.json"
        two_stage_stump_path.write_text(
            json.dumps(
                {
                    "model_type": "two_stage_near_tie_bt",
                    "base_model": {
                        "intercept": float(baseline_model.get("intercept", 0.0)),
                        "weights": baseline_model.get("weights", {}),
                    },
                    "tie_break_model": tie_stump_model,
                    "near_tie_margin": float(args.near_tie_margin),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        oracle_model_path: Path | None = None
        if args.include_oracle_reference:
            oracle_root = seed_dir / "oracle_labels"
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
                str(seed),
            ])
            oracle_dirs = sorted([p for p in oracle_root.glob("*") if p.is_dir()])
            if oracle_dirs:
                oracle_pairwise = oracle_dirs[-1] / "pairwise_oracle_preferences.jsonl"
                oracle_model_path = seed_dir / "adaptive_learned_branch_score_v7_bt_oracle_ref.json"
                _run([
                    sys.executable,
                    str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
                    "--dataset",
                    str(oracle_pairwise),
                    "--output",
                    str(oracle_model_path),
                    "--seed",
                    str(seed),
                ])

        rng = random.Random(seed)
        examples = _load_examples_with_retry(args.dataset, args.subset_size, seed)
        gen_factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
        strategies = build_frontier_strategies(
            gen_factory,
            args.budget,
            adaptive_min_expand_grid=[1],
            rng=rng,
            use_openai_api=False,
            bt_pairwise_model_path=str(baseline_model_path),
            bt_pairwise_oracle_model_path=str(oracle_model_path or baseline_model_path),
        )
        strategies["adaptive_bt_pairwise_oversample"] = AdaptiveController(
            gen_factory(),
            LearnedBTBranchScorer(oversampled_model_path, max_actions_per_problem=args.budget),
            args.budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_oversample",
        )
        strategies["adaptive_bt_pairwise_two_stage_prev_best"] = AdaptiveController(
            gen_factory(),
            TwoStageNearTieBTBranchScorer(two_stage_log_path, max_actions_per_problem=args.budget),
            args.budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_two_stage_prev_best",
        )
        strategies["adaptive_bt_pairwise_two_stage_cal_sweep_least_harm"] = AdaptiveController(
            gen_factory(),
            TwoStageNearTieBTBranchScorer(two_stage_stump_path, max_actions_per_problem=args.budget),
            args.budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_two_stage_cal_sweep_least_harm",
        )

        metrics, _ = evaluate_strategies_on_examples(examples, strategies)
        selected = [
            "adaptive_bt_pairwise",
            "adaptive_bt_pairwise_oversample",
            "adaptive_bt_pairwise_two_stage_prev_best",
            "adaptive_bt_pairwise_two_stage_cal_sweep_least_harm",
        ]
        if args.include_oracle_reference:
            selected.append("adaptive_bt_pairwise_oracle")

        pair_all = {
            "adaptive_bt_pairwise": _pair_acc(test_rows, baseline_model),
            "adaptive_bt_pairwise_oversample": _pair_acc(test_rows, oversampled_model),
            "adaptive_bt_pairwise_two_stage_prev_best": _pair_acc_two_stage(
                test_rows, baseline_model, tie_log_model, float(args.near_tie_margin)
            ),
            "adaptive_bt_pairwise_two_stage_cal_sweep_least_harm": _pair_acc_two_stage(
                test_rows, baseline_model, tie_stump_model, float(args.near_tie_margin)
            ),
        }
        near_tie_pair = {
            "adaptive_bt_pairwise": _pair_acc(hard_test_rows, baseline_model),
            "adaptive_bt_pairwise_oversample": _pair_acc(hard_test_rows, oversampled_model),
            "adaptive_bt_pairwise_two_stage_prev_best": _pair_acc_two_stage(
                hard_test_rows, baseline_model, tie_log_model, float(args.near_tie_margin)
            ),
            "adaptive_bt_pairwise_two_stage_cal_sweep_least_harm": _pair_acc_two_stage(
                hard_test_rows, baseline_model, tie_stump_model, float(args.near_tie_margin)
            ),
        }
        if args.include_oracle_reference and oracle_model_path is not None:
            oracle_model = json.loads(oracle_model_path.read_text(encoding="utf-8"))
            pair_all["adaptive_bt_pairwise_oracle"] = _pair_acc(test_rows, oracle_model)
            near_tie_pair["adaptive_bt_pairwise_oracle"] = _pair_acc(hard_test_rows, oracle_model)

        baseline_acc = float(metrics.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0))
        for method in selected:
            if method not in metrics:
                continue
            acc = float(metrics[method]["accuracy"])
            delta = acc - baseline_acc
            win = 1 if delta > 1e-12 else (-1 if delta < -1e-12 else 0)
            method_rows.append(
                {
                    "seed": seed,
                    "method": method,
                    "accuracy": acc,
                    "avg_actions": float(metrics[method]["avg_actions"]),
                    "delta_vs_baseline": delta,
                    "win_vs_baseline": win,
                    "pair_all_accuracy": pair_all.get(method, 0.0),
                    "pair_all_delta_vs_baseline": pair_all.get(method, 0.0) - pair_all.get("adaptive_bt_pairwise", 0.0),
                    "near_tie_pair_accuracy": near_tie_pair.get(method, 0.0),
                    "near_tie_pair_delta_vs_baseline": near_tie_pair.get(method, 0.0)
                    - near_tie_pair.get("adaptive_bt_pairwise", 0.0),
                    "n_test_pairs": len(test_rows),
                    "n_near_tie_test_pairs": len(hard_test_rows),
                }
            )
            near_tie_rows.append(
                {
                    "seed": seed,
                    "method": method,
                    "near_tie_pair_accuracy": near_tie_pair.get(method, 0.0),
                    "near_tie_pair_delta_vs_baseline": near_tie_pair.get(method, 0.0)
                    - near_tie_pair.get("adaptive_bt_pairwise", 0.0),
                    "n_near_tie_test_pairs": len(hard_test_rows),
                }
            )

    by_method: dict[str, list[dict[str, Any]]] = {}
    for r in method_rows:
        by_method.setdefault(str(r["method"]), []).append(r)

    summary_rows: list[dict[str, Any]] = []
    for method, rows in sorted(by_method.items()):
        accs = [float(r["accuracy"]) for r in rows]
        deltas = [float(r["delta_vs_baseline"]) for r in rows]
        near_deltas = [float(r["near_tie_pair_delta_vs_baseline"]) for r in rows]
        pair_all_deltas = [float(r["pair_all_delta_vs_baseline"]) for r in rows]
        wins = sum(1 for x in deltas if x > 0)
        losses = sum(1 for x in deltas if x < 0)
        ties = sum(1 for x in deltas if x == 0)
        summary_rows.append(
            {
                "method": method,
                "n_seeds": len(rows),
                "mean_accuracy": statistics.mean(accs),
                "std_accuracy": _std(accs),
                "mean_delta_vs_baseline": statistics.mean(deltas),
                "std_delta_vs_baseline": _std(deltas),
                "wins_vs_baseline": wins,
                "losses_vs_baseline": losses,
                "ties_vs_baseline": ties,
                "mean_pair_all_delta_vs_baseline": statistics.mean(pair_all_deltas),
                "std_pair_all_delta_vs_baseline": _std(pair_all_deltas),
                "mean_near_tie_pair_delta_vs_baseline": statistics.mean(near_deltas),
                "std_near_tie_pair_delta_vs_baseline": _std(near_deltas),
            }
        )

    _write_csv(run_dir / "method_metrics_by_seed.csv", method_rows)
    _write_csv(run_dir / "near_tie_slice_by_seed.csv", near_tie_rows)
    _write_csv(run_dir / "stability_summary.csv", summary_rows)

    summary_by_method = {r["method"]: r for r in summary_rows}
    most_stable = min(summary_rows, key=lambda r: abs(float(r["std_accuracy"]))) if summary_rows else None
    two_stage_prev = summary_by_method.get("adaptive_bt_pairwise_two_stage_prev_best", {})
    oversample = summary_by_method.get("adaptive_bt_pairwise_oversample", {})

    interp = [
        f"# Lightweight stability audit ({run_id})",
        "",
        "Bounded multi-seed audit focused on robustness (not new method invention).",
        "",
        "## Common evaluation setup selected",
        "- Dataset: openai/gsm8k pilot subset via in-repo simulator (no external API).",
        f"- Matched budget: {args.budget}.",
        f"- Ranking episodes per seed: {args.ranking_episodes}.",
        f"- Controller eval subset per seed: {args.subset_size} examples.",
        f"- Seeds: {', '.join(map(str, seeds))}.",
        "- Near-tie slice from `run_new_paper_near_tie_pair_pipeline.py` with `min-signals=1`.",
        "",
        "## Explicit answers",
        f"- Most stable variant by controller-accuracy std: `{most_stable['method']}` (std={float(most_stable['std_accuracy']):.4f})." if most_stable else "- Most stable variant: n/a.",
        f"- Did earlier +0.10 two-stage gain survive? {'likely noise (mean delta <= 0)' if float(two_stage_prev.get('mean_delta_vs_baseline', 0.0)) <= 0 else 'partially (mean delta > 0), but check variance'}; mean delta={float(two_stage_prev.get('mean_delta_vs_baseline', 0.0)):+.4f}, wins/losses={int(two_stage_prev.get('wins_vs_baseline', 0))}/{int(two_stage_prev.get('losses_vs_baseline', 0))}.",
        f"- Is oversampling consistently harmful? {'yes' if int(oversample.get('wins_vs_baseline', 0)) == 0 and float(oversample.get('mean_delta_vs_baseline', 0.0)) < 0 else 'mixed'}; mean delta={float(oversample.get('mean_delta_vs_baseline', 0.0)):+.4f}, wins/losses={int(oversample.get('wins_vs_baseline', 0))}/{int(oversample.get('losses_vs_baseline', 0))}.",
        "- Robust branch worth keeping: keep only methods with non-negative mean delta and low variance; otherwise keep baseline default.",
        "",
        "## Conservative branch decisions",
        "- Baseline default: adaptive_bt_pairwise (reference branch).",
        "- Experimental branch to keep only if repeats stay non-negative: two-stage calibration least-harm (decision stump, margin=0.06).",
        "- Dead-end candidate: hard oversampling if it remains net-negative across seeds.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "goal": "stability_variance_audit_lightweight_branch_scoring",
        "dataset": args.dataset,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "subset_size": args.subset_size,
        "seeds": seeds,
        "hard_oversample_factor": args.hard_oversample_factor,
        "near_tie_margin": args.near_tie_margin,
        "variants": [
            "adaptive_bt_pairwise",
            "adaptive_bt_pairwise_oversample",
            "adaptive_bt_pairwise_two_stage_prev_best",
            "adaptive_bt_pairwise_two_stage_cal_sweep_least_harm",
        ] + (["adaptive_bt_pairwise_oracle"] if args.include_oracle_reference else []),
        "least_harm_calibration_from_sweep": {
            "model_type": "decision_stump",
            "feature_set": "compact",
            "near_tie_margin": 0.06,
            "subset": "all_near_tie",
        },
        "artifacts": {
            "method_metrics_by_seed": str(run_dir / "method_metrics_by_seed.csv"),
            "near_tie_slice_by_seed": str(run_dir / "near_tie_slice_by_seed.csv"),
            "stability_summary": str(run_dir / "stability_summary.csv"),
            "interpretation": str(run_dir / "interpretation.md"),
            "run_manifest": str(run_dir / "run_manifest.json"),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "n_rows": len(method_rows)}, indent=2))


if __name__ == "__main__":
    main()
