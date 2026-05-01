from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

UNKNOWN_ANSWER = "__unknown__"
SAFE_TRACE_KEYS = ["trace_text", "step_text", "steps", "reasoning_trace", "trace", "candidate_trace", "terminal_trace"]


def normalize_answer(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in ("", "unknown", "n/a", "none", "null"):
        return UNKNOWN_ANSWER
    return text


def _first_non_empty(d: dict[str, Any], keys: list[str]) -> Any:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return None


def _trace_text(node: dict[str, Any]) -> str:
    for k in SAFE_TRACE_KEYS:
        v = node.get(k)
        if v in (None, ""):
            continue
        if isinstance(v, list):
            return "\n".join(str(x) for x in v)
        if isinstance(v, dict):
            return json.dumps(v, sort_keys=True)
        return str(v)
    return ""


def has_trace(node: dict[str, Any]) -> bool:
    return bool(_trace_text(node).strip())


def build_verifier_item(case: dict[str, Any], candidate: dict[str, Any], case_id: str, idx: int) -> dict[str, Any]:
    final_answer = _first_non_empty(candidate, ["final_answer", "answer", "text"]) or ""
    norm = normalize_answer(_first_non_empty(candidate, ["normalized_answer", "normalized_final_answer", "final_answer_normalized", "final_answer", "answer"]))
    trace = _trace_text(candidate)
    item = {
        "case_id": case_id,
        "candidate_id": str(candidate.get("candidate_id") or f"cand_{idx}"),
        "problem_statement": str(_first_non_empty(case, ["problem_statement", "problem", "question"]) or ""),
        "final_answer": str(final_answer),
        "normalized_answer": norm,
        "trace_text": trace,
        "source_family": _first_non_empty(candidate, ["source_family", "source", "provider", "model_family"]),
        "provenance_source": _first_non_empty(case, ["provenance_source"]),
    }
    return {k: v for k, v in item.items() if v is not None}


def dedupe_key(item: dict[str, Any]) -> str:
    p = hashlib.sha256(item.get("problem_statement", "").encode()).hexdigest()
    t = hashlib.sha256(item.get("trace_text", "").encode()).hexdigest()
    return f"{item.get('case_id')}|{p}|{item.get('normalized_answer')}|{t}"


@dataclass
class GroupScore:
    normalized_answer: str
    max_verifier_score: float | None
    mean_verifier_score: float | None
    support_count: int
    traced_support_count: int
    source_family_count: int
    best_candidate_id: str | None
    best_candidate_trace_available: bool


def score_item(item: dict[str, Any], mode: str, score_map: dict[tuple[str, str], float] | None = None) -> float | None:
    if mode == "dry_run_call_plan":
        return None
    if mode == "constant":
        return 0.5
    if mode == "mock_oracle_disabled_random_safe":
        rnd = random.Random(hash((item["case_id"], item["candidate_id"])) & 0xFFFFFFFF)
        return rnd.random()
    if mode == "trace_quality_heuristic":
        trace = item.get("trace_text", "")
        return min(1.0, 0.2 + 0.01 * len(trace.split())) if trace else 0.2
    if mode == "cached_jsonl":
        if score_map is None:
            return None
        return score_map.get((item["case_id"], item["candidate_id"]))
    if mode == "api":
        return None
    raise ValueError(f"unknown scorer mode: {mode}")


def select_case(case: dict[str, Any], items: list[dict[str, Any]], scores: dict[tuple[str, str], float | None], min_verifier_margin: float, require_trace_for_override: bool) -> dict[str, Any]:
    incumbent = normalize_answer(_first_non_empty(case, ["selected_normalized_answer", "current_normalized_answer", "selected_answer", "current_answer"]))
    groups: dict[str, list[tuple[dict[str, Any], float | None]]] = {}
    for it in items:
        groups.setdefault(normalize_answer(it["normalized_answer"]), []).append((it, scores.get((it["case_id"], it["candidate_id"]))))

    group_scores: dict[str, GroupScore] = {}
    for ans, recs in groups.items():
        vals = [s for _, s in recs if s is not None]
        traces = [bool(r.get("trace_text", "").strip()) for r, _ in recs]
        srcs = {r.get("source_family") for r, _ in recs if r.get("source_family")}
        best_i = max(range(len(recs)), key=lambda i: (-1e18 if recs[i][1] is None else recs[i][1]))
        best = recs[best_i][0]
        group_scores[ans] = GroupScore(ans, (max(vals) if vals else None), (sum(vals) / len(vals) if vals else None), len(recs), sum(1 for t in traces if t), len(srcs), best.get("candidate_id"), bool(best.get("trace_text", "").strip()))

    selected, reason = incumbent, "kept_incumbent_default"
    inc = group_scores.get(incumbent)
    challengers = [g for a, g in group_scores.items() if a != incumbent and a != UNKNOWN_ANSWER]
    challengers.sort(key=lambda g: (-(g.max_verifier_score if g.max_verifier_score is not None else -1e18), -(g.mean_verifier_score if g.mean_verifier_score is not None else -1e18), -g.traced_support_count, -g.support_count, g.normalized_answer))
    if not inc and challengers:
        selected, reason = challengers[0].normalized_answer, "incumbent_missing_chose_best_scored_group"
    elif inc and challengers:
        best = challengers[0]
        if best.max_verifier_score is not None and inc.max_verifier_score is not None:
            if best.max_verifier_score >= inc.max_verifier_score + min_verifier_margin and ((not require_trace_for_override) or best.traced_support_count > 0):
                selected, reason = best.normalized_answer, "override_verifier_margin_met"
            elif require_trace_for_override and best.traced_support_count == 0:
                reason = "blocked_missing_trace_for_override"
            else:
                reason = "blocked_insufficient_verifier_margin"
        else:
            reason = "kept_incumbent_no_challenger_score"

    return {"selected_normalized_answer": selected, "incumbent_normalized_answer": incumbent, "override": selected != incumbent, "decision_reason": reason, "group_scores": {k: v.__dict__ for k, v in group_scores.items()}}


def evaluate_case(case: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    ev = case.get("evaluation_only") or {}
    gold = normalize_answer(ev.get("gold_answer") or case.get("gold_answer"))
    cur = decision["incumbent_normalized_answer"]
    sel = decision["selected_normalized_answer"]
    return {"gold_normalized_answer": gold, "current_correct": cur == gold, "selector_correct": sel == gold, "fix": (cur != gold and sel == gold), "break": (cur == gold and sel != gold)}
