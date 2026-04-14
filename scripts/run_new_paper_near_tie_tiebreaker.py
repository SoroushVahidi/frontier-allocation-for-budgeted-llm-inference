#!/usr/bin/env python3
"""Selective two-stage near-tie tie-breaker experiment (new-paper, cheap/text-only)."""

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
    p = argparse.ArgumentParser(description="Run near-tie selective two-stage tie-breaker")
    p.add_argument("--output-root", default="outputs/new_paper/near_tie_tiebreaker")
    p.add_argument("--near-tie-output-root", default="outputs/new_paper/near_tie_pairs")
    p.add_argument("--run-id", default=None)
    p.add_argument("--seed", type=int, default=61)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=320)
    p.add_argument("--subset-size", type=int, default=36)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--hard-oversample-factor", type=int, default=3)
    p.add_argument("--near-tie-margin", type=float, default=0.06)
    p.add_argument("--tie-train-epochs", type=int, default=45)
    p.add_argument("--tie-train-lr", type=float, default=0.03)
    p.add_argument("--tie-train-l2", type=float, default=1e-4)
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def _oracle_accuracy(rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    if not by_ex:
        return 0.0
    return sum(1 for rr in by_ex.values() if any(bool(r["is_correct"]) for r in rr)) / len(by_ex)


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _tie_feature_names() -> list[str]:
    names: list[str] = []
    for k in V7_FEATURE_NAMES:
        names.append(f"diff::{k}")
    for k in ["node_3_score", "node_2_score", "parent_relative_score", "edge_2_score_delta", "stalled_steps", "verify_count"]:
        names.append(f"abs_diff::{k}")
    return names


def _tie_features(row: dict[str, Any], feat_names: list[str]) -> dict[str, float]:
    a = row["features_a"]
    b = row["features_b"]
    feats: dict[str, float] = {}
    for name in feat_names:
        if name.startswith("diff::"):
            base = name.split("::", 1)[1]
            feats[name] = float(a.get(base, 0.0)) - float(b.get(base, 0.0))
        elif name.startswith("abs_diff::"):
            base = name.split("::", 1)[1]
            feats[name] = abs(float(a.get(base, 0.0)) - float(b.get(base, 0.0)))
    return feats


def _train_tie_model(train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], epochs: int, lr: float, l2: float) -> dict[str, Any]:
    feat_names = _tie_feature_names()
    w = {k: 0.0 for k in feat_names}
    b = 0.0
    rng = random.Random(0)

    for _ in range(epochs):
        rng.shuffle(train_rows)
        for r in train_rows:
            x = _tie_features(r, feat_names)
            y = float(r.get("a_preferred", 0.0))
            z = b + sum(w[k] * x[k] for k in feat_names)
            p = _sigmoid(z)
            g = p - y
            for k in feat_names:
                w[k] -= lr * (g * x[k] + l2 * w[k])
            b -= lr * g

    def acc(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        ok = 0
        for r in rows:
            x = _tie_features(r, feat_names)
            z = b + sum(w[k] * x[k] for k in feat_names)
            pred = 1 if _sigmoid(z) >= 0.5 else 0
            ok += int(pred == int(r.get("a_preferred", 0)))
        return ok / len(rows)

    abs_rank = sorted(((k, abs(v)) for k, v in w.items()), key=lambda x: x[1], reverse=True)
    return {
        "model_type": "logistic_regression",
        "feature_names": feat_names,
        "weights": {k: float(v) for k, v in w.items()},
        "intercept": float(b),
        "train_pair_accuracy": acc(train_rows),
        "test_pair_accuracy": acc(test_rows),
        "top_abs_weight_features": [{"feature": k, "abs_weight": float(v)} for k, v in abs_rank[:12]],
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
            x = _tie_features(oriented, feat_names)
            z = float(tie_model.get("intercept", 0.0))
            for k, v in tie_model.get("weights", {}).items():
                z += float(v) * float(x.get(k, 0.0))
            keep_top = 1 if _sigmoid(z) >= 0.5 else 0
            pred = pred if keep_top == 1 else (1 - pred)
        ok += int(pred == int(r.get("a_preferred", 0)))
    return ok / len(rows)


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ranking_dataset = run_dir / "branch_scorer_v3_dataset.jsonl"
    pairwise_dataset = run_dir / "pairwise_dataset.jsonl"
    baseline_model_path = run_dir / "adaptive_learned_branch_score_v7_bt_baseline.json"
    improved_dataset = run_dir / "pairwise_dataset_hard_oversampled.jsonl"
    oversampled_model_path = run_dir / "adaptive_learned_branch_score_v7_bt_near_tie_oversample.json"
    tie_model_path = run_dir / "near_tie_tiebreaker_model.json"
    two_stage_model_path = run_dir / "adaptive_learned_branch_score_v7_bt_two_stage_near_tie.json"

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

    near_pairs = _load_jsonl(near_tie_root / run_id / "near_tie_pairs.jsonl")
    near_by_key = {r["pair_key"]: r for r in near_pairs}
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
    _write_jsonl(improved_dataset, improved_rows)

    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(improved_dataset),
        "--output",
        str(oversampled_model_path),
        "--seed",
        str(args.seed),
        "--weighting",
        "confidence",
        "--soft-uncertain-target",
    ])

    baseline_model = json.loads(baseline_model_path.read_text(encoding="utf-8"))
    oversampled_model = json.loads(oversampled_model_path.read_text(encoding="utf-8"))

    near_train_rows = [
        r
        for r in base_pairs
        if r.get("split") == "train"
        and ("|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"]))) in hard_train_keys)
    ]
    near_test_rows = [
        r
        for r in base_pairs
        if r.get("split") == "test"
        and ("|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"]))) in hard_test_keys)
    ]

    tie_model = _train_tie_model(
        near_train_rows,
        near_test_rows,
        epochs=args.tie_train_epochs,
        lr=args.tie_train_lr,
        l2=args.tie_train_l2,
    )
    tie_model_path.write_text(json.dumps(tie_model, indent=2), encoding="utf-8")

    two_stage_model = {
        "model_type": "two_stage_near_tie_bt",
        "base_model": {
            "intercept": float(baseline_model.get("intercept", 0.0)),
            "weights": baseline_model.get("weights", {}),
        },
        "tie_break_model": tie_model,
        "near_tie_margin": float(args.near_tie_margin),
    }
    two_stage_model_path.write_text(json.dumps(two_stage_model, indent=2), encoding="utf-8")

    test_rows = [r for r in base_pairs if r.get("split") == "test"]
    hard_test_rows = [
        r
        for r in test_rows
        if "|".join(map(str, _pair_key(r["episode_id"], r["decision_id"], r["branch_a_id"], r["branch_b_id"]))) in hard_test_keys
    ]

    two_stage_all = _pair_acc_two_stage(test_rows, baseline_model, tie_model, args.near_tie_margin)
    two_stage_hard = _pair_acc_two_stage(hard_test_rows, baseline_model, tie_model, args.near_tie_margin)

    failure_rows = [
        {
            "slice": "all_test_pairs",
            "n_pairs": len(test_rows),
            "baseline_pair_accuracy": _pair_acc(test_rows, baseline_model),
            "oversample_pair_accuracy": _pair_acc(test_rows, oversampled_model),
            "two_stage_pair_accuracy": two_stage_all,
            "oversample_delta_vs_baseline": _pair_acc(test_rows, oversampled_model) - _pair_acc(test_rows, baseline_model),
            "two_stage_delta_vs_baseline": two_stage_all - _pair_acc(test_rows, baseline_model),
        },
        {
            "slice": "near_tie_test_pairs",
            "n_pairs": len(hard_test_rows),
            "baseline_pair_accuracy": _pair_acc(hard_test_rows, baseline_model),
            "oversample_pair_accuracy": _pair_acc(hard_test_rows, oversampled_model),
            "two_stage_pair_accuracy": two_stage_hard,
            "oversample_delta_vs_baseline": _pair_acc(hard_test_rows, oversampled_model) - _pair_acc(hard_test_rows, baseline_model),
            "two_stage_delta_vs_baseline": two_stage_hard - _pair_acc(hard_test_rows, baseline_model),
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
        bt_pairwise_oracle_model_path=str(baseline_model_path),
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
    strategies["adaptive_bt_pairwise_two_stage_tiebreak"] = AdaptiveController(
        gen_factory(),
        TwoStageNearTieBTBranchScorer(two_stage_model_path, max_actions_per_problem=args.budget),
        args.budget,
        high_threshold=0.72,
        low_threshold=0.42,
        max_branches=3,
        allow_verify=True,
        min_expansions_before_prune=1,
        method_name="adaptive_bt_pairwise_two_stage_tiebreak",
    )

    metrics, rows = evaluate_strategies_on_examples(examples, strategies)
    selected = [
        "adaptive_bt_pairwise",
        "adaptive_bt_pairwise_oversample",
        "adaptive_bt_pairwise_two_stage_tiebreak",
        "adaptive_bt_pairwise_oracle",
    ]
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

    comparison_rows = [
        {
            "comparison": "oversample_vs_baseline",
            "baseline_accuracy": by_method.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0),
            "variant_accuracy": by_method.get("adaptive_bt_pairwise_oversample", {}).get("accuracy", 0.0),
            "delta_accuracy": by_method.get("adaptive_bt_pairwise_oversample", {}).get("accuracy", 0.0)
            - by_method.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0),
            "near_tie_pair_delta": failure_rows[1]["oversample_delta_vs_baseline"],
        },
        {
            "comparison": "two_stage_tiebreak_vs_baseline",
            "baseline_accuracy": by_method.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0),
            "variant_accuracy": by_method.get("adaptive_bt_pairwise_two_stage_tiebreak", {}).get("accuracy", 0.0),
            "delta_accuracy": by_method.get("adaptive_bt_pairwise_two_stage_tiebreak", {}).get("accuracy", 0.0)
            - by_method.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0),
            "near_tie_pair_delta": failure_rows[1]["two_stage_delta_vs_baseline"],
        },
    ]

    _write_csv(run_dir / "method_metrics.csv", method_rows)
    _write_csv(run_dir / "near_tie_tiebreaker_comparison.csv", comparison_rows)
    _write_csv(run_dir / "failure_slice_summary.csv", failure_rows)

    top_feats = tie_model.get("top_abs_weight_features", [])
    feat_lines = [f"- {x['feature']}: {x['abs_weight']:.4f}" for x in top_feats[:8]]
    interp = [
        f"# Near-tie two-stage tie-breaker ({run_id})",
        "",
        "Cheap, selective path: baseline BT for normal cases; lightweight tie-breaker only for near-tied top-2 branches.",
        "",
        "## Answers",
        f"- Selective tie-breaker better than global oversampling overall? {'yes' if comparison_rows[1]['delta_accuracy'] > comparison_rows[0]['delta_accuracy'] else 'no'}.",
        f"- Near-tie slice improved vs baseline? {'yes' if failure_rows[1]['two_stage_delta_vs_baseline'] > 0 else 'no'} ({failure_rows[1]['two_stage_delta_vs_baseline']:+.4f}).",
        f"- Overall controller accuracy improved vs baseline? {'yes' if comparison_rows[1]['delta_accuracy'] > 0 else 'no'} ({comparison_rows[1]['delta_accuracy']:+.4f}).",
        "",
        "## Feature importance inside tie-breaker (abs weight)",
        *feat_lines,
        "",
        "## Conservative take",
        "- Keep only if it raises near-tie slice without global regression.",
        "- If overall delta is non-positive, keep diagnostics but do not promote as default.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "dataset": args.dataset,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "subset_size": args.subset_size,
        "hard_oversample_factor": args.hard_oversample_factor,
        "near_tie_margin": args.near_tie_margin,
        "tie_breaker": "logistic_regression_on_near_tie_pairs",
        "near_tie_pair_artifacts": str(near_tie_root / run_id),
        "artifacts": {
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "near_tie_tiebreaker_comparison": str(run_dir / "near_tie_tiebreaker_comparison.csv"),
            "failure_slice_summary": str(run_dir / "failure_slice_summary.csv"),
            "run_manifest": str(run_dir / "run_manifest.json"),
            "interpretation": str(run_dir / "interpretation.md"),
            "tie_breaker_model": str(tie_model_path),
            "two_stage_model": str(two_stage_model_path),
        },
        "near_tie_audit": {
            "n_near_tie_pairs": len(near_pairs),
            "near_tie_rate": len(near_pairs) / max(1, len(base_pairs)),
            "oracle_disagreement_rate_on_near_ties": sum(int(r.get("proxy_oracle_disagree", 0)) for r in near_pairs)
            / max(1, len([r for r in near_pairs if r.get("oracle_preference_canonical") is not None])),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({
        "run_id": run_id,
        "run_dir": str(run_dir),
        "baseline_acc": by_method.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0),
        "oversample_acc": by_method.get("adaptive_bt_pairwise_oversample", {}).get("accuracy", 0.0),
        "two_stage_acc": by_method.get("adaptive_bt_pairwise_two_stage_tiebreak", {}).get("accuracy", 0.0),
    }, indent=2))


if __name__ == "__main__":
    main()
