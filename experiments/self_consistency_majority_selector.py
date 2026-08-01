from __future__ import annotations

"""Self-consistency majority-vote selector baseline.

Literature note: this follows Wang et al. (ICLR 2023) self-consistency:
choose the most frequent parsed final answer, with ties broken by first occurrence.
In this repo adaptation, candidate_nodes are treated as the sampled reasoning paths.
"""

from decimal import Decimal, InvalidOperation
import re
from typing import Any

_EXPLICIT_KEYS = ["normalized_answer", "final_answer", "answer", "terminal_final_answer", "extracted_final_answer", "final"]
_TRACE_KEYS = ["trace_text", "reasoning_trace", "reasoning", "solution", "text", "steps"]

_THE_ANSWER_IS_RE = re.compile(r"(?:^|\b)[Tt]he answer is\s*[:\-]?\s*([+\-]?\$?\d[\d,]*(?:\.\d+)?)")
_HASH_RE = re.compile(r"####\s*([+\-]?\$?\d[\d,]*(?:\.\d+)?)")
_NUM_RE = re.compile(r"([+\-]?\$?\d[\d,]*(?:\.\d+)?)")


def normalize_gsm8k_numeric_answer(text: str) -> str | None:
    if text is None:
        return None
    t = str(text).strip()
    if not t:
        return None
    if t.startswith("$"):
        t = t[1:]
    t = t.replace(",", "")
    if t.endswith("."):
        t = t[:-1]
    t = t.strip()
    if not t:
        return None
    if not re.fullmatch(r"[+\-]?\d+(?:\.\d+)?", t):
        return None
    try:
        d = Decimal(t)
    except (InvalidOperation, ValueError):
        return None
    s = format(d.normalize(), "f")
    if s == "-0":
        s = "0"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _extract_from_trace(trace: str) -> str | None:
    if not isinstance(trace, str) or not trace.strip():
        return None
    m = _THE_ANSWER_IS_RE.search(trace)
    if m:
        return normalize_gsm8k_numeric_answer(m.group(1))
    m = _HASH_RE.search(trace)
    if m:
        return normalize_gsm8k_numeric_answer(m.group(1))
    tail = trace[-400:]
    matches = list(_NUM_RE.finditer(tail))
    if not matches:
        return None
    return normalize_gsm8k_numeric_answer(matches[-1].group(1))


def extract_final_numeric_answer(candidate: dict) -> str | None:
    for k in _EXPLICIT_KEYS:
        if k in candidate and candidate[k] not in (None, ""):
            n = normalize_gsm8k_numeric_answer(str(candidate[k]))
            if n is not None:
                return n
    for k in _TRACE_KEYS:
        v = candidate.get(k)
        if isinstance(v, list):
            v = "\n".join(str(x) for x in v)
        if isinstance(v, str):
            n = _extract_from_trace(v)
            if n is not None:
                return n
    return None


def group_candidates_by_answer(candidates: list[dict]) -> dict:
    grouped: dict[str, list[dict[str, Any]]] = {}
    invalid: list[dict[str, Any]] = []
    for idx, c in enumerate(candidates):
        ans = extract_final_numeric_answer(c)
        cid = c.get("candidate_id", f"candidate_{idx}")
        if ans is None:
            invalid.append({"candidate_id": cid, "candidate_index": idx})
            continue
        grouped.setdefault(ans, []).append({"candidate": c, "candidate_id": cid, "candidate_index": idx})
    return {"groups": grouped, "invalid": invalid}


def select_self_consistency_answer(candidates: list[dict]) -> dict:
    grouped = group_candidates_by_answer(candidates)
    groups = grouped["groups"]
    invalid = grouped["invalid"]
    valid_vote_count = sum(len(v) for v in groups.values())
    if valid_vote_count == 0:
        return {
            "selected_normalized_answer": None,
            "selected_candidate_id": None,
            "selected_vote_count": 0,
            "valid_vote_count": 0,
            "invalid_candidate_count": len(invalid),
            "unique_answer_count": 0,
            "vote_share": 0.0,
            "tie_flag": False,
            "tied_answers": [],
            "answer_vote_histogram": {},
            "selected_candidate_ids_supporting_answer": [],
            "all_invalid": True,
            "decision_reason": "all_candidates_invalid_or_unparsable",
        }
    counts = {k: len(v) for k, v in groups.items()}
    max_votes = max(counts.values())
    tied = [a for a, c in counts.items() if c == max_votes]
    first_seen = sorted((groups[a][0]["candidate_index"], a) for a in tied)
    selected_answer = first_seen[0][1]
    selected_support = groups[selected_answer]
    return {
        "selected_normalized_answer": selected_answer,
        "selected_candidate_id": selected_support[0]["candidate_id"],
        "selected_vote_count": max_votes,
        "valid_vote_count": valid_vote_count,
        "invalid_candidate_count": len(invalid),
        "unique_answer_count": len(groups),
        "vote_share": max_votes / max(1, valid_vote_count),
        "tie_flag": len(tied) > 1,
        "tied_answers": tied if len(tied) > 1 else [],
        "answer_vote_histogram": counts,
        "selected_candidate_ids_supporting_answer": [x["candidate_id"] for x in selected_support],
        "all_invalid": False,
        "decision_reason": "majority_vote_first_occurrence_tiebreak" if len(tied) > 1 else "majority_vote",
    }


def evaluate_self_consistency_case(record: dict, decision: dict) -> dict:
    ev = record.get("evaluation_only") or {}
    gold = normalize_gsm8k_numeric_answer(ev.get("gold_answer") or record.get("gold_answer") or record.get("gold_answer_canonical") or "")
    current = normalize_gsm8k_numeric_answer(
        record.get("selected_normalized_answer") or record.get("current_normalized_answer") or record.get("selected_answer") or record.get("current_answer") or record.get("selected_answer_canonical") or record.get("final_answer_canonical") or ""
    )
    selected = decision.get("selected_normalized_answer")
    current_correct = (gold is not None and current == gold)
    selector_correct = (gold is not None and selected == gold)
    return {
        "gold_normalized_answer": gold,
        "current_correct": current_correct,
        "self_consistency_correct": selector_correct,
        "fix": (not current_correct) and selector_correct,
        "break": current_correct and (not selector_correct),
    }
