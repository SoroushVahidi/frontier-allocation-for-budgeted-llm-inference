#!/usr/bin/env python3
"""Bounded regime-gated proxyBT/Rao-Kupper hybrid audit (new-paper track)."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.controllers import AdaptiveController
from experiments.frontier_matrix_core import build_frontier_strategies, evaluate_strategies_on_examples, generator_factory_for_mode, load_pilot_examples
from experiments.scoring import RegimeGatedHybridBTBranchScorer, TieAwareBTBranchScorer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded tie-aware hybrid gating audit")
    p.add_argument("--output-root", default="outputs/new_paper/tie_aware_hybrid_gating")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--seeds", default="71,72,73,74")
    p.add_argument("--subset-size", type=int, default=18)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=130)
    p.add_argument("--near-tie-margin", type=float, default=0.06)
    p.add_argument("--include-davidson", action="store_true")
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
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _score_linear(model: dict[str, Any], features: dict[str, float]) -> float:
    score = float(model.get("intercept", 0.0))
    for n, w in model.get("weights", {}).items():
        score += float(w) * float(features.get(n, 0.0))
    return score


def _pair_probs(model: dict[str, Any], delta: float) -> tuple[float, float, float]:
    objective = str(model.get("training_objective", "bt")).lower()
    tie_raw = float(model.get("tie_raw_parameter", -2.0))

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

    p = 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, delta))))
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


def _controller_eval(
    seed: int,
    dataset: str,
    subset_size: int,
    budget: int,
    baseline_path: Path,
    raokupper_path: Path,
    gate_rules: list[dict[str, Any]],
    davidson_path: Path | None,
    include_oracle: bool,
) -> tuple[list[dict[str, Any]], float]:
    import random

    rng = random.Random(seed)
    examples = load_pilot_examples(dataset, subset_size, seed)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)

    baseline_specs = build_frontier_strategies(
        gen_factory,
        budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        bt_pairwise_model_path=str(baseline_path),
    )

    strategies: dict[str, Any] = {
        "adaptive_bt_pairwise": baseline_specs["adaptive_bt_pairwise"],
        "adaptive_bt_pairwise_tie_aware_raokupper": AdaptiveController(
            gen_factory(), TieAwareBTBranchScorer(raokupper_path, max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_tie_aware_raokupper",
        ),
    }
    if davidson_path is not None:
        strategies["adaptive_bt_pairwise_tie_aware_davidson"] = AdaptiveController(
            gen_factory(), TieAwareBTBranchScorer(davidson_path, max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_tie_aware_davidson",
        )

    for rule in gate_rules:
        method = str(rule["method"])
        strategies[method] = AdaptiveController(
            gen_factory(),
            RegimeGatedHybridBTBranchScorer(
                baseline_model_path=baseline_path,
                raokupper_model_path=raokupper_path,
                max_actions_per_problem=budget,
                gate_config=dict(rule["gate_config"]),
            ),
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            method_name=method,
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

    gate_rules = [
        {
            "method": "adaptive_bt_hybrid_rk_near_tie_only",
            "label": "extreme near-tie only",
            "gate_config": {"max_gap": 0.03, "min_tie_prob": 0.08},
        },
        {
            "method": "adaptive_bt_hybrid_rk_medium_ambiguity",
            "label": "medium ambiguity band",
            "gate_config": {"min_gap": 0.03, "max_gap": 0.12, "min_tie_prob": 0.03, "max_tie_prob": 0.20},
        },
        {
            "method": "adaptive_bt_hybrid_rk_high_tieprob",
            "label": "tie probability high",
            "gate_config": {"max_gap": 0.16, "min_tie_prob": 0.10},
        },
        {
            "method": "adaptive_bt_hybrid_rk_uncertain_not_degenerate",
            "label": "uncertain band excluding degenerate",
            "gate_config": {"min_gap": 0.01, "max_gap": 0.10, "min_tie_prob": 0.04, "max_tie_prob": 0.18},
        },
        {
            "method": "adaptive_bt_hybrid_rk_non_low_budget",
            "label": "non-low budget uncertainty",
            "gate_config": {"min_gap": 0.03, "max_gap": 0.14, "min_tie_prob": 0.04, "min_remaining_budget": 4},
        },
    ]

    method_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    gating_rows: list[dict[str, Any]] = []

    for seed in seeds:
        seed_dir = run_dir / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        ranking_path = seed_dir / "branch_scorer_v3_dataset.jsonl"
        pairwise_path = seed_dir / "pairwise_dataset.jsonl"
        baseline_path = seed_dir / "model_bt_baseline.json"
        raokupper_path = seed_dir / "model_bt_raokupper.json"
        davidson_path = seed_dir / "model_bt_davidson.json"

        _run([sys.executable, str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"), "--output-dir", str(seed_dir), "--episodes", str(args.ranking_episodes), "--budget", str(args.budget), "--seed", str(seed)])
        _run([sys.executable, str(REPO_ROOT / "scripts/build_bt_pairwise_branch_dataset.py"), "--ranking-dataset", str(ranking_path), "--output", str(pairwise_path)])
        _run([sys.executable, str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"), "--dataset", str(pairwise_path), "--output", str(baseline_path), "--seed", str(seed), "--objective", "bt"])
        _run([sys.executable, str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"), "--dataset", str(pairwise_path), "--output", str(raokupper_path), "--seed", str(seed), "--objective", "raokupper", "--tie-supervision", "tie_or_uncertain"])
        if args.include_davidson:
            _run([sys.executable, str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"), "--dataset", str(pairwise_path), "--output", str(davidson_path), "--seed", str(seed), "--objective", "davidson", "--tie-supervision", "tie_or_uncertain"])

        pair_rows = _load_jsonl(pairwise_path)
        base_model = _load_json(baseline_path)
        rk_model = _load_json(raokupper_path)

        test_rows = [r for r in pair_rows if r.get("split") == "test"]
        near_keys = {
            _pair_key(r)
            for r in pair_rows
            if abs(_score_linear(base_model, r["features_a"]) - _score_linear(base_model, r["features_b"])) <= args.near_tie_margin
        }

        def _slice(metric: str, band: str, fn: Any) -> None:
            subset = [r for r in test_rows if fn(r)]
            if not subset:
                return
            base_acc = _pair_acc(subset, base_model)
            rk_acc = _pair_acc(subset, rk_model)
            regime_rows.append(
                {
                    "seed": seed,
                    "slice": f"{metric}:{band}",
                    "count": len(subset),
                    "baseline_pair_acc": base_acc,
                    "raokupper_pair_acc": rk_acc,
                    "delta_raokupper_minus_baseline": rk_acc - base_acc,
                }
            )

        _slice("near_tie", "extreme", lambda r: abs(_score_linear(base_model, r["features_a"]) - _score_linear(base_model, r["features_b"])) <= 0.03)
        _slice("near_tie", "medium", lambda r: 0.03 < abs(_score_linear(base_model, r["features_a"]) - _score_linear(base_model, r["features_b"])) <= 0.12)
        _slice("near_tie", "broad", lambda r: _pair_key(r) in near_keys)
        _slice("pair_confidence", "low", lambda r: float(r.get("pair_confidence", 0.0)) < 0.2)
        _slice("pair_confidence", "mid", lambda r: 0.2 <= float(r.get("pair_confidence", 0.0)) < 0.5)
        _slice("pair_confidence", "high", lambda r: float(r.get("pair_confidence", 0.0)) >= 0.5)
        _slice("remaining_budget", "low", lambda r: float(r.get("remaining_budget", 0.0)) <= 3)
        _slice("remaining_budget", "non_low", lambda r: float(r.get("remaining_budget", 0.0)) >= 4)
        _slice("verify_count_max", "high", lambda r: max(float(r["features_a"].get("verify_count", 0.0)), float(r["features_b"].get("verify_count", 0.0))) >= 1.0)
        _slice("stalled_steps_max", "high", lambda r: max(float(r["features_a"].get("stalled_steps", 0.0)), float(r["features_b"].get("stalled_steps", 0.0))) >= 1.0)

        controller_rows, _ = _controller_eval(
            seed=seed,
            dataset=args.dataset,
            subset_size=args.subset_size,
            budget=args.budget,
            baseline_path=baseline_path,
            raokupper_path=raokupper_path,
            gate_rules=gate_rules,
            davidson_path=davidson_path if args.include_davidson else None,
            include_oracle=args.include_oracle_reference,
        )
        method_rows.extend(controller_rows)

        by_method = {str(r["method"]): r for r in controller_rows}
        base_acc = float(by_method["adaptive_bt_pairwise"]["accuracy"])
        rk_acc = float(by_method["adaptive_bt_pairwise_tie_aware_raokupper"]["accuracy"])
        for rule in gate_rules:
            method = str(rule["method"])
            if method not in by_method:
                continue
            acc = float(by_method[method]["accuracy"])
            gating_rows.append(
                {
                    "seed": seed,
                    "method": method,
                    "rule_label": rule["label"],
                    "accuracy": acc,
                    "delta_vs_proxy_bt": acc - base_acc,
                    "delta_vs_global_raokupper": acc - rk_acc,
                    "gate_config": json.dumps(rule["gate_config"], sort_keys=True),
                }
            )

    _write_csv(run_dir / "method_metrics_by_seed.csv", method_rows)
    _write_csv(run_dir / "regime_slice_summary.csv", regime_rows)
    _write_csv(run_dir / "gating_sweep_results.csv", gating_rows)

    # Aggregate method metrics.
    metric_map: dict[str, list[float]] = {}
    for r in method_rows:
        metric_map.setdefault(str(r["method"]), []).append(float(r["accuracy"]))

    baseline_vals = metric_map.get("adaptive_bt_pairwise", [])
    global_rk_vals = metric_map.get("adaptive_bt_pairwise_tie_aware_raokupper", [])

    method_summary: list[dict[str, Any]] = []
    for method, vals in sorted(metric_map.items()):
        mean_acc = sum(vals) / max(1, len(vals))
        std_acc = statistics.stdev(vals) if len(vals) > 1 else 0.0
        wins_vs_base = sum(1 for v, b in zip(vals, baseline_vals) if v > b) if len(vals) == len(baseline_vals) else 0
        wins_vs_rk = sum(1 for v, rk in zip(vals, global_rk_vals) if v > rk) if len(vals) == len(global_rk_vals) else 0
        method_summary.append(
            {
                "method": method,
                "mean_accuracy": mean_acc,
                "std_accuracy": std_acc,
                "n_seeds": len(vals),
                "mean_delta_vs_proxy_bt": (sum(v - b for v, b in zip(vals, baseline_vals)) / len(vals)) if (baseline_vals and len(vals) == len(baseline_vals)) else 0.0,
                "mean_delta_vs_global_raokupper": (sum(v - rk for v, rk in zip(vals, global_rk_vals)) / len(vals)) if (global_rk_vals and len(vals) == len(global_rk_vals)) else 0.0,
                "wins_vs_proxy_bt": wins_vs_base,
                "wins_vs_global_raokupper": wins_vs_rk,
            }
        )

    _write_csv(run_dir / "method_metrics.csv", method_summary)

    # Sweep aggregate.
    sweep_group: dict[str, list[dict[str, Any]]] = {}
    for row in gating_rows:
        sweep_group.setdefault(str(row["method"]), []).append(row)

    gating_agg: list[dict[str, Any]] = []
    for method, rows in sorted(sweep_group.items()):
        gating_agg.append(
            {
                "method": method,
                "rule_label": rows[0]["rule_label"],
                "mean_accuracy": sum(float(r["accuracy"]) for r in rows) / len(rows),
                "std_accuracy": statistics.stdev([float(r["accuracy"]) for r in rows]) if len(rows) > 1 else 0.0,
                "mean_delta_vs_proxy_bt": sum(float(r["delta_vs_proxy_bt"]) for r in rows) / len(rows),
                "mean_delta_vs_global_raokupper": sum(float(r["delta_vs_global_raokupper"]) for r in rows) / len(rows),
                "wins_vs_proxy_bt": sum(1 for r in rows if float(r["delta_vs_proxy_bt"]) > 0.0),
                "wins_vs_global_raokupper": sum(1 for r in rows if float(r["delta_vs_global_raokupper"]) > 0.0),
                "n_seeds": len(rows),
                "gate_config": rows[0]["gate_config"],
            }
        )
    _write_csv(run_dir / "gating_sweep_aggregate.csv", gating_agg)

    best_rule = max(gating_agg, key=lambda r: (float(r["mean_accuracy"]), float(r["mean_delta_vs_proxy_bt"]))) if gating_agg else None
    proxy = next((r for r in method_summary if r["method"] == "adaptive_bt_pairwise"), None)
    rk = next((r for r in method_summary if r["method"] == "adaptive_bt_pairwise_tie_aware_raokupper"), None)

    regime_by_slice: dict[str, list[float]] = {}
    for row in regime_rows:
        regime_by_slice.setdefault(str(row["slice"]), []).append(float(row["delta_raokupper_minus_baseline"]))
    regime_means = {k: sum(v) / len(v) for k, v in regime_by_slice.items()}
    helpful = sorted(regime_means.items(), key=lambda x: x[1], reverse=True)

    interp_lines = [
        f"# Tie-aware hybrid gating audit ({run_id})",
        "",
        "## Direct answers",
        f"- Does a regime-gated hybrid beat plain proxy BT? **{'Yes' if best_rule and float(best_rule['mean_delta_vs_proxy_bt']) > 0 else 'No'}**.",
        f"- Does it beat global Rao-Kupper? **{'Yes' if best_rule and float(best_rule['mean_delta_vs_global_raokupper']) > 0 else 'No'}**.",
        f"- Best hybrid rule: **{best_rule['rule_label']}** (`{best_rule['method']}`), mean accuracy={float(best_rule['mean_accuracy']):.4f}, delta vs proxy={float(best_rule['mean_delta_vs_proxy_bt']):+.4f}, delta vs global RK={float(best_rule['mean_delta_vs_global_raokupper']):+.4f}." if best_rule else "- Best hybrid rule: n/a.",
        f"- Is gain more stable than global Rao-Kupper? **{'Yes' if (best_rule and rk and float(best_rule['std_accuracy']) <= float(rk['std_accuracy'])) else 'No or inconclusive'}**.",
        "- Practical recommendation: keep only if mean delta is positive and wins are consistent; otherwise treat as diagnosis-only.",
        "",
        "## Regime evidence (Rao-Kupper minus proxy BT, pairwise slices)",
    ]
    for sl, delta in helpful[:6]:
        interp_lines.append(f"- `{sl}`: mean delta={delta:+.4f}.")

    if proxy is not None and rk is not None:
        interp_lines.extend(
            [
                "",
                "## Baseline context",
                f"- Proxy BT mean accuracy={float(proxy['mean_accuracy']):.4f}, std={float(proxy['std_accuracy']):.4f}.",
                f"- Global Rao-Kupper mean accuracy={float(rk['mean_accuracy']):.4f}, std={float(rk['std_accuracy']):.4f}, mean delta vs proxy={float(rk['mean_delta_vs_proxy_bt']):+.4f}.",
            ]
        )

    (run_dir / "interpretation.md").write_text("\n".join(interp_lines) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "dataset": args.dataset,
        "seeds": seeds,
        "subset_size": args.subset_size,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "near_tie_margin": args.near_tie_margin,
        "gate_rules": gate_rules,
        "artifacts": {
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "method_metrics_by_seed": str(run_dir / "method_metrics_by_seed.csv"),
            "gating_sweep_results": str(run_dir / "gating_sweep_results.csv"),
            "gating_sweep_aggregate": str(run_dir / "gating_sweep_aggregate.csv"),
            "regime_slice_summary": str(run_dir / "regime_slice_summary.csv"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
    }
    _write_json(run_dir / "run_manifest.json", manifest)
    print(json.dumps({"run_dir": str(run_dir), "best_rule": best_rule}, indent=2))


if __name__ == "__main__":
    main()
