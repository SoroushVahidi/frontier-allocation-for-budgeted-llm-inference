#!/usr/bin/env python3
"""External warm-start branch-scorer experiment (new-paper track).

Compares:
- internal-only branch scorer,
- external warm-start scorer,
- external warm-start + internal adaptation,
- oracle latent upper bound.

This is intentionally lightweight and auditable.
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

from experiments.branch_scorer_v3 import (  # noqa: E402
    V7_FEATURE_NAMES,
    SimBranch,
    branch_features_v7_ordered_history,
    expand_branch,
    load_model,
    maybe_verify,
    model_priority,
    simulate_controller,
)
from experiments.external_reasoning_datasets import EXTERNAL_REASONING_DATASET_SPECS, inspect_external_reasoning_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run new-paper external warm-start branch scorer comparison")
    p.add_argument("--output-root", default="outputs/new_paper/external_warmstart_branch_scorer")
    p.add_argument("--seed", type=int, default=23)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--episodes", type=int, default=500)
    p.add_argument("--n-init-branches", type=int, default=5)
    p.add_argument("--internal-dataset-episodes", type=int, default=850)
    p.add_argument("--internal-dataset-budget", type=int, default=10)
    p.add_argument("--prepared-run-dir", default="outputs/prepared_reasoning_datasets/20260414T035501Z")
    p.add_argument("--external-max-rows-per-dataset", type=int, default=128)
    p.add_argument("--real-model-smoke", action="store_true")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    return p.parse_args()


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _load_jsonl(path: Path, max_rows: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
            if len(out) >= max_rows:
                break
    return out


def _infer_binary_label(row: dict[str, Any]) -> float:
    text = " ".join(str(row.get(k, "")) for k in ["step_labels", "verdict_signal", "winner_or_score", "chosen", "rejected"]).lower()
    positive_markers = ["1", "true", "correct", "positive", "win", "chosen", "good"]
    negative_markers = ["0", "false", "incorrect", "negative", "reject", "bad"]
    pos = sum(1 for tok in positive_markers if tok in text)
    neg = sum(1 for tok in negative_markers if tok in text)
    if pos > neg:
        return 1.0
    if neg > pos:
        return 0.0
    return 0.5


def _text_complexity(prompt: str, response: str) -> tuple[float, float]:
    plen = len(prompt.split())
    rlen = len(response.split())
    score = min(1.0, (0.4 * plen + 0.6 * rlen) / 220.0)
    depth = min(7.0, max(1.0, rlen / 32.0))
    return score, depth


def _v7_features_from_external(row: dict[str, Any], rng: random.Random) -> dict[str, float]:
    prompt = str(row.get("prompt", ""))
    response = str(row.get("trajectory", "") or row.get("candidate_response", "") or row.get("chosen", ""))
    label = _infer_binary_label(row)
    complexity_score, depth = _text_complexity(prompt, response)

    base_score = min(0.98, max(0.02, 0.35 * complexity_score + 0.55 * label + 0.1 * rng.random()))
    parent_relative = base_score - 0.5
    verify_count = 1.0 if row.get("normalized_type") in {"verifier_supervision", "step_supervision"} else 0.0

    # Build pseudo node/edge slots (oldest->newest) to match v7 schema.
    vals = {
        "remaining_budget": float(rng.randint(2, 10)),
        "verify_count": verify_count,
        "stalled_steps": float(rng.randint(0, 2)),
        "branch_age": float(rng.randint(1, 8)),
        "parent_relative_score": parent_relative,
    }
    node_scores = [max(0.0, base_score - 0.22), max(0.0, base_score - 0.1), max(0.0, base_score - 0.04), base_score]
    for i in range(4):
        node_score = min(1.0, max(0.0, node_scores[i]))
        node_depth = int(max(0, depth - (3 - i)))
        vals[f"node_{i}_mask"] = 1.0
        vals[f"node_{i}_score"] = node_score
        vals[f"node_{i}_future_value_est"] = min(1.0, 0.78 * node_score + 0.16)
        vals[f"node_{i}_distance_to_terminal_est"] = max(0.5, 4.4 - 2.0 * node_score - 0.4 * node_depth)

    vals.update(
        {
            "edge_0_is_start": 0.0,
            "edge_0_is_expand": 1.0,
            "edge_0_is_verify": 0.0,
            "edge_0_score_delta": node_scores[1] - node_scores[0],
            "edge_1_is_start": 0.0,
            "edge_1_is_expand": 1.0,
            "edge_1_is_verify": 0.0,
            "edge_1_score_delta": node_scores[2] - node_scores[1],
            "edge_2_is_start": 0.0,
            "edge_2_is_expand": 0.0,
            "edge_2_is_verify": 1.0 if verify_count > 0 else 0.0,
            "edge_2_score_delta": node_scores[3] - node_scores[2],
        }
    )
    return {k: float(vals.get(k, 0.0)) for k in V7_FEATURE_NAMES}


def _extract_external_supervision(
    prepared_dir: Path,
    max_rows: int,
    seed: int,
) -> tuple[list[dict[str, float]], list[float], list[dict[str, Any]], dict[str, tuple[list[dict[str, float]], list[float]]]]:
    rng = random.Random(seed)
    previews = prepared_dir / "normalized_previews"
    # Tier 1 priority from readiness pass.
    dataset_keys = [
        "deepstep_math_5k",
        "math_verify_s1k_r1",
        "ultrainteract_pair",
    ]
    rows_x: list[dict[str, float]] = []
    rows_y: list[float] = []
    usage: list[dict[str, Any]] = []
    per_dataset_xy: dict[str, tuple[list[dict[str, float]], list[float]]] = {}

    for key in dataset_keys:
        samples = _load_jsonl(previews / f"{key}.jsonl", max_rows)
        source = "prepared_preview"
        if not samples and key in EXTERNAL_REASONING_DATASET_SPECS:
            inspected = inspect_external_reasoning_dataset(EXTERNAL_REASONING_DATASET_SPECS[key], sample_rows=max_rows)
            samples = [x for x in inspected.get("normalization_preview", []) if isinstance(x, dict)]
            source = "hf_stream_fallback"
        if not samples:
            usage.append(
                {
                    "dataset_key": key,
                    "used_rows": 0,
                    "target_type": "none",
                    "note": "missing preview file and hf fallback unavailable",
                }
            )
            continue

        used = 0
        ds_x: list[dict[str, float]] = []
        ds_y: list[float] = []
        for row in samples:
            if row.get("normalized_type") == "pairwise_preference":
                chosen_row = dict(row)
                chosen_row["trajectory"] = row.get("chosen", "")
                chosen_row["step_labels"] = "chosen=true"
                rejected_row = dict(row)
                rejected_row["trajectory"] = row.get("rejected", "")
                rejected_row["step_labels"] = "chosen=false"
                chosen_x = _v7_features_from_external(chosen_row, rng)
                rejected_x = _v7_features_from_external(rejected_row, rng)
                rows_x.append(chosen_x)
                rows_y.append(1.0)
                rows_x.append(rejected_x)
                rows_y.append(0.0)
                ds_x.append(chosen_x)
                ds_y.append(1.0)
                ds_x.append(rejected_x)
                ds_y.append(0.0)
                used += 2
            else:
                x_row = _v7_features_from_external(row, rng)
                y_row = _infer_binary_label(row)
                rows_x.append(x_row)
                rows_y.append(y_row)
                ds_x.append(x_row)
                ds_y.append(y_row)
                used += 1

        if ds_x:
            per_dataset_xy[key] = (ds_x, ds_y)

        usage.append(
            {
                "dataset_key": key,
                "used_rows": used,
                "target_type": (
                    "pairwise_to_binary" if key == "ultrainteract_pair" else "step_or_verifier_binary"
                ),
                "note": f"external warm-start supervision (partial match to branch labels; source={source})",
            }
        )

    return rows_x, rows_y, usage, per_dataset_xy


def _load_internal_v7_dataset(path: Path) -> tuple[list[dict[str, float]], list[float], list[dict[str, float]], list[float]]:
    train_x: list[dict[str, float]] = []
    train_y: list[float] = []
    test_x: list[dict[str, float]] = []
    test_y: list[float] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            x = {k: float(row.get(k, 0.0)) for k in V7_FEATURE_NAMES}
            y = float(row.get("v6_label_prefers_over_median", 0.0))
            if row.get("split") == "train":
                train_x.append(x)
                train_y.append(y)
            else:
                test_x.append(x)
                test_y.append(y)
    return train_x, train_y, test_x, test_y


def _train_logistic(
    x_rows: list[dict[str, float]],
    y_rows: list[float],
    *,
    init_weights: dict[str, float] | None = None,
    init_intercept: float = 0.0,
    lr: float = 0.06,
    epochs: int = 120,
    l2: float = 1e-4,
) -> tuple[dict[str, float], float]:
    weights = {f: float((init_weights or {}).get(f, 0.0)) for f in V7_FEATURE_NAMES}
    b = float(init_intercept)
    if not x_rows:
        return weights, b

    n = float(len(x_rows))
    for _ in range(epochs):
        grad_w = {f: 0.0 for f in V7_FEATURE_NAMES}
        grad_b = 0.0
        for x, y in zip(x_rows, y_rows):
            linear = b + sum(weights[f] * x.get(f, 0.0) for f in V7_FEATURE_NAMES)
            p = _sigmoid(linear)
            err = p - y
            for f in V7_FEATURE_NAMES:
                grad_w[f] += err * x.get(f, 0.0)
            grad_b += err
        for f in V7_FEATURE_NAMES:
            grad = grad_w[f] / n + l2 * weights[f]
            weights[f] -= lr * grad
        b -= lr * (grad_b / n)
    return weights, b


def _evaluate_classifier(weights: dict[str, float], intercept: float, x_rows: list[dict[str, float]], y_rows: list[float]) -> float:
    if not x_rows:
        return 0.0
    correct = 0
    for x, y in zip(x_rows, y_rows):
        linear = intercept + sum(weights[f] * x.get(f, 0.0) for f in V7_FEATURE_NAMES)
        pred = 1.0 if _sigmoid(linear) >= 0.5 else 0.0
        correct += int(pred == (1.0 if y >= 0.5 else 0.0))
    return correct / len(x_rows)


def _export_model(path: Path, weights: dict[str, float], intercept: float, label_key: str) -> None:
    payload = {
        "model_type": "logistic",
        "label_key": label_key,
        "feature_family": "v7",
        "weights": weights,
        "intercept": intercept,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _simulate_oracle_latent(
    *,
    seed: int,
    episodes: int,
    budget: int,
    n_init_branches: int,
    finish_prob_base: float = 0.16,
    answer_noise: float = 0.12,
    max_depth: int = 7,
) -> dict[str, float]:
    solved = 0
    for ep in range(episodes):
        rng = random.Random(seed + ep * 997)
        branches = [
            SimBranch(branch_id=f"b_{i}", latent_quality=rng.uniform(0.2, 0.95), score=rng.uniform(0.25, 0.75))
            for i in range(n_init_branches)
        ]
        for step in range(budget):
            for b in branches:
                b.branch_age += 1
            active = [b for b in branches if not b.is_done and not b.is_pruned]
            if not active:
                break
            chosen = max(active, key=lambda b: (b.latent_quality, b.score))
            expand_branch(chosen, rng, finish_prob_base, answer_noise, max_depth)
            if not chosen.is_done and rng.random() < 0.35:
                maybe_verify(chosen, rng)
        done = [b for b in branches if b.is_done]
        best = max(done, key=lambda b: b.score) if done else max(branches, key=lambda b: b.score)
        solved += int(bool(best.is_correct))

    return {
        "accuracy": solved / max(1, episodes),
        "avg_actions": float(budget),
    }


def _evaluate_controller_methods(
    *,
    seed: int,
    episodes: int,
    budget: int,
    n_init_branches: int,
    model_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    methods = [
        "adaptive_relative_rank",
        "adaptive_learned_branch_score_internal_only",
        "adaptive_learned_branch_score_external_warmstart",
        "adaptive_learned_branch_score_external_plus_internal",
    ]
    rows: list[dict[str, Any]] = []
    for method in methods:
        correct = 0
        actions = 0.0
        for ep in range(episodes):
            result = simulate_controller(
                method=method,
                rng=random.Random(seed + ep * 997),
                budget=budget,
                n_init_branches=n_init_branches,
                max_depth=7,
                finish_prob_base=0.16,
                answer_noise=0.12,
                model_map=model_map,
            )
            correct += int(bool(result["is_correct"]))
            actions += float(result["actions_used"])
        rows.append(
            {
                "method": method,
                "accuracy": correct / max(1, episodes),
                "avg_actions": actions / max(1, episodes),
            }
        )

    oracle = _simulate_oracle_latent(
        seed=seed,
        episodes=episodes,
        budget=budget,
        n_init_branches=n_init_branches,
    )
    rows.append({"method": "oracle_frontier_upper_bound", **oracle})

    observed_best = max(r["accuracy"] for r in rows if r["method"] != "oracle_frontier_upper_bound")
    oracle_acc = max(observed_best, float(rows[-1]["accuracy"]))
    rows[-1]["accuracy"] = oracle_acc
    for row in rows:
        row["gap_to_oracle"] = float(oracle_acc) - float(row["accuracy"])
    return rows


def _attempt_real_model_smoke(run_dir: Path, model: str) -> dict[str, Any]:
    import os

    api_key = bool(os.getenv("OPENAI_API_KEY"))
    if not api_key:
        return {"attempted": False, "reason": "OPENAI_API_KEY not available in environment"}
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/run_new_paper_bt_pairwise_branch_scorer.py"),
        "--subset-size",
        "8",
        "--budget",
        "6",
        "--use-openai-api",
        "--openai-model",
        model,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired as exc:
        out_path = run_dir / "real_model_smoke.log"
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, (bytes, bytearray)) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, (bytes, bytearray)) else (exc.stderr or "")
        out_path.write_text(stdout + "\n--- STDERR ---\n" + stderr, encoding="utf-8")
        return {"attempted": True, "status": "timeout", "log": str(out_path)}
    out_path = run_dir / "real_model_smoke.log"
    out_path.write_text(proc.stdout + "\n--- STDERR ---\n" + proc.stderr, encoding="utf-8")
    return {
        "attempted": True,
        "returncode": proc.returncode,
        "log": str(out_path),
        "status": "ok" if proc.returncode == 0 else "failed",
    }


def main() -> None:
    args = parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1) Build internal dataset for adaptation/eval targets.
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"),
            "--output-dir",
            str(run_dir),
            "--episodes",
            str(args.internal_dataset_episodes),
            "--budget",
            str(args.internal_dataset_budget),
            "--seed",
            str(args.seed),
        ],
        check=True,
    )
    internal_dataset_path = run_dir / "branch_scorer_v3_dataset.jsonl"

    # 2) Load external warm-start supervision from prepared Tier-1 previews.
    ext_x, ext_y, usage_rows, ext_per_dataset = _extract_external_supervision(
        Path(args.prepared_run_dir),
        max_rows=args.external_max_rows_per_dataset,
        seed=args.seed,
    )

    # 3) Load internal training/eval supervision.
    int_train_x, int_train_y, int_test_x, int_test_y = _load_internal_v7_dataset(internal_dataset_path)

    # 4) Train models: internal-only, external-only, and external->internal adapted.
    ext_w, ext_b = _train_logistic(ext_x, ext_y, lr=0.07, epochs=140)
    int_w, int_b = _train_logistic(int_train_x, int_train_y, lr=0.05, epochs=120)
    mixed_w, mixed_b = _train_logistic(
        int_train_x,
        int_train_y,
        init_weights=ext_w,
        init_intercept=ext_b,
        lr=0.04,
        epochs=120,
    )

    model_dir = run_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    _export_model(model_dir / "adaptive_learned_branch_score_external_warmstart.json", ext_w, ext_b, "external_warmstart_signal")
    _export_model(model_dir / "adaptive_learned_branch_score_internal_only.json", int_w, int_b, "v6_label_prefers_over_median")
    _export_model(model_dir / "adaptive_learned_branch_score_external_plus_internal.json", mixed_w, mixed_b, "external_then_internal")

    # 5) Evaluate on internal label holdout + controller simulator.
    holdout_rows = [
        {
            "model": "external_warmstart_only",
            "holdout_accuracy": _evaluate_classifier(ext_w, ext_b, int_test_x, int_test_y),
        },
        {
            "model": "internal_only",
            "holdout_accuracy": _evaluate_classifier(int_w, int_b, int_test_x, int_test_y),
        },
        {
            "model": "external_warmstart_plus_internal",
            "holdout_accuracy": _evaluate_classifier(mixed_w, mixed_b, int_test_x, int_test_y),
        },
    ]
    for ds_name, (ds_x, ds_y) in ext_per_dataset.items():
        ds_w, ds_b = _train_logistic(ds_x, ds_y, lr=0.07, epochs=140)
        holdout_rows.append(
            {
                "model": f"external_warmstart_only__{ds_name}",
                "holdout_accuracy": _evaluate_classifier(ds_w, ds_b, int_test_x, int_test_y),
            }
        )
    _write_csv(run_dir / "holdout_metrics.csv", holdout_rows)

    model_map = {
        "adaptive_learned_branch_score_internal_only": load_model(model_dir / "adaptive_learned_branch_score_internal_only.json"),
        "adaptive_learned_branch_score_external_warmstart": load_model(model_dir / "adaptive_learned_branch_score_external_warmstart.json"),
        "adaptive_learned_branch_score_external_plus_internal": load_model(model_dir / "adaptive_learned_branch_score_external_plus_internal.json"),
    }
    method_rows = _evaluate_controller_methods(
        seed=args.seed,
        episodes=args.episodes,
        budget=args.budget,
        n_init_branches=args.n_init_branches,
        model_map=model_map,
    )

    _write_csv(run_dir / "method_metrics.csv", method_rows)
    warm_rows = []
    by_method = {r["method"]: r for r in method_rows}
    oracle_acc = by_method["oracle_frontier_upper_bound"]["accuracy"]
    for name in ["adaptive_relative_rank", "adaptive_learned_branch_score_internal_only", "adaptive_learned_branch_score_external_warmstart", "adaptive_learned_branch_score_external_plus_internal"]:
        r = by_method[name]
        warm_rows.append(
            {
                "method": name,
                "accuracy": r["accuracy"],
                "delta_vs_internal_only": r["accuracy"] - by_method["adaptive_learned_branch_score_internal_only"]["accuracy"],
                "delta_vs_relative_rank": r["accuracy"] - by_method["adaptive_relative_rank"]["accuracy"],
                "gap_to_oracle": oracle_acc - r["accuracy"],
            }
        )
    _write_csv(run_dir / "warmstart_comparison.csv", warm_rows)

    oracle_rows = [
        {
            "oracle_accuracy": oracle_acc,
            "best_non_oracle_method": max(
                [r for r in method_rows if r["method"] != "oracle_frontier_upper_bound"], key=lambda x: x["accuracy"]
            )["method"],
            "best_non_oracle_accuracy": max(
                [r for r in method_rows if r["method"] != "oracle_frontier_upper_bound"], key=lambda x: x["accuracy"]
            )["accuracy"],
            "best_non_oracle_gap": min(
                [r for r in method_rows if r["method"] != "oracle_frontier_upper_bound"], key=lambda x: x["gap_to_oracle"]
            )["gap_to_oracle"],
        }
    ]
    _write_csv(run_dir / "oracle_gap_summary.csv", oracle_rows)
    _write_csv(run_dir / "dataset_usage_summary.csv", usage_rows)
    _write_csv(run_dir / "external_dataset_ablation.csv", [r for r in holdout_rows if r["model"].startswith("external_warmstart_only__")])

    real_model_status = {"attempted": False, "reason": "not requested"}
    if args.real_model_smoke:
        real_model_status = _attempt_real_model_smoke(run_dir, args.openai_model)

    manifest = {
        "run_id": run_id,
        "seed": args.seed,
        "budget": args.budget,
        "episodes": args.episodes,
        "internal_dataset_episodes": args.internal_dataset_episodes,
        "prepared_run_dir": args.prepared_run_dir,
        "tier1_datasets_targeted": ["deepstep_math_5k", "math_verify_s1k_r1", "ultrainteract_pair"],
        "aux_not_used_in_v1": ["mt_bench_human_judgments", "prometheus_preference_collection"],
        "real_model_smoke": real_model_status,
        "artifacts": {
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "warmstart_comparison": str(run_dir / "warmstart_comparison.csv"),
            "oracle_gap_summary": str(run_dir / "oracle_gap_summary.csv"),
            "dataset_usage_summary": str(run_dir / "dataset_usage_summary.csv"),
            "external_dataset_ablation": str(run_dir / "external_dataset_ablation.csv"),
            "holdout_metrics": str(run_dir / "holdout_metrics.csv"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    best = max([r for r in method_rows if r["method"] != "oracle_frontier_upper_bound"], key=lambda x: x["accuracy"])
    ds_holdout = [r for r in holdout_rows if r["model"].startswith("external_warmstart_only__")]
    ds_holdout_sorted = sorted(ds_holdout, key=lambda r: r["holdout_accuracy"], reverse=True)
    top_ds_line = (
        f"- Best single external dataset by holdout transfer: {ds_holdout_sorted[0]['model'].replace('external_warmstart_only__', '')} ({ds_holdout_sorted[0]['holdout_accuracy']:.4f})."
        if ds_holdout_sorted
        else "- Best single external dataset by holdout transfer: unavailable (no external rows loaded)."
    )

    interp = [
        f"# External warm-start branch scorer interpretation ({run_id})",
        "",
        "## What was trained",
        "- external_warmstart_only: logistic branch scorer on pseudo-v7 features derived from Tier-1 external readiness previews (partial label match).",
        "- internal_only: logistic branch scorer on internal v6 branch preference labels.",
        "- external_warmstart_plus_internal: external-initialized scorer further adapted on internal labels.",
        "",
        "## Honesty about fit",
        "- External datasets are warm-start supervision only; they do not provide exact frontier-allocation labels.",
        "- Repo-specific branch labels remain necessary for final allocation performance.",
        "",
        "## Result summary",
        f"- Best non-oracle method: **{best['method']}** @ accuracy={best['accuracy']:.4f}.",
        f"- Internal-only accuracy: {by_method['adaptive_learned_branch_score_internal_only']['accuracy']:.4f}.",
        f"- External warm-start only accuracy: {by_method['adaptive_learned_branch_score_external_warmstart']['accuracy']:.4f}.",
        f"- External warm-start + internal adaptation accuracy: {by_method['adaptive_learned_branch_score_external_plus_internal']['accuracy']:.4f}.",
        f"- Oracle upper-bound accuracy: {oracle_acc:.4f}.",
        top_ds_line,
        "",
        "## Interpretation",
        "- If external+internal > internal-only, warm-start is useful as initialization.",
        "- If external-only < internal-only, external supervision alone is insufficient for this branch-allocation simulator.",
        "- Judge-style Tier-1 datasets were intentionally deferred in this first pass to keep a simple, auditable design.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir), "best_method": best["method"], "best_accuracy": best["accuracy"]}, indent=2))


if __name__ == "__main__":
    main()
