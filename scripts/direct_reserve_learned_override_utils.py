#!/usr/bin/env python3
"""Safe diagnostic learned override selector for direct-reserve candidates."""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from scripts.train_direct_reserve_candidate_scorer import DIVERSE, _feat

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_SCHEMA_VERSION = "direct_reserve_candidate_scorer_dataset_v1"
DEFAULT_MODEL_TYPE = "random_forest"
ALLOWED_MODEL_TYPES = {"random_forest", "pairwise_logit", "logistic"}
RECOMMENDED_MODEL_TYPES = {"random_forest", "pairwise_logit"}
RUNTIME_REQUIRED_FEATURES = (
    "method",
    "normalized_answer",
    "answer_group_id",
    "answer_group_support",
    "answer_group_rank",
    "selected_by_method",
    "top2_support_gap",
    "answer_entropy",
    "extraction_ok",
)


@dataclass
class LearnedOverrideResult:
    final_answer: str
    metadata: dict[str, Any]


def resolve_model_path(model_path: str | Path | None = None) -> Path:
    if model_path:
        p = Path(model_path)
        return p if p.is_absolute() else REPO_ROOT / p
    return REPO_ROOT / "outputs" / "direct_reserve_candidate_scorer_train_20260426T150000Z" / "selected_model.joblib"


def load_scorer_payload(model_path: str | Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    path = resolve_model_path(model_path)
    if not path.exists():
        return {}, {"available": False, "reason": "model_missing", "model_path": str(path)}
    try:
        with path.open("rb") as f:
            payload = pickle.load(f)
        if not isinstance(payload, dict):
            return {}, {"available": False, "reason": "model_payload_not_dict", "model_path": str(path)}
        return payload, {"available": True, "reason": "loaded", "model_path": str(path)}
    except Exception as exc:  # pragma: no cover - exact pickle failures vary by environment
        return {}, {"available": False, "reason": f"model_load_error:{type(exc).__name__}", "model_path": str(path)}


def missing_runtime_features(candidates: list[dict[str, Any]]) -> list[str]:
    if not candidates:
        return list(RUNTIME_REQUIRED_FEATURES)
    missing: set[str] = set()
    for key in RUNTIME_REQUIRED_FEATURES:
        if any(str(c.get(key, "")).strip() == "" for c in candidates):
            missing.add(key)
    return sorted(missing)


def _invalid_answer(answer: Any) -> bool:
    text = str(answer or "").strip().lower()
    return text in {"", "na", "n/a", "none", "__unknown__"}


def _score_margin(scores: list[float], winner_idx: int) -> tuple[float, float, float]:
    if not scores:
        return 0.0, 0.0, 0.0
    ordered = sorted((float(v), i) for i, v in enumerate(scores))
    top = float(ordered[-1][0])
    if len(ordered) == 1:
        return top, 0.0, abs(top)
    second = float(ordered[-2][0]) if ordered[-1][1] == winner_idx else float(ordered[-1][0])
    return top, second, float(top - second)


def _pairwise_scores(candidates: list[dict[str, Any]], payload: dict[str, Any]) -> list[float] | None:
    pvec, plr = payload.get("pair_vectorizer"), payload.get("pair_logit")
    if not pvec or not plr or len(candidates) <= 1:
        return None
    totals = np.zeros(len(candidates), dtype=float)
    for a, b in combinations(range(len(candidates)), 2):
        fa, fb = _feat(candidates[a]), _feat(candidates[b])
        diff = {k: fa.get(k, 0.0) - fb.get(k, 0.0) for k in set(fa) | set(fb)}
        s = float(plr.decision_function(pvec.transform([diff]))[0])
        totals[a] += s
        totals[b] -= s
    return [float(x) for x in totals]


def score_candidates(candidates: list[dict[str, Any]], payload: dict[str, Any], model_type: str = DEFAULT_MODEL_TYPE) -> tuple[list[float] | None, str]:
    mtype = str(model_type or DEFAULT_MODEL_TYPE).strip().lower()
    if mtype == "rf":
        mtype = "random_forest"
    if mtype == "pairwise":
        mtype = "pairwise_logit"
    if mtype not in ALLOWED_MODEL_TYPES:
        return None, "model_type_not_allowed"
    if mtype == "pairwise_logit":
        scores = _pairwise_scores(candidates, payload)
        return scores, "ok" if scores is not None else "pairwise_model_missing"
    vec = payload.get("vectorizer")
    if not vec:
        return None, "vectorizer_missing"
    model_key = "rf" if mtype == "random_forest" else "logistic"
    model = payload.get(model_key)
    if not model:
        return None, f"{model_key}_model_missing"
    X = vec.transform([_feat(c) for c in candidates])
    if mtype == "logistic" and isinstance(model, LogisticRegression):
        return [float(x) for x in model.decision_function(X)], "ok"
    if hasattr(model, "predict_proba"):
        return [float(x) for x in model.predict_proba(X)[:, 1]], "ok"
    if hasattr(model, "decision_function"):
        return [float(x) for x in model.decision_function(X)], "ok"
    return None, "model_has_no_score_api"


def select_learned_override(
    candidates: list[dict[str, Any]],
    *,
    base_selected_answer: str,
    margin_threshold: float = 0.05,
    model_path: str | Path | None = None,
    model_payload: dict[str, Any] | None = None,
    model_type: str = DEFAULT_MODEL_TYPE,
) -> LearnedOverrideResult:
    base_answer = str(base_selected_answer or "")
    base_meta: dict[str, Any] = {
        "learned_override_available": False,
        "learned_override_triggered": False,
        "learned_override_model": str(model_type or DEFAULT_MODEL_TYPE),
        "learned_override_margin": 0.0,
        "learned_override_threshold": float(margin_threshold),
        "base_selected_answer": base_answer,
        "learned_selected_answer": "",
        "final_selected_answer": base_answer,
        "learned_override_reason": "not_evaluated",
        "learned_override_missing_features": [],
        "candidate_feature_schema_version": FEATURE_SCHEMA_VERSION,
        "candidate_count": int(len(candidates)),
        "answer_group_count": int(len({str(c.get("answer_group_id", "")) for c in candidates})),
        "learned_override_top_score": 0.0,
        "learned_override_second_score": 0.0,
        "learned_override_selected_candidate_id": "",
        "learned_override_model_type": str(model_type or DEFAULT_MODEL_TYPE),
    }
    if not candidates:
        base_meta["learned_override_reason"] = "no_candidates"
        return LearnedOverrideResult(base_answer, base_meta)

    mtype = str(model_type or DEFAULT_MODEL_TYPE).strip().lower()
    if mtype in {"hgb", "hist_gboost", "histgradientboosting"}:
        base_meta["learned_override_model"] = mtype
        base_meta["learned_override_reason"] = "hgb_not_allowed"
        return LearnedOverrideResult(base_answer, base_meta)

    missing = missing_runtime_features(candidates)
    if missing:
        base_meta["learned_override_reason"] = "missing_required_features"
        base_meta["learned_override_missing_features"] = missing
        return LearnedOverrideResult(base_answer, base_meta)

    payload = model_payload
    load_meta = {"available": True, "reason": "injected", "model_path": ""}
    if payload is None:
        payload, load_meta = load_scorer_payload(model_path)
    base_meta["learned_override_model_path"] = load_meta.get("model_path", "")
    if not payload:
        base_meta["learned_override_reason"] = str(load_meta.get("reason", "model_unavailable"))
        return LearnedOverrideResult(base_answer, base_meta)

    try:
        scores, reason = score_candidates(candidates, payload, model_type=mtype)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        base_meta["learned_override_available"] = True
        base_meta["learned_override_reason"] = f"score_error:{type(exc).__name__}"
        return LearnedOverrideResult(base_answer, base_meta)
    if not scores:
        base_meta["learned_override_available"] = True
        base_meta["learned_override_reason"] = reason
        return LearnedOverrideResult(base_answer, base_meta)
    winner = int(np.argmax(scores))
    top, second, margin = _score_margin(scores, winner)
    selected = candidates[winner]
    learned_answer = str(selected.get("normalized_answer") or selected.get("answer_group_id") or "")
    base_meta.update(
        {
            "learned_override_available": True,
            "learned_selected_answer": learned_answer,
            "learned_override_top_score": float(top),
            "learned_override_second_score": float(second),
            "learned_override_margin": float(margin),
            "learned_override_selected_candidate_id": str(selected.get("row_id") or selected.get("branch_id") or selected.get("answer_group_id") or ""),
        }
    )
    if _invalid_answer(learned_answer):
        base_meta["learned_override_reason"] = "invalid_learned_answer"
        return LearnedOverrideResult(base_answer, base_meta)
    if margin < float(margin_threshold):
        base_meta["learned_override_reason"] = "below_margin_threshold"
        return LearnedOverrideResult(base_answer, base_meta)
    if learned_answer == base_answer:
        base_meta["learned_override_reason"] = "learned_matches_base"
        base_meta["final_selected_answer"] = base_answer
        return LearnedOverrideResult(base_answer, base_meta)

    base_meta["learned_override_triggered"] = True
    base_meta["learned_override_reason"] = "margin_threshold_met"
    base_meta["final_selected_answer"] = learned_answer
    return LearnedOverrideResult(learned_answer, base_meta)


def build_runtime_answer_group_candidates(
    *,
    question: str,
    dataset: str,
    seed: int,
    budget: int,
    method: str,
    candidate_answers: list[str | None],
    selected_group: str,
    top2_support_gap: float,
    answer_entropy: float,
    action_count: int,
    expansion_count: int,
    verification_count: int,
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    first_answer: dict[str, str] = {}
    for answer in candidate_answers:
        group = str(answer or "").strip()
        if not group:
            continue
        counts[group] = counts.get(group, 0) + 1
        first_answer.setdefault(group, group)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    rows: list[dict[str, Any]] = []
    for rank, (group, support) in enumerate(ordered, start=1):
        rows.append(
            {
                "row_id": f"runtime_answer_group::{rank}",
                "source_type": "answer_group",
                "example_id": "runtime",
                "dataset": dataset,
                "question": question[:20000],
                "stratum": "runtime_unknown",
                "seed": int(seed),
                "budget": int(budget),
                "method": method or DIVERSE,
                "branch_id": f"answer_group::{group}",
                "branch_depth": 0,
                "prompt_style": "NA",
                "normalized_answer": group,
                "answer_group_id": group,
                "answer_group_support": int(support),
                "answer_group_rank": int(rank),
                "selected_by_method": int(group == selected_group),
                "top_answer_group": ordered[0][0] if ordered else "NA",
                "selected_answer_group": selected_group,
                "top2_support_gap": float(top2_support_gap),
                "answer_entropy": float(answer_entropy),
                "action_count": int(action_count),
                "expansion_count": int(expansion_count),
                "verification_count": int(verification_count),
                "extracted_answer": first_answer.get(group, group),
                "extraction_ok": int(not _invalid_answer(group)),
                "n_methods_sharing_norm_answer": 0,
                "match_strict_f3_final": 0,
                "match_external_l1_max_final": 0,
                "match_direct_reserve_strong_v1_final": 0,
                "match_direct_reserve_strong_plus_diverse_v1_final": int(group == selected_group),
                "problem_gold_present": 0,
                "problem_present_not_selected": 0,
                "diverse_gold_in_pool": 0,
            }
        )
    return rows
