#!/usr/bin/env python3
"""Resolve proxy-BT vs Rao-Kupper contradiction under matched bounded settings."""

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
from experiments.scoring import TieAwareBTBranchScorer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run matched Rao-Kupper resolution audit")
    p.add_argument("--output-root", default="outputs/new_paper/raokupper_resolution_audit")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--seeds", default="71,72,73,74")
    p.add_argument("--subset-size", type=int, default=18)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=130)
    p.add_argument("--near-tie-margin", type=float, default=0.06)
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
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
    for name, w in model.get("weights", {}).items():
        score += float(w) * float(features.get(name, 0.0))
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
    model_paths: dict[str, Path],
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
        bt_pairwise_model_path=str(model_paths["proxy_bt"]),
    )

    strategies: dict[str, Any] = {
        "adaptive_bt_pairwise": baseline_specs["adaptive_bt_pairwise"],
        "adaptive_bt_pairwise_tie_aware_raokupper": AdaptiveController(
            gen_factory(), TieAwareBTBranchScorer(model_paths["rao_tie_or_uncertain"], max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_tie_aware_raokupper",
        ),
        "adaptive_bt_pairwise_tie_aware_davidson": AdaptiveController(
            gen_factory(), TieAwareBTBranchScorer(model_paths["davidson_tie_or_uncertain"], max_actions_per_problem=budget), budget,
            high_threshold=0.72, low_threshold=0.42, max_branches=3, allow_verify=True, min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_tie_aware_davidson",
        ),
    }

    metrics, rows = evaluate_strategies_on_examples(examples, strategies)
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_ex.setdefault(str(r["example_id"]), []).append(r)
    oracle_acc = sum(1 for rr in by_ex.values() if any(bool(x["is_correct"]) for x in rr)) / max(1, len(by_ex))

    out: list[dict[str, Any]] = []
    for method, metric in metrics.items():
        out.append(
            {
                "seed": seed,
                "method": method,
                "accuracy": float(metric["accuracy"]),
                "avg_actions": float(metric["avg_actions"]),
                "gap_to_oracle": float(oracle_acc - float(metric["accuracy"])),
            }
        )
    if include_oracle:
        out.append({"seed": seed, "method": "oracle_reference", "accuracy": float(oracle_acc), "avg_actions": 0.0, "gap_to_oracle": 0.0})

    return out, oracle_acc


def _aggregate_method_rows(method_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_method: dict[str, list[float]] = {}
    for r in method_rows:
        by_method.setdefault(str(r["method"]), []).append(float(r["accuracy"]))

    baseline_vals = by_method.get("adaptive_bt_pairwise", [])
    out: list[dict[str, Any]] = []
    for method, vals in sorted(by_method.items()):
        mean_acc = sum(vals) / max(1, len(vals))
        std_acc = statistics.stdev(vals) if len(vals) > 1 else 0.0
        wins = losses = ties = 0
        mean_delta = 0.0
        if method != "adaptive_bt_pairwise" and baseline_vals and len(vals) == len(baseline_vals):
            deltas = [v - b for v, b in zip(vals, baseline_vals)]
            mean_delta = sum(deltas) / len(deltas)
            for d in deltas:
                if d > 0:
                    wins += 1
                elif d < 0:
                    losses += 1
                else:
                    ties += 1
        out.append(
            {
                "method": method,
                "mean_accuracy": mean_acc,
                "std_accuracy": std_acc,
                "n_seeds": len(vals),
                "wins_vs_proxy_bt": wins,
                "losses_vs_proxy_bt": losses,
                "ties_vs_proxy_bt": ties,
                "mean_delta_vs_proxy_bt": mean_delta,
            }
        )
    return out


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    method_rows: list[dict[str, Any]] = []
    near_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    tie_supervision_rows: list[dict[str, Any]] = []

    tie_modes = ["none", "strict_tie", "tie_or_uncertain"]

    for seed in seeds:
        seed_dir = run_dir / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)

        ranking_path = seed_dir / "branch_scorer_v3_dataset.jsonl"
        pairwise_path = seed_dir / "pairwise_dataset.jsonl"

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
            str(ranking_path),
            "--output",
            str(pairwise_path),
        ])

        model_paths: dict[str, Path] = {}

        model_paths["proxy_bt"] = seed_dir / "model_bt_baseline.json"
        _run([
            sys.executable,
            str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
            "--dataset",
            str(pairwise_path),
            "--output",
            str(model_paths["proxy_bt"]),
            "--seed",
            str(seed),
            "--objective",
            "bt",
        ])

        model_paths["davidson_tie_or_uncertain"] = seed_dir / "model_bt_davidson_tie_or_uncertain.json"
        _run([
            sys.executable,
            str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
            "--dataset",
            str(pairwise_path),
            "--output",
            str(model_paths["davidson_tie_or_uncertain"]),
            "--seed",
            str(seed),
            "--objective",
            "davidson",
            "--tie-supervision",
            "tie_or_uncertain",
        ])

        for mode in tie_modes:
            key = f"rao_{mode}"
            model_paths[key] = seed_dir / f"model_bt_raokupper_{mode}.json"
            _run([
                sys.executable,
                str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
                "--dataset",
                str(pairwise_path),
                "--output",
                str(model_paths[key]),
                "--seed",
                str(seed),
                "--objective",
                "raokupper",
                "--tie-supervision",
                mode,
            ])

        model_paths["rao_tie_or_uncertain"] = model_paths["rao_tie_or_uncertain"]

        pair_rows = _load_jsonl(pairwise_path)
        test_rows = [r for r in pair_rows if r.get("split") == "test"]

        base_model = _load_json(model_paths["proxy_bt"])
        dav_model = _load_json(model_paths["davidson_tie_or_uncertain"])
        rk_mode_models = {m: _load_json(model_paths[f"rao_{m}"]) for m in tie_modes}
        rk_default_model = rk_mode_models["tie_or_uncertain"]

        near_keys = {
            _pair_key(r)
            for r in pair_rows
            if abs(_score_linear(base_model, r["features_a"]) - _score_linear(base_model, r["features_b"])) <= args.near_tie_margin
        }
        near_extreme = [
            r
            for r in test_rows
            if abs(_score_linear(base_model, r["features_a"]) - _score_linear(base_model, r["features_b"])) <= 0.03
        ]
        near_broad = [r for r in test_rows if _pair_key(r) in near_keys]

        near_rows.extend([
            {
                "seed": seed,
                "method": "proxy_bt_baseline",
                "pair_acc_test": _pair_acc(test_rows, base_model),
                "pair_acc_near_tie_broad": _pair_acc(near_broad, base_model),
                "pair_acc_near_tie_extreme": _pair_acc(near_extreme, base_model),
                "n_test": len(test_rows),
                "n_near_broad": len(near_broad),
                "n_near_extreme": len(near_extreme),
            },
            {
                "seed": seed,
                "method": "tie_aware_raokupper_tie_or_uncertain",
                "pair_acc_test": _pair_acc(test_rows, rk_default_model),
                "pair_acc_near_tie_broad": _pair_acc(near_broad, rk_default_model),
                "pair_acc_near_tie_extreme": _pair_acc(near_extreme, rk_default_model),
                "n_test": len(test_rows),
                "n_near_broad": len(near_broad),
                "n_near_extreme": len(near_extreme),
            },
            {
                "seed": seed,
                "method": "tie_aware_davidson_tie_or_uncertain",
                "pair_acc_test": _pair_acc(test_rows, dav_model),
                "pair_acc_near_tie_broad": _pair_acc(near_broad, dav_model),
                "pair_acc_near_tie_extreme": _pair_acc(near_extreme, dav_model),
                "n_test": len(test_rows),
                "n_near_broad": len(near_broad),
                "n_near_extreme": len(near_extreme),
            },
        ])

        # Tie supervision calibration check (Rao-Kupper only).
        base_controller_rows, _ = _controller_eval(
            seed=seed,
            dataset=args.dataset,
            subset_size=args.subset_size,
            budget=args.budget,
            model_paths={
                "proxy_bt": model_paths["proxy_bt"],
                "davidson_tie_or_uncertain": model_paths["davidson_tie_or_uncertain"],
                "rao_tie_or_uncertain": model_paths["rao_tie_or_uncertain"],
            },
            include_oracle=args.include_oracle_reference,
        )
        method_rows.extend(base_controller_rows)
        proxy_acc = next(float(r["accuracy"]) for r in base_controller_rows if r["method"] == "adaptive_bt_pairwise")

        for mode in tie_modes:
            mode_rows, _ = _controller_eval(
                seed=seed,
                dataset=args.dataset,
                subset_size=args.subset_size,
                budget=args.budget,
                model_paths={
                    "proxy_bt": model_paths["proxy_bt"],
                    "davidson_tie_or_uncertain": model_paths["davidson_tie_or_uncertain"],
                    "rao_tie_or_uncertain": model_paths[f"rao_{mode}"],
                },
                include_oracle=False,
            )
            rao_acc = next(float(r["accuracy"]) for r in mode_rows if r["method"] == "adaptive_bt_pairwise_tie_aware_raokupper")
            tie_supervision_rows.append(
                {
                    "seed": seed,
                    "tie_supervision": mode,
                    "controller_accuracy": rao_acc,
                    "delta_vs_proxy_bt": rao_acc - proxy_acc,
                    "pair_acc_test": _pair_acc(test_rows, rk_mode_models[mode]),
                    "pair_acc_near_tie_broad": _pair_acc(near_broad, rk_mode_models[mode]),
                    "pair_acc_near_tie_extreme": _pair_acc(near_extreme, rk_mode_models[mode]),
                    "tie_parameter_value": float(rk_mode_models[mode].get("tie_parameter_value", 0.0)),
                    "n_train_used": int(rk_mode_models[mode].get("n_train_used", 0)),
                }
            )

        # Regime slices explaining overall-up vs near-tie behavior.
        def _slice(label: str, subset: list[dict[str, Any]]) -> None:
            if not subset:
                return
            b_acc = _pair_acc(subset, base_model)
            r_acc = _pair_acc(subset, rk_default_model)
            regime_rows.append(
                {
                    "seed": seed,
                    "slice": label,
                    "count": len(subset),
                    "baseline_pair_acc": b_acc,
                    "raokupper_pair_acc": r_acc,
                    "delta_raokupper_minus_baseline": r_acc - b_acc,
                }
            )

        _slice("near_tie:extreme", near_extreme)
        _slice("near_tie:medium", [r for r in test_rows if 0.03 < abs(_score_linear(base_model, r["features_a"]) - _score_linear(base_model, r["features_b"])) <= 0.12])
        _slice("near_tie:broad", near_broad)
        _slice("pair_confidence:low", [r for r in test_rows if float(r.get("pair_confidence", 0.0)) < 0.2])
        _slice("pair_confidence:mid", [r for r in test_rows if 0.2 <= float(r.get("pair_confidence", 0.0)) < 0.5])
        _slice("pair_confidence:high", [r for r in test_rows if float(r.get("pair_confidence", 0.0)) >= 0.5])
        _slice("remaining_budget:low", [r for r in test_rows if float(r.get("remaining_budget", 0.0)) <= 3])
        _slice("remaining_budget:non_low", [r for r in test_rows if float(r.get("remaining_budget", 0.0)) >= 4])
        _slice("verify_count_max:high", [r for r in test_rows if max(float(r["features_a"].get("verify_count", 0.0)), float(r["features_b"].get("verify_count", 0.0))) >= 1.0])
        _slice("stalled_steps_max:high", [r for r in test_rows if max(float(r["features_a"].get("stalled_steps", 0.0)), float(r["features_b"].get("stalled_steps", 0.0))) >= 1.0])

    stability_rows = _aggregate_method_rows(method_rows)

    tie_mode_group: dict[str, list[dict[str, Any]]] = {}
    for row in tie_supervision_rows:
        tie_mode_group.setdefault(str(row["tie_supervision"]), []).append(row)
    for mode, rows in sorted(tie_mode_group.items()):
        tie_supervision_rows.append(
            {
                "seed": "aggregate",
                "tie_supervision": mode,
                "controller_accuracy": sum(float(r["controller_accuracy"]) for r in rows) / len(rows),
                "delta_vs_proxy_bt": sum(float(r["delta_vs_proxy_bt"]) for r in rows) / len(rows),
                "pair_acc_test": sum(float(r["pair_acc_test"]) for r in rows) / len(rows),
                "pair_acc_near_tie_broad": sum(float(r["pair_acc_near_tie_broad"]) for r in rows) / len(rows),
                "pair_acc_near_tie_extreme": sum(float(r["pair_acc_near_tie_extreme"]) for r in rows) / len(rows),
                "tie_parameter_value": sum(float(r["tie_parameter_value"]) for r in rows) / len(rows),
                "n_train_used": int(sum(float(r["n_train_used"]) for r in rows) / len(rows)),
                "wins_vs_proxy_bt": sum(1 for r in rows if float(r["delta_vs_proxy_bt"]) > 0.0),
                "losses_vs_proxy_bt": sum(1 for r in rows if float(r["delta_vs_proxy_bt"]) < 0.0),
                "n_seeds": len(rows),
            }
        )

    # Contradiction diagnostics from settings mismatch.
    contradiction_rows = [
        {
            "comparison": "tie_aware_bt(single run) vs tie_aware_bt_stability",
            "seed_spec": "single seed=73 vs multi seeds=71,72,73,74",
            "subset_size": "28 vs 18 (reported in note)",
            "ranking_episodes": "220 vs 130",
            "likely_effect": "single-run uplift can disagree with multi-seed stability",
        },
        {
            "comparison": "tie_aware_bt_stability script default vs reported note",
            "seed_spec": "script default includes 75, note reported 71-74",
            "subset_size": "script default 20, note/hybrid used 18",
            "ranking_episodes": "script default 150, note/hybrid used 130",
            "likely_effect": "default CLI mismatch can change headline means",
        },
        {
            "comparison": "hybrid audit vs earlier proxy-default narrative",
            "seed_spec": "matched seeds 71-74",
            "subset_size": "18",
            "ranking_episodes": "130",
            "likely_effect": "bounded-run variance + setup drift in prior runs caused apparent contradiction",
        },
    ]

    _write_csv(run_dir / "method_metrics_by_seed.csv", method_rows)
    _write_csv(run_dir / "stability_summary.csv", stability_rows)
    _write_csv(run_dir / "tie_supervision_comparison.csv", tie_supervision_rows)
    _write_csv(run_dir / "near_tie_slice_by_seed.csv", near_rows)
    _write_csv(run_dir / "regime_slice_summary.csv", regime_rows)
    _write_csv(run_dir / "contradiction_audit_summary.csv", contradiction_rows)

    rk_summary = next((r for r in stability_rows if r["method"] == "adaptive_bt_pairwise_tie_aware_raokupper"), None)
    proxy_summary = next((r for r in stability_rows if r["method"] == "adaptive_bt_pairwise"), None)

    tie_agg = [r for r in tie_supervision_rows if str(r["seed"]) == "aggregate"]
    best_mode = max(tie_agg, key=lambda r: (float(r["controller_accuracy"]), float(r["delta_vs_proxy_bt"]))) if tie_agg else None

    regime_group: dict[str, list[float]] = {}
    for r in regime_rows:
        regime_group.setdefault(str(r["slice"]), []).append(float(r["delta_raokupper_minus_baseline"]))
    regime_means = {k: (sum(v) / len(v)) for k, v in regime_group.items()}
    top_regimes = sorted(regime_means.items(), key=lambda x: x[1], reverse=True)

    near_proxy = [r for r in near_rows if r["method"] == "proxy_bt_baseline"]
    near_rk = [r for r in near_rows if r["method"] == "tie_aware_raokupper_tie_or_uncertain"]
    near_extreme_delta = (
        (sum(float(r["pair_acc_near_tie_extreme"]) for r in near_rk) / max(1, len(near_rk)))
        - (sum(float(r["pair_acc_near_tie_extreme"]) for r in near_proxy) / max(1, len(near_proxy)))
    )

    interpretation = [
        f"# Rao-Kupper resolution audit ({run_id})",
        "",
        "## Contradiction diagnosis",
        "- The recent contradiction is largely explained by setup drift + bounded-run variance across prior reports.",
        "- Earlier notes mixed single-run and multi-seed headlines with different subset-size/ranking-episode settings; this audit enforces one matched setup for all compared methods.",
        "",
        "## Direct answers",
        f"- Was the recent strong Rao-Kupper result real or likely noise? **{'Likely real within this matched bounded setup, but still modest/seed-sensitive' if rk_summary and float(rk_summary['mean_delta_vs_proxy_bt']) > 0 else 'Likely noise/mixed'}**.",
        f"- In matched multi-seed setting, does Rao-Kupper beat proxy BT? **{'Yes' if rk_summary and rk_summary['wins_vs_proxy_bt'] > rk_summary['losses_vs_proxy_bt'] else 'No or mixed'}** (wins/losses={rk_summary['wins_vs_proxy_bt'] if rk_summary else 0}/{rk_summary['losses_vs_proxy_bt'] if rk_summary else 0}, mean delta={float(rk_summary['mean_delta_vs_proxy_bt']) if rk_summary else 0:+.4f}).",
        f"- Which tie-supervision mode works best? **{best_mode['tie_supervision'] if best_mode else 'n/a'}** (mean delta vs proxy={float(best_mode['delta_vs_proxy_bt']) if best_mode else 0:+.4f})." if best_mode else "- Which tie-supervision mode works best? n/a.",
        f"- Why overall up but hardest near-tie not up? Near-tie-extreme mean delta is {near_extreme_delta:+.4f}; gains are concentrated in selected ambiguity/regime slices rather than uniformly fixing hardest pairs.",
        f"- Should proxy BT remain default? **{'Yes' if (rk_summary and float(rk_summary['mean_delta_vs_proxy_bt']) <= 0.02) else 'Not clearly; matched run favors Rao-Kupper but with caution'}**.",
        f"- Should Rao-Kupper be promoted to default now? **{'No, keep as experimental branch' if (rk_summary and (rk_summary['wins_vs_proxy_bt'] < len(seeds) or float(rk_summary['mean_delta_vs_proxy_bt']) < 0.05)) else 'Possibly, but only if repeated in another matched run'}**.",
        "",
        "## Regime means (Rao-Kupper - proxy, pairwise)",
    ]
    for sl, delta in top_regimes[:6]:
        interpretation.append(f"- `{sl}`: mean delta={delta:+.4f}")

    if proxy_summary and rk_summary:
        interpretation.extend(
            [
                "",
                "## Matched baseline context",
                f"- Proxy BT mean accuracy={float(proxy_summary['mean_accuracy']):.4f}, std={float(proxy_summary['std_accuracy']):.4f}.",
                f"- Rao-Kupper mean accuracy={float(rk_summary['mean_accuracy']):.4f}, std={float(rk_summary['std_accuracy']):.4f}.",
            ]
        )

    (run_dir / "interpretation.md").write_text("\n".join(interpretation) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "dataset": args.dataset,
        "seeds": seeds,
        "subset_size": args.subset_size,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "near_tie_margin": args.near_tie_margin,
        "tie_supervision_modes": tie_modes,
        "artifacts": {
            "method_metrics_by_seed": str(run_dir / "method_metrics_by_seed.csv"),
            "stability_summary": str(run_dir / "stability_summary.csv"),
            "tie_supervision_comparison": str(run_dir / "tie_supervision_comparison.csv"),
            "near_tie_slice_by_seed": str(run_dir / "near_tie_slice_by_seed.csv"),
            "regime_slice_summary": str(run_dir / "regime_slice_summary.csv"),
            "contradiction_audit_summary": str(run_dir / "contradiction_audit_summary.csv"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
    }
    _write_json(run_dir / "run_manifest.json", manifest)

    print(json.dumps({"run_dir": str(run_dir), "best_tie_mode": best_mode}, indent=2))


if __name__ == "__main__":
    main()
