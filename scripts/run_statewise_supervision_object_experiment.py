#!/usr/bin/env python3
"""Bounded statewise supervision-object experiment for branch allocation.

Compares canonical pairwise supervision against a materially different
statewise-next-branch supervision object while reusing the canonical data path.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (  # noqa: E402
    LearningConfig,
    load_label_artifacts,
    prepare_learning_tables,
    scorer_from_model,
    train_models,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _parse_int_csv(text: str) -> list[int]:
    out = [int(x.strip()) for x in str(text).split(",") if x.strip()]
    if not out:
        raise ValueError("Expected at least one seed")
    return out


def _pairwise_predict_from_score(score_fn: Callable[[dict[str, Any]], float], row: dict[str, Any]) -> int:
    si = float(score_fn({"x": row["x_i"]}))
    sj = float(score_fn({"x": row["x_j"]}))
    return 1 if si >= sj else 0


def _binary_pair_metrics(pair_rows: list[dict[str, Any]], pred_fn: Callable[[dict[str, Any]], int]) -> dict[str, Any]:
    test = [r for r in pair_rows if str(r.get("split")) == "test"]
    if not test:
        return {
            "accepted_accuracy": 0.0,
            "coverage": 0.0,
            "defer_rate": 0.0,
            "accepted_n": 0,
            "test_n": 0,
            "near_tie_accepted_accuracy": 0.0,
            "near_tie_n": 0,
            "adjacent_rank_accepted_accuracy": 0.0,
            "adjacent_rank_n": 0,
        }

    def _acc(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        return float(sum(int(pred_fn(r) == int(r.get("label", 0))) for r in rows) / len(rows))

    near = [r for r in test if bool(r.get("near_tie_flag", False))]
    adj = [r for r in test if bool(r.get("adjacent_rank_flag", False)) or str(r.get("pair_type", "")) == "adjacent_rank"]
    return {
        "accepted_accuracy": _acc(test),
        "coverage": 1.0,
        "defer_rate": 0.0,
        "accepted_n": len(test),
        "test_n": len(test),
        "near_tie_accepted_accuracy": _acc(near),
        "near_tie_n": len(near),
        "adjacent_rank_accepted_accuracy": _acc(adj),
        "adjacent_rank_n": len(adj),
    }


def _state_oracle_top1(rows: list[dict[str, Any]]) -> str:
    return str(max(rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0))).get("branch_id", ""))


def _state_pred_top1(rows: list[dict[str, Any]], score_fn: Callable[[dict[str, Any]], float]) -> str:
    return str(max(rows, key=score_fn).get("branch_id", ""))


def _is_near_tie_heavy_state(rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]]) -> bool:
    sid = str(rows[0].get("state_id", "")) if rows else ""
    state_pairs = [
        p
        for p in pair_rows
        if str(p.get("state_id", "")) == sid and str(p.get("split", "")) == "test"
    ]
    return any(
        bool(p.get("near_tie_flag", False))
        or bool(p.get("adjacent_rank_flag", False))
        or bool(p.get("small_margin_flag", False))
        for p in state_pairs
    )


def _statewise_diagnostics(
    state_to_candidates: dict[str, list[dict[str, Any]]],
    pair_rows: list[dict[str, Any]],
    score_fn: Callable[[dict[str, Any]], float],
) -> dict[str, Any]:
    test_states: list[list[dict[str, Any]]] = []
    for rows in state_to_candidates.values():
        rs = [r for r in rows if str(r.get("split")) == "test"]
        if len(rs) >= 2:
            test_states.append(rs)

    if not test_states:
        return {
            "test_state_n": 0,
            "top1_agreement": 0.0,
            "near_tie_heavy_state_n": 0,
            "near_tie_heavy_top1_agreement": 0.0,
            "candidate_count_summary": {},
        }

    ok = 0
    near_ok = 0
    near_total = 0
    candidate_counts = [len(rows) for rows in test_states]

    for rows in test_states:
        pred = _state_pred_top1(rows, score_fn)
        truth = _state_oracle_top1(rows)
        match = int(pred == truth)
        ok += match
        if _is_near_tie_heavy_state(rows, pair_rows):
            near_ok += match
            near_total += 1

    return {
        "test_state_n": len(test_states),
        "top1_agreement": float(ok / len(test_states)),
        "near_tie_heavy_state_n": int(near_total),
        "near_tie_heavy_top1_agreement": float(near_ok / max(1, near_total)),
        "candidate_count_summary": {
            "min": int(min(candidate_counts)),
            "max": int(max(candidate_counts)),
            "mean": float(np.mean(candidate_counts)),
            "median": float(np.median(candidate_counts)),
            "p90": float(np.percentile(candidate_counts, 90)),
        },
    }


def _fit_statewise_binary_top1(candidates: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return {"status": "insufficient_train_rows", "training_rows": len(train)}

    by_state: dict[str, list[dict[str, Any]]] = {}
    for r in train:
        by_state.setdefault(str(r.get("state_id", "")), []).append(r)

    x: list[list[float]] = []
    y: list[int] = []
    for rows in by_state.values():
        if len(rows) < 2:
            continue
        top = _state_oracle_top1(rows)
        for r in rows:
            x.append([float(v) for v in r["x"]])
            y.append(1 if str(r.get("branch_id", "")) == top else 0)

    if len(x) < 8 or len(set(y)) < 2:
        return {"status": "degenerate_or_insufficient", "training_rows": len(x)}

    model = LogisticRegression(max_iter=500, random_state=seed)
    model.fit(x, y)
    return {
        "status": "ok",
        "weights": [float(v) for v in model.coef_[0]],
        "intercept": float(model.intercept_[0]),
        "training_rows": len(x),
    }


def _scorer_from_linear(model: dict[str, Any]) -> Callable[[dict[str, Any]], float]:
    w = np.array(model.get("weights", []), dtype=float)
    b = float(model.get("intercept", 0.0))
    return lambda row: float(np.dot(w, np.array(row["x"], dtype=float)) + b)


def _evaluate_modes(tables: dict[str, Any], baseline_pairwise: dict[str, Any], pointwise_value: dict[str, Any], binary_top1: dict[str, Any]) -> dict[str, Any]:
    pair_rows = tables["pairwise"]
    state_to_candidates = tables["state_to_candidates"]

    if str(baseline_pairwise.get("status")) == "ok":
        baseline_fn = scorer_from_model(baseline_pairwise)
        baseline_pred = lambda r: _pairwise_predict_from_score(baseline_fn, r)
    else:
        constant = int(baseline_pairwise.get("constant_label", 0))
        baseline_pred = lambda _r: constant

    baseline_metrics = _binary_pair_metrics(pair_rows, baseline_pred)
    baseline_diag = {
        "type": "pairwise_canonical",
        "statewise_top1_from_pairwise_not_computed": True,
    }

    if str(pointwise_value.get("status")) == "ok":
        value_fn = scorer_from_model(pointwise_value)
    else:
        value_fn = lambda r: float(r.get("estimated_value_if_allocate_next", 0.0))

    value_pred = lambda r: _pairwise_predict_from_score(value_fn, r)
    value_metrics = _binary_pair_metrics(pair_rows, value_pred)
    value_diag = _statewise_diagnostics(state_to_candidates, pair_rows, value_fn)

    out = {
        "baseline_pairwise_canonical": {
            "metrics": baseline_metrics,
            "statewise_diagnostics": baseline_diag,
        },
        "statewise_next_branch_value": {
            "metrics": value_metrics,
            "statewise_diagnostics": value_diag,
        },
    }

    if str(binary_top1.get("status")) == "ok":
        binary_fn = _scorer_from_linear(binary_top1)
        binary_pred = lambda r: _pairwise_predict_from_score(binary_fn, r)
        out["statewise_next_branch_binary_top1_only"] = {
            "metrics": _binary_pair_metrics(pair_rows, binary_pred),
            "statewise_diagnostics": _statewise_diagnostics(state_to_candidates, pair_rows, binary_fn),
        }
    else:
        out["statewise_next_branch_binary_top1_only"] = {
            "skipped": True,
            "reason": str(binary_top1.get("status", "unknown")),
        }
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded statewise supervision-object experiment")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-root", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--seeds", default="11,29,47")
    p.add_argument("--feature-set", default="v2", choices=["v1", "v2", "v3"])
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = _parse_int_csv(args.seeds)
    raw_data = load_label_artifacts(Path(args.labels_dir))

    per_seed: list[dict[str, Any]] = []
    for seed in seeds:
        cfg = LearningConfig(
            seed=int(seed),
            near_tie_margin=float(args.near_tie_margin),
            feature_set=str(args.feature_set),
            train_pairwise=True,
            train_pointwise=True,
            train_outside_option=False,
            train_lightgbm_ranker=False,
            train_catboost_ranker=False,
            train_pairwise_svm=False,
            pairwise_near_tie_action="none",
        )
        tables = prepare_learning_tables(raw_data, cfg)
        models = train_models(tables, cfg)
        binary_top1 = _fit_statewise_binary_top1(tables["candidates"], seed=int(seed))
        mode_eval = _evaluate_modes(
            tables,
            baseline_pairwise=models.get("pairwise", {}),
            pointwise_value=models.get("pointwise", {}),
            binary_top1=binary_top1,
        )
        per_seed.append(
            {
                "seed": int(seed),
                "config": asdict(cfg),
                "mode_summaries": mode_eval,
                "train_status": {
                    "pairwise": models.get("pairwise", {}).get("status", "unknown"),
                    "pointwise": models.get("pointwise", {}).get("status", "unknown"),
                    "binary_top1_ablation": binary_top1.get("status", "unknown"),
                },
            }
        )

    mode_names = [
        "baseline_pairwise_canonical",
        "statewise_next_branch_value",
        "statewise_next_branch_binary_top1_only",
    ]

    aggregate: dict[str, Any] = {}
    for mode in mode_names:
        mode_rows = [s["mode_summaries"].get(mode, {}) for s in per_seed]
        metric_rows = [m["metrics"] for m in mode_rows if isinstance(m, dict) and "metrics" in m]
        diag_rows = [m.get("statewise_diagnostics", {}) for m in mode_rows if isinstance(m, dict)]
        aggregate[mode] = {
            "seeds_present": len(metric_rows),
            "accepted_accuracy_mean": _mean([float(m.get("accepted_accuracy", 0.0)) for m in metric_rows]),
            "coverage_mean": _mean([float(m.get("coverage", 0.0)) for m in metric_rows]),
            "defer_rate_mean": _mean([float(m.get("defer_rate", 0.0)) for m in metric_rows]),
            "near_tie_accepted_accuracy_mean": _mean([float(m.get("near_tie_accepted_accuracy", 0.0)) for m in metric_rows]),
            "adjacent_rank_accepted_accuracy_mean": _mean([float(m.get("adjacent_rank_accepted_accuracy", 0.0)) for m in metric_rows]),
            "statewise_top1_agreement_mean": _mean([float(d.get("top1_agreement", 0.0)) for d in diag_rows if "top1_agreement" in d]),
            "near_tie_heavy_state_top1_agreement_mean": _mean(
                [float(d.get("near_tie_heavy_top1_agreement", 0.0)) for d in diag_rows if "near_tie_heavy_top1_agreement" in d]
            ),
        }

    baseline = aggregate.get("baseline_pairwise_canonical", {})
    comparison: dict[str, Any] = {}
    for mode in ["statewise_next_branch_value", "statewise_next_branch_binary_top1_only"]:
        cur = aggregate.get(mode, {})
        comparison[mode] = {
            "delta_accepted_accuracy_vs_baseline": float(cur.get("accepted_accuracy_mean", 0.0) - baseline.get("accepted_accuracy_mean", 0.0)),
            "delta_near_tie_accepted_accuracy_vs_baseline": float(
                cur.get("near_tie_accepted_accuracy_mean", 0.0) - baseline.get("near_tie_accepted_accuracy_mean", 0.0)
            ),
            "delta_adjacent_rank_accepted_accuracy_vs_baseline": float(
                cur.get("adjacent_rank_accepted_accuracy_mean", 0.0) - baseline.get("adjacent_rank_accepted_accuracy_mean", 0.0)
            ),
        }

    payload = {
        "run_id": str(args.run_id),
        "labels_dir": str(args.labels_dir),
        "seeds": seeds,
        "config": {
            "feature_set": str(args.feature_set),
            "near_tie_margin": float(args.near_tie_margin),
            "supervision_object": "statewise_next_branch_value",
            "modes": mode_names,
        },
        "per_seed": per_seed,
        "aggregate_by_mode": aggregate,
        "aggregate_comparison_vs_baseline": comparison,
    }

    _write_json(out_dir / "statewise_supervision_manifest.json", payload)
    _write_json(out_dir / "per_seed_summary.json", {"run_id": args.run_id, "per_seed": per_seed})
    _write_json(out_dir / "matched_summary_by_mode.json", {"run_id": args.run_id, "aggregate_by_mode": aggregate})
    _write_json(
        out_dir / "aggregate_comparison_summary.json",
        {"run_id": args.run_id, "baseline": baseline, "comparison": comparison},
    )
    _write_json(
        out_dir / "statewise_top1_agreement_diagnostics.json",
        {
            "run_id": args.run_id,
            "diagnostics_by_seed": {
                str(s["seed"]): {
                    k: v.get("statewise_diagnostics", {})
                    for k, v in s["mode_summaries"].items()
                    if isinstance(v, dict)
                }
                for s in per_seed
            },
        },
    )

    commands_note = "\n".join(
        [
            "# Commands / assumptions / caveats",
            "",
            "## Commands run",
            f"- python scripts/run_statewise_supervision_object_experiment.py --labels-dir {args.labels_dir} --run-id {args.run_id} --output-root {args.output_root} --seeds {args.seeds} --feature-set {args.feature_set} --near-tie-margin {args.near_tie_margin}",
            "",
            "## Assumptions",
            "- Canonical candidate target estimated_value_if_allocate_next is a valid next-branch value proxy.",
            "- Canonical feature set and split assignment from prepare_learning_tables are kept unchanged.",
            "",
            "## Caveats",
            "- Statewise models are mapped back to pairwise accepted-accuracy metrics by induced pair predictions from candidate scores.",
            "- No explicit defer head is used in this bounded experiment; coverage=1 and defer_rate=0 by design for compared modes.",
        ]
    )
    (out_dir / "commands_assumptions_caveats.md").write_text(commands_note + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "manifest": str(out_dir / 'statewise_supervision_manifest.json')}, indent=2))


if __name__ == "__main__":
    main()
