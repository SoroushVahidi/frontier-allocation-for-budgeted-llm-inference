"""Learning pipeline for branch-allocation models from brute-force supervision labels."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.svm import LinearSVC

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
ALLOC_FEATURE_NAMES_V3 = ALLOC_FEATURE_NAMES_V2 + [
    # structured ambiguity representation (feature set v3)
    "frontier_topk_gap_1",
    "frontier_topk_gap_2",
    "frontier_topk_gap_3",
    "frontier_viable_branch_count_above_threshold",
    "frontier_local_density_near_score",
    "frontier_crowding_near_cutline",
    "frontier_duplicate_or_near_duplicate_count",
    "frontier_gap_hist_mean",
    "frontier_gap_hist_std",
    "frontier_gap_hist_min",
    "frontier_rank_instability_proxy",
    "time_since_last_improvement_proxy",
    "widening_vs_shrinking_margin_proxy",
    "responsive_middle_regime_proxy",
    "branch_vs_outside_gap_x_budget",
    "expected_gain_per_cost_proxy",
    "stop_or_defer_proxy_score",
]
ALLOC_FEATURE_NAMES = ALLOC_FEATURE_NAMES_V1
PAIR_RELATIONAL_FEATURE_NAMES_V3 = [
    "pair_margin_abs",
    "pair_relative_margin",
    "pair_rank_gap_abs",
    "pair_adjacent_rank_flag",
    "pair_gap_to_next_best",
    "pair_gap_to_prev_best",
    "pair_uncertainty_std_mean",
    "pair_uncertainty_std_diff",
    "pair_score_gap_to_top_diff",
    "pair_shadow_price_adjusted_margin_proxy",
    "pair_margin_x_budget",
    "uncertainty_x_budget",
    "expected_gain_per_cost_proxy_diff",
    "branch_vs_outside_gap_x_budget_diff",
    "pair_best_vs_outside_gap",
    "pair_both_below_outside_flag",
    "defer_candidate_flag",
    "outside_option_advantage_abs",
    "outside_option_margin_to_best_branch",
    "stop_or_defer_proxy_score_mean",
    "rank_instability_under_small_margin",
    "high_uncertainty_and_small_gap_flag",
    "low_gap_high_entropy_like_flag",
    "disagreement_risk_score",
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
    feature_set: str = "v1"  # one of: v1, v2, v3
    train_pairwise_ternary: bool = False
    tie_abs_margin_threshold: float = 0.03
    tie_relative_margin_threshold: float = 0.15
    tie_std_threshold: float = 0.08
    tie_use_near_tie_flag: bool = True
    tie_include_approx: bool = True
    tie_require_exact_or_mixed: bool = False
    train_pairwise_svm: bool = True
    train_pairwise_svm_nystroem: bool = False
    svm_c: float = 1.0
    svm_class_weight_balanced: bool = False
    svm_use_sample_weight: bool = True
    svm_nystroem_components: int = 256
    svm_nystroem_gamma: float = 0.5
    svm_max_train_rows_for_nystroem: int = 8000
    svm_margin_calibration: str = "none"  # one of: none, platt
    train_pairwise_defer_classifier: bool = False
    defer_abs_margin_threshold: float = 0.03
    defer_relative_margin_threshold: float = 0.15
    defer_std_threshold: float = 0.08
    defer_use_outside_option: bool = True
    defer_outside_gap_threshold: float = 0.02
    defer_require_exact_or_mixed: bool = False
    defer_include_approx: bool = True
    defer_model_type: str = "multinomial_logreg"


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
    if feature_set == "v3":
        return ALLOC_FEATURE_NAMES_V3
    raise ValueError(f"Unknown feature_set: {feature_set}")


def build_candidate_feature_vector(row: dict[str, Any], *, feature_set: str = "v1") -> list[float]:
    f = row.get("features_branch_v1", {}) if isinstance(row.get("features_branch_v1"), dict) else {}
    f2 = row.get("features_branch_v2", {}) if isinstance(row.get("features_branch_v2"), dict) else {}
    f3 = row.get("features_branch_v3", {}) if isinstance(row.get("features_branch_v3"), dict) else {}
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
        **{k: float(f3.get(k, 0.0)) for k in ALLOC_FEATURE_NAMES_V3 if k not in ALLOC_FEATURE_NAMES_V2},
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
    gaps_sorted = [
        float(by_score[i].get("features_branch_v1", {}).get("score", 0.0))
        - float(by_score[i + 1].get("features_branch_v1", {}).get("score", 0.0))
        for i in range(max(0, len(by_score) - 1))
    ]
    topk_gaps = list(gaps_sorted[:3]) + [0.0] * max(0, 3 - len(gaps_sorted))
    local_gap_mean = float(np.mean(gaps_sorted)) if gaps_sorted else 0.0
    local_gap_std = float(np.std(gaps_sorted)) if gaps_sorted else 0.0
    local_gap_min = float(min(gaps_sorted)) if gaps_sorted else 0.0
    top_score = float(by_score[0].get("features_branch_v1", {}).get("score", 0.0))
    viable_threshold = top_score - max(0.05, abs(top_score) * 0.1)
    viable_count = sum(1 for s in score_vals if s >= viable_threshold)

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
        near_eps = max(0.02, score_std * 0.25)
        local_density = sum(1 for s in score_vals if abs(float(s) - score) <= near_eps) / max(1, len(score_vals))
        score_gap_to_next = float(row["features_branch_v2"].get("score_gap_to_next", 0.0))
        crowding_cutline = 1.0 if rank <= 2 and abs(score_gap_to_next) <= near_eps else 0.0
        duplicate_count = sum(1 for s in score_vals if abs(float(s) - score) <= 0.01) - 1
        rank_instability_proxy = min(1.0, abs(float(row["features_branch_v2"]["score_gap_to_prev"]) - float(row["features_branch_v2"]["score_gap_to_next"])) / max(1e-6, score_std + 1e-6))
        time_since_improvement_proxy = branch_age / max(1.0, 1.0 + abs(recent_delta) * 10.0)
        widening_vs_shrinking = recent_delta * (float(row["features_branch_v2"]["score_gap_to_next"]) - float(row["features_branch_v2"]["score_gap_to_prev"]))
        branch_outside_gap = float(row.get("branch_vs_outside_gap", 0.0))
        budget_norm = budget / max(1.0, budget_max)
        expected_gain_per_cost = score / max(1.0, budget + 1.0)
        responsive_middle = 1.0 if 2.0 < budget <= 4.0 else 0.0
        stop_or_defer = (
            float(row.get("allocation_value_std", 0.0))
            - abs(score - score_mean) * 0.1
            - max(branch_outside_gap, 0.0) * 0.5
        )
        row["features_branch_v3"] = {
            "frontier_topk_gap_1": float(topk_gaps[0]),
            "frontier_topk_gap_2": float(topk_gaps[1]),
            "frontier_topk_gap_3": float(topk_gaps[2]),
            "frontier_viable_branch_count_above_threshold": float(viable_count),
            "frontier_local_density_near_score": float(local_density),
            "frontier_crowding_near_cutline": float(crowding_cutline),
            "frontier_duplicate_or_near_duplicate_count": float(max(0, duplicate_count)),
            "frontier_gap_hist_mean": float(local_gap_mean),
            "frontier_gap_hist_std": float(local_gap_std),
            "frontier_gap_hist_min": float(local_gap_min),
            "frontier_rank_instability_proxy": float(rank_instability_proxy),
            "time_since_last_improvement_proxy": float(time_since_improvement_proxy),
            "widening_vs_shrinking_margin_proxy": float(widening_vs_shrinking),
            "responsive_middle_regime_proxy": float(responsive_middle),
            "branch_vs_outside_gap_x_budget": float(branch_outside_gap * budget_norm),
            "expected_gain_per_cost_proxy": float(expected_gain_per_cost),
            "stop_or_defer_proxy_score": float(stop_or_defer),
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

    weight *= float(row.get("supervision_reliability_weight", 1.0))
    return (True, max(weight, 1e-8))


def _is_ambiguous_pair(row: dict[str, Any], cfg: LearningConfig) -> bool:
    if "ambiguous_tie_target" in row:
        return bool(row.get("ambiguous_tie_target", False))
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


def _is_defer_pair(row: dict[str, Any], cfg: LearningConfig) -> bool:
    margin_abs = float(row.get("margin_abs", abs(float(row.get("margin", 0.0)))))
    rel_margin = float(row.get("relative_margin", 1e9))
    pair_std = float(row.get("pair_uncertainty_std_mean", row.get("pair_allocation_value_std", 0.0)))
    pair_mode = str(row.get("pair_mode_provenance", row.get("pair_mode", "unknown")))
    if (not bool(cfg.defer_include_approx)) and pair_mode == "approx":
        return False
    if bool(cfg.defer_require_exact_or_mixed) and pair_mode not in {"exact", "mixed"}:
        return False
    ambiguous_like = (
        margin_abs <= float(cfg.defer_abs_margin_threshold)
        or rel_margin <= float(cfg.defer_relative_margin_threshold)
        or pair_std >= float(cfg.defer_std_threshold)
        or bool(row.get("ambiguous_target_flag", False))
    )
    if not ambiguous_like:
        return False
    if not bool(cfg.defer_use_outside_option):
        return True
    outside_gap = float(row.get("pair_best_vs_outside_gap", row.get("outside_option_margin_to_best_branch", 0.0)))
    return outside_gap <= float(cfg.defer_outside_gap_threshold)


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
        fi3 = ci.get("features_branch_v3", {}) if isinstance(ci.get("features_branch_v3"), dict) else {}
        fj3 = cj.get("features_branch_v3", {}) if isinstance(cj.get("features_branch_v3"), dict) else {}
        margin_abs = float(row.get("margin_abs", abs(float(row.get("margin", 0.0)))))
        relative_margin = float(row.get("relative_margin", margin_abs / max(1e-6, abs(float(row.get("pair_value_i", 0.0))) + abs(float(row.get("pair_value_j", 0.0))))))
        remaining_budget = float(row.get("remaining_budget", ci.get("remaining_budget", 0.0)))
        pair_std_mean = 0.5 * (float(ci.get("allocation_value_std", 0.0)) + float(cj.get("allocation_value_std", 0.0)))
        pair_std_diff = abs(float(ci.get("allocation_value_std", 0.0)) - float(cj.get("allocation_value_std", 0.0)))
        score_gap_to_top_diff = abs(float(fi.get("score_gap_to_top", 0.0)) - float(fj.get("score_gap_to_top", 0.0)))
        rank_gap_abs = abs(float(fi.get("branch_rank", 0.0)) - float(fj.get("branch_rank", 0.0)))
        adjacent_rank_flag = 1.0 if rank_gap_abs <= 1.0 else 0.0
        pair_gap_to_next_best = min(abs(float(fi.get("score_gap_to_next", 0.0))), abs(float(fj.get("score_gap_to_next", 0.0))))
        pair_gap_to_prev_best = min(abs(float(fi.get("score_gap_to_prev", 0.0))), abs(float(fj.get("score_gap_to_prev", 0.0))))
        budget_norm = max(float(fi.get("budget_norm_in_state", 0.0)), float(fj.get("budget_norm_in_state", 0.0)))
        expected_gain_cost_proxy_i = float(fi3.get("expected_gain_per_cost_proxy", 0.0))
        expected_gain_cost_proxy_j = float(fj3.get("expected_gain_per_cost_proxy", 0.0))
        outside_i = float(ci.get("branch_vs_outside_gap", 0.0))
        outside_j = float(cj.get("branch_vs_outside_gap", 0.0))
        best_outside_gap = max(outside_i, outside_j)
        outside_margin_to_best = best_outside_gap
        both_below_outside = 1.0 if (outside_i <= 0.0 and outside_j <= 0.0) else 0.0
        shadow_price_adjusted_margin_proxy = margin_abs - (remaining_budget / max(1.0, remaining_budget + 2.0))
        disagreement_risk = (1.0 / (1.0 + margin_abs * 10.0)) * (1.0 + pair_std_mean) * (1.0 + 0.5 * adjacent_rank_flag)
        row["pair_relational_v2"] = {
            "rank_gap_abs": rank_gap_abs,
            "score_gap_abs": abs(float(ci.get("features_branch_v1", {}).get("score", 0.0)) - float(cj.get("features_branch_v1", {}).get("score", 0.0))),
            "score_z_gap_abs": abs(float(fi.get("score_z", 0.0)) - float(fj.get("score_z", 0.0))),
            "verify_rate_gap_abs": abs(float(fi.get("verify_rate", 0.0)) - float(fj.get("verify_rate", 0.0))),
            "uncertainty_gap_abs": abs(float(ci.get("allocation_value_std", 0.0)) - float(cj.get("allocation_value_std", 0.0))),
            "score_to_top_gap_abs_diff": score_gap_to_top_diff,
            "adjacent_rank_flag": adjacent_rank_flag,
        }
        row["pair_relational_v3"] = {
            "pair_margin_abs": margin_abs,
            "pair_relative_margin": relative_margin,
            "pair_rank_gap_abs": rank_gap_abs,
            "pair_adjacent_rank_flag": adjacent_rank_flag,
            "pair_gap_to_next_best": pair_gap_to_next_best,
            "pair_gap_to_prev_best": pair_gap_to_prev_best,
            "pair_uncertainty_std_mean": pair_std_mean,
            "pair_uncertainty_std_diff": pair_std_diff,
            "pair_score_gap_to_top_diff": score_gap_to_top_diff,
            "pair_shadow_price_adjusted_margin_proxy": shadow_price_adjusted_margin_proxy,
            "pair_margin_x_budget": margin_abs * budget_norm,
            "uncertainty_x_budget": pair_std_mean * budget_norm,
            "expected_gain_per_cost_proxy_diff": expected_gain_cost_proxy_i - expected_gain_cost_proxy_j,
            "branch_vs_outside_gap_x_budget_diff": float(fi3.get("branch_vs_outside_gap_x_budget", 0.0)) - float(fj3.get("branch_vs_outside_gap_x_budget", 0.0)),
            "pair_best_vs_outside_gap": best_outside_gap,
            "pair_both_below_outside_flag": both_below_outside,
            "defer_candidate_flag": 1.0 if (margin_abs <= float(cfg.defer_abs_margin_threshold) or pair_std_mean >= float(cfg.defer_std_threshold)) else 0.0,
            "outside_option_advantage_abs": abs(min(outside_i, outside_j)),
            "outside_option_margin_to_best_branch": outside_margin_to_best,
            "stop_or_defer_proxy_score_mean": 0.5 * (float(fi3.get("stop_or_defer_proxy_score", 0.0)) + float(fj3.get("stop_or_defer_proxy_score", 0.0))),
            "rank_instability_under_small_margin": float(max(fi3.get("frontier_rank_instability_proxy", 0.0), fj3.get("frontier_rank_instability_proxy", 0.0)))
            * (1.0 if margin_abs <= float(cfg.near_tie_margin) else 0.0),
            "high_uncertainty_and_small_gap_flag": 1.0 if (pair_std_mean >= float(cfg.defer_std_threshold) and margin_abs <= float(cfg.defer_abs_margin_threshold)) else 0.0,
            "low_gap_high_entropy_like_flag": 1.0 if (margin_abs <= float(cfg.defer_abs_margin_threshold) and max(float(fi.get("frontier_score_entropy", 0.0)), float(fj.get("frontier_score_entropy", 0.0))) >= 0.8) else 0.0,
            "disagreement_risk_score": disagreement_risk,
        }
        row["x_pair_v3"] = [float(v) for v in row["x_diff"]] + [float(row["pair_relational_v3"].get(name, 0.0)) for name in PAIR_RELATIONAL_FEATURE_NAMES_V3]
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
        row["pair_margin_abs"] = margin_abs
        row["pair_relative_margin"] = relative_margin
        row["pair_uncertainty_std_mean"] = pair_std_mean
        row["pair_best_vs_outside_gap"] = best_outside_gap
        defer_flag = _is_defer_pair(row, cfg)
        binary_label = int(row.get("label", 0))
        row["ternary_defer_label"] = 1 if defer_flag else (2 if binary_label == 1 else 0)
        if row["ternary_defer_label"] == 1:
            row["ternary_defer_label_name"] = "defer_or_outside_option"
        elif row["ternary_defer_label"] == 2:
            row["ternary_defer_label_name"] = "allocate_to_branch_i"
        else:
            row["ternary_defer_label_name"] = "allocate_to_branch_j"

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
        "pair_feature_names_v3": PAIR_RELATIONAL_FEATURE_NAMES_V3,
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


def _fit_pairwise_defer_classifier(rows: list[dict[str, Any]], cfg: LearningConfig) -> dict[str, Any]:
    if not cfg.train_pairwise_defer_classifier:
        return {"model_type": "pairwise_defer_multinomial_logreg", "status": "disabled"}
    train = [r for r in rows if r["split"] == "train" and bool(r.get("include_for_pairwise_training", True))]
    if len(train) < 3:
        return {"model_type": "pairwise_defer_multinomial_logreg", "status": "insufficient_train_rows"}
    x = [r.get("x_pair_v3", r["x_diff"]) for r in train]
    y = [int(r.get("ternary_defer_label", 1)) for r in train]
    weights = [float(r.get("pair_train_weight", 1.0)) for r in train]
    if len(set(y)) < 2:
        return {
            "model_type": "pairwise_defer_multinomial_logreg",
            "status": "single_class_train",
            "constant_label": int(y[0]) if y else 1,
        }
    model = LogisticRegression(
        max_iter=max(500, cfg.pairwise_max_iter),
        random_state=cfg.seed,
        multi_class="multinomial",
    )
    model.fit(x, y, sample_weight=weights)
    return {
        "model_type": "pairwise_defer_multinomial_logreg",
        "status": "ok",
        "feature_names": _feature_names_for_set(str(cfg.feature_set)) + PAIR_RELATIONAL_FEATURE_NAMES_V3,
        "feature_set": str(cfg.feature_set),
        "weights": [[float(v) for v in row] for row in model.coef_],
        "intercepts": [float(v) for v in model.intercept_],
        "classes": [int(c) for c in model.classes_],
        "training_rows": len(train),
        "defer_config": {
            "defer_abs_margin_threshold": float(cfg.defer_abs_margin_threshold),
            "defer_relative_margin_threshold": float(cfg.defer_relative_margin_threshold),
            "defer_std_threshold": float(cfg.defer_std_threshold),
            "defer_use_outside_option": bool(cfg.defer_use_outside_option),
            "defer_outside_gap_threshold": float(cfg.defer_outside_gap_threshold),
            "defer_include_approx": bool(cfg.defer_include_approx),
            "defer_require_exact_or_mixed": bool(cfg.defer_require_exact_or_mixed),
            "defer_model_type": str(cfg.defer_model_type),
        },
    }


def _deterministic_cap_rows(rows: list[dict[str, Any]], cap: int, seed: int) -> tuple[list[dict[str, Any]], bool]:
    if len(rows) <= cap:
        return rows, False
    ordered = sorted(
        rows,
        key=lambda r: _stable_hash01(
            f"{seed}|{r.get('state_id', '')}|{r.get('branch_i', '')}|{r.get('branch_j', '')}|{r.get('example_id', '')}"
        ),
    )
    return ordered[:cap], True


def _fit_pairwise_linear_svm(rows: list[dict[str, Any]], cfg: LearningConfig, model_artifact_dir: Path | None) -> dict[str, Any]:
    if model_artifact_dir is None:
        return {"model_type": "pairwise_linear_svm", "status": "artifact_dir_required"}
    train = [r for r in rows if r["split"] == "train" and bool(r.get("include_for_pairwise_training", True))]
    if len(train) < 2:
        return {"model_type": "pairwise_linear_svm", "status": "insufficient_train_rows"}
    x = np.array([r["x_diff"] for r in train], dtype=float)
    y = np.array([int(r["label"]) for r in train], dtype=int)
    if len(set(y.tolist())) < 2:
        return {
            "model_type": "pairwise_linear_svm",
            "status": "single_class_train",
            "constant_label": int(y[0]),
        }
    weights = np.array([float(r.get("pair_train_weight", 1.0)) for r in train], dtype=float)
    use_sample_weight = bool(cfg.svm_use_sample_weight)
    class_weight = "balanced" if cfg.svm_class_weight_balanced else None
    model = LinearSVC(C=float(cfg.svm_c), class_weight=class_weight, random_state=cfg.seed, max_iter=max(2000, cfg.pairwise_max_iter))
    if use_sample_weight:
        model.fit(x, y, sample_weight=weights)
    else:
        model.fit(x, y)
    model_path = model_artifact_dir / "pairwise_linear_svm.joblib"
    joblib.dump(model, model_path)
    return {
        "model_type": "pairwise_linear_svm",
        "status": "ok",
        "feature_names": _feature_names_for_set(str(cfg.feature_set)),
        "feature_set": str(cfg.feature_set),
        "model_path": str(model_path),
        "training_rows": len(train),
        "used_pair_train_weight": use_sample_weight,
        "svm_variant": "linear",
        "svm_hyperparameters": {
            "svm_c": float(cfg.svm_c),
            "svm_class_weight_balanced": bool(cfg.svm_class_weight_balanced),
            "svm_use_sample_weight": bool(cfg.svm_use_sample_weight),
            "svm_margin_calibration": str(cfg.svm_margin_calibration),
            "svm_random_state": int(cfg.seed),
        },
    }


def _fit_pairwise_nystroem_svm(rows: list[dict[str, Any]], cfg: LearningConfig, model_artifact_dir: Path | None) -> dict[str, Any]:
    if model_artifact_dir is None:
        return {"model_type": "pairwise_nystroem_svm", "status": "artifact_dir_required"}
    train = [r for r in rows if r["split"] == "train" and bool(r.get("include_for_pairwise_training", True))]
    if len(train) < 2:
        return {"model_type": "pairwise_nystroem_svm", "status": "insufficient_train_rows"}
    capped_train, was_capped = _deterministic_cap_rows(train, int(cfg.svm_max_train_rows_for_nystroem), int(cfg.seed))
    x = np.array([r["x_diff"] for r in capped_train], dtype=float)
    y = np.array([int(r["label"]) for r in capped_train], dtype=int)
    if len(set(y.tolist())) < 2:
        return {
            "model_type": "pairwise_nystroem_svm",
            "status": "single_class_train",
            "constant_label": int(y[0]),
        }
    weights = np.array([float(r.get("pair_train_weight", 1.0)) for r in capped_train], dtype=float)
    use_sample_weight = bool(cfg.svm_use_sample_weight)
    class_weight = "balanced" if cfg.svm_class_weight_balanced else None
    n_components = int(min(max(8, int(cfg.svm_nystroem_components)), max(8, x.shape[0])))
    nystroem = Nystroem(
        kernel="rbf",
        gamma=float(cfg.svm_nystroem_gamma),
        n_components=n_components,
        random_state=cfg.seed,
    )
    z = nystroem.fit_transform(x)
    svm = LinearSVC(C=float(cfg.svm_c), class_weight=class_weight, random_state=cfg.seed, max_iter=max(2000, cfg.pairwise_max_iter))
    if use_sample_weight:
        svm.fit(z, y, sample_weight=weights)
    else:
        svm.fit(z, y)
    model_bundle = {"feature_map": nystroem, "classifier": svm}
    model_path = model_artifact_dir / "pairwise_nystroem_svm.joblib"
    joblib.dump(model_bundle, model_path)
    return {
        "model_type": "pairwise_nystroem_svm",
        "status": "ok",
        "feature_names": _feature_names_for_set(str(cfg.feature_set)),
        "feature_set": str(cfg.feature_set),
        "model_path": str(model_path),
        "training_rows": len(capped_train),
        "used_pair_train_weight": use_sample_weight,
        "svm_variant": "nystroem_rbf",
        "svm_hyperparameters": {
            "svm_c": float(cfg.svm_c),
            "svm_nystroem_gamma": float(cfg.svm_nystroem_gamma),
            "svm_max_train_rows_for_nystroem": int(cfg.svm_max_train_rows_for_nystroem),
            "svm_nystroem_components": int(cfg.svm_nystroem_components),
            "svm_class_weight_balanced": bool(cfg.svm_class_weight_balanced),
            "svm_use_sample_weight": bool(cfg.svm_use_sample_weight),
            "svm_margin_calibration": str(cfg.svm_margin_calibration),
            "svm_random_state": int(cfg.seed),
        },
        "training_capped": bool(was_capped),
        "training_rows_before_cap": len(train),
    }


def _fit_pairwise_svm_model(rows: list[dict[str, Any]], cfg: LearningConfig, model_artifact_dir: Path | None) -> dict[str, Any]:
    if not cfg.train_pairwise_svm:
        return {"model_type": "pairwise_linear_svm", "status": "disabled"}
    if bool(cfg.train_pairwise_svm_nystroem):
        return _fit_pairwise_nystroem_svm(rows, cfg, model_artifact_dir)
    return _fit_pairwise_linear_svm(rows, cfg, model_artifact_dir)


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
    if cfg.train_pairwise_svm:
        models["pairwise_svm_linear"] = _fit_pairwise_linear_svm(tables["pairwise"], cfg, model_artifact_dir)
    if cfg.train_pairwise_svm and cfg.train_pairwise_svm_nystroem:
        models["pairwise_svm_nystroem"] = _fit_pairwise_nystroem_svm(tables["pairwise"], cfg, model_artifact_dir)
    if cfg.train_pairwise_ternary:
        models["pairwise_ternary"] = _fit_pairwise_ternary_model(tables["pairwise"], cfg)
    if cfg.train_pairwise_defer_classifier:
        models["pairwise_defer_classifier"] = _fit_pairwise_defer_classifier(tables["pairwise"], cfg)
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


def pairwise_decision_function_from_model(model: dict[str, Any]) -> Callable[[dict[str, Any]], float]:
    status = str(model.get("status", ""))
    if status != "ok":
        constant = float(model.get("constant_label", 0.0))
        return lambda _row: 1.0 if constant >= 0.5 else -1.0
    model_type = str(model.get("model_type", ""))
    if model_type == "pairwise_logreg":
        w = [float(v) for v in model.get("weights", [])]
        b = float(model.get("intercept", 0.0))
        return lambda row: _dot(w, row["x_diff"]) + b
    if model_type == "pairwise_linear_svm":
        svm = joblib.load(str(model.get("model_path", "")))
        return lambda row: float(svm.decision_function(np.array([row["x_diff"]], dtype=float))[0])
    if model_type == "pairwise_nystroem_svm":
        bundle = joblib.load(str(model.get("model_path", "")))
        feature_map = bundle["feature_map"]
        classifier = bundle["classifier"]
        return lambda row: float(classifier.decision_function(feature_map.transform(np.array([row["x_diff"]], dtype=float)))[0])
    return lambda row: 0.0


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
    score_fn: Callable[[dict[str, Any]], float] | None,
    pair_decision_fn: Callable[[dict[str, Any]], float] | None,
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
        if pair_decision_fn is not None:
            margin = float(pair_decision_fn(r))
            pred_label = 1 if margin >= 0.0 else 0
            pred_prob = _sigmoid(margin)
        else:
            assert score_fn is not None
            si = score_fn({"x": r["x_i"]})
            sj = score_fn({"x": r["x_j"]})
            margin = si - sj
            pred_label = 1 if margin >= 0.0 else 0
            pred_prob = _sigmoid(margin)
        y = int(r["label"])
        correct += int(pred_label == y)
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
    score_fn: Callable[[dict[str, Any]], float] | None,
    pair_decision_fn: Callable[[dict[str, Any]], float] | None,
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
            if pair_decision_fn is not None:
                margin = float(pair_decision_fn(r))
                pred = 1 if margin >= 0.0 else 0
            else:
                assert score_fn is not None
                si = score_fn({"x": r["x_i"]})
                sj = score_fn({"x": r["x_j"]})
                pred = 1 if si >= sj else 0
            ok += int(pred == int(r["label"]))
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
    pair_types = sorted({str(r.get("pair_type", "unknown")) for r in subset})
    by_pair_type = {
        p: acc_for(lambda r, pp=p: str(r.get("pair_type", "unknown")) == pp)
        for p in pair_types
    }
    label_sources = sorted({str(r.get("label_source", "unknown")) for r in subset})
    by_label_source = {
        s: acc_for(lambda r, ss=s: str(r.get("label_source", "unknown")) == ss)
        for s in label_sources
    }
    return {
        "pairwise_accuracy_by_budget": by_budget,
        "pairwise_accuracy_by_mode": by_mode,
        "pairwise_accuracy_by_dataset": by_dataset,
        "pairwise_accuracy_by_pair_type": by_pair_type,
        "pairwise_accuracy_by_label_source": by_label_source,
    }


def _eval_pairwise_defer_classifier(model: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    status = str(model.get("status", ""))
    if status != "ok":
        return {"model_status": status}
    w = np.array(model.get("weights", []), dtype=float)
    b = np.array(model.get("intercepts", []), dtype=float)
    classes = [int(c) for c in model.get("classes", [0, 1, 2])]
    test = [r for r in rows if r.get("split") == "test"]
    if not test:
        return {"model_status": "ok", "three_way_accuracy_test": 0.0}
    y_true = np.array([int(r.get("ternary_defer_label", 1)) for r in test], dtype=int)
    x = np.array([r.get("x_pair_v3", r["x_diff"]) for r in test], dtype=float)
    logits = x @ w.T + b
    y_pred = np.array([classes[int(i)] for i in np.argmax(logits, axis=1)], dtype=int)
    three_way_acc = float(np.mean(y_pred == y_true))
    pred_defer = y_pred == 1
    true_defer = y_true == 1
    tp = int(np.sum(pred_defer & true_defer))
    fp = int(np.sum(pred_defer & (~true_defer)))
    fn = int(np.sum((~pred_defer) & true_defer))
    defer_precision = tp / max(1, tp + fp)
    defer_recall = tp / max(1, tp + fn)
    defer_f1 = 0.0 if (defer_precision + defer_recall) <= 0 else (2.0 * defer_precision * defer_recall) / (defer_precision + defer_recall)
    accept_mask = y_pred != 1
    accepted_only_acc = float(np.mean(y_pred[accept_mask] == y_true[accept_mask])) if np.any(accept_mask) else 0.0
    coverage = float(np.mean(accept_mask))

    def _accepted_slice_acc(predicate: Callable[[dict[str, Any]], bool]) -> float:
        idxs = [i for i, r in enumerate(test) if predicate(r) and bool(accept_mask[i])]
        if not idxs:
            return 0.0
        return float(np.mean(y_pred[idxs] == y_true[idxs]))

    confusion = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    for yt, yp in zip(y_true.tolist(), y_pred.tolist()):
        confusion[int(yt)][int(yp)] += 1
    return {
        "model_status": "ok",
        "three_way_accuracy_test": three_way_acc,
        "defer_precision_test": defer_precision,
        "defer_recall_test": defer_recall,
        "defer_f1_test": defer_f1,
        "accepted_only_accuracy_test": accepted_only_acc,
        "coverage_test": coverage,
        "near_tie_accepted_accuracy_test": _accepted_slice_acc(lambda r: abs(float(r.get("margin", 0.0))) <= 0.05),
        "adjacent_rank_accepted_accuracy_test": _accepted_slice_acc(lambda r: str(r.get("pair_type", "")) == "adjacent_rank"),
        "exact_promoted_hard_region_accepted_accuracy_test": _accepted_slice_acc(
            lambda r: str(r.get("label_source", "")) == "exact_promoted_hard_region"
        ),
        "confusion_matrix_left_defer_right_test": confusion,
        "ranking_top1_accuracy_test": None,
        "note": "pairwise defer classifier evaluated in pairwise space; candidate top-1 ranking not defined",
    }


def evaluate_models(models: dict[str, Any], tables: dict[str, Any], cfg: LearningConfig) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, model in models.items():
        if str(model.get("model_type", "")) == "pairwise_defer_multinomial_logreg":
            out[name] = _eval_pairwise_defer_classifier(model, tables["pairwise"])
            continue
        if str(model.get("model_type", "")) == "pairwise_ternary_logreg":
            out[name] = {
                "model_status": model.get("status", "unknown"),
                "note": "pairwise_ternary_logreg requires pair-level evaluation; candidate ranking metrics are not computed here",
            }
            continue
        model_type = str(model.get("model_type", ""))
        pairwise_only = model_type in {"pairwise_linear_svm", "pairwise_nystroem_svm"}
        scorer = None if pairwise_only else scorer_from_model(model)
        pair_decision_fn = pairwise_decision_function_from_model(model) if model_type.startswith("pairwise_") else None
        pair_acc, near_acc, far_acc, brier = _pairwise_agreement(
            tables["pairwise"],
            scorer,
            pair_decision_fn,
            "test",
            near_tie_margin=float(cfg.near_tie_margin),
        )
        top1 = None
        if scorer is not None:
            top1 = _ranking_top1_accuracy(tables["state_to_candidates"], scorer, "test")
        slices = _slice_pairwise_accuracy(
            tables["pairwise"],
            scorer,
            pair_decision_fn,
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
            "adjacent_rank_pairwise_accuracy_test": slices.get("pairwise_accuracy_by_pair_type", {}).get("adjacent_rank", 0.0),
            "exact_promoted_pairwise_accuracy_test": slices.get("pairwise_accuracy_by_label_source", {}).get("exact_promoted", 0.0),
            "exact_promoted_hard_region_pairwise_accuracy_test": slices.get("pairwise_accuracy_by_label_source", {}).get("exact_promoted_hard_region", 0.0),
            **slices,
        }
        if top1 is None:
            out[name]["note"] = "ranking_top1_accuracy_test omitted for pairwise-difference-only SVM model"
        if model_type in {"pairwise_linear_svm", "pairwise_nystroem_svm"} and str(cfg.svm_margin_calibration) != "platt":
            out[name]["pairwise_margin_brier_test"] = "not_applicable"
            out[name]["note"] = (
                f"{out[name].get('note', '')}; brier omitted because svm_margin_calibration={cfg.svm_margin_calibration}"
            ).strip("; ")
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
        "SVM results are bounded margin-based baselines and are not by themselves evidence that supervision-target bottlenecks are solved.",
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
