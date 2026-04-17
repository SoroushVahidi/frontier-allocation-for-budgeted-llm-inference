#!/usr/bin/env python3
"""Run one bounded Confident-Learning-style hard-pair cleanup pass.

This pass:
1) scores suspicious hard pairs using out-of-fold model-vs-label inconsistency,
2) writes an auditable suspicious-pair ranking artifact,
3) builds one cleaned regime by excluding only the worst suspicious hard pairs,
4) preserves broad coverage by keeping all non-hard pairs and most hard pairs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from sklearn.linear_model import LogisticRegression

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import LearningConfig, load_label_artifacts, prepare_learning_tables


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _stable_hash_int(text: str) -> int:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def _pair_key(row: dict[str, Any]) -> tuple[str, str, str]:
    sid = str(row.get("state_id", ""))
    bi = str(row.get("branch_i", ""))
    bj = str(row.get("branch_j", ""))
    a, b = sorted([bi, bj])
    return (sid, a, b)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded CL-style hard-pair cleanup pass")
    p.add_argument("--labels-dir", required=True, help="Input labels dir (typically regime_all_pairs)")
    p.add_argument("--run-id", required=True)
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    p.add_argument("--low-margin-threshold", type=float, default=0.08)
    p.add_argument("--high-std-threshold", type=float, default=0.08)
    p.add_argument("--hard-relative-margin-threshold", type=float, default=0.15)
    p.add_argument("--cv-folds", type=int, default=5)
    p.add_argument("--feature-set", choices=["v1", "v2"], default="v2")
    p.add_argument("--suspicious-top-hard-fraction", type=float, default=0.15)
    p.add_argument("--max-exclude-hard", type=int, default=32)
    p.add_argument("--min-hard-exclude", type=int, default=8)
    return p.parse_args()


def _hard_flags(row: dict[str, Any], args: argparse.Namespace) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    margin_abs = float(row.get("margin_abs", abs(float(row.get("margin", 0.0)))) )
    rel_margin = float(row.get("relative_margin", 1e9))
    pair_std = float(row.get("pair_uncertainty_std_mean", row.get("pair_allocation_value_std", 0.0)))
    near_tie = bool(row.get("near_tie_flag", margin_abs <= float(args.near_tie_margin)))
    pair_type = str(row.get("pair_type", "generic"))
    pair_mode = str(row.get("pair_mode_provenance", row.get("pair_mode", "unknown")))

    if near_tie:
        reasons.append("near_tie")
    if pair_type == "adjacent_rank":
        reasons.append("adjacent_rank")
    if margin_abs <= float(args.low_margin_threshold):
        reasons.append("low_margin")
    if rel_margin <= float(args.hard_relative_margin_threshold):
        reasons.append("low_relative_margin")
    if pair_std >= float(args.high_std_threshold):
        reasons.append("high_uncertainty_std")
    if (pair_mode == "approx") and (margin_abs <= float(args.low_margin_threshold)) and (pair_std >= float(args.high_std_threshold)):
        reasons.append("approx_low_margin_high_std_disagreement_prone")
    return (len(reasons) > 0, reasons)


def _fit_predict_oof(rows: list[dict[str, Any]], folds: int, seed: int) -> list[float]:
    probs = [0.5 for _ in rows]
    fold_ids = [_stable_hash_int(f"{seed}|{r['state_id']}") % max(2, folds) for r in rows]

    for fold in range(max(2, folds)):
        train_idx = [i for i, f in enumerate(fold_ids) if f != fold]
        test_idx = [i for i, f in enumerate(fold_ids) if f == fold]
        if not test_idx:
            continue
        x_train = [rows[i]["x_diff"] for i in train_idx]
        y_train = [int(rows[i]["label"]) for i in train_idx]
        w_train = [float(rows[i].get("pair_train_weight", 1.0)) for i in train_idx]

        if len(set(y_train)) < 2:
            p = 0.99 if (y_train and int(y_train[0]) == 1) else 0.01
            for i in test_idx:
                probs[i] = p
            continue

        model = LogisticRegression(max_iter=500, random_state=seed)
        model.fit(x_train, y_train, sample_weight=w_train)

        x_test = [rows[i]["x_diff"] for i in test_idx]
        fold_probs = model.predict_proba(x_test)[:, 1]
        for i, pp in zip(test_idx, fold_probs):
            probs[i] = float(pp)
    return probs


def main() -> None:
    args = parse_args()
    labels_dir = Path(args.labels_dir)

    cfg = LearningConfig(seed=17, near_tie_margin=float(args.near_tie_margin), feature_set=str(args.feature_set))
    artifacts = load_label_artifacts(labels_dir)
    tables = prepare_learning_tables(artifacts, cfg)

    pair_rows = [dict(r) for r in tables["pairwise"]]
    oof_probs = _fit_predict_oof(pair_rows, folds=int(args.cv_folds), seed=cfg.seed)

    scored: list[dict[str, Any]] = []
    for row, p_i in zip(pair_rows, oof_probs):
        y = int(row.get("label", 0))
        p_obs = float(p_i if y == 1 else (1.0 - p_i))
        p_wrong = float(1.0 - p_obs)
        pred_label = 1 if p_i >= 0.5 else 0
        is_hard, hard_reasons = _hard_flags(row, args)
        severity = p_wrong
        if "near_tie" in hard_reasons:
            severity *= 1.10
        if "adjacent_rank" in hard_reasons:
            severity *= 1.10
        if "high_uncertainty_std" in hard_reasons:
            severity *= 1.05
        if "approx_low_margin_high_std_disagreement_prone" in hard_reasons:
            severity *= 1.15

        scored.append(
            {
                "state_id": str(row.get("state_id", "")),
                "example_id": str(row.get("example_id", "")),
                "dataset_name": str(row.get("dataset_name", "unknown")),
                "remaining_budget": int(row.get("remaining_budget", 0)),
                "branch_i": str(row.get("branch_i", "")),
                "branch_j": str(row.get("branch_j", "")),
                "label": y,
                "pred_label": pred_label,
                "pred_prob_branch_i": float(p_i),
                "observed_label_confidence": p_obs,
                "predicted_label_error_prob": p_wrong,
                "suspicious_score": float(severity),
                "hard_region_flag": bool(is_hard),
                "hard_region_reasons": hard_reasons,
                "pair_type": str(row.get("pair_type", "generic")),
                "near_tie_flag": bool(row.get("near_tie_flag", False)),
                "margin_abs": float(row.get("margin_abs", abs(float(row.get("margin", 0.0))))),
                "relative_margin": float(row.get("relative_margin", 0.0)),
                "pair_uncertainty_std_mean": float(row.get("pair_uncertainty_std_mean", row.get("pair_allocation_value_std", 0.0))),
                "pair_mode_provenance": str(row.get("pair_mode_provenance", row.get("pair_mode", "unknown"))),
                "label_source": str(row.get("label_source", "unknown")),
            }
        )

    hard_scored = [r for r in scored if bool(r["hard_region_flag"])]
    hard_scored = sorted(hard_scored, key=lambda r: float(r["suspicious_score"]), reverse=True)

    n_hard = len(hard_scored)
    raw_take = int(round(float(args.suspicious_top_hard_fraction) * n_hard))
    n_exclude = max(int(args.min_hard_exclude), raw_take)
    n_exclude = min(n_exclude, int(args.max_exclude_hard), n_hard)
    exclude_keys = {_pair_key(r) for r in hard_scored[:n_exclude]}

    base_pairs = _read_jsonl(labels_dir / "pairwise_labels.jsonl")
    cleaned_pairs = [r for r in base_pairs if _pair_key(r) not in exclude_keys]

    output_root = Path(args.output_root)
    ranking_dir = output_root / "suspicious_hard_pairs" / args.run_id
    ranking_dir.mkdir(parents=True, exist_ok=True)

    ranking_rows = []
    for rank, r in enumerate(hard_scored, start=1):
        out = dict(r)
        out["rank"] = rank
        out["selected_for_cleanup_exclusion"] = bool(_pair_key(r) in exclude_keys)
        ranking_rows.append(out)

    _write_jsonl(ranking_dir / "suspicious_pair_ranking.jsonl", ranking_rows)
    (ranking_dir / "suspicious_pair_ranking_top200.json").write_text(json.dumps(ranking_rows[:200], indent=2), encoding="utf-8")

    targets_root = output_root / "branch_label_bruteforce_targets" / args.run_id
    baseline_dir = targets_root / "regime_all_pairs_baseline"
    cleaned_dir = targets_root / "regime_cl_hardpair_excluded"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    cands = _read_jsonl(labels_dir / "candidate_labels.jsonl")
    states = _read_jsonl(labels_dir / "state_summaries.jsonl")

    _write_jsonl(baseline_dir / "candidate_labels.jsonl", cands)
    _write_jsonl(baseline_dir / "pairwise_labels.jsonl", base_pairs)
    _write_jsonl(baseline_dir / "state_summaries.jsonl", states)

    _write_jsonl(cleaned_dir / "candidate_labels.jsonl", cands)
    _write_jsonl(cleaned_dir / "pairwise_labels.jsonl", cleaned_pairs)
    _write_jsonl(cleaned_dir / "state_summaries.jsonl", states)

    near_tie_base = sum(1 for r in base_pairs if bool(r.get("near_tie_flag", False)))
    near_tie_clean = sum(1 for r in cleaned_pairs if bool(r.get("near_tie_flag", False)))

    summary = {
        "run_id": args.run_id,
        "input_labels_dir": str(labels_dir),
        "ranking_artifact": str(ranking_dir / "suspicious_pair_ranking.jsonl"),
        "targets_root": str(targets_root),
        "method": {
            "name": "bounded_confident_learning_style_hard_pair_error_ranking_v1",
            "oof_model": "pairwise_logistic_regression",
            "oof_cv_folds": int(args.cv_folds),
            "suspicious_score": "(1-p_observed_label) with hard-region severity multipliers",
            "hard_region_definition": {
                "near_tie_margin": float(args.near_tie_margin),
                "low_margin_threshold": float(args.low_margin_threshold),
                "hard_relative_margin_threshold": float(args.hard_relative_margin_threshold),
                "high_std_threshold": float(args.high_std_threshold),
                "adjacent_rank": True,
            },
            "cleanup_action": "exclude_top_suspicious_hard_pairs",
        },
        "counts": {
            "base_pairs": len(base_pairs),
            "hard_pairs_scored": len(hard_scored),
            "excluded_pairs": len(exclude_keys),
            "cleaned_pairs": len(cleaned_pairs),
            "base_near_tie_pairs": near_tie_base,
            "cleaned_near_tie_pairs": near_tie_clean,
            "overall_retention_rate": len(cleaned_pairs) / max(1, len(base_pairs)),
            "hard_exclusion_rate": len(exclude_keys) / max(1, len(hard_scored)),
        },
    }
    (targets_root / "cl_hard_pair_cleanup_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# Bounded CL-style hard-pair cleanup summary",
        "",
        f"- run_id: `{args.run_id}`",
        f"- input labels: `{labels_dir}`",
        f"- suspicious ranking: `{ranking_dir / 'suspicious_pair_ranking.jsonl'}`",
        f"- cleanup action: `exclude_top_suspicious_hard_pairs`",
        f"- base pairs: `{len(base_pairs)}`",
        f"- hard pairs scored: `{len(hard_scored)}`",
        f"- excluded hard pairs: `{len(exclude_keys)}`",
        f"- cleaned pairs: `{len(cleaned_pairs)}`",
        f"- retention rate: `{summary['counts']['overall_retention_rate']:.4f}`",
        f"- near-tie pairs retained: `{near_tie_clean}/{near_tie_base}`",
    ]
    (targets_root / "cl_hard_pair_cleanup_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"targets_root": str(targets_root), "ranking_dir": str(ranking_dir), "excluded_pairs": len(exclude_keys)}, indent=2))


if __name__ == "__main__":
    main()
