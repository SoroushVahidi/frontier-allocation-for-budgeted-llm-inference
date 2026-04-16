#!/usr/bin/env python3
"""Run a matched learning pass from a canonical branch-learning corpus."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable
import sys

import numpy as np
from sklearn.linear_model import Ridge

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


def _extract_step_idx(branch_id: str) -> int:
    m = re.search(r"step(\d+)", branch_id)
    if m:
        return int(m.group(1))
    m = re.search(r"cand(\d+)$", branch_id)
    return int(m.group(1)) if m else 0


def _external_prm_candidate_to_x(row: dict[str, Any], *, feature_names: list[str]) -> list[float]:
    """Map PRM candidate rows to canonical features conservatively (derived supervision)."""
    quality = float(row.get("quality_score", 0.0))
    step_idx = _extract_step_idx(str(row.get("branch_id", "")))
    comp_idx_match = re.search(r"cand(\d+)$", str(row.get("branch_id", "")))
    comp_idx = int(comp_idx_match.group(1)) if comp_idx_match else 0
    supervision_origin = str(row.get("supervision_origin", "derived"))
    feat = {k: 0.0 for k in feature_names}
    feat["remaining_budget"] = float(row.get("remaining_budget", 1.0))
    feat["score"] = quality
    feat["depth"] = float(step_idx + 1)
    feat["recent_delta"] = quality - 0.5
    feat["stalled_steps"] = 1.0 if quality <= 0.25 else 0.0
    feat["verify_count"] = 0.0
    feat["branch_age"] = float(step_idx + 1)
    feat["parent_relative_score"] = -float(comp_idx)
    feat["allocation_candidates_evaluated"] = float(comp_idx + 1)
    feat["allocation_value_std"] = quality * (1.0 - quality)
    feat["mode_exact"] = 1.0 if supervision_origin.startswith("native") else 0.0
    feat["mode_approx"] = 0.0 if feat["mode_exact"] > 0 else 1.0
    feat["mode_degenerate"] = 0.0
    return [float(feat.get(name, 0.0)) for name in feature_names]


def _fit_external_prm_pointwise_prior(
    external_corpus_dir: Path,
    *,
    feature_names: list[str],
    source_dataset_key: str,
    source_split: str,
) -> dict[str, Any]:
    path = external_corpus_dir / "rows" / "candidate_rows.jsonl"
    if not path.exists():
        return {"status": "external_candidate_rows_missing", "path": str(path)}
    rows = _read_jsonl(path)
    rows = [
        r
        for r in rows
        if str(r.get("source_dataset_key", "")) == source_dataset_key and str(r.get("source_split", "")) == source_split
    ]
    if len(rows) < 8:
        return {"status": "insufficient_external_rows", "n": len(rows)}
    x = [_external_prm_candidate_to_x(r, feature_names=feature_names) for r in rows]
    y = [float(r.get("quality_score", 0.0)) for r in rows]
    y_mean = float(np.mean(y))
    y_std = float(np.std(y))
    x_arr = np.array(x, dtype=float)
    x_std = np.std(x_arr, axis=0) if x_arr.size else np.array([])
    nonconstant_features = int(np.sum(x_std > 1e-8)) if x_arr.size else 0
    if y_std <= 1e-8:
        return {
            "status": "degenerate_target_variance",
            "n": len(rows),
            "target_mean": y_mean,
            "target_std": y_std,
            "nonconstant_feature_count": nonconstant_features,
        }
    model = Ridge(alpha=1.0, random_state=17)
    model.fit(x, y)
    return {
        "status": "ok",
        "n": len(rows),
        "target_mean": y_mean,
        "target_std": y_std,
        "nonconstant_feature_count": nonconstant_features,
        "feature_names": feature_names,
        "weights": [float(v) for v in model.coef_],
        "intercept": float(model.intercept_),
        "source_dataset_key": source_dataset_key,
        "source_split": source_split,
    }


def _blended_linear_scorer(
    base_model: dict[str, Any],
    ext_prior: dict[str, Any],
    *,
    blend_alpha: float,
    norm_match_to_base: bool = True,
) -> Callable[[dict[str, Any]], float]:
    wb = np.array([float(v) for v in base_model.get("weights", [])], dtype=float)
    bb = float(base_model.get("intercept", 0.0))
    we = np.array([float(v) for v in ext_prior.get("weights", [])], dtype=float)
    be = float(ext_prior.get("intercept", 0.0))
    if wb.shape != we.shape or wb.size == 0:
        return scorer_from_model(base_model)
    if norm_match_to_base:
        base_norm = float(np.linalg.norm(wb))
        ext_norm = float(np.linalg.norm(we))
        if base_norm > 1e-12 and ext_norm > 1e-12:
            we = we * (base_norm / ext_norm)
    w = (1.0 - blend_alpha) * wb + blend_alpha * we
    b = (1.0 - blend_alpha) * bb + blend_alpha * be
    return lambda row: float(np.dot(w, np.array(row["x"], dtype=float)) + b)


def _uncertainty_gated_blended_scorer(
    base_model: dict[str, Any],
    ext_prior: dict[str, Any],
    *,
    blend_alpha: float,
    std_threshold: float,
    gap_threshold: float,
) -> Callable[[dict[str, Any]], float]:
    base_fn = scorer_from_model(base_model)
    broad_fn = _blended_linear_scorer(
        base_model,
        ext_prior,
        blend_alpha=blend_alpha,
        norm_match_to_base=True,
    )

    def _gate(row: dict[str, Any]) -> float:
        std = float(row.get("allocation_value_std", 0.0))
        f2 = row.get("features_branch_v2", {}) if isinstance(row.get("features_branch_v2"), dict) else {}
        gap_to_top = abs(float(f2.get("score_gap_to_top", 0.0)))
        hard_flag = bool(std >= std_threshold or gap_to_top <= gap_threshold)
        return 1.0 if hard_flag else 0.0

    return lambda row: float(base_fn(row) + _gate(row) * (broad_fn(row) - base_fn(row)))


def _external_activity_diagnostics(
    *,
    base_fn: Callable[[dict[str, Any]], float],
    ext_fn: Callable[[dict[str, Any]], float],
    tables: dict[str, Any],
    uncertainty_std_threshold: float,
    top_gap_threshold: float,
) -> dict[str, Any]:
    test_cands = [r for r in tables["candidates"] if r.get("split") == "test"]
    if not test_cands:
        return {"status": "no_test_candidates"}
    score_deltas = [abs(float(ext_fn(r)) - float(base_fn(r))) for r in test_cands]
    targeted = 0
    targeted_changed = 0
    changed = 0
    for r, d in zip(test_cands, score_deltas):
        f2 = r.get("features_branch_v2", {}) if isinstance(r.get("features_branch_v2"), dict) else {}
        is_targeted = bool(
            float(r.get("allocation_value_std", 0.0)) >= uncertainty_std_threshold
            or abs(float(f2.get("score_gap_to_top", 0.0))) <= top_gap_threshold
        )
        targeted += int(is_targeted)
        changed += int(d > 1e-9)
        targeted_changed += int(is_targeted and d > 1e-9)

    pair_rows = [r for r in tables["pairwise"] if r.get("split") == "test"]
    changed_pair = 0
    changed_pair_hard = 0
    hard_n = 0
    for r in pair_rows:
        b_label = _predict_pair_label(base_fn, r)
        e_label = _predict_pair_label(ext_fn, r)
        diff = int(b_label != e_label)
        changed_pair += diff
        hard = bool(r.get("near_tie_flag", False) or r.get("adjacent_rank_flag", False) or r.get("small_margin_flag", False))
        hard_n += int(hard)
        changed_pair_hard += int(diff and hard)

    return {
        "status": "ok",
        "candidate_test_n": len(test_cands),
        "candidate_score_shift_mean_abs": float(np.mean(score_deltas)),
        "candidate_score_shift_max_abs": float(np.max(score_deltas)),
        "candidate_changed_fraction": float(changed / max(1, len(test_cands))),
        "targeted_candidate_n": int(targeted),
        "targeted_candidate_fraction": float(targeted / max(1, len(test_cands))),
        "targeted_changed_fraction": float(targeted_changed / max(1, max(1, targeted))),
        "pair_test_n": len(pair_rows),
        "pair_decision_changed_n": int(changed_pair),
        "pair_decision_changed_fraction": float(changed_pair / max(1, len(pair_rows))),
        "pair_hard_slice_n": int(hard_n),
        "pair_hard_slice_changed_n": int(changed_pair_hard),
    }


def _comparator_boundary_pair_predictor(
    *,
    base_fn: Callable[[dict[str, Any]], float],
    external_fn: Callable[[dict[str, Any]], float],
    pair_margin_threshold: float,
    pair_uncertainty_std_threshold: float,
) -> Callable[[dict[str, Any]], int]:
    def _pred(row: dict[str, Any]) -> int:
        b_i = float(base_fn({"x": row["x_i"]}))
        b_j = float(base_fn({"x": row["x_j"]}))
        base_margin = b_i - b_j
        pair_std = float(row.get("pair_uncertainty_std_mean", 0.0))
        eligible = bool(abs(base_margin) <= pair_margin_threshold and pair_std >= pair_uncertainty_std_threshold)
        if eligible:
            e_i = float(external_fn({"x": row["x_i"]}))
            e_j = float(external_fn({"x": row["x_j"]}))
            return 1 if e_i >= e_j else 0
        return 1 if base_margin >= 0.0 else 0

    return _pred


def _boundary_intervention_diagnostics(
    *,
    tables: dict[str, Any],
    base_score_fn: Callable[[dict[str, Any]], float],
    external_score_fn: Callable[[dict[str, Any]], float],
    boundary_pair_pred_fn: Callable[[dict[str, Any]], int],
    pair_margin_threshold: float,
    pair_uncertainty_std_threshold: float,
) -> dict[str, Any]:
    pair_rows = [r for r in tables["pairwise"] if r.get("split") == "test"]
    if not pair_rows:
        return {"status": "no_test_pairs"}

    eligible_n = 0
    eligible_external_disagree_n = 0
    changed_n = 0
    helpful_n = 0
    harmful_n = 0
    changed_by_dataset: dict[str, int] = {}
    changed_by_budget: dict[str, int] = {}
    changed_hard_slice_n = 0

    for row in pair_rows:
        b_i = float(base_score_fn({"x": row["x_i"]}))
        b_j = float(base_score_fn({"x": row["x_j"]}))
        margin = b_i - b_j
        pair_std = float(row.get("pair_uncertainty_std_mean", 0.0))
        eligible = bool(abs(margin) <= pair_margin_threshold and pair_std >= pair_uncertainty_std_threshold)
        eligible_n += int(eligible)
        base_pred = 1 if margin >= 0.0 else 0
        ext_pred = 1 if float(external_score_fn({"x": row["x_i"]})) >= float(external_score_fn({"x": row["x_j"]})) else 0
        eligible_external_disagree_n += int(eligible and ext_pred != base_pred)
        new_pred = int(boundary_pair_pred_fn(row))
        changed = int(base_pred != new_pred)
        changed_n += changed
        if changed:
            truth = int(row.get("label", 0))
            helpful_n += int(new_pred == truth and base_pred != truth)
            harmful_n += int(new_pred != truth and base_pred == truth)
            ds = str(row.get("dataset_name", "unknown"))
            changed_by_dataset[ds] = changed_by_dataset.get(ds, 0) + 1
            b = str(int(row.get("remaining_budget", 0)))
            changed_by_budget[b] = changed_by_budget.get(b, 0) + 1
            hard = bool(row.get("near_tie_flag", False) or row.get("adjacent_rank_flag", False) or row.get("small_margin_flag", False))
            changed_hard_slice_n += int(hard)

    state_to_cands = tables["state_to_candidates"]
    top1_total = 0
    top1_changed = 0
    top1_helpful = 0
    top1_harmful = 0
    for rows in state_to_cands.values():
        test_rows = [r for r in rows if r.get("split") == "test"]
        if len(test_rows) < 2:
            continue
        top1_total += 1
        base_top = max(test_rows, key=base_score_fn)["branch_id"]
        new_top = _state_top1_from_pair_predictor(test_rows, boundary_pair_pred_fn, base_score_fn)
        truth = max(test_rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0)))["branch_id"]
        changed = int(base_top != new_top)
        top1_changed += changed
        if changed:
            top1_helpful += int(new_top == truth and base_top != truth)
            top1_harmful += int(new_top != truth and base_top == truth)

    return {
        "status": "ok",
        "pair_test_n": len(pair_rows),
        "eligible_pair_n": int(eligible_n),
        "eligible_pair_fraction": float(eligible_n / max(1, len(pair_rows))),
        "eligible_external_disagree_n": int(eligible_external_disagree_n),
        "changed_pair_n": int(changed_n),
        "changed_pair_fraction": float(changed_n / max(1, len(pair_rows))),
        "changed_pair_helpful_n": int(helpful_n),
        "changed_pair_harmful_n": int(harmful_n),
        "changed_pair_neutral_n": int(max(0, changed_n - helpful_n - harmful_n)),
        "changed_pair_hard_slice_n": int(changed_hard_slice_n),
        "changed_pair_by_dataset": changed_by_dataset,
        "changed_pair_by_budget": changed_by_budget,
        "top1_test_state_n": int(top1_total),
        "top1_changed_state_n": int(top1_changed),
        "top1_changed_helpful_n": int(top1_helpful),
        "top1_changed_harmful_n": int(top1_harmful),
        "top1_changed_neutral_n": int(max(0, top1_changed - top1_helpful - top1_harmful)),
        "pair_margin_threshold": float(pair_margin_threshold),
        "pair_uncertainty_std_threshold": float(pair_uncertainty_std_threshold),
    }


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


def _state_top1_from_pair_predictor(
    rows: list[dict[str, Any]],
    pair_pred_fn: Callable[[dict[str, Any]], int],
    score_fn_tiebreak: Callable[[dict[str, Any]], float],
) -> str:
    if not rows:
        return ""
    if len(rows) == 1:
        return str(rows[0].get("branch_id", ""))
    win_counts: dict[str, int] = {str(r.get("branch_id", "")): 0 for r in rows}
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            ri = rows[i]
            rj = rows[j]
            pred = int(
                pair_pred_fn(
                    {
                        "x_i": ri["x"],
                        "x_j": rj["x"],
                    }
                )
            )
            winner = str(ri.get("branch_id", "")) if pred == 1 else str(rj.get("branch_id", ""))
            win_counts[winner] = win_counts.get(winner, 0) + 1
    return max(
        rows,
        key=lambda r: (
            win_counts.get(str(r.get("branch_id", "")), 0),
            float(score_fn_tiebreak(r)),
        ),
    )["branch_id"]


def _top1_accuracy_with_pair_predictor(
    state_to_candidates: dict[str, list[dict[str, Any]]],
    *,
    pair_pred_fn: Callable[[dict[str, Any]], int],
    score_fn_tiebreak: Callable[[dict[str, Any]], float],
) -> float:
    total = 0
    ok = 0
    for rows in state_to_candidates.values():
        test_rows = [r for r in rows if r.get("split") == "test"]
        if len(test_rows) < 2:
            continue
        pred = _state_top1_from_pair_predictor(test_rows, pair_pred_fn, score_fn_tiebreak)
        truth = max(test_rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0)))["branch_id"]
        ok += int(pred == truth)
        total += 1
    return float(ok / max(1, total))


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


def _evaluate_model(
    name: str,
    score_fn: Callable[[dict[str, Any]], float],
    tables: dict[str, Any],
    *,
    pair_pred_fn: Callable[[dict[str, Any]], int] | None = None,
) -> dict[str, Any]:
    pair_rows = tables["pairwise"]
    state_to_cands = tables["state_to_candidates"]
    state_branch_count = {sid: len(rows) for sid, rows in state_to_cands.items()}

    pred_fn = pair_pred_fn if pair_pred_fn is not None else (lambda r: _predict_pair_label(score_fn, r))

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
        "ranking_top1_accuracy_test": (
            _top1_accuracy_with_pair_predictor(state_to_cands, pair_pred_fn=pred_fn, score_fn_tiebreak=score_fn)
            if pair_pred_fn is not None
            else _top1_accuracy(state_to_cands, score_fn)
        ),
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
    p.add_argument(
        "--external-supervision",
        default="none",
        choices=[
            "none",
            "prm800k_pointwise_blend",
            "prm800k_uncertainty_gated_blend",
            "prm800k_comparator_boundary_tiebreak",
        ],
        help="Conservative external auxiliary supervision path.",
    )
    p.add_argument("--external-prm-corpus-dir", default="")
    p.add_argument("--external-source-key", default="prm800k")
    p.add_argument("--external-source-split", default="train")
    p.add_argument("--external-pointwise-blend-alpha", type=float, default=0.2)
    p.add_argument("--external-gate-uncertainty-std-threshold", type=float, default=0.03)
    p.add_argument("--external-gate-top-gap-threshold", type=float, default=0.04)
    p.add_argument("--external-boundary-pair-margin-threshold", type=float, default=0.02)
    p.add_argument("--external-boundary-pair-uncertainty-std-threshold", type=float, default=0.02)
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

    external_meta: dict[str, Any] = {"external_supervision": str(args.external_supervision), "status": "not_run"}
    if str(args.external_supervision) in {
        "prm800k_pointwise_blend",
        "prm800k_uncertainty_gated_blend",
        "prm800k_comparator_boundary_tiebreak",
    }:
        ext_dir = Path(args.external_prm_corpus_dir) if args.external_prm_corpus_dir else None
        if ext_dir is None:
            external_meta = {"external_supervision": str(args.external_supervision), "status": "missing_external_prm_corpus_dir"}
        else:
            ext_prior = _fit_external_prm_pointwise_prior(
                ext_dir,
                feature_names=list(tables.get("feature_names", [])),
                source_dataset_key=str(args.external_source_key),
                source_split=str(args.external_source_split),
            )
            external_meta = {
                "external_supervision": str(args.external_supervision),
                "external_prm_corpus_dir": str(ext_dir),
                "external_source_key": str(args.external_source_key),
                "external_source_split": str(args.external_source_split),
                "external_pointwise_blend_alpha": float(args.external_pointwise_blend_alpha),
                "external_gate_uncertainty_std_threshold": float(args.external_gate_uncertainty_std_threshold),
                "external_gate_top_gap_threshold": float(args.external_gate_top_gap_threshold),
                "external_boundary_pair_margin_threshold": float(args.external_boundary_pair_margin_threshold),
                "external_boundary_pair_uncertainty_std_threshold": float(args.external_boundary_pair_uncertainty_std_threshold),
                "prior_fit": ext_prior,
                "status": "base_or_prior_unavailable",
            }
            pointwise_model = reweighted_models.get("pointwise", {})
            if str(pointwise_model.get("status", "")) == "ok" and str(ext_prior.get("status", "")) == "ok":
                base_fn = scorer_from_model(pointwise_model)
                broad_fn = _blended_linear_scorer(
                    pointwise_model,
                    ext_prior,
                    blend_alpha=float(args.external_pointwise_blend_alpha),
                )
                broad_key = "external::prm800k_pointwise_blend_from_reweighted_pointwise"
                results[broad_key] = _evaluate_model(broad_key, broad_fn, reweighted_tables)
                results[broad_key]["train_status"] = "ok_external_blend"
                test_rows = [r for r in reweighted_tables["candidates"] if r.get("split") == "test"]
                if test_rows:
                    deltas = [abs(float(broad_fn(r)) - float(base_fn(r))) for r in test_rows]
                    external_meta["score_shift_test_mean_abs"] = float(np.mean(deltas))
                    external_meta["score_shift_test_max_abs"] = float(np.max(deltas))

                external_meta["broad_blend_activity"] = _external_activity_diagnostics(
                    base_fn=base_fn,
                    ext_fn=broad_fn,
                    tables=reweighted_tables,
                    uncertainty_std_threshold=float(args.external_gate_uncertainty_std_threshold),
                    top_gap_threshold=float(args.external_gate_top_gap_threshold),
                )

                if str(args.external_supervision) == "prm800k_uncertainty_gated_blend":
                    aligned_fn = _uncertainty_gated_blended_scorer(
                        pointwise_model,
                        ext_prior,
                        blend_alpha=float(args.external_pointwise_blend_alpha),
                        std_threshold=float(args.external_gate_uncertainty_std_threshold),
                        gap_threshold=float(args.external_gate_top_gap_threshold),
                    )
                    aligned_key = "external::prm800k_uncertainty_gated_blend_from_reweighted_pointwise"
                    results[aligned_key] = _evaluate_model(aligned_key, aligned_fn, reweighted_tables)
                    results[aligned_key]["train_status"] = "ok_external_aligned_blend"
                    external_meta["aligned_blend_activity"] = _external_activity_diagnostics(
                        base_fn=base_fn,
                        ext_fn=aligned_fn,
                        tables=reweighted_tables,
                        uncertainty_std_threshold=float(args.external_gate_uncertainty_std_threshold),
                        top_gap_threshold=float(args.external_gate_top_gap_threshold),
                    )
                elif str(args.external_supervision) == "prm800k_comparator_boundary_tiebreak":
                    boundary_pair_pred = _comparator_boundary_pair_predictor(
                        base_fn=base_fn,
                        external_fn=broad_fn,
                        pair_margin_threshold=float(args.external_boundary_pair_margin_threshold),
                        pair_uncertainty_std_threshold=float(args.external_boundary_pair_uncertainty_std_threshold),
                    )
                    boundary_key = "external::prm800k_comparator_boundary_tiebreak_from_reweighted_pointwise"
                    results[boundary_key] = _evaluate_model(
                        boundary_key,
                        base_fn,
                        reweighted_tables,
                        pair_pred_fn=boundary_pair_pred,
                    )
                    results[boundary_key]["train_status"] = "ok_external_boundary_tiebreak"
                    external_meta["boundary_tiebreak_diagnostics"] = _boundary_intervention_diagnostics(
                        tables=reweighted_tables,
                        base_score_fn=base_fn,
                        external_score_fn=broad_fn,
                        boundary_pair_pred_fn=boundary_pair_pred,
                        pair_margin_threshold=float(args.external_boundary_pair_margin_threshold),
                        pair_uncertainty_std_threshold=float(args.external_boundary_pair_uncertainty_std_threshold),
                    )
                external_meta["status"] = "ok"

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
            "external_supervision": str(args.external_supervision),
            "external_prm_corpus_dir": str(args.external_prm_corpus_dir),
            "external_source_key": str(args.external_source_key),
            "external_source_split": str(args.external_source_split),
            "external_pointwise_blend_alpha": float(args.external_pointwise_blend_alpha),
            "external_gate_uncertainty_std_threshold": float(args.external_gate_uncertainty_std_threshold),
            "external_gate_top_gap_threshold": float(args.external_gate_top_gap_threshold),
            "external_boundary_pair_margin_threshold": float(args.external_boundary_pair_margin_threshold),
            "external_boundary_pair_uncertainty_std_threshold": float(args.external_boundary_pair_uncertainty_std_threshold),
        },
        "intervention_meta": intervention_meta,
        "external_meta": external_meta,
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
