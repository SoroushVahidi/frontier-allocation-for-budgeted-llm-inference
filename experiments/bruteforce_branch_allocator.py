"""Learning pipeline for branch-allocation models from brute-force supervision labels."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

try:
    import lightgbm as lgb
except Exception:  # pragma: no cover - optional dependency
    lgb = None

try:
    from catboost import CatBoostRanker, Pool
except Exception:  # pragma: no cover - optional dependency
    CatBoostRanker = None
    Pool = None


ALLOC_FEATURE_NAMES_V1 = [
    "remaining_budget",
    "score",
    "depth",
    "stalled_steps",
    "recent_delta",
    "verify_count",
    "branch_age",
    "parent_relative_score",
    "allocation_candidates_evaluated",
    "allocation_value_std",
    "mode_exact",
    "mode_approx",
    "mode_degenerate",
    "branch_hash",
]

ALLOC_FEATURE_NAMES_V2 = ALLOC_FEATURE_NAMES_V1 + [
    # hard-case representation features (feature set v2)
    "frontier_branch_count",
    "frontier_score_mean",
    "frontier_score_std",
    "frontier_score_entropy",
    "frontier_score_hhi",
    "frontier_top2_gap",
    "branch_rank",
    "branch_rank_norm",
    "score_gap_to_top",
    "score_gap_to_prev",
    "score_gap_to_next",
    "score_z",
    "verify_rate",
    "verify_recent_delta_interaction",
    "recent_delta_per_depth",
    "stalled_ratio",
    "budget_norm_in_state",
    "score_budget_interaction",
    "score_per_budget",
    "score_x_budget_low",
    "score_x_budget_mid",
    "score_x_budget_high",
    "uncertainty_rel_to_score_std",
]


@dataclass(frozen=True)
class LearningConfig:
    seed: int = 17
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    near_tie_margin: float = 0.05
    pairwise_max_iter: int = 500
    outside_max_iter: int = 500
    pointwise_alpha: float = 1.0
    train_pairwise: bool = True
    train_pointwise: bool = True
    train_outside_option: bool = True
    train_lightgbm_ranker: bool = True
    train_catboost_ranker: bool = True
    pairwise_near_tie_action: str = "none"  # one of: none, filter, downweight
    pairwise_near_tie_downweight: float = 0.25
    uncertainty_weighting: bool = False
    margin_weight_power: float = 1.0
    std_weight_scale: float = 3.0
    approx_mode_weight: float = 0.9
    exact_mode_weight: float = 1.05
    lightgbm_num_leaves: int = 31
    lightgbm_learning_rate: float = 0.05
    lightgbm_n_estimators: int = 200
    catboost_iterations: int = 250
    catboost_learning_rate: float = 0.05
    catboost_depth: int = 6
    feature_set: str = "v1"  # one of: v1, v2
    train_pairwise_ternary: bool = False
    tie_abs_margin_threshold: float = 0.03
    tie_relative_margin_threshold: float = 0.15
    tie_std_threshold: float = 0.08
    tie_use_near_tie_flag: bool = True
    tie_include_approx: bool = True
    tie_require_exact_or_mixed: bool = False


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _stable_hash01(text: str) -> float:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:12], 16) / float(16**12)


def _branch_hash(branch_id: str) -> float:
    return 2.0 * _stable_hash01(branch_id) - 1.0


def load_label_artifacts(labels_dir: Path) -> dict[str, list[dict[str, Any]]]:
    required = {
        "candidate_labels": labels_dir / "candidate_labels.jsonl",
        "pairwise_labels": labels_dir / "pairwise_labels.jsonl",
        "state_summaries": labels_dir / "state_summaries.jsonl",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required label artifacts in {labels_dir}: {missing}")

    data = {name: _read_jsonl(path) for name, path in required.items()}
    if not data["candidate_labels"]:
        raise ValueError("candidate_labels.jsonl is empty")
    if not data["pairwise_labels"]:
        raise ValueError("pairwise_labels.jsonl is empty")
    return data


def _feature_names_for_set(feature_set: str) -> list[str]:
    if feature_set == "v1":
        return ALLOC_FEATURE_NAMES_V1
    if feature_set == "v2":
        return ALLOC_FEATURE_NAMES_V2
    raise ValueError(f"Unknown feature_set: {feature_set}")


def build_candidate_feature_vector(row: dict[str, Any], *, feature_set: str = "v1") -> list[float]:
    f = row.get("features_branch_v1", {}) if isinstance(row.get("features_branch_v1"), dict) else {}
    f2 = row.get("features_branch_v2", {}) if isinstance(row.get("features_branch_v2"), dict) else {}
    mode = str(row.get("mode", "approx"))
    out = {
        "remaining_budget": float(row.get("remaining_budget", 0.0)),
        "score": float(f.get("score", 0.0)),
        "depth": float(f.get("depth", 0.0)),
        "stalled_steps": float(f.get("stalled_steps", 0.0)),
        "recent_delta": float(f.get("recent_delta", 0.0)),
        "verify_count": float(f.get("verify_count", 0.0)),
        "branch_age": float(f.get("branch_age", 0.0)),
        "parent_relative_score": float(f.get("parent_relative_score", 0.0)),
        "allocation_candidates_evaluated": float(row.get("allocation_candidates_evaluated", 0.0)),
        "allocation_value_std": float(row.get("allocation_value_std", 0.0)),
        "mode_exact": 1.0 if mode == "exact" else 0.0,
        "mode_approx": 1.0 if mode == "approx" else 0.0,
        "mode_degenerate": 1.0 if mode == "degenerate" else 0.0,
        "branch_hash": _branch_hash(str(row.get("branch_id", ""))),
        **{k: float(f2.get(k, 0.0)) for k in ALLOC_FEATURE_NAMES_V2 if k not in ALLOC_FEATURE_NAMES_V1},
    }
    return [float(out[name]) for name in _feature_names_for_set(feature_set)]


def _distribution_entropy(vals: list[float]) -> float:
    if not vals:
        return 0.0
    total = sum(max(float(v), 0.0) for v in vals)
    if total <= 1e-12:
        return 0.0
    probs = [max(float(v), 0.0) / total for v in vals if max(float(v), 0.0) > 0.0]
    return -sum(p * math.log(max(p, 1e-12)) for p in probs)


def _build_state_context_features(state_rows: list[dict[str, Any]]) -> None:
    """Attach richer hard-case context features to candidate rows.

    Feature-audit rationale:
    v1 captures local branch state but misses hard-slice context (near-tie/adjacent):
    rank structure, frontier competition concentration, relative top/neighbor gaps,
    verification dynamics normalized by branch age, and budget-context interactions.
    """
    if not state_rows:
        return
    by_score = sorted(state_rows, key=lambda r: float(r.get("features_branch_v1", {}).get("score", 0.0)), reverse=True)
    score_vals = [float(r.get("features_branch_v1", {}).get("score", 0.0)) for r in state_rows]
    score_mean = float(np.mean(score_vals)) if score_vals else 0.0
    score_std = float(np.std(score_vals)) if len(score_vals) > 1 else 0.0
    score_top = float(by_score[0].get("features_branch_v1", {}).get("score", 0.0))
    top2_gap = 0.0
    if len(by_score) >= 2:
        top2_gap = float(by_score[0].get("features_branch_v1", {}).get("score", 0.0)) - float(
            by_score[1].get("features_branch_v1", {}).get("score", 0.0)
        )
    score_nonneg = [max(v, 0.0) for v in score_vals]
    score_sum = sum(score_nonneg)
    score_hhi = sum((v / max(score_sum, 1e-12)) ** 2 for v in score_nonneg) if score_nonneg else 0.0
    budget_max = max(float(r.get("remaining_budget", 0.0)) for r in state_rows)
    score_rank = {str(r.get("branch_id", "")): idx for idx, r in enumerate(by_score)}

    for row in state_rows:
        bid = str(row.get("branch_id", ""))
        f = row.get("features_branch_v1", {}) if isinstance(row.get("features_branch_v1"), dict) else {}
        score = float(f.get("score", 0.0))
        rank = int(score_rank.get(bid, 0))
        rank_norm = rank / max(1, len(state_rows) - 1)
        prev_score = float(by_score[rank - 1].get("features_branch_v1", {}).get("score", score)) if rank > 0 else score
        next_score = float(by_score[rank + 1].get("features_branch_v1", {}).get("score", score)) if (rank + 1) < len(by_score) else score
        verify_count = float(f.get("verify_count", 0.0))
        branch_age = float(f.get("branch_age", 0.0))
        recent_delta = float(f.get("recent_delta", 0.0))
        depth = float(f.get("depth", 0.0))
        stalled = float(f.get("stalled_steps", 0.0))
        budget = float(row.get("remaining_budget", 0.0))

        row["features_branch_v2"] = {
            "frontier_branch_count": float(len(state_rows)),
            "frontier_score_mean": score_mean,
            "frontier_score_std": score_std,
            "frontier_score_entropy": _distribution_entropy(score_nonneg),
            "frontier_score_hhi": score_hhi,
            "frontier_top2_gap": top2_gap,
            "branch_rank": float(rank),
            "branch_rank_norm": float(rank_norm),
            "score_gap_to_top": score_top - score,
            "score_gap_to_prev": prev_score - score,
            "score_gap_to_next": score - next_score,
            "score_z": (score - score_mean) / max(score_std, 1e-6),
            "verify_rate": verify_count / max(1.0, branch_age + 1.0),
            "verify_recent_delta_interaction": verify_count * recent_delta,
            "recent_delta_per_depth": recent_delta / max(1.0, depth + 1.0),
            "stalled_ratio": stalled / max(1.0, depth + 1.0),
            "budget_norm_in_state": budget / max(1.0, budget_max),
            "score_budget_interaction": score * (budget / max(1.0, budget_max)),
            "score_per_budget": score / max(1.0, budget),
            "score_x_budget_low": score if budget <= 2.0 else 0.0,
            "score_x_budget_mid": score if 2.0 < budget <= 3.0 else 0.0,
            "score_x_budget_high": score if budget > 3.0 else 0.0,
            "uncertainty_rel_to_score_std": float(row.get("allocation_value_std", 0.0)) / max(score_std, 1e-6),
        }


def assign_split(state_id: str, cfg: LearningConfig) -> str:
    r = _stable_hash01(f"{cfg.seed}|{state_id}")
    if r < cfg.train_ratio:
        return "train"
    if r < cfg.train_ratio + cfg.val_ratio:
        return "val"
    return "test"


def _pairwise_weight(row: dict[str, Any], cfg: LearningConfig) -> tuple[bool, float]:
    margin_abs = abs(float(row.get("margin", 0.0)))
    near_tie = margin_abs <= float(cfg.near_tie_margin)
    if near_tie and cfg.pairwise_near_tie_action == "filter":
        return (False, 0.0)

    weight = 1.0
    if near_tie and cfg.pairwise_near_tie_action == "downweight":
        weight *= float(cfg.pairwise_near_tie_downweight)

    if cfg.uncertainty_weighting:
        weight *= max(margin_abs, 1e-6) ** float(cfg.margin_weight_power)
        pair_std = float(row.get("pair_allocation_value_std", 0.0))
        weight *= 1.0 / (1.0 + float(cfg.std_weight_scale) * max(pair_std, 0.0))
        pair_mode = str(row.get("pair_mode", "unknown"))
        if pair_mode == "approx":
            weight *= float(cfg.approx_mode_weight)
        elif pair_mode == "exact":
            weight *= float(cfg.exact_mode_weight)

    return (True, max(weight, 1e-8))


def _is_ambiguous_pair(row: dict[str, Any], cfg: LearningConfig) -> bool:
    margin_abs = float(row.get("margin_abs", abs(float(row.get("margin", 0.0)))))
    rel_margin = float(row.get("relative_margin", 1e9))
    pair_std = float(row.get("pair_uncertainty_std_mean", row.get("pair_allocation_value_std", 0.0)))
    near_tie_flag = bool(row.get("near_tie_flag", margin_abs <= float(cfg.near_tie_margin)))
    pair_mode = str(row.get("pair_mode_provenance", row.get("pair_mode", "unknown")))
    is_exact_or_mixed = pair_mode in {"exact", "mixed"}
    if (not bool(cfg.tie_include_approx)) and pair_mode == "approx":
        return False
    if bool(cfg.tie_require_exact_or_mixed) and (not is_exact_or_mixed):
        return False
    return bool(
        margin_abs <= float(cfg.tie_abs_margin_threshold)
        or rel_margin <= float(cfg.tie_relative_margin_threshold)
        or pair_std >= float(cfg.tie_std_threshold)
        or (bool(cfg.tie_use_near_tie_flag) and near_tie_flag)
    )


def prepare_learning_tables(data: dict[str, list[dict[str, Any]]], cfg: LearningConfig) -> dict[str, Any]:
    candidates = [dict(row) for row in data["candidate_labels"]]
    pairwise = [dict(row) for row in data["pairwise_labels"]]
    states = [dict(row) for row in data["state_summaries"]]

    by_state_rows: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        by_state_rows.setdefault(str(row["state_id"]), []).append(row)
    for rows in by_state_rows.values():
        _build_state_context_features(rows)

    cand_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        state_id = str(row["state_id"])
        branch_id = str(row["branch_id"])
        row["split"] = assign_split(state_id, cfg)
        row["x"] = build_candidate_feature_vector(row, feature_set=str(cfg.feature_set))
        cand_by_key[(state_id, branch_id)] = row

    for row in pairwise:
        state_id = str(row["state_id"])
        bi = str(row["branch_i"])
        bj = str(row["branch_j"])
        row["split"] = assign_split(state_id, cfg)
        ci = cand_by_key.get((state_id, bi))
        cj = cand_by_key.get((state_id, bj))
        if ci is None or cj is None:
            raise KeyError(f"Pairwise row references missing candidate rows: {(state_id, bi, bj)}")
        xi = ci["x"]
        xj = cj["x"]
        row["x_i"] = xi
        row["x_j"] = xj
        row["x_diff"] = [float(a - b) for a, b in zip(xi, xj)]
        fi = ci.get("features_branch_v2", {}) if isinstance(ci.get("features_branch_v2"), dict) else {}
        fj = cj.get("features_branch_v2", {}) if isinstance(cj.get("features_branch_v2"), dict) else {}
        row["pair_relational_v2"] = {
            "rank_gap_abs": abs(float(fi.get("branch_rank", 0.0)) - float(fj.get("branch_rank", 0.0))),
            "score_gap_abs": abs(float(ci.get("features_branch_v1", {}).get("score", 0.0)) - float(cj.get("features_branch_v1", {}).get("score", 0.0))),
            "score_z_gap_abs": abs(float(fi.get("score_z", 0.0)) - float(fj.get("score_z", 0.0))),
            "verify_rate_gap_abs": abs(float(fi.get("verify_rate", 0.0)) - float(fj.get("verify_rate", 0.0))),
            "uncertainty_gap_abs": abs(float(ci.get("allocation_value_std", 0.0)) - float(cj.get("allocation_value_std", 0.0))),
            "score_to_top_gap_abs_diff": abs(float(fi.get("score_gap_to_top", 0.0)) - float(fj.get("score_gap_to_top", 0.0))),
            "adjacent_rank_flag": 1.0 if abs(float(fi.get("branch_rank", 0.0)) - float(fj.get("branch_rank", 0.0))) <= 1.0 else 0.0,
        }
        if "label" not in row:
            row["label"] = int(row.get("preference", 0))
        row["pair_allocation_value_std"] = 0.5 * (
            float(ci.get("allocation_value_std", 0.0)) + float(cj.get("allocation_value_std", 0.0))
        )
        mode_i = str(ci.get("mode", "unknown"))
        mode_j = str(cj.get("mode", "unknown"))
        row["pair_mode"] = mode_i if mode_i == mode_j else "mixed"
        include, weight = _pairwise_weight(row, cfg)
        row["include_for_pairwise_training"] = include
        row["pair_train_weight"] = weight
        ambiguous = _is_ambiguous_pair(row, cfg)
        row["ambiguous_target_flag"] = ambiguous
        # ternary labels: 0 -> prefer_branch_j, 1 -> tie/ambiguous, 2 -> prefer_branch_i
        binary_label = int(row.get("label", 0))
        row["ternary_label"] = 1 if ambiguous else (2 if binary_label == 1 else 0)
        if row["ternary_label"] == 1:
            row["ternary_label_name"] = "tie_ambiguous"
        elif row["ternary_label"] == 2:
            row["ternary_label_name"] = "prefer_branch_i"
        else:
            row["ternary_label_name"] = "prefer_branch_j"

    state_to_candidates: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        state_to_candidates.setdefault(str(row["state_id"]), []).append(row)

    state_to_mode = {str(r["state_id"]): str(r.get("candidate_mode", "unknown")) for r in states}
    state_to_dataset = {
        str(r["state_id"]): str(r.get("dataset_name", "unknown"))
        for r in states
    }
    return {
        "candidates": candidates,
        "pairwise": pairwise,
        "states": states,
        "state_to_candidates": state_to_candidates,
        "state_to_mode": state_to_mode,
        "state_to_dataset": state_to_dataset,
        "feature_set": str(cfg.feature_set),
        "feature_names": _feature_names_for_set(str(cfg.feature_set)),
    }


def _fit_pairwise_model(rows: list[dict[str, Any]], cfg: LearningConfig) -> dict[str, Any]:
    train = [r for r in rows if r["split"] == "train" and bool(r.get("include_for_pairwise_training", True))]
    if len(train) < 2:
        return {"model_type": "pairwise_logreg", "status": "insufficient_train_rows"}
    x = [r["x_diff"] for r in train]
    y = [int(r["label"]) for r in train]
    weights = [float(r.get("pair_train_weight", 1.0)) for r in train]
    if len(set(y)) < 2:
        return {
            "model_type": "pairwise_logreg",
            "status": "single_class_train",
            "constant_label": int(y[0]),
        }
    model = LogisticRegression(max_iter=cfg.pairwise_max_iter, random_state=cfg.seed)
    model.fit(x, y, sample_weight=weights)
    coef = list(float(v) for v in model.coef_[0])
    return {
        "model_type": "pairwise_logreg",
        "status": "ok",
        "feature_names": _feature_names_for_set(str(cfg.feature_set)),
        "feature_set": str(cfg.feature_set),
        "weights": coef,
        "intercept": float(model.intercept_[0]),
        "training_rows": len(train),
        "weighting": {
            "pairwise_near_tie_action": cfg.pairwise_near_tie_action,
            "pairwise_near_tie_downweight": cfg.pairwise_near_tie_downweight,
            "uncertainty_weighting": cfg.uncertainty_weighting,
        },
    }


def _fit_pairwise_ternary_model(rows: list[dict[str, Any]], cfg: LearningConfig) -> dict[str, Any]:
    train = [r for r in rows if r["split"] == "train" and bool(r.get("include_for_pairwise_training", True))]
    if len(train) < 3:
        return {"model_type": "pairwise_ternary_logreg", "status": "insufficient_train_rows"}
    x = [r["x_diff"] for r in train]
    y = [int(r.get("ternary_label", 1)) for r in train]
    weights = [float(r.get("pair_train_weight", 1.0)) for r in train]
    classes = sorted(set(y))
    if len(classes) < 2:
        return {
            "model_type": "pairwise_ternary_logreg",
            "status": "single_class_train",
            "constant_label": int(y[0]) if y else 1,
        }
    model = LogisticRegression(
        max_iter=cfg.pairwise_max_iter,
        random_state=cfg.seed,
    )
    model.fit(x, y, sample_weight=weights)
    return {
        "model_type": "pairwise_ternary_logreg",
        "status": "ok",
        "feature_names": _feature_names_for_set(str(cfg.feature_set)),
        "feature_set": str(cfg.feature_set),
        "weights": [[float(v) for v in row] for row in model.coef_],
        "intercepts": [float(v) for v in model.intercept_],
        "classes": [int(c) for c in model.classes_],
        "training_rows": len(train),
    }


def _fit_pointwise_model(rows: list[dict[str, Any]], cfg: LearningConfig) -> dict[str, Any]:
    train = [r for r in rows if r["split"] == "train"]
    if len(train) < 2:
        return {"model_type": "pointwise_ridge", "status": "insufficient_train_rows"}
    x = [r["x"] for r in train]
    y = [float(r["estimated_value_if_allocate_next"]) for r in train]
    model = Ridge(alpha=cfg.pointwise_alpha, random_state=cfg.seed)
    model.fit(x, y)
    return {
        "model_type": "pointwise_ridge",
        "status": "ok",
        "feature_names": _feature_names_for_set(str(cfg.feature_set)),
        "feature_set": str(cfg.feature_set),
        "weights": [float(v) for v in model.coef_],
        "intercept": float(model.intercept_),
    }


def _fit_outside_option_model(rows: list[dict[str, Any]], cfg: LearningConfig) -> dict[str, Any]:
    train = [r for r in rows if r["split"] == "train"]
    if len(train) < 2:
        return {"model_type": "outside_option_logreg", "status": "insufficient_train_rows"}
    x = [r["x"] for r in train]
    y = [1 if float(r.get("branch_vs_outside_gap", 0.0)) > 0 else 0 for r in train]
    if len(set(y)) < 2:
        return {
            "model_type": "outside_option_logreg",
            "status": "single_class_train",
            "constant_label": int(y[0]),
        }
    model = LogisticRegression(max_iter=cfg.outside_max_iter, random_state=cfg.seed)
    model.fit(x, y)
    return {
        "model_type": "outside_option_logreg",
        "status": "ok",
        "feature_names": _feature_names_for_set(str(cfg.feature_set)),
        "feature_set": str(cfg.feature_set),
        "weights": [float(v) for v in model.coef_[0]],
        "intercept": float(model.intercept_[0]),
    }


def _grouped_candidate_arrays(candidates: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, list[int], np.ndarray]:
    train_rows = [r for r in candidates if r["split"] == "train"]
    by_state: dict[str, list[dict[str, Any]]] = {}
    for row in train_rows:
        by_state.setdefault(str(row["state_id"]), []).append(row)
    ordered_groups = [rows for _sid, rows in sorted(by_state.items()) if len(rows) >= 2]
    if not ordered_groups:
        n_feats = len(candidates[0].get("x", [])) if candidates else 0
        return np.zeros((0, n_feats)), np.zeros((0,)), [], np.zeros((0,))
    x = np.array([r["x"] for grp in ordered_groups for r in grp], dtype=float)
    y = np.array([float(r["estimated_value_if_allocate_next"]) for grp in ordered_groups for r in grp], dtype=float)
    group = [len(grp) for grp in ordered_groups]
    weights = np.array([
        max(1e-8, 1.0 / (1.0 + float(r.get("allocation_value_std", 0.0)) * 4.0))
        for grp in ordered_groups
        for r in grp
    ], dtype=float)
    return x, y, group, weights


def _fit_lightgbm_ranker(candidates: list[dict[str, Any]], cfg: LearningConfig, model_artifact_dir: Path | None) -> dict[str, Any]:
    if not cfg.train_lightgbm_ranker:
        return {"model_type": "lightgbm_lambdarank", "status": "disabled"}
    if lgb is None:
        return {"model_type": "lightgbm_lambdarank", "status": "dependency_unavailable"}
    if model_artifact_dir is None:
        return {"model_type": "lightgbm_lambdarank", "status": "artifact_dir_required"}
    x, y, group, w = _grouped_candidate_arrays(candidates)
    if x.shape[0] < 4 or len(group) < 2:
        return {"model_type": "lightgbm_lambdarank", "status": "insufficient_train_rows"}
    y_rel = np.zeros_like(y, dtype=int)
    idx = 0
    for g in group:
        segment = y[idx : idx + g]
        order = np.argsort(segment)
        rel = np.zeros(g, dtype=int)
        for rank_pos, local_idx in enumerate(order):
            rel[local_idx] = rank_pos
        y_rel[idx : idx + g] = rel
        idx += g

    model = lgb.LGBMRanker(
        objective="lambdarank",
        random_state=cfg.seed,
        learning_rate=cfg.lightgbm_learning_rate,
        n_estimators=cfg.lightgbm_n_estimators,
        num_leaves=cfg.lightgbm_num_leaves,
        min_data_in_leaf=5,
    )
    model.fit(x, y_rel, group=group, sample_weight=w)
    model_path = model_artifact_dir / "lightgbm_lambdarank_model.txt"
    model.booster_.save_model(str(model_path))
    return {
        "model_type": "lightgbm_lambdarank",
        "status": "ok",
        "feature_names": _feature_names_for_set(str(cfg.feature_set)),
        "feature_set": str(cfg.feature_set),
        "model_path": str(model_path),
        "training_rows": int(x.shape[0]),
        "training_groups": int(len(group)),
    }


def _fit_catboost_ranker(candidates: list[dict[str, Any]], cfg: LearningConfig, model_artifact_dir: Path | None) -> dict[str, Any]:
    if not cfg.train_catboost_ranker:
        return {"model_type": "catboost_yetirankpairwise", "status": "disabled"}
    if CatBoostRanker is None or Pool is None:
        return {"model_type": "catboost_yetirankpairwise", "status": "dependency_unavailable"}
    if model_artifact_dir is None:
        return {"model_type": "catboost_yetirankpairwise", "status": "artifact_dir_required"}

    train_rows = [r for r in candidates if r["split"] == "train"]
    by_state: dict[str, list[dict[str, Any]]] = {}
    for row in train_rows:
        by_state.setdefault(str(row["state_id"]), []).append(row)
    groups = [rows for _sid, rows in sorted(by_state.items()) if len(rows) >= 2]
    if sum(len(g) for g in groups) < 4 or len(groups) < 2:
        return {"model_type": "catboost_yetirankpairwise", "status": "insufficient_train_rows"}

    x = np.array([r["x"] for grp in groups for r in grp], dtype=float)
    y = np.array([float(r["estimated_value_if_allocate_next"]) for grp in groups for r in grp], dtype=float)
    group_id = np.array([gi for gi, grp in enumerate(groups) for _ in grp], dtype=int)
    weights = np.array([
        max(1e-8, 1.0 / (1.0 + float(r.get("allocation_value_std", 0.0)) * 4.0))
        for grp in groups
        for r in grp
    ], dtype=float)

    train_pool = Pool(data=x, label=y, group_id=group_id, weight=weights)
    model = CatBoostRanker(
        loss_function="YetiRankPairwise",
        random_seed=cfg.seed,
        iterations=cfg.catboost_iterations,
        learning_rate=cfg.catboost_learning_rate,
        depth=cfg.catboost_depth,
        verbose=False,
    )
    model.fit(train_pool)
    model_path = model_artifact_dir / "catboost_yetirankpairwise_model.json"
    model.save_model(str(model_path), format="json")
    return {
        "model_type": "catboost_yetirankpairwise",
        "status": "ok",
        "feature_names": _feature_names_for_set(str(cfg.feature_set)),
        "feature_set": str(cfg.feature_set),
        "model_path": str(model_path),
        "training_rows": int(x.shape[0]),
        "training_groups": int(len(groups)),
    }


def train_models(tables: dict[str, Any], cfg: LearningConfig, model_artifact_dir: Path | None = None) -> dict[str, Any]:
    models: dict[str, Any] = {}
    if model_artifact_dir is not None:
        model_artifact_dir.mkdir(parents=True, exist_ok=True)
    if cfg.train_pairwise:
        models["pairwise"] = _fit_pairwise_model(tables["pairwise"], cfg)
    if cfg.train_pairwise_ternary:
        models["pairwise_ternary"] = _fit_pairwise_ternary_model(tables["pairwise"], cfg)
    if cfg.train_pointwise:
        models["pointwise"] = _fit_pointwise_model(tables["candidates"], cfg)
    if cfg.train_outside_option:
        models["outside_option"] = _fit_outside_option_model(tables["candidates"], cfg)
    models["lightgbm_ranker"] = _fit_lightgbm_ranker(tables["candidates"], cfg, model_artifact_dir)
    models["catboost_ranker"] = _fit_catboost_ranker(tables["candidates"], cfg, model_artifact_dir)
    return models


def _dot(w: list[float], x: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(w, x))


def scorer_from_model(model: dict[str, Any]) -> Callable[[dict[str, Any]], float]:
    status = str(model.get("status", ""))
    if status != "ok":
        constant = float(model.get("constant_label", 0.0))
        return lambda _row: constant

    model_type = str(model.get("model_type", ""))
    if model_type in {"pairwise_logreg", "pointwise_ridge", "outside_option_logreg"}:
        w = [float(v) for v in model.get("weights", [])]
        b = float(model.get("intercept", 0.0))
        if model_type == "pairwise_logreg":
            return lambda row: _dot(w, row["x"])
        return lambda row: _dot(w, row["x"]) + b

    if model_type == "lightgbm_lambdarank":
        if lgb is None:
            return lambda _row: 0.0
        booster = lgb.Booster(model_file=str(model.get("model_path", "")))
        return lambda row: float(booster.predict(np.array([row["x"]], dtype=float))[0])

    if model_type == "catboost_yetirankpairwise":
        if CatBoostRanker is None:
            return lambda _row: 0.0
        cb_model = CatBoostRanker()
        cb_model.load_model(str(model.get("model_path", "")), format="json")
        return lambda row: float(cb_model.predict(np.array([row["x"]], dtype=float))[0])

    return lambda _row: 0.0


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _safe_mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _ranking_top1_accuracy(state_to_candidates: dict[str, list[dict[str, Any]]], score_fn: Callable[[dict[str, Any]], float], split: str) -> float:
    ok = 0
    total = 0
    for rows in state_to_candidates.values():
        subset = [r for r in rows if r["split"] == split]
        if len(subset) < 2:
            continue
        pred = max(subset, key=score_fn)["branch_id"]
        truth = max(subset, key=lambda r: float(r["estimated_value_if_allocate_next"]))["branch_id"]
        ok += int(pred == truth)
        total += 1
    return ok / max(1, total)


def _pairwise_agreement(
    rows: list[dict[str, Any]],
    score_fn: Callable[[dict[str, Any]], float],
    split: str,
    *,
    near_tie_margin: float,
) -> tuple[float, float, float, float]:
    subset = [r for r in rows if r["split"] == split]
    if not subset:
        return (0.0, 0.0, 0.0, 0.0)
    correct = 0
    near_correct = 0
    far_correct = 0
    near_n = 0
    far_n = 0
    brier_vals: list[float] = []
    for r in subset:
        si = score_fn({"x": r["x_i"]})
        sj = score_fn({"x": r["x_j"]})
        pred_label = 1 if si >= sj else 0
        y = int(r["label"])
        correct += int(pred_label == y)

        pred_prob = _sigmoid(si - sj)
        brier_vals.append((pred_prob - float(y)) ** 2)

        true_margin = abs(float(r.get("margin", 0.0)))
        if true_margin <= float(near_tie_margin):
            near_n += 1
            near_correct += int(pred_label == y)
        else:
            far_n += 1
            far_correct += int(pred_label == y)
    acc = correct / len(subset)
    near = near_correct / max(1, near_n)
    far = far_correct / max(1, far_n)
    brier = _safe_mean(brier_vals)
    return (acc, near, far, brier)


def _slice_pairwise_accuracy(
    rows: list[dict[str, Any]],
    score_fn: Callable[[dict[str, Any]], float],
    split: str,
    state_to_mode: dict[str, str],
    state_to_dataset: dict[str, str],
) -> dict[str, Any]:
    subset = [r for r in rows if r["split"] == split]

    def acc_for(predicate: Callable[[dict[str, Any]], bool]) -> float:
        filt = [r for r in subset if predicate(r)]
        if not filt:
            return 0.0
        ok = 0
        for r in filt:
            si = score_fn({"x": r["x_i"]})
            sj = score_fn({"x": r["x_j"]})
            ok += int((1 if si >= sj else 0) == int(r["label"]))
        return ok / len(filt)

    budgets = sorted({int(r.get("remaining_budget", 0)) for r in subset})
    by_budget = {str(b): acc_for(lambda r, bb=b: int(r.get("remaining_budget", 0)) == bb) for b in budgets}

    modes = sorted({state_to_mode.get(str(r["state_id"]), "unknown") for r in subset})
    by_mode = {
        m: acc_for(lambda r, mm=m: state_to_mode.get(str(r["state_id"]), "unknown") == mm)
        for m in modes
    }

    datasets = sorted({state_to_dataset.get(str(r["state_id"]), "unknown") for r in subset})
    by_dataset = {
        d: acc_for(lambda r, dd=d: state_to_dataset.get(str(r["state_id"]), "unknown") == dd)
        for d in datasets
    }
    return {
        "pairwise_accuracy_by_budget": by_budget,
        "pairwise_accuracy_by_mode": by_mode,
        "pairwise_accuracy_by_dataset": by_dataset,
    }


def evaluate_models(models: dict[str, Any], tables: dict[str, Any], cfg: LearningConfig) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, model in models.items():
        if str(model.get("model_type", "")) == "pairwise_ternary_logreg":
            out[name] = {
                "model_status": model.get("status", "unknown"),
                "note": "pairwise_ternary_logreg requires pair-level evaluation; candidate ranking metrics are not computed here",
            }
            continue
        scorer = scorer_from_model(model)
        pair_acc, near_acc, far_acc, brier = _pairwise_agreement(
            tables["pairwise"],
            scorer,
            "test",
            near_tie_margin=float(cfg.near_tie_margin),
        )
        top1 = _ranking_top1_accuracy(tables["state_to_candidates"], scorer, "test")
        slices = _slice_pairwise_accuracy(
            tables["pairwise"],
            scorer,
            "test",
            tables["state_to_mode"],
            tables["state_to_dataset"],
        )
        out[name] = {
            "model_status": model.get("status", "unknown"),
            "pairwise_accuracy_test": pair_acc,
            "ranking_top1_accuracy_test": top1,
            "agreement_with_bruteforce_labels": pair_acc,
            "near_tie_pairwise_accuracy_test": near_acc,
            "far_margin_pairwise_accuracy_test": far_acc,
            "pairwise_margin_brier_test": brier,
            "exact_only_pairwise_accuracy_test": slices.get("pairwise_accuracy_by_mode", {}).get("exact", 0.0),
            **slices,
        }
    return out


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown_report(path: Path, *, run_id: str, config: LearningConfig, eval_summary: dict[str, Any]) -> None:
    lines = [
        "# Brute-force label branch-allocation learning report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Seed: `{config.seed}`",
        f"- Near-tie threshold: `{config.near_tie_margin}`",
        f"- Feature set: `{config.feature_set}`",
        f"- Pairwise near-tie handling: `{config.pairwise_near_tie_action}`",
        f"- Uncertainty weighting enabled: `{config.uncertainty_weighting}`",
        "",
        "## Safe interpretation",
        "",
        "Models here are learned approximations to expensive branch-allocation labels.",
        "Do not interpret this as exact global oracle allocation on real model trajectories.",
        "",
        "## Test metrics",
        "",
    ]
    for model_name, metrics in eval_summary.items():
        lines.append(f"### {model_name}")
        for k, v in metrics.items():
            lines.append(f"- {k}: `{v}`")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def config_to_dict(cfg: LearningConfig) -> dict[str, Any]:
    return asdict(cfg)
