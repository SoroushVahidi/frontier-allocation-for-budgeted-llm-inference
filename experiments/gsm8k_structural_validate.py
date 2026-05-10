"""Offline structural validation for GSM8K/PAL candidates (never raises).

Produces telemetry only — no gold inputs, no controller hooks.
Inspired by lightweight verify-* patterns (combinatorial-opt-agent style).
"""

from __future__ import annotations

import ast
import math
import re
from typing import Any

# --- Numeric extraction ------------------------------------------------------------

_DIGIT_TOKEN_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_FRAC_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")

# Single-token English numbers (v0; compounds like "twenty-one" not split).
_WORD_TO_INT: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}

_WORD_NUM_RE = re.compile(
    r"\b(?:" + "|".join(sorted(_WORD_TO_INT.keys(), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _normalize_numeric_string(raw: str) -> str | None:
    s = str(raw).strip().replace(",", "")
    if not s:
        return None
    m = _FRAC_RE.match(s) if "/" in s else None
    if not m and "/" in s:
        m = _FRAC_RE.search(s)
    if m:
        try:
            a, b = int(m.group(1)), int(m.group(2))
            if b == 0:
                return None
            v = a / b
        except ValueError:
            return None
        return _fmt_float(v)
    try:
        v = float(s)
    except ValueError:
        return None
    return _fmt_float(v)


def _fmt_float(v: float) -> str:
    if math.isfinite(v) and abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.10g}"


def _extract_quantity_mentions(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not text or not str(text).strip():
        return out
    t = str(text)
    seen_spans: set[tuple[int, int]] = set()

    for m in _DIGIT_TOKEN_RE.finditer(t):
        span = (m.start(), m.end())
        if span in seen_spans:
            continue
        seen_spans.add(span)
        raw = m.group(0)
        norm = _normalize_numeric_string(raw)
        if norm is not None:
            out.append({"raw": raw, "normalized": norm, "source": "digit"})

    for m in _FRAC_RE.finditer(t):
        span = (m.start(), m.end())
        if span in seen_spans:
            continue
        seen_spans.add(span)
        raw = m.group(0)
        norm = _normalize_numeric_string(raw)
        if norm is not None:
            out.append({"raw": raw, "normalized": norm, "source": "digit"})

    for m in _WORD_NUM_RE.finditer(t):
        span = (m.start(), m.end())
        if span in seen_spans:
            continue
        seen_spans.add(span)
        w = m.group(0).lower()
        val = _WORD_TO_INT.get(w)
        if val is not None:
            out.append({"raw": m.group(0), "normalized": str(int(val)), "source": "word"})
    return out


def _candidate_channels_haystack(
    *,
    candidate_trace: str | None,
    candidate_code: str | None,
    candidate_answer: str | None,
) -> str:
    """Trace/code/answer only — excludes problem text so checks measure candidate evidence."""
    parts = [candidate_trace or "", candidate_code or "", candidate_answer or ""]
    return "\n".join(parts).lower()


def _normalized_value_in_haystack(norm: str, haystack_lower: str) -> bool:
    if not norm:
        return False
    if norm in haystack_lower.replace(",", ""):
        return True
    # tolerate "32.0" vs "32"
    try:
        fv = float(norm)
        alt = _fmt_float(fv)
        if alt != norm and alt in haystack_lower.replace(",", ""):
            return True
    except ValueError:
        pass
    return False


def _salient_problem_norms(problem_text: str) -> list[str]:
    mentions = _extract_quantity_mentions(problem_text)
    norms = []
    for m in mentions:
        n = m.get("normalized")
        if isinstance(n, str) and n.strip():
            norms.append(n.strip())
    # de-dupe preserve order
    out: list[str] = []
    seen: set[str] = set()
    for n in norms:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


# --- Target type & operation cues --------------------------------------------------

_RATE_HINTS = re.compile(
    r"\b(per|each|every|mph|/hour|per hour|per day|per minute|rate)\b", re.IGNORECASE
)
_DIFF_HINTS = re.compile(
    r"\b(more than|less than|difference|longer|shorter|heavier|larger|smaller|taller|faster|slower)\b",
    re.IGNORECASE,
)
_TOTAL_HINTS = re.compile(r"\b(in total|altogether|combined|sum of|total of)\b", re.IGNORECASE)
_TEMP_HINTS = re.compile(
    r"\b(before|after|then|next|still|another|remaining|left over|starts? with)\b", re.IGNORECASE
)
_FRAC_HINTS = re.compile(r"\b(percent|ratio|fraction|half of|quarter of|third of)\b", re.IGNORECASE)
_MONEY_HINTS = re.compile(r"[\$£€]|dollars?|cents?|costs?|paid|bills?|change\b", re.IGNORECASE)
_DURATION_HINTS = re.compile(
    r"\b(minutes?|hours?|days?|weeks?|months?|years?|seconds?)\b", re.IGNORECASE
)
_COUNT_HINTS = re.compile(r"\bhow many\b", re.IGNORECASE)


def _classify_target_question_type(problem_text: str) -> str:
    p = problem_text or ""
    low = p.lower()
    if _COUNT_HINTS.search(low):
        return "count"
    if _MONEY_HINTS.search(p):
        return "money"
    if _RATE_HINTS.search(low):
        return "rate"
    if _DIFF_HINTS.search(low):
        return "difference"
    if _FRAC_HINTS.search(low):
        return "fraction"
    if _DURATION_HINTS.search(low):
        return "duration"
    if _TOTAL_HINTS.search(low):
        return "total"
    return "unknown"


def _required_operation_cues(problem_text: str) -> list[str]:
    p = problem_text or ""
    low = p.lower()
    req: list[str] = []
    if _RATE_HINTS.search(low):
        req.append("rate")
    if _DIFF_HINTS.search(low):
        req.append("difference")
    if _TOTAL_HINTS.search(low):
        req.append("total")
    if _TEMP_HINTS.search(low):
        req.append("temporal")
    if _FRAC_HINTS.search(low):
        req.append("fraction")
    return req


def _found_operation_cues(haystack_lower: str) -> list[str]:
    found: list[str] = []
    if re.search(r"/|//|\*\*|divide| per | each | every ", haystack_lower):
        found.append("rate")
    if re.search(r"-|\+|more than|less than|difference|compare", haystack_lower):
        found.append("difference")
    if re.search(r"sum\(|total|altogether|combined|\+ ", haystack_lower):
        found.append("total")
    if re.search(r"then|after|before|next|still", haystack_lower):
        found.append("temporal")
    if re.search(r"%|percent|ratio|fraction", haystack_lower):
        found.append("fraction")
    # de-dupe
    out: list[str] = []
    seen: set[str] = set()
    for c in found:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _check_python_syntax(code: str | None) -> tuple[bool | None, list[str]]:
    if code is None or not str(code).strip():
        return None, []
    errs: list[str] = []
    try:
        ast.parse(str(code))
        return True, errs
    except SyntaxError as e:
        errs.append(f"code_syntax_error:{e.msg or 'syntax_error'}")
        return False, errs


def _answer_type_match(target_type: str, answer_raw: str | None, problem_text: str) -> bool | None:
    if answer_raw is None or not str(answer_raw).strip():
        return None
    a = str(answer_raw).strip()
    low_p = (problem_text or "").lower()
    if target_type == "money":
        has_currency = bool(_MONEY_HINTS.search(problem_text or ""))
        ans_has_money_sym = bool(re.search(r"[\$£€]", a))
        if has_currency and not ans_has_money_sym:
            # numeric dollars still OK if purely numeric
            num = _normalize_numeric_string(re.sub(r"[^\d.\-]", "", a))
            return num is not None
        return True
    if target_type in {"count", "rate", "total", "difference", "fraction", "duration"}:
        return _normalize_numeric_string(a) is not None or bool(re.search(r"\d", a))
    return None


def _exec_ok_from_metadata(md: dict[str, Any] | None) -> bool | None:
    if not isinstance(md, dict) or not md:
        return None
    for key in ("pal_exec_ok", "exec_ok", "execution_ok", "pal_parse_ok"):
        if key in md:
            v = md[key]
            if isinstance(v, bool):
                return v
            if isinstance(v, int):
                return bool(v)
            if isinstance(v, str) and v.strip().lower() in {"1", "true", "yes"}:
                return True
            if isinstance(v, str) and v.strip().lower() in {"0", "false", "no"}:
                return False
    return None


def _structural_score(
    *,
    quantity_coverage: float | None,
    required: list[str],
    found: list[str],
    errors: list[str],
    warnings: list[str],
) -> float:
    req_set = set(required)
    found_set = set(found)
    overlap = req_set & found_set
    cue_ratio = len(overlap) / max(len(req_set), 1) if req_set else 1.0

    if quantity_coverage is None:
        base = 0.45
    else:
        base = 0.25 + 0.55 * float(max(0.0, min(1.0, quantity_coverage)))

    score = 0.75 * base + 0.25 * cue_ratio
    score -= 0.08 * len(errors)
    score -= 0.03 * max(0, len(warnings) - 3)
    return float(max(0.0, min(1.0, score)))


def _empty_payload(*, internal_note: str | None = None) -> dict[str, Any]:
    base = {
        "errors": [],
        "warnings": [],
        "quantity_mentions": [],
        "quantity_coverage": None,
        "unused_salient_quantities": [],
        "operation_cues_required": [],
        "operation_cues_found": [],
        "target_question_type": "unknown",
        "target_type_match": None,
        "code_syntax_ok": None,
        "exec_ok": None,
        "structural_score": 0.0,
        "abstain_reasons": [],
        "source_family": None,
        "validator_version": "gsm8k_structural_validate_v0",
    }
    if internal_note:
        base["errors"].append(internal_note)
        base["abstain_reasons"].append("validator_internal_exception")
    return base


def validate_gsm8k_candidate(
    *,
    problem_text: str,
    candidate_answer: str | int | float | None,
    candidate_trace: str | None = None,
    candidate_code: str | None = None,
    source_family: str | None = None,
    execution_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate structural coherence of a GSM8K candidate (offline, gold-free).

    Never raises: internal failures return a payload with ``errors`` populated.
    """
    try:
        return _validate_gsm8k_candidate_impl(
            problem_text=problem_text,
            candidate_answer=candidate_answer,
            candidate_trace=candidate_trace,
            candidate_code=candidate_code,
            source_family=source_family,
            execution_metadata=execution_metadata,
        )
    except Exception as exc:  # noqa: BLE001 — intentional umbrella for never-raise contract
        out = _empty_payload(internal_note=f"validator_swallowed_exception:{type(exc).__name__}")
        out["source_family"] = source_family
        out["structural_score"] = 0.0
        out["abstain_reasons"].append("internal_exception")
        return out


def _validate_gsm8k_candidate_impl(
    *,
    problem_text: str,
    candidate_answer: str | int | float | None,
    candidate_trace: str | None,
    candidate_code: str | None,
    source_family: str | None,
    execution_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    abstain: list[str] = []

    pt = str(problem_text or "")
    ans_str: str | None
    if candidate_answer is None:
        ans_str = None
    elif isinstance(candidate_answer, (int, float)):
        ans_str = _fmt_float(float(candidate_answer))
    else:
        ans_str = str(candidate_answer).strip() or None

    code_syntax_ok, syn_errs = _check_python_syntax(candidate_code)
    errors.extend(syn_errs)
    if code_syntax_ok is False:
        warnings.append("candidate_code_failed_syntax_check")

    exec_ok = _exec_ok_from_metadata(execution_metadata)

    q_mentions = _extract_quantity_mentions(pt)
    salient = _salient_problem_norms(pt)
    cand_hay = _candidate_channels_haystack(
        candidate_trace=candidate_trace,
        candidate_code=candidate_code,
        candidate_answer=ans_str or "",
    )

    unused: list[str] = []
    matched = 0
    if salient:
        for n in salient:
            if _normalized_value_in_haystack(n, cand_hay):
                matched += 1
            else:
                unused.append(n)
        coverage = matched / max(len(salient), 1)
        if coverage < 0.34:
            warnings.append("low_quantity_coverage_vs_problem")
        if unused:
            warnings.append("unused_salient_problem_quantities")
    else:
        coverage = None
        abstain.append("no_numeric_mentions_extracted_from_problem")

    tgt = _classify_target_question_type(pt)
    if tgt == "unknown":
        abstain.append("ambiguous_target_question_type")

    req_cues = _required_operation_cues(pt)
    found_cues = _found_operation_cues(cand_hay)
    for cue in req_cues:
        if cue not in found_cues:
            warnings.append(f"missing_operation_cue_in_trace_or_code:{cue}")

    # Lightweight cue-family warnings (plan §D)
    low = pt.lower()
    if _RATE_HINTS.search(low):
        if not re.search(r"/|//| per | each | divide |\*|\*\*", cand_hay):
            warnings.append("rate_question_weak_operator_evidence_in_trace")
    if _TEMP_HINTS.search(low):
        if not re.search(r"then|after|before|next|step", cand_hay):
            warnings.append("temporal_story_weak_follow_through_in_trace")
    if _DIFF_HINTS.search(low):
        if not re.search(r"-|−|more|less|difference|compare|than", cand_hay):
            warnings.append("comparison_question_weak_contrast_evidence_in_trace")
    if _TOTAL_HINTS.search(low):
        if "sum(" not in cand_hay and "+" not in cand_hay and "total" not in cand_hay:
            warnings.append("aggregation_question_weak_total_evidence_in_trace")

    # Unit / money heuristic
    if _MONEY_HINTS.search(pt) and ans_str and "$" not in ans_str and "€" not in ans_str and "£" not in ans_str:
        if _normalize_numeric_string(re.sub(r"[^\d.\-]", "", ans_str)) is None:
            warnings.append("money_context_but_answer_not_numeric")

    tm = _answer_type_match(tgt, ans_str, pt)
    if tm is False:
        warnings.append("target_type_vs_answer_surface_mismatch_heuristic")

    score = _structural_score(
        quantity_coverage=coverage,
        required=req_cues,
        found=found_cues,
        errors=errors,
        warnings=warnings,
    )

    out: dict[str, Any] = {
        "errors": list(errors),
        "warnings": list(warnings),
        "quantity_mentions": q_mentions,
        "quantity_coverage": coverage,
        "unused_salient_quantities": unused,
        "operation_cues_required": req_cues,
        "operation_cues_found": found_cues,
        "target_question_type": tgt,
        "target_type_match": tm,
        "code_syntax_ok": code_syntax_ok,
        "exec_ok": exec_ok,
        "structural_score": score,
        "abstain_reasons": abstain,
        "source_family": source_family,
        "validator_version": "gsm8k_structural_validate_v0",
    }
    return out

