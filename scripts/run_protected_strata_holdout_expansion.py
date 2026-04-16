#!/usr/bin/env python3
"""Bounded protected-strata holdout expansion for canonical branch-learning corpora.

Strategy: choose a split seed (without changing row content) that improves held-out
support on underpowered protected strata, then materialize a split-frozen corpus and
manifest-backed test holdout definition for reuse.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_canonical_boundary_sensitive_evaluation import _to_allocator_tables
from experiments.bruteforce_branch_allocator import LearningConfig, prepare_learning_tables, train_models, scorer_from_model
from scripts.run_canonical_branch_learning_pass import _apply_reweighting


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _stable_split(state_id: str, seed: int, train_ratio: float, val_ratio: float) -> str:
    h = hashlib.sha256(f"split|{seed}|{state_id}".encode("utf-8")).hexdigest()
    r = int(h[:12], 16) / float(16**12)
    if r < train_ratio:
        return "train"
    if r < train_ratio + val_ratio:
        return "val"
    return "test"


def _counts_from_rows(
    rows: list[dict[str, Any]],
    *,
    near_boundary_margin_threshold: float,
    near_boundary_uncertainty_threshold: float,
) -> dict[str, int]:
    def _near_boundary(r: dict[str, Any]) -> bool:
        return bool(
            abs(float(r.get("model_margin", 0.0))) <= near_boundary_margin_threshold
            and float(r.get("pair_uncertainty_std_mean", 0.0)) >= near_boundary_uncertainty_threshold
        )

    c = {
        "total_test_pairs": len(rows),
        "near_tie": sum(1 for r in rows if bool(r.get("near_tie_flag", False))),
        "adjacent_rank": sum(1 for r in rows if str(r.get("pair_type", "")) == "adjacent_rank"),
        "small_margin": sum(1 for r in rows if bool(r.get("small_margin_flag", False))),
        "exact_promoted": sum(1 for r in rows if bool(r.get("replaced_approx_label", False))),
        "exact_only": sum(1 for r in rows if bool(r.get("is_exact_label", False))),
        "approx_only": sum(1 for r in rows if not bool(r.get("is_exact_label", False))),
        "low_budget": sum(1 for r in rows if int(r.get("remaining_budget", 0)) <= 2),
        "extreme_low_budget": sum(1 for r in rows if int(r.get("remaining_budget", 0)) <= 1),
        "boundary_eligible": sum(1 for r in rows if _near_boundary(r)),
        "exact_promoted_near_boundary": sum(
            1 for r in rows if bool(r.get("replaced_approx_label", False)) and _near_boundary(r)
        ),
        "exact_promoted_non_boundary": sum(
            1 for r in rows if bool(r.get("replaced_approx_label", False)) and not _near_boundary(r)
        ),
        "approx_near_boundary": sum(
            1 for r in rows if (not bool(r.get("is_exact_label", False))) and _near_boundary(r)
        ),
        "approx_non_boundary": sum(
            1 for r in rows if (not bool(r.get("is_exact_label", False))) and not _near_boundary(r)
        ),
        "low_budget_near_boundary": sum(
            1 for r in rows if int(r.get("remaining_budget", 0)) <= 2 and _near_boundary(r)
        ),
        "low_budget_non_boundary": sum(
            1 for r in rows if int(r.get("remaining_budget", 0)) <= 2 and not _near_boundary(r)
        ),
        "extreme_low_budget_boundary_eligible": sum(
            1 for r in rows if int(r.get("remaining_budget", 0)) <= 1 and _near_boundary(r)
        ),
    }
    return c


def _score_counts(c: dict[str, int]) -> float:
    # Prioritize the most underpowered protected strata.
    return (
        6.0 * c["exact_promoted_near_boundary"]
        + 5.0 * c["low_budget_near_boundary"]
        + 6.0 * c["extreme_low_budget_boundary_eligible"]
        + 3.0 * c["exact_promoted_non_boundary"]
        + 1.0 * c["boundary_eligible"]
        + 0.2 * c["total_test_pairs"]
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run one bounded protected-strata holdout expansion pass")
    p.add_argument("--canonical-corpus-dir", required=True)
    p.add_argument("--output-corpus-dir", required=True)
    p.add_argument("--output-manifest-json", required=True)
    p.add_argument("--output-holdout-jsonl", required=True)
    p.add_argument("--output-audit-json", required=True)
    p.add_argument("--seed-min", type=int, default=1)
    p.add_argument("--seed-max", type=int, default=128)
    p.add_argument("--baseline-seed", type=int, default=17)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--near-boundary-margin-threshold", type=float, default=0.02)
    p.add_argument("--near-boundary-uncertainty-threshold", type=float, default=0.02)
    p.add_argument("--near-tie-margin", type=float, default=0.05)
    p.add_argument("--feature-set", default="v2")
    p.add_argument("--hard-case-mult", type=float, default=1.75)
    p.add_argument("--exact-promoted-mult", type=float, default=2.0)
    p.add_argument("--min-support-threshold", type=int, default=5)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    corpus_dir = Path(args.canonical_corpus_dir)
    rows_dir = corpus_dir / "rows"
    pair_path = rows_dir / "pairwise_rows.jsonl"
    cand_path = rows_dir / "candidate_rows.jsonl"
    outside_path = rows_dir / "outside_option_rows.jsonl"
    if not pair_path.exists() or not cand_path.exists() or not outside_path.exists():
        raise FileNotFoundError("canonical corpus rows/ missing required jsonl files")

    raw = _to_allocator_tables(corpus_dir)
    seed_candidates: list[dict[str, Any]] = []
    for seed in range(int(args.seed_min), int(args.seed_max) + 1):
        cfg = LearningConfig(
            seed=int(seed),
            train_ratio=float(args.train_ratio),
            val_ratio=float(args.val_ratio),
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
        model = train_models(reweighted, cfg)["pointwise"]
        pointwise_fn = scorer_from_model(model)
        test_rows = [dict(r) for r in reweighted["pairwise"] if str(r.get("split")) == "test"]
        for r in test_rows:
            r["model_margin"] = float(pointwise_fn({"x": r["x_i"]}) - pointwise_fn({"x": r["x_j"]}))
        counts = _counts_from_rows(
            test_rows,
            near_boundary_margin_threshold=float(args.near_boundary_margin_threshold),
            near_boundary_uncertainty_threshold=float(args.near_boundary_uncertainty_threshold),
        )
        seed_candidates.append({"seed": seed, "score": _score_counts(counts), "counts": counts})

    seed_candidates.sort(key=lambda x: (x["score"], x["counts"]["exact_promoted_near_boundary"], x["counts"]["low_budget_near_boundary"]), reverse=True)
    best = seed_candidates[0]

    baseline = next((r for r in seed_candidates if int(r["seed"]) == int(args.baseline_seed)), None)
    if baseline is None:
        raise RuntimeError("baseline seed is outside scanned seed range")
    baseline_counts = baseline["counts"]

    # Build test rows for selected seed for frozen holdout manifest.
    selected_cfg = LearningConfig(
        seed=int(best["seed"]),
        train_ratio=float(args.train_ratio),
        val_ratio=float(args.val_ratio),
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
    selected_tables = prepare_learning_tables(raw, selected_cfg)
    selected_reweighted = _apply_reweighting(
        prepare_learning_tables(raw, selected_cfg),
        hard_case_mult=float(args.hard_case_mult),
        exact_promoted_mult=float(args.exact_promoted_mult),
    )
    selected_model = train_models(selected_reweighted, selected_cfg)["pointwise"]
    selected_pointwise_fn = scorer_from_model(selected_model)
    test_pair_rows = [dict(r) for r in selected_reweighted["pairwise"] if str(r.get("split")) == "test"]
    for r in test_pair_rows:
        r["model_margin"] = float(selected_pointwise_fn({"x": r["x_i"]}) - selected_pointwise_fn({"x": r["x_j"]}))

    baseline_selected_counts = _counts_from_rows(
        [dict(r) for r in selected_reweighted["pairwise"] if str(r.get("split")) == "test"],
        near_boundary_margin_threshold=float(args.near_boundary_margin_threshold),
        near_boundary_uncertainty_threshold=float(args.near_boundary_uncertainty_threshold),
    )

    underpowered_before = {
        k: v for k, v in baseline_counts.items()
        if k in {
            "exact_promoted_near_boundary",
            "exact_promoted_non_boundary",
            "approx_near_boundary",
            "approx_non_boundary",
            "low_budget_near_boundary",
            "low_budget_non_boundary",
            "extreme_low_budget_boundary_eligible",
        }
        and v < int(args.min_support_threshold)
    }
    underpowered_after = {
        k: v for k, v in best["counts"].items()
        if k in underpowered_before and v < int(args.min_support_threshold)
    }

    # Materialize split-frozen corpus with the selected seed.
    output_corpus_dir = Path(args.output_corpus_dir)
    out_rows_dir = output_corpus_dir / "rows"
    output_corpus_dir.mkdir(parents=True, exist_ok=True)

    original_candidates = _read_jsonl(cand_path)
    original_pairwise = _read_jsonl(pair_path)
    original_outside = _read_jsonl(outside_path)

    for row in original_candidates:
        row["split"] = _stable_split(str(row.get("state_id", "")), int(best["seed"]), float(args.train_ratio), float(args.val_ratio))
    for row in original_pairwise:
        row["split"] = _stable_split(str(row.get("state_id", "")), int(best["seed"]), float(args.train_ratio), float(args.val_ratio))
    for row in original_outside:
        row["split"] = _stable_split(str(row.get("state_id", "")), int(best["seed"]), float(args.train_ratio), float(args.val_ratio))

    _write_jsonl(out_rows_dir / "candidate_rows.jsonl", original_candidates)
    _write_jsonl(out_rows_dir / "pairwise_rows.jsonl", original_pairwise)
    _write_jsonl(out_rows_dir / "outside_option_rows.jsonl", original_outside)

    # Carry through metadata files if present.
    for rel in ["manifest.json", "meta/checksums.json", "meta/source_artifacts.json", "summaries/corpus_summary.json", "summaries/slice_stats.json"]:
        src = corpus_dir / rel
        if src.exists():
            dst = output_corpus_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # Freeze protected-strata holdout manifest (test pair rows only).
    # Compute state-level pivot branch in held-out split.
    state_best_est: dict[str, float] = {}
    state_to_best_branch: dict[str, str] = {}
    for c in original_candidates:
        if str(c.get("split", "")) != "test":
            continue
        sid = str(c.get("state_id", ""))
        est = float(c.get("estimated_value_if_allocate_next", 0.0))
        if sid not in state_best_est or est > state_best_est[sid]:
            state_best_est[sid] = est
            state_to_best_branch[sid] = str(c.get("branch_id", ""))

    holdout_rows: list[dict[str, Any]] = []
    for r in test_pair_rows:
        near_boundary = bool(
            abs(float(r.get("model_margin", 0.0))) <= float(args.near_boundary_margin_threshold)
            and float(r.get("pair_uncertainty_std_mean", 0.0)) >= float(args.near_boundary_uncertainty_threshold)
        )
        is_exact = bool(r.get("is_exact_label", False))
        is_promoted = bool(r.get("replaced_approx_label", False))
        low_budget = int(r.get("remaining_budget", 0)) <= 2
        extreme_low_budget = int(r.get("remaining_budget", 0)) <= 1
        holdout_rows.append(
            {
                "state_id": str(r.get("state_id", "")),
                "dataset_name": str(r.get("dataset_name", "")),
                "pair_uid": str(r.get("canonical_pair_uid", "")),
                "branch_i": str(r.get("branch_i", "")),
                "branch_j": str(r.get("branch_j", "")),
                "pivot_branch_id": state_to_best_branch.get(str(r.get("state_id", ""))),
                "group_key": f"{r.get('dataset_name', '')}|budget_{int(r.get('remaining_budget', 0))}",
                "stratum_assignment": {
                    "exact_promoted_near_boundary": bool(is_promoted and near_boundary),
                    "exact_promoted_non_boundary": bool(is_promoted and not near_boundary),
                    "approx_near_boundary": bool((not is_exact) and near_boundary),
                    "approx_non_boundary": bool((not is_exact) and (not near_boundary)),
                    "low_budget_near_boundary": bool(low_budget and near_boundary),
                    "low_budget_non_boundary": bool(low_budget and (not near_boundary)),
                    "extreme_low_budget_boundary_eligible": bool(extreme_low_budget and near_boundary),
                },
                "provenance": {
                    "is_exact_label": is_exact,
                    "is_approx_label": not is_exact,
                    "replaced_approx_label": is_promoted,
                    "label_source": str(r.get("label_source", "")),
                    "pair_mode_provenance": str(r.get("pair_mode_provenance", "")),
                },
                "remaining_budget_bucket": {
                    "remaining_budget": int(r.get("remaining_budget", 0)),
                    "low_budget_le_2": low_budget,
                    "extreme_low_budget_le_1": extreme_low_budget,
                },
                "boundary_eligibility": {
                    "near_boundary": near_boundary,
                    "model_margin": float(r.get("model_margin", 0.0)),
                    "pair_uncertainty_std_mean": float(r.get("pair_uncertainty_std_mean", 0.0)),
                    "margin_threshold": float(args.near_boundary_margin_threshold),
                    "uncertainty_threshold": float(args.near_boundary_uncertainty_threshold),
                },
            }
        )
    _write_jsonl(Path(args.output_holdout_jsonl), holdout_rows)

    audit = {
        "strategy": "split_seed_selection_for_protected_strata_support",
        "baseline_seed": int(args.baseline_seed),
        "selected_seed": int(best["seed"]),
        "baseline_counts": baseline_counts,
        "selected_recomputed_counts": baseline_selected_counts,
        "selected_counts": best["counts"],
        "underpowered_before": underpowered_before,
        "underpowered_after": underpowered_after,
        "support_threshold": int(args.min_support_threshold),
        "seed_scan": seed_candidates,
        "materialized_corpus_dir": str(output_corpus_dir),
        "frozen_holdout_jsonl": str(args.output_holdout_jsonl),
    }
    _write_json(Path(args.output_audit_json), audit)

    manifest = {
        "generator": "scripts/run_protected_strata_holdout_expansion.py",
        "canonical_corpus_dir": str(corpus_dir),
        "output_corpus_dir": str(output_corpus_dir),
        "holdout_definition": str(args.output_holdout_jsonl),
        "audit_json": str(args.output_audit_json),
        "split": {
            "selected_seed": int(best["seed"]),
            "train_ratio": float(args.train_ratio),
            "val_ratio": float(args.val_ratio),
        },
        "boundary_definition": {
            "margin_threshold": float(args.near_boundary_margin_threshold),
            "uncertainty_threshold": float(args.near_boundary_uncertainty_threshold),
        },
        "protected_strata": [
            "exact_promoted_near_boundary",
            "exact_promoted_non_boundary",
            "approx_near_boundary",
            "approx_non_boundary",
            "low_budget_near_boundary",
            "low_budget_non_boundary",
            "extreme_low_budget_boundary_eligible",
        ],
    }
    _write_json(Path(args.output_manifest_json), manifest)

    print(json.dumps({"selected_seed": int(best["seed"]), "output_manifest_json": args.output_manifest_json}, indent=2))


if __name__ == "__main__":
    main()
