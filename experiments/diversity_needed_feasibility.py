from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)

from experiments.bruteforce_branch_labels import (
    BruteForceLabelConfig,
    collect_frontier_states,
    config_to_dict,
    evaluate_state_candidates,
    load_dataset_examples,
    write_jsonl,
)


@dataclass(frozen=True)
class DiversityNeededFeasibilityConfig:
    seed: int = 23
    run_id: str = "diversity_needed_feasibility_20260419"
    output_dir: str = "outputs/branch_label_bruteforce_learning"
    max_frontier_states: int = 84
    frontier_budget: int = 7
    rollout_samples_per_candidate: int = 8
    max_allocation_samples: int = 18
    target_estimation_repeats: int = 2
    min_remaining_budget: int = 2
    max_remaining_budget: int = 5
    episodes_per_example: int = 2
    diversity_plausibility_margin: float = 0.12
    diversity_threshold: float = 0.0
    gate_threshold: float = 0.0


def _stable_hash01(text: str) -> float:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:12], 16) / float(16**12)


def _split_name(state_id: str) -> str:
    bucket = _stable_hash01(state_id)
    if bucket < 0.7:
        return "train"
    if bucket < 0.85:
        return "val"
    return "test"


def _entropy(counts: list[int]) -> float:
    total = float(sum(counts))
    if total <= 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return float(-sum(p * math.log(max(p, 1e-12)) for p in probs))


def _branch_vec(row: dict[str, Any]) -> np.ndarray:
    f = row.get("features_branch_v1", {})
    return np.asarray(
        [
            float(f.get("score", 0.0)),
            float(f.get("depth", 0.0)) / 8.0,
            float(f.get("recent_delta", 0.0)),
            float(f.get("verify_count", 0.0)) / 4.0,
            float(f.get("stalled_steps", 0.0)) / 6.0,
            float(f.get("branch_age", 0.0)) / 8.0,
        ],
        dtype=np.float64,
    )


def _answer_group_key(row: dict[str, Any]) -> str:
    f = row.get("features_branch_v1", {})
    score_bin = int(min(4, max(0, math.floor(float(f.get("score", 0.0)) * 5.0))))
    depth_bin = int(min(3, float(f.get("depth", 0.0)) // 2))
    delta_sign = "pos" if float(f.get("recent_delta", 0.0)) >= 0.0 else "neg"
    verify_bin = int(min(2, float(f.get("verify_count", 0.0))))
    return f"s{score_bin}_d{depth_bin}_v{verify_bin}_{delta_sign}"


def _build_state_row(state_summary: dict[str, Any], candidate_rows: list[dict[str, Any]], cfg: DiversityNeededFeasibilityConfig) -> dict[str, Any]:
    support: dict[str, int] = {}
    group_members: dict[str, list[dict[str, Any]]] = {}
    for row in candidate_rows:
        key = _answer_group_key(row)
        support[key] = support.get(key, 0) + 1
        group_members.setdefault(key, []).append(row)

    sorted_support = sorted(support.items(), key=lambda kv: (-kv[1], kv[0]))
    top_group, top_group_count = sorted_support[0]
    second_group_count = sorted_support[1][1] if len(sorted_support) > 1 else 0
    n = len(candidate_rows)

    top_score = max(float(r.get("features_branch_v1", {}).get("score", 0.0)) for r in candidate_rows)
    plausible = [
        r
        for r in candidate_rows
        if float(r.get("features_branch_v1", {}).get("score", 0.0)) >= max(0.20, top_score - float(cfg.diversity_plausibility_margin))
    ]
    undercovered_groups = {g for g, c in support.items() if c < top_group_count}
    plausible_undercovered = [r for r in plausible if _answer_group_key(r) in undercovered_groups]

    def _diversity_priority(row: dict[str, Any]) -> float:
        key = _answer_group_key(row)
        cont = float(row.get("estimated_value_if_allocate_next", 0.0))
        support_count = float(support.get(key, 1))
        vec = _branch_vec(row)
        overlap = 0.0
        if candidate_rows:
            sims = []
            for other in candidate_rows:
                ov = float(np.dot(vec, _branch_vec(other)) / (np.linalg.norm(vec) * np.linalg.norm(_branch_vec(other)) + 1e-8))
                sims.append(ov)
            overlap = float(np.mean(sims))
        diversity_bonus = 1.0 / (1.0 + support_count)
        return cont + 0.08 * diversity_bonus - 0.04 * overlap

    diverse_pool = plausible_undercovered if plausible_undercovered else plausible
    diverse_pick = max(diverse_pool, key=_diversity_priority)

    nondiverse_pool = [r for r in candidate_rows if _answer_group_key(r) == top_group]
    exploit_pick = max(nondiverse_pool, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0))) if nondiverse_pool else max(
        candidate_rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0))
    )

    q_diverse = float(diverse_pick.get("estimated_value_if_allocate_next", 0.0))
    q_exploit = float(exploit_pick.get("estimated_value_if_allocate_next", 0.0))
    q_commit = float(state_summary.get("Q_commit", 0.0))
    q_nondiv = max(q_exploit, q_commit)
    y = q_diverse - q_nondiv

    vecs = [_branch_vec(r) for r in candidate_rows]
    sims: list[float] = []
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            num = float(np.dot(vecs[i], vecs[j]))
            den = float(np.linalg.norm(vecs[i]) * np.linalg.norm(vecs[j]) + 1e-8)
            sims.append(num / den)
    sim_mean = float(np.mean(sims)) if sims else 0.0
    sim_max = float(np.max(sims)) if sims else 0.0
    duplicate_rate = float(sum(1 for s in sims if s > 0.98) / max(1, len(sims))) if sims else 0.0

    scores = sorted([float(r.get("features_branch_v1", {}).get("score", 0.0)) for r in candidate_rows], reverse=True)
    top = scores[0]
    second = scores[1] if len(scores) > 1 else scores[0]
    novelty_gain = float(np.mean([max(0.0, float(r.get("features_branch_v1", {}).get("recent_delta", 0.0))) for r in candidate_rows]))
    new_group_recent = 1.0 if any(float(r.get("features_branch_v1", {}).get("branch_age", 0.0)) <= 1.0 and _answer_group_key(r) in undercovered_groups for r in candidate_rows) else 0.0

    reliabilities = [float(r.get("target_reliability", 0.0)) for r in candidate_rows]
    stderrs = [float(r.get("target_stderr", 0.0)) for r in candidate_rows]
    provenance = state_summary.get("candidate_mode", "approx")

    ambiguity = str(state_summary.get("ambiguity_bucket", "high_margin"))
    near_tie = 1.0 if ambiguity == "near_tie" else 0.0

    failure_group = "diversity_saturated"
    if y > 0:
        failure_group = "insufficient_diversity_realized"
    elif near_tie > 0 and len(support) >= 2:
        failure_group = "near_tie_ambiguity"

    return {
        "state_id": str(state_summary["state_id"]),
        "example_id": str(state_summary["example_id"]),
        "split": _split_name(str(state_summary["state_id"])),
        "dataset_name": str(state_summary.get("dataset_name", "unknown")),
        "task_type": "math_word_problem",
        "remaining_budget": float(state_summary.get("remaining_budget", 0.0)),
        "n_active_branches": float(n),
        "n_answer_groups": float(len(support)),
        "answer_group_entropy": _entropy(list(support.values())),
        "top_group_support_fraction": float(top_group_count / max(1, n)),
        "top_minus_second_support_margin": float((top_group_count - second_group_count) / max(1, n)),
        "dominant_group_branch_fraction": float(top_group_count / max(1, n)),
        "novelty_gain_recent": novelty_gain,
        "new_answer_group_recent_flag": new_group_recent,
        "semantic_overlap_mean": sim_mean,
        "semantic_overlap_max": sim_max,
        "duplicate_rate": duplicate_rate,
        "undercovered_group_count": float(len(undercovered_groups)),
        "branch_score_std": float(np.std(scores)) if len(scores) > 1 else 0.0,
        "top_branch_score": float(top),
        "second_branch_score": float(second),
        "top_second_score_margin": float(top - second),
        "commit_readiness_q_commit": q_commit,
        "one_step_continuation_best": float(max(float(r.get("estimated_value_if_allocate_next", 0.0)) for r in candidate_rows)),
        "one_step_continuation_minus_commit": float(max(float(r.get("estimated_value_if_allocate_next", 0.0)) for r in candidate_rows) - q_commit),
        "ambiguity_near_tie_flag": near_tie,
        "ambiguity_medium_flag": 1.0 if ambiguity == "medium_margin" else 0.0,
        "target_reliability_mean": float(np.mean(reliabilities)) if reliabilities else 0.0,
        "target_stderr_mean": float(np.mean(stderrs)) if stderrs else 0.0,
        "target_provenance": provenance,
        "target_provenance_exact_flag": 1.0 if provenance == "exact" else 0.0,
        "target_provenance_approx_flag": 1.0 if provenance == "approx" else 0.0,
        "failure_group": failure_group,
        "diversity_action_branch_id": str(diverse_pick.get("branch_id", "")),
        "diversity_action_group": _answer_group_key(diverse_pick),
        "diversity_action_definition": "expand_plausible_undercovered_group_with_diversity_priority",
        "q_diverse_expand": q_diverse,
        "q_exploit_expand": q_exploit,
        "q_commit": q_commit,
        "q_best_nondiverse": q_nondiv,
        "y_diversity_needed": y,
        "needs_more_diversity": 1 if y > float(cfg.diversity_threshold) else 0,
    }


def _feature_columns(rows: list[dict[str, Any]]) -> list[str]:
    skip = {
        "state_id",
        "example_id",
        "split",
        "dataset_name",
        "task_type",
        "target_provenance",
        "failure_group",
        "diversity_action_branch_id",
        "diversity_action_group",
        "diversity_action_definition",
        "needs_more_diversity",
        "y_diversity_needed",
        "q_diverse_expand",
        "q_exploit_expand",
        "q_commit",
        "q_best_nondiverse",
    }
    return [k for k in rows[0].keys() if k not in skip]


def _to_matrix(rows: list[dict[str, Any]], feature_cols: list[str]) -> np.ndarray:
    return np.asarray([[float(r.get(c, 0.0)) for c in feature_cols] for r in rows], dtype=np.float64)


def _classification_metrics(y_true: np.ndarray, pred: np.ndarray, prob: np.ndarray) -> dict[str, float]:
    out = {
        "accuracy": float(accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
    }
    if len(set(y_true.tolist())) > 1:
        out["auc"] = float(roc_auc_score(y_true, prob))
    brier = float(np.mean((prob - y_true) ** 2))
    out["brier"] = brier
    return out


def _regression_metrics(y_true: np.ndarray, pred: np.ndarray) -> dict[str, float | None]:
    # sklearn's r2_score is undefined for n < 2; keep smoke tests warning-free.
    r2_value: float | None = None
    if len(y_true) >= 2:
        r2_value = float(r2_score(y_true, pred))
    return {
        "mae": float(mean_absolute_error(y_true, pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_true, pred))),
        "r2": r2_value,
    }


def _calibration_summary(y: np.ndarray, p: np.ndarray, bins: int = 5) -> list[dict[str, float]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    out: list[dict[str, float]] = []
    for i in range(bins):
        lo, hi = float(edges[i]), float(edges[i + 1])
        mask = (p >= lo) & (p < hi if i < bins - 1 else p <= hi)
        if int(mask.sum()) == 0:
            continue
        out.append(
            {
                "bin_lo": lo,
                "bin_hi": hi,
                "count": int(mask.sum()),
                "mean_pred": float(np.mean(p[mask])),
                "empirical_positive_rate": float(np.mean(y[mask])),
            }
        )
    return out


def run_feasibility_pass(cfg: DiversityNeededFeasibilityConfig) -> dict[str, Any]:
    out_root = Path(cfg.output_dir) / cfg.run_id
    out_root.mkdir(parents=True, exist_ok=True)

    label_cfg = BruteForceLabelConfig(
        seed=int(cfg.seed),
        max_frontier_states=int(cfg.max_frontier_states),
        frontier_budget=int(cfg.frontier_budget),
        rollout_samples_per_candidate=int(cfg.rollout_samples_per_candidate),
        max_allocation_samples=int(cfg.max_allocation_samples),
        target_estimation_repeats=int(cfg.target_estimation_repeats),
        min_remaining_budget=int(cfg.min_remaining_budget),
        max_remaining_budget=int(cfg.max_remaining_budget),
        episodes_per_example=int(cfg.episodes_per_example),
        exact_mode=True,
        allow_mock_data=True,
    )

    examples = load_dataset_examples(label_cfg)
    states = collect_frontier_states(examples, label_cfg)

    summaries: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []

    for state in states:
        eval_out = evaluate_state_candidates(state, label_cfg)
        ss = dict(eval_out["state_summary"])
        ss["dataset_name"] = label_cfg.dataset_name
        cand = [
            {
                **c,
                "state_id": state.state_id,
                "example_id": state.example_id,
                "remaining_budget": state.remaining_budget,
                "dataset_name": label_cfg.dataset_name,
            }
            for c in eval_out["candidate_labels"]
        ]
        summaries.append(ss)
        candidates.extend(cand)
        state_rows.append(_build_state_row(ss, cand, cfg))

    labels_dir = out_root / "labels"
    write_jsonl(labels_dir / "state_summaries.jsonl", summaries)
    write_jsonl(labels_dir / "candidate_labels.jsonl", candidates)
    write_jsonl(labels_dir / "diversity_needed_state_dataset.jsonl", state_rows)

    feature_cols = _feature_columns(state_rows)
    split_rows = {
        split: [r for r in state_rows if r["split"] == split]
        for split in ("train", "val", "test")
    }
    train, val, test = split_rows["train"], split_rows["val"], split_rows["test"]

    X_train = _to_matrix(train, feature_cols)
    X_test = _to_matrix(test, feature_cols)
    y_train_reg = np.asarray([float(r["y_diversity_needed"]) for r in train], dtype=np.float64)
    y_test_reg = np.asarray([float(r["y_diversity_needed"]) for r in test], dtype=np.float64)
    y_train_cls = np.asarray([int(r["needs_more_diversity"]) for r in train], dtype=np.int64)
    y_test_cls = np.asarray([int(r["needs_more_diversity"]) for r in test], dtype=np.int64)

    ridge = Ridge(alpha=1.0, random_state=int(cfg.seed))
    ridge.fit(X_train, y_train_reg)
    reg_gbt = GradientBoostingRegressor(random_state=int(cfg.seed))
    reg_gbt.fit(X_train, y_train_reg)

    logreg = LogisticRegression(max_iter=1000, random_state=int(cfg.seed), class_weight="balanced")
    logreg.fit(X_train, y_train_cls)
    cls_gbt = GradientBoostingClassifier(random_state=int(cfg.seed))
    cls_gbt.fit(X_train, y_train_cls)

    pred_ridge = ridge.predict(X_test)
    pred_reg_gbt = reg_gbt.predict(X_test)
    prob_log = logreg.predict_proba(X_test)[:, 1]
    pred_log = (prob_log >= 0.5).astype(np.int64)
    prob_gbt = cls_gbt.predict_proba(X_test)[:, 1]
    pred_gbt = (prob_gbt >= 0.5).astype(np.int64)

    eval_summary: dict[str, Any] = {
        "regression": {
            "ridge": _regression_metrics(y_test_reg, pred_ridge),
            "gradient_boosted_tree": _regression_metrics(y_test_reg, pred_reg_gbt),
        },
        "classification": {
            "logistic": _classification_metrics(y_test_cls, pred_log, prob_log),
            "gradient_boosted_tree": _classification_metrics(y_test_cls, pred_gbt, prob_gbt),
            "calibration_test_gbt": _calibration_summary(y_test_cls, prob_gbt),
        },
    }

    def _bucket_eval(bucket_key: str, value: str) -> dict[str, float]:
        rows = [r for r in test if str(r.get(bucket_key, "")) == value]
        if not rows:
            return {}
        X = _to_matrix(rows, feature_cols)
        y = np.asarray([int(r["needs_more_diversity"]) for r in rows], dtype=np.int64)
        p = cls_gbt.predict_proba(X)[:, 1]
        pred = (p >= 0.5).astype(np.int64)
        return _classification_metrics(y, pred, p)

    breakdown = {
        "by_ambiguity": {
            "near_tie": _bucket_eval("ambiguity_near_tie_flag", "1.0"),
            "not_near_tie": _bucket_eval("ambiguity_near_tie_flag", "0.0"),
        },
        "by_provenance": {
            "exact": _bucket_eval("target_provenance", "exact"),
            "approx": _bucket_eval("target_provenance", "approx"),
        },
        "by_failure_group": {
            k: _bucket_eval("failure_group", k)
            for k in sorted({str(r.get("failure_group", "")) for r in test})
        },
    }

    importances = sorted(
        [{"feature": f, "importance": float(v)} for f, v in zip(feature_cols, cls_gbt.feature_importances_)],
        key=lambda r: r["importance"],
        reverse=True,
    )

    ambiguity_only = ["ambiguity_near_tie_flag", "ambiguity_medium_flag", "top_second_score_margin"]
    X_train_amb = _to_matrix(train, ambiguity_only)
    X_test_amb = _to_matrix(test, ambiguity_only)
    amb_model = LogisticRegression(max_iter=1000, random_state=int(cfg.seed), class_weight="balanced")
    amb_model.fit(X_train_amb, y_train_cls)
    p_amb = amb_model.predict_proba(X_test_amb)[:, 1]
    pred_amb = (p_amb >= 0.5).astype(np.int64)
    ablation = {
        "ambiguity_only_logistic": _classification_metrics(y_test_cls, pred_amb, p_amb),
        "full_feature_gbt": _classification_metrics(y_test_cls, pred_gbt, prob_gbt),
    }

    # lightweight policy gate check on test split
    realized_gate = []
    realized_diverse = []
    realized_nondiv = []
    realized_oracle = []
    for row, p in zip(test, prob_gbt):
        choose_diverse = p > float(cfg.gate_threshold)
        gate_q = float(row["q_diverse_expand"] if choose_diverse else row["q_best_nondiverse"])
        realized_gate.append(gate_q)
        realized_diverse.append(float(row["q_diverse_expand"]))
        realized_nondiv.append(float(row["q_best_nondiverse"]))
        realized_oracle.append(float(max(row["q_diverse_expand"], row["q_best_nondiverse"])))
    policy_check = {
        "avg_value_predictor_gate": float(np.mean(realized_gate)) if realized_gate else 0.0,
        "avg_value_always_diverse": float(np.mean(realized_diverse)) if realized_diverse else 0.0,
        "avg_value_always_nondiverse": float(np.mean(realized_nondiv)) if realized_nondiv else 0.0,
        "avg_value_oracle": float(np.mean(realized_oracle)) if realized_oracle else 0.0,
        "n_test_states": len(test),
    }

    metrics = {
        "config": asdict(cfg),
        "label_config": config_to_dict(label_cfg),
        "counts": {"states": len(state_rows), "train": len(train), "val": len(val), "test": len(test)},
        "evaluation": eval_summary,
        "breakdown": breakdown,
        "feature_importance_gbt": importances[:20],
        "ablation": ablation,
        "policy_gate_check": policy_check,
    }

    (out_root / "manifest.json").write_text(
        json.dumps(
            {
                "generator": "diversity_needed_feasibility_v1",
                "artifacts": {
                    "state_dataset": str(labels_dir / "diversity_needed_state_dataset.jsonl"),
                    "state_summaries": str(labels_dir / "state_summaries.jsonl"),
                    "candidate_labels": str(labels_dir / "candidate_labels.jsonl"),
                    "metrics": str(out_root / "metrics.json"),
                    "feature_importance": str(out_root / "feature_importance.json"),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_root / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_root / "feature_importance.json").write_text(json.dumps(importances, indent=2), encoding="utf-8")
    return metrics
