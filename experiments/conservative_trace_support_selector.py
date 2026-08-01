from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

UNKNOWN_ANSWER = "__unknown__"


def normalize_answer(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text else UNKNOWN_ANSWER


def _first_non_empty(d: dict[str, Any], keys: list[str]) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _candidate_norm_answer(node: dict[str, Any]) -> str:
    return normalize_answer(
        _first_non_empty(
            node,
            [
                "normalized_final_answer",
                "normalized_answer",
                "final_answer_normalized",
                "final_answer",
                "answer",
            ],
        )
    )


def _candidate_source_family(node: dict[str, Any]) -> str | None:
    val = _first_non_empty(node, ["source_family", "source", "provider", "model_family"])
    return str(val).strip().lower() if val not in (None, "") else None


def _candidate_score(node: dict[str, Any]) -> float | None:
    for k in ["source_score", "score", "candidate_score", "confidence"]:
        v = node.get(k)
        if v in (None, ""):
            continue
        try:
            return float(v)
        except Exception:
            continue
    return None


def _has_trace(node: dict[str, Any]) -> bool:
    if isinstance(node.get("has_trace"), bool):
        return node["has_trace"]
    for k in ["trace", "candidate_trace", "terminal_trace", "trace_path"]:
        v = node.get(k)
        if isinstance(v, list):
            return len(v) > 0
        if isinstance(v, str):
            return bool(v.strip())
        if isinstance(v, dict):
            return bool(v)
    return False


@dataclass
class GroupFeatures:
    normalized_answer: str
    support_count: int
    traced_support_count: int
    source_family_count: int | None
    max_source_score: float | None
    avg_source_score: float | None
    has_trace: bool
    all_group_candidates_traced: bool
    is_incumbent: bool

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def select_case(
    case: dict[str, Any],
    *,
    selector_name: str,
    min_support_margin: int = 1,
    require_trace_for_override: bool = True,
    prefer_source_diversity: bool = True,
    no_gold_features: bool = True,
) -> dict[str, Any]:
    _ = no_gold_features
    nodes = case.get("candidate_nodes") or []
    groups: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        groups.setdefault(_candidate_norm_answer(n), []).append(n)

    incumbent = normalize_answer(
        _first_non_empty(
            case,
            ["selected_normalized_answer", "current_normalized_answer", "selected_answer", "current_answer"],
        )
    )
    if incumbent not in groups:
        groups.setdefault(incumbent, [])

    feats: dict[str, GroupFeatures] = {}
    for ans, gnodes in groups.items():
        traces = [_has_trace(n) for n in gnodes]
        srcs = {_candidate_source_family(n) for n in gnodes if _candidate_source_family(n)}
        scores = [_candidate_score(n) for n in gnodes]
        scores_f = [s for s in scores if s is not None]
        feats[ans] = GroupFeatures(
            normalized_answer=ans,
            support_count=len(gnodes),
            traced_support_count=sum(1 for t in traces if t),
            source_family_count=(len(srcs) if srcs else None),
            max_source_score=(max(scores_f) if scores_f else None),
            avg_source_score=((sum(scores_f) / len(scores_f)) if scores_f else None),
            has_trace=any(traces),
            all_group_candidates_traced=(all(traces) if gnodes else False),
            is_incumbent=(ans == incumbent),
        )

    incf = feats[incumbent]
    selected = incumbent
    reason = "kept_incumbent_default"
    blocked: list[str] = []

    candidates = [f for a, f in feats.items() if a != incumbent and a not in ("", UNKNOWN_ANSWER)]
    candidates.sort(
        key=lambda f: (
            -f.support_count,
            -f.traced_support_count,
            -(f.source_family_count if f.source_family_count is not None else -1),
            -(f.avg_source_score if f.avg_source_score is not None else -1e18),
            f.normalized_answer,
        )
    )

    for cf in candidates:
        cond_support = cf.support_count >= incf.support_count + min_support_margin
        cond_trace = (not require_trace_for_override) or cf.has_trace
        cond_div = True
        if prefer_source_diversity and incf.source_family_count is not None and cf.source_family_count is not None:
            cond_div = cf.source_family_count >= incf.source_family_count
        if cond_support and cond_trace and cond_div:
            selected = cf.normalized_answer
            reason = "override_higher_support"
            break

    if selected == incumbent:
        if candidates:
            best = candidates[0]
            if not (best.support_count >= incf.support_count + min_support_margin):
                blocked.append("insufficient_support_margin")
            if require_trace_for_override and not best.has_trace:
                blocked.append("missing_trace_for_override")
            if prefer_source_diversity and incf.source_family_count is not None and best.source_family_count is not None and best.source_family_count < incf.source_family_count:
                blocked.append("lower_source_diversity")
        else:
            blocked.append("no_valid_challenger")

    return {
        "selected_normalized_answer": selected,
        "incumbent_normalized_answer": incumbent,
        "override": selected != incumbent,
        "decision_reason": reason,
        "blocked_conditions": blocked,
        "group_features": {k: v.as_dict() for k, v in feats.items()},
        "selector_name": selector_name,
    }


def evaluate_case(case: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    ev = case.get("evaluation_only") or {}
    gold = normalize_answer(ev.get("gold_answer") or case.get("gold_answer"))
    cur = decision["incumbent_normalized_answer"]
    sel = decision["selected_normalized_answer"]
    current_correct = cur == gold
    selector_correct = sel == gold
    return {
        "gold_normalized_answer": gold,
        "current_correct": current_correct,
        "selector_correct": selector_correct,
        "fix": (not current_correct) and selector_correct,
        "break": current_correct and (not selector_correct),
    }
