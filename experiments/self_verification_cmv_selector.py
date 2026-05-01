from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any

_EXPLICIT_KEYS = ["normalized_answer", "final_answer", "answer", "terminal_final_answer", "extracted_final_answer", "final"]
_TRACE_KEYS = ["trace_text", "reasoning_trace", "reasoning", "solution", "text", "steps"]
_NUM_RE = re.compile(r"([+\-]?\$?\d[\d,]*(?:\.\d+)?)")
_HASH_RE = re.compile(r"####\s*([+\-]?\$?\d[\d,]*(?:\.\d+)?)")
_ANSWER_RE = re.compile(r"(?:^|\b)[Tt]he answer is\s*[:\-]?\s*([+\-]?\$?\d[\d,]*(?:\.\d+)?)")


def normalize_gsm8k_numeric_answer(text: str) -> str | None:
    if text is None:
        return None
    t = str(text).strip().replace(",", "")
    if t.startswith("$"):
        t = t[1:]
    if t.endswith("."):
        t = t[:-1]
    if not t or not re.fullmatch(r"[+\-]?\d+(?:\.\d+)?", t):
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
    if not trace:
        return None
    for rx in (_ANSWER_RE, _HASH_RE):
        m = rx.search(trace)
        if m:
            n = normalize_gsm8k_numeric_answer(m.group(1))
            if n is not None:
                return n
    ms = list(_NUM_RE.finditer(trace[-500:]))
    return normalize_gsm8k_numeric_answer(ms[-1].group(1)) if ms else None


def extract_candidate_final_answer(candidate: dict) -> str | None:
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


def extract_numeric_conditions(problem_text: str, max_conditions: int | None = 4) -> list[dict]:
    out: list[dict] = []
    for i, m in enumerate(_NUM_RE.finditer(problem_text or "")):
        raw = m.group(1)
        norm = normalize_gsm8k_numeric_answer(raw)
        if norm is None:
            continue
        s, e = m.span(1)
        out.append({
            "condition_id": f"cond_{len(out)}",
            "span": [s, e],
            "raw_value": raw,
            "normalized_value": norm,
            "snippet": (problem_text[max(0, s - 24): min(len(problem_text), e + 24)] if problem_text else ""),
        })
        if max_conditions is not None and len(out) >= max_conditions:
            break
    return out


def mask_condition(problem_text: str, span: tuple[int, int]) -> str:
    s, e = span
    masked = f"{problem_text[:s]}X{problem_text[e:]}"
    return masked + "\n\nWhat is the value of X?"


def build_declarative_conclusion(problem_text: str, candidate_answer: str) -> str:
    _ = problem_text
    return f"The answer to the original problem is {candidate_answer}."


def build_cmv_prompt(problem_text: str, masked_condition: dict, candidate_answer: str, conclusion: str) -> str:
    _ = candidate_answer
    return (
        "Solve for the masked value X using the problem and the provided conclusion condition. "
        "Return strict JSON only with keys x_value and reason. Keep reason short.\n\n"
        f"Masked problem:\n{problem_text}\n\n"
        f"Conclusion condition:\n{conclusion}\n\n"
        f"Target condition id: {masked_condition.get('condition_id')}\n"
        "Output JSON: {\"x_value\": \"...\", \"reason\": \"short\"}"
    )


def parse_masked_value_prediction(model_text: str) -> str | None:
    raw = (model_text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        obj = json.loads(raw)
        return str(obj.get("x_value")) if obj.get("x_value") not in (None, "") else None
    except Exception:
        m = _NUM_RE.search(raw)
        return m.group(1) if m else None


def score_candidate_from_cached_checks(candidate: dict, checks: list[dict]) -> dict:
    cand_ans = extract_candidate_final_answer(candidate)
    cid = str(candidate.get("candidate_id", ""))
    if cand_ans is None:
        return {"candidate_id": cid, "candidate_index": candidate.get("candidate_index"), "normalized_candidate_answer": None, "valid_candidate": False, "score": -1, "total_checks": 0, "matches": 0, "match_rate": 0.0, "conditions_checked": 0, "repeats_per_condition": 0}
    rel = [c for c in checks if str(c.get("candidate_id")) == cid]
    matches = sum(1 for c in rel if bool(c.get("match")))
    total = len(rel)
    conds = len(set(str(c.get("condition_id")) for c in rel))
    rpt = int(round(total / conds)) if conds else 0
    return {"candidate_id": cid, "candidate_index": int(candidate.get("candidate_index", 0)), "normalized_candidate_answer": cand_ans, "valid_candidate": True, "score": matches, "total_checks": total, "matches": matches, "match_rate": (matches / total if total else 0.0), "conditions_checked": conds, "repeats_per_condition": rpt}


def select_self_verification_candidate(candidates: list[dict], cached_scores: dict) -> dict:
    table = [cached_scores.get(str(c.get("candidate_id", f"candidate_{i}")), score_candidate_from_cached_checks({**c, "candidate_index": i}, [])) for i, c in enumerate(candidates)]
    valid = [r for r in table if r.get("valid_candidate")]
    invalid_count = len(table) - len(valid)
    if not valid:
        return {"selected_normalized_answer": None, "selected_candidate_id": None, "selected_candidate_index": None, "selected_score": -1, "selected_match_rate": 0.0, "selected_total_checks": 0, "selected_conditions_checked": 0, "valid_candidate_count": 0, "invalid_candidate_count": invalid_count, "unverifiable_case": True, "tie_flag": False, "tied_candidate_ids": [], "decision_reason": "no_valid_candidates", "candidate_score_table": table}
    best_score = max(v["score"] for v in valid)
    tied = [v for v in valid if v["score"] == best_score]
    tied_sorted = sorted(tied, key=lambda x: int(x.get("candidate_index", 10**9)))
    sel = tied_sorted[0]
    return {"selected_normalized_answer": sel.get("normalized_candidate_answer"), "selected_candidate_id": sel.get("candidate_id"), "selected_candidate_index": sel.get("candidate_index"), "selected_score": sel.get("score"), "selected_match_rate": sel.get("match_rate"), "selected_total_checks": sel.get("total_checks"), "selected_conditions_checked": sel.get("conditions_checked"), "valid_candidate_count": len(valid), "invalid_candidate_count": invalid_count, "unverifiable_case": all(v.get("total_checks", 0) == 0 for v in valid), "tie_flag": len(tied_sorted) > 1, "tied_candidate_ids": [t.get("candidate_id") for t in tied_sorted] if len(tied_sorted) > 1 else [], "decision_reason": "highest_cmv_score_first_candidate_tiebreak", "candidate_score_table": table}


def evaluate_self_verification_case(record: dict, decision: dict) -> dict:
    ev = record.get("evaluation_only") or {}
    gold = normalize_gsm8k_numeric_answer(ev.get("gold_answer") or record.get("gold_answer") or record.get("gold_answer_canonical") or "")
    current = normalize_gsm8k_numeric_answer(record.get("selected_normalized_answer") or record.get("final_answer_canonical") or "")
    selected = decision.get("selected_normalized_answer")
    return {"gold_normalized_answer": gold, "current_correct": gold is not None and current == gold, "self_verification_correct": gold is not None and selected == gold, "fix": gold is not None and current != gold and selected == gold, "break": gold is not None and current == gold and selected != gold}
