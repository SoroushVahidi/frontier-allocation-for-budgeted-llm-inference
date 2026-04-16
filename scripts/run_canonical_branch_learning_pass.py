#!/usr/bin/env python3
"""Run a matched learning pass from a canonical branch-learning corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (
    LearningConfig,
    prepare_learning_tables,
    scorer_from_model,
    train_models,
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _find_latest_real_corpus(root: Path) -> Path:
    if not root.exists():
        raise FileNotFoundError(f"Corpus root does not exist: {root}")
    candidates = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        if "fixture" in d.name.lower() or "test" in d.name.lower():
            continue
        if (d / "rows" / "candidate_rows.jsonl").exists() and (d / "rows" / "pairwise_rows.jsonl").exists():
            candidates.append(d)
    if not candidates:
        raise FileNotFoundError(f"No non-fixture canonical corpus found under {root}")
    return sorted(candidates, key=lambda p: p.stat().st_mtime)[-1]


def _to_allocator_tables(corpus_dir: Path) -> dict[str, list[dict[str, Any]]]:
    cands = _read_jsonl(corpus_dir / "rows" / "candidate_rows.jsonl")
    pairs = _read_jsonl(corpus_dir / "rows" / "pairwise_rows.jsonl")

    state_info: dict[str, dict[str, Any]] = {}
    by_state_count: dict[str, int] = {}
    for c in cands:
        sid = str(c["state_id"])
        by_state_count[sid] = by_state_count.get(sid, 0) + 1
        mode = "exact" if bool(c.get("is_exact_label", False)) else ("approx" if bool(c.get("is_approx_label", False)) else str(c.get("mode", "unknown")))
        state_info[sid] = {
            "state_id": sid,
            "dataset_name": str(c.get("dataset_name", "unknown")),
            "remaining_budget": int(c.get("remaining_budget", 0)),
            "candidate_mode": mode,
            "branch_count": 0,
        }
    for sid, n in by_state_count.items():
        state_info[sid]["branch_count"] = int(n)

    # map canonical field names expected by allocator helpers
    mapped_cands: list[dict[str, Any]] = []
    for c in cands:
        row = dict(c)
        row["mode"] = str(c.get("mode", "exact" if c.get("is_exact_label") else "approx"))
        mapped_cands.append(row)

    mapped_pairs: list[dict[str, Any]] = []
    for p in pairs:
        row = dict(p)
        row["pair_mode_provenance"] = str(p.get("pair_mode_provenance", "exact" if p.get("is_exact_label") else "approx"))
        mapped_pairs.append(row)

    return {
        "candidate_labels": mapped_cands,
        "pairwise_labels": mapped_pairs,
        "state_summaries": list(state_info.values()),
    }


def _predict_pair_label(score_fn: Callable[[dict[str, Any]], float], row: dict[str, Any]) -> int:
    si = float(score_fn({"x": row["x_i"]}))
    sj = float(score_fn({"x": row["x_j"]}))
    return 1 if si >= sj else 0


def _pairwise_accuracy(rows: list[dict[str, Any]], pred_fn: Callable[[dict[str, Any]], int], pred_filter: Callable[[dict[str, Any]], bool]) -> dict[str, float]:
    subset = [r for r in rows if r.get("split") == "test" and pred_filter(r)]
    if not subset:
        return {"n": 0.0, "acc": 0.0}
    ok = sum(1 for r in subset if pred_fn(r) == int(r.get("label", 0)))
    return {"n": float(len(subset)), "acc": float(ok / len(subset))}


def _top1_accuracy(state_to_candidates: dict[str, list[dict[str, Any]]], score_fn: Callable[[dict[str, Any]], float]) -> float:
    total = 0
    ok = 0
    for rows in state_to_candidates.values():
        test_rows = [r for r in rows if r.get("split") == "test"]
        if len(test_rows) < 2:
            continue
        pred = max(test_rows, key=score_fn)["branch_id"]
        truth = max(test_rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0)))["branch_id"]
        ok += int(pred == truth)
        total += 1
    return float(ok / max(1, total))


def _evaluate_model(name: str, score_fn: Callable[[dict[str, Any]], float], tables: dict[str, Any]) -> dict[str, Any]:
    pair_rows = tables["pairwise"]
    state_to_cands = tables["state_to_candidates"]
    state_branch_count = {sid: len(rows) for sid, rows in state_to_cands.items()}

    pred_fn = lambda r: _predict_pair_label(score_fn, r)

    agg = _pairwise_accuracy(pair_rows, pred_fn, lambda _r: True)
    near_tie = _pairwise_accuracy(pair_rows, pred_fn, lambda r: bool(r.get("near_tie_flag", False)))
    adjacent = _pairwise_accuracy(pair_rows, pred_fn, lambda r: bool(r.get("adjacent_rank_flag", False)))
    small_margin = _pairwise_accuracy(pair_rows, pred_fn, lambda r: bool(r.get("small_margin_flag", False)))
    exact_promoted = _pairwise_accuracy(pair_rows, pred_fn, lambda r: bool(r.get("replaced_approx_label", False)))
    exact_only = _pairwise_accuracy(pair_rows, pred_fn, lambda r: bool(r.get("is_exact_label", False)))
    approx_only = _pairwise_accuracy(pair_rows, pred_fn, lambda r: bool(r.get("is_approx_label", False)))

    by_dataset = {}
    datasets = sorted({str(r.get("dataset_name", "unknown")) for r in pair_rows if r.get("split") == "test"})
    for ds in datasets:
        by_dataset[ds] = _pairwise_accuracy(pair_rows, pred_fn, lambda r, d=ds: str(r.get("dataset_name", "unknown")) == d)

    by_budget = {}
    budgets = sorted({int(r.get("remaining_budget", 0)) for r in pair_rows if r.get("split") == "test"})
    for b in budgets:
        by_budget[str(b)] = _pairwise_accuracy(pair_rows, pred_fn, lambda r, bb=b: int(r.get("remaining_budget", 0)) == bb)

    by_branch_count = {}
    for bc in sorted({state_branch_count.get(str(r.get("state_id", "")), 0) for r in pair_rows if r.get("split") == "test"}):
        by_branch_count[str(bc)] = _pairwise_accuracy(
            pair_rows,
            pred_fn,
            lambda r, bb=bc: state_branch_count.get(str(r.get("state_id", "")), 0) == bb,
        )

    return {
        "model_name": name,
        "pairwise_accuracy_test": agg,
        "ranking_top1_accuracy_test": _top1_accuracy(state_to_cands, score_fn),
        "hard_slices": {
            "near_tie": near_tie,
            "adjacent_rank": adjacent,
            "small_margin": small_margin,
            "exact_promoted": exact_promoted,
            "exact_only": exact_only,
            "approx_only": approx_only,
        },
        "dataset_slices": by_dataset,
        "budget_slices": by_budget,
        "branch_count_slices": by_branch_count,
    }


def _apply_reweighting(tables: dict[str, Any], *, hard_case_mult: float, exact_promoted_mult: float) -> dict[str, Any]:
    for r in tables["pairwise"]:
        w = float(r.get("pair_train_weight", 1.0))
        if bool(r.get("near_tie_flag", False)) or bool(r.get("adjacent_rank_flag", False)) or bool(r.get("small_margin_flag", False)):
            w *= float(hard_case_mult)
        if bool(r.get("replaced_approx_label", False)):
            w *= float(exact_promoted_mult)
        r["pair_train_weight"] = max(1e-8, w)
    return tables


def _apply_balanced_hardcase_weighting(tables: dict[str, Any], *, target_boost: float) -> tuple[dict[str, Any], dict[str, Any]]:
    """Intervention: balance pairwise training weights across dataset/budget/hardness slices.

    Hardness bucket:
    - near_tie
    - adjacent_or_small_margin
    - other
    """
    train_rows = [r for r in tables["pairwise"] if r.get("split") == "train" and bool(r.get("include_for_pairwise_training", True))]
    if not train_rows:
        return tables, {"status": "no_train_rows"}

    def bucket(row: dict[str, Any]) -> str:
        if bool(row.get("near_tie_flag", False)):
            return "near_tie"
        if bool(row.get("adjacent_rank_flag", False)) or bool(row.get("small_margin_flag", False)):
            return "adjacent_or_small_margin"
        return "other"

    counts: dict[str, int] = {}
    for r in train_rows:
        key = f"{r.get('dataset_name', 'unknown')}|b{int(r.get('remaining_budget', 0))}|{bucket(r)}"
        counts[key] = counts.get(key, 0) + 1

    max_count = max(counts.values())
    multipliers = {k: (max_count / max(1, v)) ** float(target_boost) for k, v in counts.items()}

    for r in tables["pairwise"]:
        if r.get("split") != "train" or not bool(r.get("include_for_pairwise_training", True)):
            continue
        key = f"{r.get('dataset_name', 'unknown')}|b{int(r.get('remaining_budget', 0))}|{bucket(r)}"
        w = float(r.get("pair_train_weight", 1.0))
        r["pair_train_weight"] = max(1e-8, w * float(multipliers.get(key, 1.0)))

    meta = {
        "status": "ok",
        "bucket_counts_train": counts,
        "bucket_multiplier": multipliers,
        "target_boost": float(target_boost),
    }
    return tables, meta


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run canonical matched learning pass from canonical corpus")
    p.add_argument("--canonical-corpus-dir", default="")
    p.add_argument("--canonical-root", default="outputs/branch_learning_corpora")
    p.add_argument("--output-root", default="outputs/canonical_branch_learning_pass")
    p.add_argument("--run-id", default="canonical_learning_pass_20260416")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--hard-case-mult", type=float, default=1.5)
    p.add_argument("--exact-promoted-mult", type=float, default=1.75)
    p.add_argument("--feature-set", default="v2")
    p.add_argument("--uncertainty-weighting", action="store_true")
    p.add_argument(
        "--intervention",
        default="none",
        choices=["none", "balanced_hardcase_weighting"],
        help="Single targeted intervention under matched protocol.",
    )
    p.add_argument(
        "--intervention-target-boost",
        type=float,
        default=0.5,
        help="Exponent for balanced_hardcase_weighting inverse-frequency multiplier.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    corpus_dir = Path(args.canonical_corpus_dir) if args.canonical_corpus_dir else _find_latest_real_corpus(Path(args.canonical_root))
    out_dir = Path(args.output_root) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_data = _to_allocator_tables(corpus_dir)

    base_cfg = LearningConfig(
        seed=int(args.seed),
        near_tie_margin=float(args.near_tie_margin),
        feature_set=str(args.feature_set),
        uncertainty_weighting=bool(args.uncertainty_weighting),
        pairwise_near_tie_action="none",
        train_pairwise=True,
        train_pointwise=True,
        train_outside_option=True,
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
    )

    tables = prepare_learning_tables(raw_data, base_cfg)

    # Matched learner families.
    model_artifacts = out_dir / "model_artifacts"
    baseline_models = train_models(tables, base_cfg, model_artifact_dir=model_artifacts / "baseline")

    reweighted_tables = _apply_reweighting(
        prepare_learning_tables(raw_data, base_cfg),
        hard_case_mult=float(args.hard_case_mult),
        exact_promoted_mult=float(args.exact_promoted_mult),
    )
    reweighted_models = train_models(reweighted_tables, base_cfg, model_artifact_dir=model_artifacts / "reweighted")

    # Heuristic candidate-score baselines.
    heuristics: dict[str, Callable[[dict[str, Any]], float]] = {
        "heuristic_score_only": lambda row: float(row.get("features_branch_v1", {}).get("score", 0.0)),
        "heuristic_score_minus_uncertainty": lambda row: float(row.get("features_branch_v1", {}).get("score", 0.0))
        - float(row.get("allocation_value_std", 0.0)),
    }

    results: dict[str, Any] = {}

    for name, model in baseline_models.items():
        if str(model.get("status", "")) != "ok":
            continue
        results[f"baseline::{name}"] = _evaluate_model(f"baseline::{name}", scorer_from_model(model), tables)
        results[f"baseline::{name}"]["train_status"] = model.get("status", "unknown")

    for name, model in reweighted_models.items():
        if str(model.get("status", "")) != "ok":
            continue
        results[f"reweighted::{name}"] = _evaluate_model(f"reweighted::{name}", scorer_from_model(model), reweighted_tables)
        results[f"reweighted::{name}"]["train_status"] = model.get("status", "unknown")

    intervention_meta: dict[str, Any] = {"intervention": str(args.intervention), "status": "not_run"}
    intervention_models: dict[str, Any] = {}
    if str(args.intervention) == "balanced_hardcase_weighting":
        intervention_tables, intervention_meta = _apply_balanced_hardcase_weighting(
            prepare_learning_tables(raw_data, base_cfg),
            target_boost=float(args.intervention_target_boost),
        )
        intervention_models = train_models(
            intervention_tables,
            base_cfg,
            model_artifact_dir=model_artifacts / "intervention",
        )

    for name, fn in heuristics.items():
        results[name] = _evaluate_model(name, fn, tables)
        results[name]["train_status"] = "heuristic"

    if intervention_models:
        for name, model in intervention_models.items():
            if str(model.get("status", "")) != "ok":
                continue
            results[f"intervention::{name}"] = _evaluate_model(
                f"intervention::{name}",
                scorer_from_model(model),
                intervention_tables,
            )
            results[f"intervention::{name}"]["train_status"] = model.get("status", "unknown")

    ranking = sorted(
        [
            {
                "model": k,
                "pairwise_acc": float(v["pairwise_accuracy_test"]["acc"]),
                "pairwise_n": int(v["pairwise_accuracy_test"]["n"]),
                "top1_acc": float(v["ranking_top1_accuracy_test"]),
                "near_tie_acc": float(v["hard_slices"]["near_tie"]["acc"]),
                "near_tie_n": int(v["hard_slices"]["near_tie"]["n"]),
                "exact_promoted_acc": float(v["hard_slices"]["exact_promoted"]["acc"]),
                "exact_promoted_n": int(v["hard_slices"]["exact_promoted"]["n"]),
            }
            for k, v in results.items()
        ],
        key=lambda r: (r["pairwise_acc"], r["near_tie_acc"], r["top1_acc"]),
        reverse=True,
    )

    payload = {
        "run_id": args.run_id,
        "canonical_corpus_dir": str(corpus_dir),
        "config": {
            "seed": int(args.seed),
            "near_tie_margin": float(args.near_tie_margin),
            "feature_set": str(args.feature_set),
            "hard_case_mult": float(args.hard_case_mult),
            "exact_promoted_mult": float(args.exact_promoted_mult),
            "uncertainty_weighting": bool(args.uncertainty_weighting),
            "intervention": str(args.intervention),
            "intervention_target_boost": float(args.intervention_target_boost),
        },
        "intervention_meta": intervention_meta,
        "methods_compared": list(results.keys()),
        "ranking": ranking,
        "metrics": results,
    }

    _write_json(out_dir / "canonical_learning_summary.json", payload)

    lines = [
        "# Canonical branch-learning matched pass",
        "",
        f"- run_id: `{args.run_id}`",
        f"- canonical_corpus_dir: `{corpus_dir}`",
        f"- methods_compared: `{len(results)}`",
        "",
        "## Ranked aggregate view (pairwise test accuracy)",
    ]
    for row in ranking:
        lines.append(
            f"- {row['model']}: pairwise_acc={row['pairwise_acc']:.4f} (n={row['pairwise_n']}), "
            f"top1_acc={row['top1_acc']:.4f}, near_tie_acc={row['near_tie_acc']:.4f} (n={row['near_tie_n']}), "
            f"exact_promoted_acc={row['exact_promoted_acc']:.4f} (n={row['exact_promoted_n']})"
        )

    lines.extend(["", "## Per-model slices"]) 
    for name, m in results.items():
        lines.extend(
            [
                "",
                f"### {name}",
                f"- pairwise_test_acc: {m['pairwise_accuracy_test']['acc']:.4f} (n={int(m['pairwise_accuracy_test']['n'])})",
                f"- top1_test_acc: {m['ranking_top1_accuracy_test']:.4f}",
                f"- near_tie_test_acc: {m['hard_slices']['near_tie']['acc']:.4f} (n={int(m['hard_slices']['near_tie']['n'])})",
                f"- adjacent_rank_test_acc: {m['hard_slices']['adjacent_rank']['acc']:.4f} (n={int(m['hard_slices']['adjacent_rank']['n'])})",
                f"- small_margin_test_acc: {m['hard_slices']['small_margin']['acc']:.4f} (n={int(m['hard_slices']['small_margin']['n'])})",
                f"- exact_promoted_test_acc: {m['hard_slices']['exact_promoted']['acc']:.4f} (n={int(m['hard_slices']['exact_promoted']['n'])})",
                f"- exact_only_test_acc: {m['hard_slices']['exact_only']['acc']:.4f} (n={int(m['hard_slices']['exact_only']['n'])})",
                f"- approx_only_test_acc: {m['hard_slices']['approx_only']['acc']:.4f} (n={int(m['hard_slices']['approx_only']['n'])})",
                f"- dataset_slices: {m['dataset_slices']}",
                f"- budget_slices: {m['budget_slices']}",
                f"- branch_count_slices: {m['branch_count_slices']}",
            ]
        )

    (out_dir / "canonical_learning_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out_dir), "summary": str(out_dir / 'canonical_learning_summary.json')}, indent=2))


if __name__ == "__main__":
    main()
