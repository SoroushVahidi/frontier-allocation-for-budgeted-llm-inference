from __future__ import annotations

import hashlib
import json
import re
from typing import Any

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
WEEKDAY_RE = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
CATEG_RE = re.compile(r"\b(weekday|day of the week|month|yes or no)\b", re.I)
MORE_RE = re.compile(r"how\s+much\s+more", re.I)
FIRST_PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")
TAIL_EQ_RE = re.compile(r"=\s*\$?\s*(-?[\d,]+(?:\.\d+)?)\s*(?:$|\n|\.|\))", re.I)
COUNT_RE = re.compile(r"\b(how many|number of)\b", re.I)
RATE_RE = re.compile(r"\b(per|each|rate)\b", re.I)
TOTAL_RE = re.compile(r"\b(total|in all)\b", re.I)
REMAIN_RE = re.compile(r"\b(remaining|left)\b", re.I)

_FINAL_ROLE_TARGET = {
    "current_final",
    "pal_stdout",
    "overlay_tiebreak",
    "target",
    "final",
    "answer",
}
_INTERMEDIATE_ROLE = {
    "direct_reserve",
    "intermediate",
    "subtotal",
    "component",
    "supporting",
    "helper",
}

_TARGET_KIND_HINTS = {
    "money": re.compile(r"[\$£€]|dollars?|cents?|costs?|paid|bills?|change\b|price|prices|revenue|profit", re.I),
    "count": re.compile(r"\b(how many|number of|count|counts)\b", re.I),
    "rate": re.compile(r"\b(per|each|every|mph|/hour|per hour|per day|per minute|rate)\b", re.I),
    "difference": re.compile(r"\b(more than|less than|difference|longer|shorter|heavier|larger|smaller|taller|faster|slower)\b", re.I),
    "fraction": re.compile(r"\b(percent|ratio|fraction|half of|quarter of|third of)\b", re.I),
    "duration": re.compile(r"\b(minutes?|hours?|days?|weeks?|months?|years?|seconds?)\b", re.I),
    "total": re.compile(r"\b(total|in all|altogether|combined|sum of)\b", re.I),
}

_TARGET_SURFACE_RE = re.compile(
    r"(?:what is(?: the)?|how many|how much|find the|calculate|determine|express the)\s+(.+?)(?:\?|$)",
    re.I,
)

_OP_FAMILY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("conversion", re.compile(r"\b(convert|conversion|per\s+.*\bto\b|hours?\s+to\s+minutes?|minutes?\s+to\s+hours?)\b", re.I)),
    ("divide", re.compile(r"/|//|\bdivide(?:d|s|r)?\b|\bper\b|\beach\b|\bevery\b", re.I)),
    ("multiply", re.compile(r"\*|\bmultipl(?:y|ied|ies|ied)\b|\btimes\b|\bdouble\b|\btriple\b", re.I)),
    ("subtract", re.compile(r"-|−|\bsubtract(?:ed|s|ing)?\b|\bminus\b|\bless\b|\bremaining\b|\bleft\b", re.I)),
    ("add", re.compile(r"\+|\badd(?:ed|s|ing)?\b|\bplus\b|\btotal\b|\bsum\b|\baltogether\b|\bcombined\b", re.I)),
    ("ratio", re.compile(r"\bratio\b|\bfraction\b|%", re.I)),
    ("comparison", re.compile(r"\bmore than\b|\bless than\b|\bdifference\b|\bcompare\b", re.I)),
)


def _to_float(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return None


def _extract_final_num(ans: str) -> float | None:
    m = list(NUM_RE.finditer(ans or ""))
    return _to_float(m[-1].group(0)) if m else None


def _normalize_numeric_text(value: Any) -> str:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return ""
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return text.lower()
    try:
        number = float(match.group(0))
    except Exception:
        return text.lower()
    if number.is_integer():
        return str(int(number))
    return ("%f" % number).rstrip("0").rstrip(".")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _question_kind(question: str) -> str:
    q = question or ""
    for kind, pattern in _TARGET_KIND_HINTS.items():
        if pattern.search(q):
            return kind
    return "unknown"


def _target_surface(question: str) -> str:
    m = _TARGET_SURFACE_RE.search(question or "")
    if not m:
        return ""
    surface = m.group(1).strip()
    surface = re.sub(r"\s+", " ", surface)
    surface = surface.strip(" .")
    return surface[:120]


def _target_unit(question: str, metadata: dict[str, Any] | None) -> str:
    md = metadata or {}
    for key in ("target_unit", "answer_unit", "unit"):
        unit = _safe_text(md.get(key))
        if unit:
            return unit
    kind = _question_kind(question)
    if kind == "money":
        return "money"
    if kind == "count":
        return "count"
    if kind == "rate":
        return "rate"
    if kind == "difference":
        return "difference"
    if kind == "fraction":
        return "fraction"
    if kind == "duration":
        return "duration"
    if kind == "total":
        return "total"
    return "unknown"


def _target_entity(question: str, metadata: dict[str, Any] | None) -> str:
    md = metadata or {}
    for key in ("target_entity", "entity", "target_object", "target_subject"):
        entity = _safe_text(md.get(key))
        if entity:
            return entity
    surface = _target_surface(question)
    if surface:
        lead = surface.split(",")[0].strip()
        return lead[:80]
    return ""


def _target_tuple(question: str, metadata: dict[str, Any] | None) -> dict[str, str]:
    return {
        "question_kind": _question_kind(question),
        "target_surface": _target_surface(question),
        "target_entity": _target_entity(question, metadata),
        "target_unit": _target_unit(question, metadata),
    }


def _candidate_channels_haystack(
    *,
    candidate_trace: str | None,
    candidate_code: str | None,
    candidate_answer: str | None,
) -> str:
    """Trace/code/answer only - excludes problem text so checks measure candidate evidence."""
    parts = [candidate_trace or "", candidate_code or "", candidate_answer or ""]
    return "\n".join(parts).lower()


def _normalized_value_in_haystack(norm: str, haystack_lower: str) -> bool:
    if not norm:
        return False
    haystack = haystack_lower.replace(",", "")
    if norm in haystack:
        return True
    try:
        fv = float(norm)
        alt = _normalize_numeric_text(fv)
        if alt != norm and alt in haystack:
            return True
    except Exception:
        pass
    return False


def compute_candidate_consistency_flags(question: str, trace: str, final_answer: str) -> dict[str, bool]:
    q = (question or "").lower()
    t = trace or ""
    a = (final_answer or "").strip().lower()
    anum = _extract_final_num(a)
    last_eq = TAIL_EQ_RE.findall(t)
    last_eq_num = _to_float(last_eq[-1].replace(",", "")) if last_eq else None
    first_price = _to_float(FIRST_PRICE_RE.findall(question)[0]) if FIRST_PRICE_RE.findall(question) else None
    flags = {
        "categorical_numeric_mismatch": bool((WEEKDAY_RE.search(q) or CATEG_RE.search(q)) and anum is not None),
        "how_much_more_echo_original_price": bool(
            MORE_RE.search(q) and first_price is not None and anum is not None and abs(anum - first_price) < 1e-9
        ),
        "last_equation_disagrees_with_final": bool(last_eq_num is not None and anum is not None and abs(last_eq_num - anum) > 1e-9),
        "numeric_type_mismatch": bool((NUM_RE.search(q) is not None) and (anum is None)),
        "non_integer_count": bool(COUNT_RE.search(q) and anum is not None and abs(anum - round(anum)) > 1e-9),
        "negative_impossible": bool(anum is not None and anum < 0 and ("temperature" not in q)),
        "remaining_total_conflict": bool(REMAIN_RE.search(q) and TOTAL_RE.search(q) and anum is not None and anum == 0),
        "rate_vs_total_conflict": bool(RATE_RE.search(q) and TOTAL_RE.search(q) and anum is not None and anum < 1),
        "intermediate_echo_risk": bool(anum is not None and str(int(anum) if anum.is_integer() else anum) in (question or "")),
    }
    return flags


def _answer_role_from_metadata(metadata: dict[str, Any] | None) -> str:
    md = metadata or {}
    for key in ("final_answer_role", "candidate_role", "reasoning_role", "role"):
        role = _safe_text(md.get(key)).lower()
        if role:
            if role in _FINAL_ROLE_TARGET:
                return "target"
            if role in _INTERMEDIATE_ROLE:
                return "intermediate"
            if role in {"unknown", "__unknown__", "other"}:
                return "unknown"
    return "unknown"


def _last_operation_family(question: str, trace: str, code: str | None) -> str:
    _ = question
    text = "\n".join(part for part in (trace or "", code or "") if part).lower()
    if not text.strip():
        return "unknown"
    for line in reversed([ln.strip() for ln in text.splitlines() if ln.strip()]):
        for family, pattern in _OP_FAMILY_PATTERNS:
            if pattern.search(line):
                return family
    for family, pattern in _OP_FAMILY_PATTERNS:
        if pattern.search(text):
            return family
    return "unknown"


def _ledger_hint(question: str, trace: str, code: str | None, metadata: dict[str, Any] | None) -> dict[str, Any]:
    md = metadata or {}
    target_entity = _safe_text(md.get("target_entity"))
    target_unit = _safe_text(md.get("target_unit"))
    entity_ledger = md.get("entity_ledger")
    unit_consistency_status = _safe_text(md.get("unit_consistency_status")).lower()
    entity_hints: list[str] = []
    unit_hints: list[str] = []
    for blob in (question, trace, code or ""):
        low = (blob or "").lower()
        if not low.strip():
            continue
        if "$" in low or "dollar" in low or "money" in low or "cost" in low or "price" in low:
            unit_hints.append("money")
        if "hour" in low or "minute" in low or "day" in low or "week" in low or "year" in low:
            unit_hints.append("time")
        if "percent" in low or "%" in low or "ratio" in low or "fraction" in low:
            unit_hints.append("ratio")
        if "remaining" in low or "left" in low:
            entity_hints.append("remaining")
        nums = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", low)
        if nums:
            entity_hints.extend(nums[:4])
    if not target_entity:
        target_entity = _target_entity(question, metadata)
    if not target_unit:
        target_unit = _target_unit(question, metadata)
    if not unit_consistency_status:
        if target_unit in {"money", "count", "rate", "difference", "fraction", "duration", "total"}:
            unit_consistency_status = "unknown"
        else:
            unit_consistency_status = "unknown"
    ledger_consistent = None
    if unit_consistency_status in {"consistent", "ok", "aligned"}:
        ledger_consistent = True
    elif unit_consistency_status in {"inconsistent", "conflict", "mismatch"}:
        ledger_consistent = False
    elif target_unit != "unknown" and target_unit in unit_hints:
        ledger_consistent = True
    elif target_unit != "unknown" and target_unit not in unit_hints and unit_hints:
        ledger_consistent = False

    confidence = 0.35
    if target_entity:
        confidence += 0.10
    if target_unit and target_unit != "unknown":
        confidence += 0.15
    if ledger_consistent is True:
        confidence += 0.25
    elif ledger_consistent is False:
        confidence -= 0.20
    if entity_ledger:
        confidence += 0.10
    if unit_hints:
        confidence += 0.05
    confidence = float(max(0.0, min(1.0, confidence)))
    return {
        "target_entity": target_entity,
        "target_unit": target_unit,
        "entity_hints": sorted(dict.fromkeys(entity_hints)),
        "unit_hints": sorted(dict.fromkeys(unit_hints)),
        "ledger_status": unit_consistency_status or "unknown",
        "ledger_consistent": ledger_consistent,
        "ledger_confidence": confidence,
        "entity_ledger_present": bool(entity_ledger),
    }


def _target_alignment_score(
    *,
    question: str,
    candidate_trace: str,
    candidate_code: str | None,
    candidate_answer: str,
    metadata: dict[str, Any] | None,
    final_answer_role: str,
    last_operation_family: str,
    ledger_hint: dict[str, Any],
) -> float:
    score = 0.22
    qkind = _question_kind(question)
    if qkind != "unknown":
        score += 0.05
    if final_answer_role == "target":
        score += 0.35
    elif final_answer_role == "intermediate":
        score -= 0.28
    else:
        score -= 0.03

    if ledger_hint.get("ledger_consistent") is True:
        score += 0.18
    elif ledger_hint.get("ledger_consistent") is False:
        score -= 0.15
    score += 0.12 * float(ledger_hint.get("ledger_confidence") or 0.0)

    plausible_ops = {
        "money": {"add", "subtract", "multiply", "divide", "conversion"},
        "count": {"add", "subtract", "multiply"},
        "rate": {"multiply", "divide", "conversion"},
        "difference": {"subtract", "comparison"},
        "fraction": {"divide", "multiply", "ratio"},
        "duration": {"add", "subtract", "conversion"},
        "total": {"add", "multiply", "subtract"},
    }
    if last_operation_family in plausible_ops.get(qkind, set()):
        score += 0.14
    elif last_operation_family not in {"unknown"}:
        score -= 0.06

    flags = compute_candidate_consistency_flags(question, candidate_trace, candidate_answer)
    if flags["last_equation_disagrees_with_final"]:
        score -= 0.12
    if flags["intermediate_echo_risk"] and final_answer_role != "target":
        score -= 0.12

    answer_text = _safe_text(candidate_answer)
    if answer_text and candidate_trace:
        if answer_text in candidate_trace and "therefore" in candidate_trace.lower():
            score += 0.05
    if candidate_code:
        if "print(" in candidate_code or "return " in candidate_code:
            score += 0.02

    return float(max(0.0, min(1.0, score)))


def _intermediate_answer_penalty(
    *,
    question: str,
    candidate_trace: str,
    candidate_answer: str,
    final_answer_role: str,
) -> float:
    flags = compute_candidate_consistency_flags(question, candidate_trace, candidate_answer)
    penalty = 0.0
    if final_answer_role == "intermediate":
        penalty += 0.75
    elif final_answer_role == "unknown":
        penalty += 0.10
    if flags["intermediate_echo_risk"]:
        penalty += 0.20
    if flags["last_equation_disagrees_with_final"]:
        penalty += 0.15
    if REMAIN_RE.search(question or "") and TOTAL_RE.search(question or "") and final_answer_role != "target":
        penalty += 0.10
    return float(max(0.0, min(1.0, penalty)))


def _duplicate_wrong_signature(
    *,
    question: str,
    candidate_trace: str,
    candidate_code: str | None,
    candidate_answer: str,
    final_answer_role: str,
    last_operation_family: str,
    target_tuple: dict[str, str],
    ledger_hint: dict[str, Any],
) -> str:
    answer_norm = _normalize_numeric_text(candidate_answer)
    trace_tail = "\n".join(
        line.strip()
        for line in (candidate_trace or "").splitlines()[-3:]
        if line.strip()
    )
    payload = {
        "question_kind": target_tuple.get("question_kind", "unknown"),
        "target_unit": target_tuple.get("target_unit", "unknown"),
        "target_surface": target_tuple.get("target_surface", ""),
        "target_entity": target_tuple.get("target_entity", ""),
        "answer": answer_norm,
        "role": final_answer_role,
        "op": last_operation_family,
        "ledger": ledger_hint.get("ledger_status", "unknown"),
        "trace_tail": trace_tail,
        "code_head": (candidate_code or "")[:120],
        "question_head": (question or "")[:120],
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def build_structural_target_feature_row(
    *,
    question: str,
    candidate_trace: str | None = None,
    candidate_code: str | None = None,
    candidate_answer: str | int | float | None = None,
    execution_metadata: dict[str, Any] | None = None,
    support_count: int = 1,
) -> dict[str, Any]:
    md = execution_metadata or {}
    if candidate_answer is None:
        ans_str = ""
    elif isinstance(candidate_answer, (int, float)):
        ans_str = _normalize_numeric_text(candidate_answer)
    else:
        ans_str = str(candidate_answer).strip()
    trace = _safe_text(candidate_trace)
    code = _safe_text(candidate_code)
    target = _target_tuple(question, md)
    ledger = _ledger_hint(question, trace, code, md)
    role = _answer_role_from_metadata(md)
    if role == "unknown":
        flags = compute_candidate_consistency_flags(question, trace, ans_str)
        if flags["last_equation_disagrees_with_final"]:
            role = "intermediate"
        elif ans_str and trace and ans_str in trace and ("therefore" in trace.lower() or "final" in trace.lower()):
            role = "target"
        elif ans_str and trace and any(tok in trace.lower() for tok in ("subtotal", "intermediate", "remaining", "left", "so far", "after first")):
            role = "intermediate"
    op_family = _last_operation_family(question, trace, candidate_code)
    target_alignment = _target_alignment_score(
        question=question,
        candidate_trace=trace,
        candidate_code=candidate_code,
        candidate_answer=ans_str,
        metadata=md,
        final_answer_role=role,
        last_operation_family=op_family,
        ledger_hint=ledger,
    )
    intermediate_penalty = _intermediate_answer_penalty(
        question=question,
        candidate_trace=trace,
        candidate_answer=ans_str,
        final_answer_role=role,
    )
    support_norm = max(0.0, min(1.0, float(support_count) / 3.0))
    ledger_score = float(ledger.get("ledger_confidence") or 0.0)
    structural_selector_score = float(
        max(
            0.0,
            min(
                1.0,
                0.35 * support_norm
                + 0.35 * target_alignment
                + 0.15 * ledger_score
                + 0.15 * (1.0 - intermediate_penalty),
            ),
        )
    )
    return {
        "target_tuple": target,
        "entity_unit_ledger_proxy": ledger,
        "final_answer_role": role,
        "last_operation_family": op_family,
        "target_alignment_score": target_alignment,
        "intermediate_answer_penalty": intermediate_penalty,
        "duplicate_wrong_signature": _duplicate_wrong_signature(
            question=question,
            candidate_trace=trace,
            candidate_code=candidate_code,
            candidate_answer=ans_str,
            final_answer_role=role,
            last_operation_family=op_family,
            target_tuple=target,
            ledger_hint=ledger,
        ),
        "structural_selector_score": structural_selector_score,
    }


def compute_unified_confidence_error(
    question: str,
    trace: str,
    final_answer: str,
    support_count: int = 1,
    ov_score: float | None = None,
    prm_score: float | None = None,
) -> dict[str, float]:
    flags = compute_candidate_consistency_flags(question, trace, final_answer)
    err = float(sum(flags.values()))
    model = 0.0
    if ov_score is not None:
        model += max(min(float(ov_score), 1.0), 0.0)
    if prm_score is not None:
        model += max(min(float(prm_score), 1.0), 0.0)
    if ov_score is not None and prm_score is not None:
        model /= 2.0
    elif ov_score is None and prm_score is None:
        model = 0.5
    support = min(1.0, max(0.0, support_count / 3.0))
    confidence = max(0.0, min(1.0, 0.55 * model + 0.25 * support + 0.20 * (1.0 - min(err / 5.0, 1.0))))
    return {"unified_error_score": err, "unified_confidence_score": confidence, "hybrid_selector_score": confidence - 0.15 * err}


def build_group_feature_rows(question: str, candidate_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for g in candidate_groups:
        trace = _safe_text(g.get("trace") or g.get("reasoning_text") or "")
        candidate_answer = g.get("final_answer") or g.get("candidate_answer") or g.get("normalized_answer")
        flags = compute_candidate_consistency_flags(question, trace, str(candidate_answer or ""))
        scores = compute_unified_confidence_error(
            question,
            trace,
            str(candidate_answer or ""),
            int(g.get("support_count", 1) or 1),
            g.get("ov_score"),
            g.get("prm_score"),
        )
        structural = build_structural_target_feature_row(
            question=question,
            candidate_trace=trace,
            candidate_code=g.get("code") if isinstance(g.get("code"), str) else None,
            candidate_answer=candidate_answer,
            execution_metadata=dict(g.get("execution_metadata") or {}),
            support_count=int(g.get("support_count", 1) or 1),
        )
        row = dict(g)
        row["consistency_flags"] = flags
        row.update(scores)
        row.update(structural)
        out.append(row)
    return out
