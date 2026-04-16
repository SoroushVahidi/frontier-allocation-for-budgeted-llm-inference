#!/usr/bin/env python3
"""Boundary-sensitive held-out evaluation protocol for canonical branch-learning runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import LearningConfig, prepare_learning_tables, scorer_from_model, train_models
from scripts.run_canonical_branch_learning_pass import (
    _apply_balanced_hardcase_weighting,
    _apply_reweighting,
    _blended_linear_scorer,
    _comparator_boundary_pair_predictor,
    _fit_external_prm_pointwise_prior,
    _to_allocator_tables,
    _uncertainty_gated_blended_scorer,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _pair_pred(row: dict[str, Any], score_fn: Callable[[dict[str, Any]], float]) -> int:
    return 1 if float(score_fn({"x": row["x_i"]})) >= float(score_fn({"x": row["x_j"]})) else 0


def _pair_correct(row: dict[str, Any], score_fn: Callable[[dict[str, Any]], float]) -> int:
    truth = int(row.get("label", row.get("preference", 0)))
    return int(_pair_pred(row, score_fn) == truth)


def _pair_correct_boundary(
    row: dict[str, Any],
    *,
    base_fn: Callable[[dict[str, Any]], float],
    boundary_pair_pred: Callable[[dict[str, Any]], int],
) -> int:
    pred = int(boundary_pair_pred(row))
    truth = int(row.get("label", row.get("preference", 0)))
    return int(pred == truth)


def _bootstrap_ci(deltas: np.ndarray, *, n_boot: int, seed: int) -> dict[str, float]:
    if deltas.size == 0:
        return {"mean_delta": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0}
    rng = np.random.default_rng(seed)
    n = deltas.size
    means = []
    for _ in range(int(n_boot)):
        idx = rng.integers(0, n, size=n)
        means.append(float(np.mean(deltas[idx])))
    means_arr = np.array(means, dtype=float)
    return {
        "mean_delta": float(np.mean(deltas)),
        "ci_low": float(np.quantile(means_arr, 0.025)),
        "ci_high": float(np.quantile(means_arr, 0.975)),
        "n": int(n),
    }


def _pivot_consistency(
    pair_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    pred_pair_fn: Callable[[dict[str, Any]], int],
    near_boundary_fn: Callable[[dict[str, Any]], bool],
) -> dict[str, float]:
    by_state_pairs: dict[str, list[dict[str, Any]]] = {}
    for r in pair_rows:
        by_state_pairs.setdefault(str(r["state_id"]), []).append(r)
    by_state_cands: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        if str(c.get("split")) == "test":
            by_state_cands.setdefault(str(c["state_id"]), []).append(c)

    eligible = 0
    consistent = 0
    for sid, rows in by_state_pairs.items():
        b_rows = [r for r in rows if near_boundary_fn(r)]
        if len(b_rows) < 1:
            continue
        cands = by_state_cands.get(sid, [])
        if len(cands) < 3:
            continue
        pivot = max(cands, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0)))["branch_id"]
        pivot_pairs = [r for r in b_rows if str(r["branch_i"]) == str(pivot) or str(r["branch_j"]) == str(pivot)]
        if not pivot_pairs:
            continue
        ok = True
        for r in pivot_pairs:
            pred = int(pred_pair_fn(r))
            if str(r["branch_i"]) == str(pivot):
                want = 1
            elif str(r["branch_j"]) == str(pivot):
                want = 0
            else:
                continue
            if pred != want:
                ok = False
                break
        eligible += 1
        consistent += int(ok)
    return {"eligible_state_n": int(eligible), "consistency": float(consistent / max(1, eligible))}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run boundary-sensitive canonical held-out evaluation")
    p.add_argument("--canonical-corpus-dir", required=True)
    p.add_argument("--external-prm-corpus-dir", required=True)
    p.add_argument("--output-json", required=True)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--near-tie-margin", type=float, default=0.05)
    p.add_argument("--feature-set", default="v2")
    p.add_argument("--hard-case-mult", type=float, default=1.75)
    p.add_argument("--exact-promoted-mult", type=float, default=2.0)
    p.add_argument("--intervention-target-boost", type=float, default=0.6)
    p.add_argument("--external-source-key", default="prm800k")
    p.add_argument("--external-source-split", default="train")
    p.add_argument("--external-pointwise-blend-alpha", type=float, default=0.2)
    p.add_argument("--external-gate-uncertainty-std-threshold", type=float, default=0.03)
    p.add_argument("--external-gate-top-gap-threshold", type=float, default=0.04)
    p.add_argument("--external-boundary-pair-margin-threshold", type=float, default=0.02)
    p.add_argument("--external-boundary-pair-uncertainty-std-threshold", type=float, default=0.02)
    p.add_argument("--external-prm-max-uncertainty-std", type=float, default=1.0)
    p.add_argument("--bootstrap-samples", type=int, default=2000)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    raw = _to_allocator_tables(Path(args.canonical_corpus_dir))
    cfg = LearningConfig(
        seed=int(args.seed),
        near_tie_margin=float(args.near_tie_margin),
        feature_set=str(args.feature_set),
        uncertainty_weighting=True,
        pairwise_near_tie_action="none",
        train_pairwise=True,
        train_pointwise=True,
        train_outside_option=True,
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
    )
    base_tables = prepare_learning_tables(raw, cfg)
    reweighted = _apply_reweighting(
        prepare_learning_tables(raw, cfg),
        hard_case_mult=float(args.hard_case_mult),
        exact_promoted_mult=float(args.exact_promoted_mult),
    )
    intervention_tables, _ = _apply_balanced_hardcase_weighting(
        prepare_learning_tables(raw, cfg),
        target_boost=float(args.intervention_target_boost),
    )

    reweighted_models = train_models(reweighted, cfg)
    intervention_models = train_models(intervention_tables, cfg)
    pointwise_model = reweighted_models["pointwise"]
    anchor_model = intervention_models["pointwise"]

    ext_prior = _fit_external_prm_pointwise_prior(
        Path(args.external_prm_corpus_dir),
        feature_names=list(base_tables["feature_names"]),
        source_dataset_key=str(args.external_source_key),
        source_split=str(args.external_source_split),
        max_uncertainty_std=float(args.external_prm_max_uncertainty_std),
    )

    anchor_fn = scorer_from_model(anchor_model)
    base_fn = scorer_from_model(pointwise_model)
    broad_fn = _blended_linear_scorer(pointwise_model, ext_prior, blend_alpha=float(args.external_pointwise_blend_alpha))
    aligned_fn = _uncertainty_gated_blended_scorer(
        pointwise_model,
        ext_prior,
        blend_alpha=float(args.external_pointwise_blend_alpha),
        std_threshold=float(args.external_gate_uncertainty_std_threshold),
        gap_threshold=float(args.external_gate_top_gap_threshold),
    )
    boundary_pair_pred = _comparator_boundary_pair_predictor(
        base_fn=base_fn,
        external_fn=broad_fn,
        pair_margin_threshold=float(args.external_boundary_pair_margin_threshold),
        pair_uncertainty_std_threshold=float(args.external_boundary_pair_uncertainty_std_threshold),
    )

    test_pairs = [r for r in reweighted["pairwise"] if str(r.get("split")) == "test"]
    test_cands = [r for r in reweighted["candidates"] if str(r.get("split")) == "test"]
    state_to_cands: dict[str, list[dict[str, Any]]] = {}
    for c in test_cands:
        state_to_cands.setdefault(str(c["state_id"]), []).append(c)
    top1_states = [sid for sid, rows in state_to_cands.items() if len(rows) >= 2]

    def near_boundary(row: dict[str, Any]) -> bool:
        margin = float(base_fn({"x": row["x_i"]}) - base_fn({"x": row["x_j"]}))
        return bool(
            abs(margin) <= float(args.external_boundary_pair_margin_threshold)
            and float(row.get("pair_uncertainty_std_mean", 0.0)) >= float(args.external_boundary_pair_uncertainty_std_threshold)
        )

    slices: dict[str, Callable[[dict[str, Any]], bool]] = {
        "all": lambda _r: True,
        "near_tie": lambda r: bool(abs(float(r.get("margin", 0.0))) <= float(args.near_tie_margin)),
        "adjacent_rank": lambda r: str(r.get("pair_type", "")) == "adjacent_rank",
        "small_margin": lambda r: bool(r.get("small_margin_flag", False)),
        "exact_promoted": lambda r: bool(r.get("replaced_approx_label", False)),
        "exact_only": lambda r: bool(r.get("is_exact_label", False)),
        "approx_only": lambda r: not bool(r.get("is_exact_label", False)),
        "low_budget": lambda r: int(r.get("remaining_budget", 0)) <= 2,
        "boundary_eligible": near_boundary,
        "exact_promoted_near_boundary": lambda r: bool(r.get("replaced_approx_label", False)) and near_boundary(r),
        "exact_promoted_non_boundary": lambda r: bool(r.get("replaced_approx_label", False)) and not near_boundary(r),
        "approx_near_boundary": lambda r: (not bool(r.get("is_exact_label", False))) and near_boundary(r),
        "approx_non_boundary": lambda r: (not bool(r.get("is_exact_label", False))) and not near_boundary(r),
        "low_budget_near_boundary": lambda r: int(r.get("remaining_budget", 0)) <= 2 and near_boundary(r),
        "low_budget_non_boundary": lambda r: int(r.get("remaining_budget", 0)) <= 2 and not near_boundary(r),
    }

    methods = {
        "anchor": lambda r: _pair_correct(r, anchor_fn),
        "broad": lambda r: _pair_correct(r, broad_fn),
        "aligned": lambda r: _pair_correct(r, aligned_fn),
        "boundary": lambda r: _pair_correct_boundary(r, base_fn=base_fn, boundary_pair_pred=boundary_pair_pred),
    }

    slice_metrics: dict[str, Any] = {}
    per_row_correct: dict[str, list[int]] = {k: [] for k in methods}
    for slice_name, pred in slices.items():
        rows = [r for r in test_pairs if pred(r)]
        out = {"n": int(len(rows))}
        for m, fn in methods.items():
            vals = [int(fn(r)) for r in rows]
            out[m] = float(sum(vals) / max(1, len(vals)))
            if slice_name == "all":
                per_row_correct[m] = vals
        slice_metrics[slice_name] = out

    def _paired_delta(m1: str, m0: str, rows: list[dict[str, Any]]) -> dict[str, float]:
        d = np.array([methods[m1](r) - methods[m0](r) for r in rows], dtype=float)
        return _bootstrap_ci(d, n_boot=int(args.bootstrap_samples), seed=int(args.seed))

    paired = {}
    key_slices = ["all", "near_tie", "adjacent_rank", "small_margin", "low_budget", "boundary_eligible"]
    for s in key_slices:
        rows = [r for r in test_pairs if slices[s](r)]
        paired[s] = {
            "anchor_vs_broad": _paired_delta("broad", "anchor", rows),
            "anchor_vs_aligned": _paired_delta("aligned", "anchor", rows),
            "anchor_vs_boundary": _paired_delta("boundary", "anchor", rows),
        }

    pivot_metrics = {
        "anchor": _pivot_consistency(test_pairs, test_cands, pred_pair_fn=lambda r: _pair_pred(r, anchor_fn), near_boundary_fn=near_boundary),
        "broad": _pivot_consistency(test_pairs, test_cands, pred_pair_fn=lambda r: _pair_pred(r, broad_fn), near_boundary_fn=near_boundary),
        "aligned": _pivot_consistency(test_pairs, test_cands, pred_pair_fn=lambda r: _pair_pred(r, aligned_fn), near_boundary_fn=near_boundary),
        "boundary": _pivot_consistency(test_pairs, test_cands, pred_pair_fn=lambda r: int(boundary_pair_pred(r)), near_boundary_fn=near_boundary),
    }

    out = {
        "canonical_corpus_dir": str(args.canonical_corpus_dir),
        "external_prm_corpus_dir": str(args.external_prm_corpus_dir),
        "config": vars(args),
        "support_counts": {
            "total_test_pairs": int(len(test_pairs)),
            "total_top1_states": int(len(top1_states)),
            "dataset_slices": {
                k: int(sum(1 for r in test_pairs if str(r.get("dataset_name", "")) == k))
                for k in sorted({str(r.get("dataset_name", "")) for r in test_pairs})
            },
            "budget_slices": {
                str(b): int(sum(1 for r in test_pairs if int(r.get("remaining_budget", 0)) == int(b)))
                for b in sorted({int(r.get("remaining_budget", 0)) for r in test_pairs})
            },
        },
        "slice_metrics": slice_metrics,
        "pivot_boundary_consistency": pivot_metrics,
        "paired_uncertainty": paired,
    }
    _write_json(Path(args.output_json), out)
    print(json.dumps({"output_json": str(args.output_json)}, indent=2))


if __name__ == "__main__":
    main()
