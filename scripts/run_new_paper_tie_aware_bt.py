#!/usr/bin/env python3
"""Bounded tie-aware BT experiment for the new-paper track.

Compares:
- baseline proxy BT
- tie-aware BT variants (Davidson / Rao-Kupper)
- hard-pair oversampling reference
- two-stage near-tie tie-breaker reference

Cheap, text-only, reproducible.
"""

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
from experiments.frontier_matrix_core import build_frontier_strategies, evaluate_strategies_on_examples, generator_factory_for_mode, load_pilot_examples
from experiments.scoring import LearnedBTBranchScorer, TieAwareBTBranchScorer, TwoStageNearTieBTBranchScorer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded tie-aware BT comparison (new-paper)")
    p.add_argument("--output-root", default="outputs/new_paper/tie_aware_bt")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=28)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--seed", type=int, default=73)
    p.add_argument("--ranking-episodes", type=int, default=220)
    p.add_argument("--near-tie-margin", type=float, default=0.06)
    p.add_argument("--hard-oversample-factor", type=int, default=3)
    p.add_argument("--include-oracle-reference", action="store_true")
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _score_linear(model: dict[str, Any], features: dict[str, float]) -> float:
    s = float(model.get("intercept", 0.0))
    for n, w in model.get("weights", {}).items():
        s += float(w) * float(features.get(n, 0.0))
    return s


def _pair_probs(model: dict[str, Any], delta: float) -> tuple[float, float, float]:
    objective = str(model.get("training_objective", "bt")).lower()
    tie_raw = float(model.get("tie_raw_parameter", -2.0))
    if objective == "davidson":
        nu = max(1e-6, pow(2.718281828, tie_raw))
        a = pow(2.718281828, max(-40.0, min(40.0, delta / 2.0)))
        b = pow(2.718281828, max(-40.0, min(40.0, -delta / 2.0)))
        d = a + b + nu
        return a / d, b / d, nu / d
    if objective == "raokupper":
        eta = 1.0 + math.log1p(math.exp(tie_raw))
        ed = pow(2.718281828, max(-40.0, min(40.0, delta)))
        p_win = ed / (ed + eta)
        p_loss = 1.0 / (1.0 + eta * ed)
        p_tie = max(1e-12, 1.0 - p_win - p_loss)
        z = p_win + p_loss + p_tie
        return p_win / z, p_loss / z, p_tie / z
    p = 1.0 / (1.0 + pow(2.718281828, -max(-40.0, min(40.0, delta))))
    return p, 1.0 - p, 0.0


def _pair_acc(rows: list[dict[str, Any]], model: dict[str, Any]) -> float:
    if not rows:
        return 0.0
    ok = 0
    for r in rows:
        d = _score_linear(model, r["features_a"]) - _score_linear(model, r["features_b"])
        p_a, p_b, _ = _pair_probs(model, d)
        pred = 1 if p_a >= p_b else 0
        ok += int(pred == int(r.get("a_preferred", 0)))
    return ok / len(rows)


def _fit_two_stage_tie_model(train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], epochs: int = 35, lr: float = 0.03) -> dict[str, Any]:
    feat_names = [f"diff::{k}" for k in [
        "parent_relative_score",
        "node_2_score",
        "node_3_score",
        "node_3_distance_to_terminal_est",
        "edge_1_score_delta",
        "edge_2_score_delta",
        "stalled_steps",
        "verify_count",
    ]]
    feat_names += [f"abs_diff::{k}" for k in ["node_3_score", "parent_relative_score", "edge_2_score_delta"]]

    def feats(row: dict[str, Any]) -> dict[str, float]:
        a, b = row["features_a"], row["features_b"]
        out: dict[str, float] = {}
        for n in feat_names:
            if n.startswith("diff::"):
                k = n.split("::", 1)[1]
                out[n] = float(a.get(k, 0.0)) - float(b.get(k, 0.0))
            else:
                k = n.split("::", 1)[1]
                out[n] = abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0)))
        return out

    w = {k: 0.0 for k in feat_names}
    b = 0.0
    rng = random.Random(0)

    def sigmoid(z: float) -> float:
        if z >= 0:
            ez = pow(2.718281828, -z)
            return 1.0 / (1.0 + ez)
        ez = pow(2.718281828, z)
        return ez / (1.0 + ez)

    for _ in range(epochs):
        rng.shuffle(train_rows)
        for r in train_rows:
            x = feats(r)
            y = float(r.get("a_preferred", 0.0))
            z = b + sum(w[k] * x[k] for k in feat_names)
            p = sigmoid(z)
            g = p - y
            for k in feat_names:
                w[k] -= lr * (g * x[k] + 1e-4 * w[k])
            b -= lr * g

    def _acc(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        ok = 0
        for r in rows:
            x = feats(r)
            z = b + sum(w[k] * x[k] for k in feat_names)
            ok += int((1 if sigmoid(z) >= 0.5 else 0) == int(r.get("a_preferred", 0)))
        return ok / len(rows)

    return {
        "model_type": "logistic_regression",
        "feature_names": feat_names,
        "weights": {k: float(v) for k, v in w.items()},
        "intercept": float(b),
        "train_pair_accuracy": _acc(train_rows),
        "test_pair_accuracy": _acc(test_rows),
    }


def _pair_key(r: dict[str, Any]) -> str:
    a, b = sorted([str(r["branch_a_id"]), str(r["branch_b_id"])])
    return f"{int(r['episode_id'])}|{int(r['decision_id'])}|{a}|{b}"


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ranking_dataset = run_dir / "branch_scorer_v3_dataset.jsonl"
    pairwise_dataset = run_dir / "pairwise_dataset.jsonl"
    baseline_path = run_dir / "adaptive_learned_branch_score_v7_bt_baseline.json"
    davidson_path = run_dir / "adaptive_learned_branch_score_v7_bt_davidson.json"
    raokupper_path = run_dir / "adaptive_learned_branch_score_v7_bt_raokupper.json"
    oversampled_dataset = run_dir / "pairwise_dataset_hard_oversampled.jsonl"
    oversampled_path = run_dir / "adaptive_learned_branch_score_v7_bt_hard_oversample.json"
    two_stage_path = run_dir / "adaptive_learned_branch_score_v7_bt_two_stage_reference.json"

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

    _run([sys.executable, str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"), "--dataset", str(pairwise_dataset), "--output", str(baseline_path), "--seed", str(args.seed), "--objective", "bt"])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pairwise_dataset),
        "--output",
        str(davidson_path),
        "--seed",
        str(args.seed),
        "--objective",
        "davidson",
        "--tie-supervision",
        "tie_or_uncertain",
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pairwise_dataset),
        "--output",
        str(raokupper_path),
        "--seed",
        str(args.seed),
        "--objective",
        "raokupper",
        "--tie-supervision",
        "tie_or_uncertain",
    ])

    pair_rows = _load_jsonl(pairwise_dataset)
    base_model = _load_json(baseline_path)

    near_keys = {
        _pair_key(r)
        for r in pair_rows
        if abs(_score_linear(base_model, r["features_a"]) - _score_linear(base_model, r["features_b"])) <= args.near_tie_margin
    }
    oversampled_rows: list[dict[str, Any]] = []
    for r in pair_rows:
        oversampled_rows.append(r)
        if r.get("split") == "train" and _pair_key(r) in near_keys:
            for _ in range(max(0, args.hard_oversample_factor - 1)):
                oversampled_rows.append(dict(r))
    _write_jsonl(oversampled_dataset, oversampled_rows)
    _run([sys.executable, str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"), "--dataset", str(oversampled_dataset), "--output", str(oversampled_path), "--seed", str(args.seed), "--objective", "bt"])

    train_rows = [r for r in pair_rows if r.get("split") == "train" and _pair_key(r) in near_keys]
    test_rows = [r for r in pair_rows if r.get("split") == "test" and _pair_key(r) in near_keys]
    tie_model = _fit_two_stage_tie_model(train_rows, test_rows)
    two_stage = {
        "model_type": "two_stage_bt_tie_break",
        "base_model": base_model,
        "tie_break_model": tie_model,
        "near_tie_margin": float(args.near_tie_margin),
        "trigger_source": "baseline_score_gap",
    }
    two_stage_path.write_text(json.dumps(two_stage, indent=2), encoding="utf-8")

    davidson_model = _load_json(davidson_path)
    raokupper_model = _load_json(raokupper_path)
    oversampled_model = _load_json(oversampled_path)

    all_test = [r for r in pair_rows if r.get("split") == "test"]
    near_tie_slice = [r for r in all_test if int(r.get("tie_or_uncertain", 0)) == 1 or _pair_key(r) in near_keys]

    near_rows = []
    for name, model in [
        ("proxy_bt_baseline", base_model),
        ("tie_aware_davidson", davidson_model),
        ("tie_aware_raokupper", raokupper_model),
        ("hard_pair_oversample", oversampled_model),
    ]:
        near_rows.append({
            "method": name,
            "pair_acc_test": _pair_acc(all_test, model),
            "pair_acc_near_tie_slice": _pair_acc(near_tie_slice, model),
            "test_pairs": len(all_test),
            "near_tie_pairs": len(near_tie_slice),
        })

    # two-stage pairwise reference
    def tie_prob(row: dict[str, Any]) -> float:
        a, b = row["features_a"], row["features_b"]
        z = float(tie_model.get("intercept", 0.0))
        for n, w in tie_model.get("weights", {}).items():
            if n.startswith("diff::"):
                k = n.split("::", 1)[1]
                x = float(a.get(k, 0.0)) - float(b.get(k, 0.0))
            else:
                k = n.split("::", 1)[1]
                x = abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0)))
            z += float(w) * x
        return 1.0 / (1.0 + pow(2.718281828, -max(-40.0, min(40.0, z))))

    def pair_acc_two_stage(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        ok = 0
        for r in rows:
            sa = _score_linear(base_model, r["features_a"])
            sb = _score_linear(base_model, r["features_b"])
            pred = 1 if sa >= sb else 0
            if abs(sa - sb) <= args.near_tie_margin:
                oriented = r if pred == 1 else {**r, "features_a": r["features_b"], "features_b": r["features_a"], "a_preferred": 1 - int(r.get("a_preferred", 0))}
                keep_top = 1 if tie_prob(oriented) >= 0.5 else 0
                pred = pred if keep_top == 1 else (1 - pred)
            ok += int(pred == int(r.get("a_preferred", 0)))
        return ok / len(rows)

    near_rows.append({
        "method": "two_stage_tie_breaker",
        "pair_acc_test": pair_acc_two_stage(all_test),
        "pair_acc_near_tie_slice": pair_acc_two_stage(near_tie_slice),
        "test_pairs": len(all_test),
        "near_tie_pairs": len(near_tie_slice),
    })

    rng = random.Random(args.seed)
    examples = load_pilot_examples(args.dataset, args.subset_size, args.seed)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
    baseline_strategies = build_frontier_strategies(
        gen_factory,
        args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        bt_pairwise_model_path=str(baseline_path),
    )

    strategies: dict[str, Any] = {
        "adaptive_min_expand_1": baseline_strategies["adaptive_min_expand_1"],
        "adaptive_bt_pairwise": baseline_strategies["adaptive_bt_pairwise"],
    }
    strategies["adaptive_bt_pairwise_tie_aware_davidson"] = AdaptiveController(
        gen_factory(), TieAwareBTBranchScorer(davidson_path, max_actions_per_problem=args.budget), args.budget,
        high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
        method_name="adaptive_bt_pairwise_tie_aware_davidson",
    )
    strategies["adaptive_bt_pairwise_tie_aware_raokupper"] = AdaptiveController(
        gen_factory(), TieAwareBTBranchScorer(raokupper_path, max_actions_per_problem=args.budget), args.budget,
        high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
        method_name="adaptive_bt_pairwise_tie_aware_raokupper",
    )
    strategies["adaptive_bt_pairwise_hard_oversample"] = AdaptiveController(
        gen_factory(), LearnedBTBranchScorer(oversampled_path, max_actions_per_problem=args.budget), args.budget,
        high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
        method_name="adaptive_bt_pairwise_hard_oversample",
    )
    strategies["adaptive_bt_pairwise_two_stage"] = AdaptiveController(
        gen_factory(), TwoStageNearTieBTBranchScorer(two_stage_path, max_actions_per_problem=args.budget), args.budget,
        high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
        method_name="adaptive_bt_pairwise_two_stage",
    )

    metrics, rows = evaluate_strategies_on_examples(examples, strategies)
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    oracle_acc = sum(1 for rr in by_ex.values() if any(bool(r["is_correct"]) for r in rr)) / max(1, len(by_ex))

    method_rows: list[dict[str, Any]] = []
    for name in strategies:
        method_rows.append({
            "method": name,
            "accuracy": float(metrics[name]["accuracy"]),
            "avg_actions": float(metrics[name]["avg_actions"]),
            "gap_to_oracle": float(oracle_acc - float(metrics[name]["accuracy"])),
        })

    if args.include_oracle_reference:
        method_rows.append({"method": "oracle_reference", "accuracy": float(oracle_acc), "avg_actions": 0.0, "gap_to_oracle": 0.0})

    method_map = {r["method"]: r for r in method_rows}
    compare_rows: list[dict[str, Any]] = []
    for nr in near_rows:
        m = nr["method"]
        strategy_name = {
            "proxy_bt_baseline": "adaptive_bt_pairwise",
            "tie_aware_davidson": "adaptive_bt_pairwise_tie_aware_davidson",
            "tie_aware_raokupper": "adaptive_bt_pairwise_tie_aware_raokupper",
            "hard_pair_oversample": "adaptive_bt_pairwise_hard_oversample",
            "two_stage_tie_breaker": "adaptive_bt_pairwise_two_stage",
        }.get(m, "")
        controller_acc = float(method_map.get(strategy_name, {}).get("accuracy", 0.0))
        compare_rows.append({
            "method": m,
            "pair_acc_test": nr["pair_acc_test"],
            "pair_acc_near_tie_slice": nr["pair_acc_near_tie_slice"],
            "controller_accuracy": controller_acc,
            "controller_delta_vs_baseline": controller_acc - float(method_map.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0)),
            "near_tie_pair_delta_vs_baseline": nr["pair_acc_near_tie_slice"] - next(x["pair_acc_near_tie_slice"] for x in near_rows if x["method"] == "proxy_bt_baseline"),
        })

    _write_csv(run_dir / "method_metrics.csv", method_rows)
    _write_csv(run_dir / "tie_aware_comparison.csv", compare_rows)
    _write_csv(run_dir / "near_tie_slice_results.csv", near_rows)

    best_tie_aware = max(
        [r for r in compare_rows if r["method"] in {"tie_aware_davidson", "tie_aware_raokupper"}],
        key=lambda r: (float(r["controller_accuracy"]), float(r["pair_acc_near_tie_slice"])),
    )

    interp = [
        f"# Tie-aware BT comparison ({run_id})",
        "",
        "## Scope and insertion point",
        "- Clean insertion point is existing `train_bt_pairwise_branch_scorer.py` (objective switch), because inference is already scalar in `LearnedBTBranchScorer`/controller flow.",
        "- Tie-aware variants keep scalar utility inference while exposing explicit win/loss/tie probabilities at pairwise diagnostic time.",
        "",
        "## Required answers",
        f"- Does tie-aware BT handle near-tie pairs better than plain BT? **{'Yes' if best_tie_aware['near_tie_pair_delta_vs_baseline'] > 0 else 'No'}** (best tie-aware near-tie delta: {best_tie_aware['near_tie_pair_delta_vs_baseline']:.4f}).",
        f"- Does it improve the near-tie slice? **{'Yes' if best_tie_aware['near_tie_pair_delta_vs_baseline'] > 0 else 'No / marginal'}**.",
        f"- Does it preserve or improve overall controller accuracy? **{'Yes' if best_tie_aware['controller_delta_vs_baseline'] >= 0 else 'No'}** (delta={best_tie_aware['controller_delta_vs_baseline']:.4f}).",
        f"- Is it better than hard-pair oversampling? **{'Yes' if best_tie_aware['controller_accuracy'] >= next(r['controller_accuracy'] for r in compare_rows if r['method']=='hard_pair_oversample') else 'No'}** on controller accuracy.",
        f"- Is it better than the two-stage tie-breaker branch? **{'Yes' if best_tie_aware['controller_accuracy'] >= next(r['controller_accuracy'] for r in compare_rows if r['method']=='two_stage_tie_breaker') else 'No'}** on controller accuracy.",
        f"- Should tie-aware BT become the next lightweight experimental branch? **{'Yes, as the next lightweight branch to track' if best_tie_aware['controller_delta_vs_baseline'] >= 0 and best_tie_aware['near_tie_pair_delta_vs_baseline'] > 0 else 'Keep as diagnostic-only for now; baseline proxy BT stays default'}**.",
        "",
        "## Honesty note",
        "- Tie labels here are still proxy-derived (`tie_or_uncertain`) and not oracle human ties.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "budget": args.budget,
        "seed": args.seed,
        "ranking_episodes": args.ranking_episodes,
        "near_tie_margin": args.near_tie_margin,
        "hard_oversample_factor": args.hard_oversample_factor,
        "artifacts": {
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "tie_aware_comparison": str(run_dir / "tie_aware_comparison.csv"),
            "near_tie_slice_results": str(run_dir / "near_tie_slice_results.csv"),
            "interpretation": str(run_dir / "interpretation.md"),
            "baseline_model": str(baseline_path),
            "davidson_model": str(davidson_path),
            "raokupper_model": str(raokupper_path),
            "oversampled_model": str(oversampled_path),
            "two_stage_model": str(two_stage_path),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir), "best_tie_aware_method": best_tie_aware["method"]}, indent=2))


if __name__ == "__main__":
    main()
