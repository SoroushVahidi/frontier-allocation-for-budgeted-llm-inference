#!/usr/bin/env python3
"""Bounded stability + calibration audit for tie-aware BT (new-paper track)."""

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
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.controllers import AdaptiveController
from experiments.frontier_matrix_core import build_frontier_strategies, evaluate_strategies_on_examples, generator_factory_for_mode, load_pilot_examples
from experiments.scoring import LearnedBTBranchScorer, TieAwareBTBranchScorer, TwoStageNearTieBTBranchScorer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded tie-aware BT stability audit")
    p.add_argument("--output-root", default="outputs/new_paper/tie_aware_bt_stability")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--seeds", default="71,72,73,74,75")
    p.add_argument("--subset-size", type=int, default=20)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=150)
    p.add_argument("--near-tie-margin", type=float, default=0.06)
    p.add_argument("--hard-oversample-factor", type=int, default=3)
    p.add_argument("--include-reference-branches", action="store_true")
    p.add_argument("--include-oracle-reference", action="store_true")
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for k in row.keys():
                if k not in seen:
                    seen.add(k)
                    fieldnames.append(k)
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line))
    return out


def _score_linear(model: dict[str, Any], features: dict[str, float]) -> float:
    s = float(model.get("intercept", 0.0))
    for n, w in model.get("weights", {}).items():
        s += float(w) * float(features.get(n, 0.0))
    return s


def _pair_probs(model: dict[str, Any], delta: float) -> tuple[float, float, float]:
    objective = str(model.get("training_objective", "bt")).lower()
    tie_raw = float(model.get("tie_raw_parameter", -2.0))

    def _sigmoid(z: float) -> float:
        if z >= 0:
            ez = math.exp(-z)
            return 1.0 / (1.0 + ez)
        ez = math.exp(z)
        return ez / (1.0 + ez)

    if objective == "davidson":
        nu = max(1e-6, math.exp(tie_raw))
        a = math.exp(max(-40.0, min(40.0, delta / 2.0)))
        b = math.exp(max(-40.0, min(40.0, -delta / 2.0)))
        d = a + b + nu
        return a / d, b / d, nu / d
    if objective == "raokupper":
        eta = 1.0 + math.log1p(math.exp(tie_raw))
        ed = math.exp(max(-40.0, min(40.0, delta)))
        p_win = ed / (ed + eta)
        p_loss = 1.0 / (1.0 + eta * ed)
        p_tie = max(1e-12, 1.0 - p_win - p_loss)
        z = p_win + p_loss + p_tie
        return p_win / z, p_loss / z, p_tie / z

    p = _sigmoid(delta)
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


def _pair_key(r: dict[str, Any]) -> str:
    a, b = sorted([str(r["branch_a_id"]), str(r["branch_b_id"])])
    return f"{int(r['episode_id'])}|{int(r['decision_id'])}|{a}|{b}"


def _fit_two_stage_tie_model(rows: list[dict[str, Any]], epochs: int = 30, lr: float = 0.03) -> dict[str, Any]:
    feature_names = [
        "diff::parent_relative_score",
        "diff::node_2_score",
        "diff::node_3_score",
        "diff::node_3_distance_to_terminal_est",
        "diff::edge_2_score_delta",
        "diff::stalled_steps",
        "diff::verify_count",
        "abs_diff::node_3_score",
        "abs_diff::parent_relative_score",
    ]

    def feats(row: dict[str, Any]) -> dict[str, float]:
        a, b = row["features_a"], row["features_b"]
        out: dict[str, float] = {}
        for n in feature_names:
            op, k = n.split("::", 1)
            av = float(a.get(k, 0.0))
            bv = float(b.get(k, 0.0))
            out[n] = (av - bv) if op == "diff" else abs(av - bv)
        return out

    def sig(z: float) -> float:
        if z >= 0:
            ez = math.exp(-z)
            return 1.0 / (1.0 + ez)
        ez = math.exp(z)
        return ez / (1.0 + ez)

    w = {k: 0.0 for k in feature_names}
    b = 0.0
    rng = random.Random(0)
    train = list(rows)
    for _ in range(epochs):
        rng.shuffle(train)
        for r in train:
            x = feats(r)
            y = float(r.get("a_preferred", 0.0))
            z = b + sum(w[k] * x[k] for k in feature_names)
            g = sig(z) - y
            for k in feature_names:
                w[k] -= lr * (g * x[k] + 1e-4 * w[k])
            b -= lr * g

    return {
        "model_type": "logistic_regression",
        "feature_names": feature_names,
        "weights": {k: float(v) for k, v in w.items()},
        "intercept": float(b),
    }


def _pair_acc_two_stage(rows: list[dict[str, Any]], base_model: dict[str, Any], tie_model: dict[str, Any], margin: float) -> float:
    if not rows:
        return 0.0

    def tie_prob(row: dict[str, Any]) -> float:
        z = float(tie_model.get("intercept", 0.0))
        a, b = row["features_a"], row["features_b"]
        for n, w in tie_model.get("weights", {}).items():
            op, k = n.split("::", 1)
            av = float(a.get(k, 0.0))
            bv = float(b.get(k, 0.0))
            x = (av - bv) if op == "diff" else abs(av - bv)
            z += float(w) * x
        if z >= 0:
            ez = math.exp(-z)
            return 1.0 / (1.0 + ez)
        ez = math.exp(z)
        return ez / (1.0 + ez)

    ok = 0
    for r in rows:
        sa = _score_linear(base_model, r["features_a"])
        sb = _score_linear(base_model, r["features_b"])
        pred = 1 if sa >= sb else 0
        if abs(sa - sb) <= margin:
            oriented = r if pred == 1 else {**r, "features_a": r["features_b"], "features_b": r["features_a"], "a_preferred": 1 - int(r.get("a_preferred", 0))}
            keep_top = 1 if tie_prob(oriented) >= 0.5 else 0
            pred = pred if keep_top == 1 else (1 - pred)
        ok += int(pred == int(r.get("a_preferred", 0)))
    return ok / len(rows)


def _controller_eval(seed: int, dataset: str, subset_size: int, budget: int, model_paths: dict[str, Path], include_reference: bool, include_oracle: bool) -> tuple[list[dict[str, Any]], float]:
    rng = random.Random(seed)
    examples = load_pilot_examples(dataset, subset_size, seed)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)

    baseline_specs = build_frontier_strategies(
        gen_factory,
        budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        bt_pairwise_model_path=str(model_paths["baseline"]),
    )
    strategies: dict[str, Any] = {
        "adaptive_min_expand_1": baseline_specs["adaptive_min_expand_1"],
        "adaptive_bt_pairwise": baseline_specs["adaptive_bt_pairwise"],
        "adaptive_bt_pairwise_tie_aware_davidson": AdaptiveController(
            gen_factory(), TieAwareBTBranchScorer(model_paths["davidson"], max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_tie_aware_davidson",
        ),
        "adaptive_bt_pairwise_tie_aware_raokupper": AdaptiveController(
            gen_factory(), TieAwareBTBranchScorer(model_paths["raokupper"], max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_tie_aware_raokupper",
        ),
    }
    if include_reference and "oversample" in model_paths:
        strategies["adaptive_bt_pairwise_hard_oversample"] = AdaptiveController(
            gen_factory(), LearnedBTBranchScorer(model_paths["oversample"], max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_hard_oversample",
        )
    if include_reference and "two_stage" in model_paths:
        strategies["adaptive_bt_pairwise_two_stage"] = AdaptiveController(
            gen_factory(), TwoStageNearTieBTBranchScorer(model_paths["two_stage"], max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_two_stage",
        )

    metrics, rows = evaluate_strategies_on_examples(examples, strategies)
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_ex.setdefault(str(r["example_id"]), []).append(r)
    oracle_acc = sum(1 for rr in by_ex.values() if any(bool(x["is_correct"]) for x in rr)) / max(1, len(by_ex))

    out: list[dict[str, Any]] = []
    for method, m in metrics.items():
        out.append(
            {
                "seed": seed,
                "method": method,
                "accuracy": float(m["accuracy"]),
                "avg_actions": float(m["avg_actions"]),
                "gap_to_oracle": float(oracle_acc - float(m["accuracy"])),
            }
        )
    if include_oracle:
        out.append({"seed": seed, "method": "oracle_reference", "accuracy": float(oracle_acc), "avg_actions": 0.0, "gap_to_oracle": 0.0})
    return out, oracle_acc


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    method_rows: list[dict[str, Any]] = []
    near_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    sweep_rows: list[dict[str, Any]] = []

    sweep_seed = seeds[0] if seeds else 0

    for seed in seeds:
        seed_dir = run_dir / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        ranking_path = seed_dir / "branch_scorer_v3_dataset.jsonl"
        pairwise_path = seed_dir / "pairwise_dataset.jsonl"
        baseline_path = seed_dir / "model_bt_baseline.json"
        davidson_path = seed_dir / "model_bt_davidson_tie_or_uncertain.json"
        raokupper_path = seed_dir / "model_bt_raokupper_tie_or_uncertain.json"

        _run([sys.executable, str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"), "--output-dir", str(seed_dir), "--episodes", str(args.ranking_episodes), "--budget", str(args.budget), "--seed", str(seed)])
        _run([sys.executable, str(REPO_ROOT / "scripts/build_bt_pairwise_branch_dataset.py"), "--ranking-dataset", str(ranking_path), "--output", str(pairwise_path)])

        _run([sys.executable, str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"), "--dataset", str(pairwise_path), "--output", str(baseline_path), "--seed", str(seed), "--objective", "bt"])
        _run([sys.executable, str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"), "--dataset", str(pairwise_path), "--output", str(davidson_path), "--seed", str(seed), "--objective", "davidson", "--tie-supervision", "tie_or_uncertain"])
        _run([sys.executable, str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"), "--dataset", str(pairwise_path), "--output", str(raokupper_path), "--seed", str(seed), "--objective", "raokupper", "--tie-supervision", "tie_or_uncertain"])

        model_paths: dict[str, Path] = {"baseline": baseline_path, "davidson": davidson_path, "raokupper": raokupper_path}

        pair_rows = _load_jsonl(pairwise_path)
        base_model = _load_json(baseline_path)
        dav_model = _load_json(davidson_path)
        rao_model = _load_json(raokupper_path)

        near_keys = {
            _pair_key(r)
            for r in pair_rows
            if abs(_score_linear(base_model, r["features_a"]) - _score_linear(base_model, r["features_b"])) <= args.near_tie_margin
        }
        test_rows = [r for r in pair_rows if r.get("split") == "test"]
        near_slice = [r for r in test_rows if int(r.get("tie_or_uncertain", 0)) == 1 or _pair_key(r) in near_keys]

        near_rows.extend(
            [
                {"seed": seed, "method": "proxy_bt_baseline", "pair_acc_test": _pair_acc(test_rows, base_model), "pair_acc_near_tie_slice": _pair_acc(near_slice, base_model), "n_test": len(test_rows), "n_near": len(near_slice)},
                {"seed": seed, "method": "tie_aware_davidson", "pair_acc_test": _pair_acc(test_rows, dav_model), "pair_acc_near_tie_slice": _pair_acc(near_slice, dav_model), "n_test": len(test_rows), "n_near": len(near_slice)},
                {"seed": seed, "method": "tie_aware_raokupper", "pair_acc_test": _pair_acc(test_rows, rao_model), "pair_acc_near_tie_slice": _pair_acc(near_slice, rao_model), "n_test": len(test_rows), "n_near": len(near_slice)},
            ]
        )

        if args.include_reference_branches:
            oversampled_path = seed_dir / "model_bt_hard_oversample.json"
            oversampled_dataset = seed_dir / "pairwise_hard_oversample.jsonl"
            oversampled_rows: list[dict[str, Any]] = []
            for r in pair_rows:
                oversampled_rows.append(r)
                if r.get("split") == "train" and _pair_key(r) in near_keys:
                    for _ in range(max(0, args.hard_oversample_factor - 1)):
                        oversampled_rows.append(dict(r))
            with oversampled_dataset.open("w", encoding="utf-8") as f:
                for r in oversampled_rows:
                    f.write(json.dumps(r) + "\n")
            _run([sys.executable, str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"), "--dataset", str(oversampled_dataset), "--output", str(oversampled_path), "--seed", str(seed), "--objective", "bt"])
            over_model = _load_json(oversampled_path)
            near_rows.append({"seed": seed, "method": "hard_pair_oversample", "pair_acc_test": _pair_acc(test_rows, over_model), "pair_acc_near_tie_slice": _pair_acc(near_slice, over_model), "n_test": len(test_rows), "n_near": len(near_slice)})
            model_paths["oversample"] = oversampled_path

            tie_rows = [r for r in pair_rows if r.get("split") == "train" and _pair_key(r) in near_keys]
            tie_model = _fit_two_stage_tie_model(tie_rows)
            two_stage_path = seed_dir / "model_two_stage_reference.json"
            two_stage_payload = {"base_model": base_model, "tie_break_model": tie_model, "near_tie_margin": float(args.near_tie_margin)}
            _write_json(two_stage_path, two_stage_payload)
            near_rows.append({"seed": seed, "method": "two_stage_tie_breaker", "pair_acc_test": _pair_acc_two_stage(test_rows, base_model, tie_model, args.near_tie_margin), "pair_acc_near_tie_slice": _pair_acc_two_stage(near_slice, base_model, tie_model, args.near_tie_margin), "n_test": len(test_rows), "n_near": len(near_slice)})
            model_paths["two_stage"] = two_stage_path

        # Regime diagnostics for "overall up, near-tie not up"
        def pred(model: dict[str, Any], row: dict[str, Any]) -> int:
            d = _score_linear(model, row["features_a"]) - _score_linear(model, row["features_b"])
            p_a, p_b, _ = _pair_probs(model, d)
            return 1 if p_a >= p_b else 0

        changed = 0
        changed_correct_gain = 0
        changed_in_near = 0
        for r in test_rows:
            pb = pred(base_model, r)
            pr = pred(rao_model, r)
            if pb != pr:
                changed += 1
                y = int(r.get("a_preferred", 0))
                changed_correct_gain += int(pr == y) - int(pb == y)
                if int(r.get("tie_or_uncertain", 0)) == 1 or _pair_key(r) in near_keys:
                    changed_in_near += 1

        regime_rows.append({
            "seed": seed,
            "slice": "changed_predictions",
            "count": changed,
            "fraction_of_test": changed / max(1, len(test_rows)),
            "net_accuracy_gain_on_changed": changed_correct_gain / max(1, changed),
            "near_tie_share_of_changed": changed_in_near / max(1, changed),
        })

        # confidence / budget / verify / stalled / depth band diagnostics
        bands = [
            ("pair_confidence", "low", lambda r: float(r.get("pair_confidence", 0.0)) < 0.2),
            ("pair_confidence", "mid", lambda r: 0.2 <= float(r.get("pair_confidence", 0.0)) < 0.5),
            ("pair_confidence", "high", lambda r: float(r.get("pair_confidence", 0.0)) >= 0.5),
            ("remaining_budget", "low", lambda r: float(r.get("remaining_budget", 0.0)) <= 3),
            ("remaining_budget", "mid", lambda r: 4 <= float(r.get("remaining_budget", 0.0)) <= 6),
            ("remaining_budget", "high", lambda r: float(r.get("remaining_budget", 0.0)) >= 7),
            ("verify_count_max", "low", lambda r: max(float(r["features_a"].get("verify_count", 0.0)), float(r["features_b"].get("verify_count", 0.0))) <= 0),
            ("verify_count_max", "high", lambda r: max(float(r["features_a"].get("verify_count", 0.0)), float(r["features_b"].get("verify_count", 0.0))) >= 1),
            ("stalled_steps_max", "low", lambda r: max(float(r["features_a"].get("stalled_steps", 0.0)), float(r["features_b"].get("stalled_steps", 0.0))) <= 0),
            ("stalled_steps_max", "high", lambda r: max(float(r["features_a"].get("stalled_steps", 0.0)), float(r["features_b"].get("stalled_steps", 0.0))) >= 1),
            ("depth_max", "shallow", lambda r: max(float(r["features_a"].get("node_3_distance_to_terminal_est", 0.0)), float(r["features_b"].get("node_3_distance_to_terminal_est", 0.0))) <= 2.0),
            ("depth_max", "deeper", lambda r: max(float(r["features_a"].get("node_3_distance_to_terminal_est", 0.0)), float(r["features_b"].get("node_3_distance_to_terminal_est", 0.0))) > 2.0),
        ]
        for metric, band, fn in bands:
            subset = [r for r in test_rows if fn(r)]
            if not subset:
                continue
            regime_rows.append(
                {
                    "seed": seed,
                    "slice": f"{metric}:{band}",
                    "count": len(subset),
                    "baseline_pair_acc": _pair_acc(subset, base_model),
                    "raokupper_pair_acc": _pair_acc(subset, rao_model),
                    "delta_raokupper_minus_baseline": _pair_acc(subset, rao_model) - _pair_acc(subset, base_model),
                }
            )

        seed_metrics, _ = _controller_eval(
            seed,
            args.dataset,
            args.subset_size,
            args.budget,
            model_paths,
            include_reference=args.include_reference_branches,
            include_oracle=args.include_oracle_reference,
        )
        method_rows.extend(seed_metrics)

        if seed == sweep_seed:
            sweep_settings = [
                ("none", 0.0),
                ("tie_or_uncertain", 0.0),
                ("strict_tie", 0.0),
                ("tie_or_uncertain", 0.1),
                ("tie_or_uncertain", 0.2),
            ]
            for tie_supervision, min_conf in sweep_settings:
                sweep_model = seed_dir / f"sweep_raokupper_{tie_supervision}_minconf{str(min_conf).replace('.', 'p')}.json"
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
                    "--dataset",
                    str(pairwise_path),
                    "--output",
                    str(sweep_model),
                    "--seed",
                    str(seed),
                    "--objective",
                    "raokupper",
                    "--tie-supervision",
                    tie_supervision,
                ]
                if min_conf > 0:
                    cmd.extend(["--min-confidence", str(min_conf), "--weighting", "confidence"])
                _run(cmd)
                sm = _load_json(sweep_model)

                seed_eval, _ = _controller_eval(
                    seed,
                    args.dataset,
                    args.subset_size,
                    args.budget,
                    {"baseline": baseline_path, "davidson": davidson_path, "raokupper": sweep_model},
                    include_reference=False,
                    include_oracle=False,
                )
                ra = next(r for r in seed_eval if r["method"] == "adaptive_bt_pairwise_tie_aware_raokupper")
                sweep_rows.append(
                    {
                        "seed": seed,
                        "objective": "raokupper",
                        "tie_supervision": tie_supervision,
                        "min_confidence": min_conf,
                        "weighting": "confidence" if min_conf > 0 else "none",
                        "controller_accuracy": float(ra["accuracy"]),
                        "pair_acc_test": float(sm.get("test_pair_accuracy", 0.0)),
                        "near_tie_pair_acc": _pair_acc(near_slice, sm),
                        "tie_parameter_value": float(sm.get("tie_parameter_value", 0.0)),
                        "n_train_used": int(sm.get("n_train_used", 0)),
                    }
                )

    _write_csv(run_dir / "method_metrics_by_seed.csv", method_rows)
    _write_csv(run_dir / "near_tie_slice_by_seed.csv", near_rows)
    _write_csv(run_dir / "regime_slice_summary.csv", regime_rows)
    _write_csv(run_dir / "tie_aware_sweep_results.csv", sweep_rows)

    # Stability summary
    by_method: dict[str, list[float]] = {}
    for r in method_rows:
        by_method.setdefault(r["method"], []).append(float(r["accuracy"]))

    baseline = by_method.get("adaptive_bt_pairwise", [])
    stability_rows: list[dict[str, Any]] = []
    for method, vals in sorted(by_method.items()):
        mean_v = sum(vals) / max(1, len(vals))
        std_v = statistics.stdev(vals) if len(vals) > 1 else 0.0
        wins = 0
        losses = 0
        ties = 0
        if method != "adaptive_bt_pairwise" and baseline and len(vals) == len(baseline):
            for v, b in zip(vals, baseline):
                if v > b:
                    wins += 1
                elif v < b:
                    losses += 1
                else:
                    ties += 1
        stability_rows.append(
            {
                "method": method,
                "mean_accuracy": mean_v,
                "std_accuracy": std_v,
                "n_seeds": len(vals),
                "wins_vs_baseline": wins,
                "losses_vs_baseline": losses,
                "ties_vs_baseline": ties,
                "mean_delta_vs_baseline": (sum(v - b for v, b in zip(vals, baseline)) / len(vals)) if (baseline and len(vals) == len(baseline)) else 0.0,
            }
        )

    _write_csv(run_dir / "stability_summary.csv", stability_rows)

    # Interpretation
    rk = next((r for r in stability_rows if r["method"] == "adaptive_bt_pairwise_tie_aware_raokupper"), None)
    dv = next((r for r in stability_rows if r["method"] == "adaptive_bt_pairwise_tie_aware_davidson"), None)
    best_sweep = max(sweep_rows, key=lambda r: (float(r["controller_accuracy"]), float(r["near_tie_pair_acc"]))) if sweep_rows else None

    near_by_method: dict[str, list[float]] = {}
    for r in near_rows:
        near_by_method.setdefault(str(r["method"]), []).append(float(r["pair_acc_near_tie_slice"]))
    near_base_mean = sum(near_by_method.get("proxy_bt_baseline", [0.0])) / max(1, len(near_by_method.get("proxy_bt_baseline", [])))
    near_rk_mean = sum(near_by_method.get("tie_aware_raokupper", [0.0])) / max(1, len(near_by_method.get("tie_aware_raokupper", [])))

    changed_rows = [r for r in regime_rows if r.get("slice") == "changed_predictions"]
    mean_changed_fraction = sum(float(r.get("fraction_of_test", 0.0)) for r in changed_rows) / max(1, len(changed_rows))
    mean_changed_near_share = sum(float(r.get("near_tie_share_of_changed", 0.0)) for r in changed_rows) / max(1, len(changed_rows))

    interp = [
        f"# Tie-aware BT stability audit ({run_id})",
        "",
        "## Core answers",
        f"- Was Rao-Kupper gain robust across seeds? **{'Mostly yes' if rk and rk['wins_vs_baseline'] > rk['losses_vs_baseline'] else 'Likely fragile/noisy'}** (wins/losses={rk['wins_vs_baseline'] if rk else 0}/{rk['losses_vs_baseline'] if rk else 0}, mean delta={rk['mean_delta_vs_baseline'] if rk else 0:.4f}).",
        f"- Best tie-aware variant overall: **{'Rao-Kupper' if (rk and dv and rk['mean_accuracy'] >= dv['mean_accuracy']) else 'Davidson or inconclusive'}**.",
        f"- Best tie supervision mode (sweep): **{best_sweep['tie_supervision'] if best_sweep else 'n/a'}** with min_conf={best_sweep['min_confidence'] if best_sweep else 0}." if best_sweep else "- Best tie supervision mode (sweep): n/a.",
        f"- Near-tie slice improved? **{'No' if near_rk_mean <= near_base_mean else 'Yes'}** (mean near-tie acc baseline={near_base_mean:.4f}, Rao-Kupper={near_rk_mean:.4f}).",
        f"- Promote tie-aware BT to default? **No (keep proxy BT default), keep Rao-Kupper as experimental branch**.",
        "",
        "## Why overall can improve while hardest near-tie does not",
        f"- Rao-Kupper changed about **{mean_changed_fraction:.3f}** of test pair decisions on average.",
        (
            f"- About **{mean_changed_near_share:.3f}** of changed decisions were in the near-tie slice, so most decision shifts are near-tie concentrated."
            if mean_changed_near_share >= 0.60
            else f"- About **{mean_changed_near_share:.3f}** of changed decisions were in the near-tie slice, so many shifts occur outside the hardest near-ties."
        ),
        "- The mixed seed-wise deltas suggest gains come from selective calibration/regularization regimes, not a universal fix for extreme near-tie errors.",
        "",
        "## Conservatism",
        "- Tie supervision here remains proxy-derived (`tie_or_uncertain` / strict utility ties), not oracle tie labels.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "dataset": args.dataset,
        "seeds": seeds,
        "subset_size": args.subset_size,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "near_tie_margin": args.near_tie_margin,
        "include_reference_branches": bool(args.include_reference_branches),
        "artifacts": {
            "method_metrics_by_seed": str(run_dir / "method_metrics_by_seed.csv"),
            "stability_summary": str(run_dir / "stability_summary.csv"),
            "tie_aware_sweep_results": str(run_dir / "tie_aware_sweep_results.csv"),
            "near_tie_slice_by_seed": str(run_dir / "near_tie_slice_by_seed.csv"),
            "regime_slice_summary": str(run_dir / "regime_slice_summary.csv"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
    }
    _write_json(run_dir / "run_manifest.json", manifest)

    print(json.dumps({"run_dir": str(run_dir), "n_seeds": len(seeds)}, indent=2))


if __name__ == "__main__":
    main()
