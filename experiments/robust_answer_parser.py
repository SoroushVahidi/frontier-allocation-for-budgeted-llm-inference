"""Robust offline answer parser/canonicalizer for GSM8K-style outputs.

This module is deterministic and gold-free at runtime. It extracts final-answer
candidates using explicit cues first, then applies conservative fallbacks.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import re
from typing import Any


CONF_HIGH = "high"
CONF_MED = "medium"
CONF_LOW = "low"
CONF_AMBIGUOUS = "ambiguous"

_CUE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("hashes", re.compile(r"####\s*([^\n]+)")),
    ("boxed", re.compile(r"\\boxed\{([^{}]+)\}")),
    ("final_answer_colon", re.compile(r"(?i)\bfinal answer\s*:\s*([^\n]+)")),
    ("answer_colon", re.compile(r"(?i)\banswer\s*:\s*([^\n]+)")),
    ("the_answer_is", re.compile(r"(?i)\bthe answer is\b\s*([^\n\.]+)")),
    ("so_the_answer_is", re.compile(r"(?i)\bso the answer is\b\s*([^\n\.]+)")),
    ("therefore_the_answer_is", re.compile(r"(?i)\btherefore[, ]+the answer is\b\s*([^\n\.]+)")),
    ("thus_the_answer_is", re.compile(r"(?i)\bthus[, ]+the answer is\b\s*([^\n\.]+)")),
    ("in_total", re.compile(r"(?i)\bin total\b\s*[:,]?\s*([^\n\.]+)")),
    ("altogether", re.compile(r"(?i)\baltogether\b\s*[:,]?\s*([^\n\.]+)")),
]

_NUM_TOKEN_RE = re.compile(
    r"(?P<sign>[-+]?)"
    r"(?P<currency>\$?)"
    r"(?P<num>\d+\s*/\s*\d+|(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"\s*(?P<pct>%?)",
)
_UNIT_WORD_RE = re.compile(r"(?i)\b(dollars?|cents?|miles?|hours?|minutes?|people|items?|kg|lbs?|meters?|m)\b")
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_CALC_ANN_RE = re.compile(r"<<[^<>]*>>")
_OPER_RE = re.compile(r"[=+\-*/^]")
_SENT_SPLIT_RE = re.compile(r"(?<=[\.\!\?])\s+")


@dataclass(frozen=True)
class CanonicalAnswer:
    raw_text: str
    canonical_value: str | None
    numeric_value: float | None
    numeric_type: str
    unit: str | None
    cue_type: str
    confidence: str
    ambiguous: bool
    ambiguity_reason: str | None
    line_index: int
    sentence_index: int
    operator_density: float
    competing_candidates: int


@dataclass(frozen=True)
class ParsedAnswerCandidate:
    raw_span: str
    cue_type: str
    line_index: int
    sentence_index: int
    operator_density: float
    competing_candidates: int
    canonical: CanonicalAnswer


@dataclass(frozen=True)
class ParsedAnswerDecision:
    selected: CanonicalAnswer | None
    all_candidates: tuple[ParsedAnswerCandidate, ...]
    confidence: str
    ambiguous: bool
    ambiguity_reason: str | None
    used_fallback_to_none: bool


def _clean_text(text: str) -> str:
    s = str(text or "")
    s = _CODE_FENCE_RE.sub(" ", s)
    s = _CALC_ANN_RE.sub(" ", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _normalize_unit(raw_span: str) -> str | None:
    low = raw_span.lower()
    if "cent" in low:
        return "usd_cent"
    if "$" in raw_span or "dollar" in low:
        return "usd"
    if "%" in raw_span:
        return "percent"
    m = _UNIT_WORD_RE.search(raw_span)
    if not m:
        return None
    unit = m.group(1).lower()
    if unit.endswith("s") and unit not in {"lbs"}:
        unit = unit[:-1]
    return unit


def _normalize_numeric_token(raw: str) -> tuple[str | None, float | None, str]:
    s = raw.strip().replace(",", "")
    s = s.replace("$", "")
    if not s:
        return None, None, "text"
    pct = s.endswith("%")
    if pct:
        s = s[:-1].strip()
    frac_m = re.match(r"^\s*([-+]?\d+)\s*/\s*(\d+)\s*$", s)
    try:
        if frac_m:
            den = int(frac_m.group(2))
            if den == 0:
                return None, None, "fraction"
            value = Fraction(int(frac_m.group(1)), den)
            dec = Decimal(value.numerator) / Decimal(value.denominator)
            kind = "fraction"
        else:
            dec = Decimal(s)
            kind = "decimal" if "." in s else "integer"
        if pct:
            dec = dec / Decimal("100")
            kind = "percent"
        if dec == dec.to_integral():
            can = str(int(dec))
        else:
            can = format(dec.normalize(), "f").rstrip("0").rstrip(".")
        return can, float(dec), kind
    except (InvalidOperation, ValueError, OverflowError):
        return None, None, "text"


def _operator_density(s: str) -> float:
    if not s:
        return 0.0
    return len(_OPER_RE.findall(s)) / max(len(s), 1)


def _candidate_from_span(span: str, cue_type: str, line_index: int, sentence_index: int) -> ParsedAnswerCandidate | None:
    nums = list(_NUM_TOKEN_RE.finditer(span))
    comp = len(nums)
    op_density = _operator_density(span)
    ambiguous = comp != 1
    if comp == 0:
        return None
    if comp > 1:
        first = nums[-1]
    else:
        first = nums[0]
    raw = first.group(0)
    can, val, num_type = _normalize_numeric_token(raw)
    unit = _normalize_unit(span)
    if can is None:
        return None
    conf = CONF_HIGH if cue_type in {"hashes", "boxed", "final_answer_colon", "answer_colon", "the_answer_is", "so_the_answer_is", "therefore_the_answer_is", "thus_the_answer_is", "in_total", "altogether"} else CONF_MED
    if ambiguous:
        conf = CONF_AMBIGUOUS
    elif cue_type in {"fallback_ambiguous", "fallback_last_line_arithmetic"}:
        conf = CONF_LOW
    elif op_density > 0.08 and cue_type in {"fallback_last_line_singleton", "fallback_sentence_singleton"}:
        conf = CONF_LOW
    cand = CanonicalAnswer(
        raw_text=span.strip(),
        canonical_value=can,
        numeric_value=val,
        numeric_type=num_type,
        unit=unit,
        cue_type=cue_type,
        confidence=conf,
        ambiguous=ambiguous,
        ambiguity_reason=("multiple_numeric_candidates" if ambiguous else None),
        line_index=line_index,
        sentence_index=sentence_index,
        operator_density=op_density,
        competing_candidates=comp,
    )
    return ParsedAnswerCandidate(
        raw_span=span.strip(),
        cue_type=cue_type,
        line_index=line_index,
        sentence_index=sentence_index,
        operator_density=op_density,
        competing_candidates=comp,
        canonical=cand,
    )


def extract_answer_candidates(text: str) -> list[ParsedAnswerCandidate]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    lines = cleaned.split("\n")
    cands: list[ParsedAnswerCandidate] = []

    # Priority 1-3: explicit cues.
    for cue, pat in _CUE_PATTERNS:
        for m in pat.finditer(cleaned):
            span = (m.group(1) or "").strip()
            if not span:
                continue
            line_idx = cleaned[: m.start()].count("\n")
            sent_idx = len(_SENT_SPLIT_RE.split(cleaned[: m.start()]))
            c = _candidate_from_span(span, cue, line_idx, sent_idx)
            if c:
                cands.append(c)

    if cands:
        return cands

    # Priority 4: final declarative sentence with exactly one numeric.
    sents = _SENT_SPLIT_RE.split(cleaned)
    if sents:
        final_sent = sents[-1].strip()
        nums = list(_NUM_TOKEN_RE.finditer(final_sent))
        if len(nums) == 1:
            c = _candidate_from_span(final_sent, "fallback_sentence_singleton", len(lines) - 1, len(sents) - 1)
            if c:
                cands.append(c)
                return cands

    # Priority 5: last line singleton with low operator density.
    if lines:
        last_line = lines[-1].strip()
        nums = list(_NUM_TOKEN_RE.finditer(last_line))
        if len(nums) == 1 and _operator_density(last_line) <= 0.08:
            c = _candidate_from_span(last_line, "fallback_last_line_singleton", len(lines) - 1, max(0, len(sents) - 1))
            if c:
                cands.append(c)
                return cands
        if len(nums) >= 1 and _operator_density(last_line) > 0.08:
            c = _candidate_from_span(nums[-1].group(0), "fallback_last_line_arithmetic", len(lines) - 1, max(0, len(sents) - 1))
            if c:
                cands.append(c)
                return cands

    # Fall back to all numeric mentions as ambiguous low confidence.
    for rev_idx, line in enumerate(reversed(lines)):
        line_idx = len(lines) - 1 - rev_idx
        nums = list(_NUM_TOKEN_RE.finditer(line))
        if not nums:
            continue
        c = _candidate_from_span(line, "fallback_ambiguous", line_idx, line_idx)
        if c:
            cands.append(c)
    return cands


def canonicalize_answer(text: str) -> CanonicalAnswer:
    cands = extract_answer_candidates(text)
    if not cands:
        return CanonicalAnswer(
            raw_text=str(text or ""),
            canonical_value=None,
            numeric_value=None,
            numeric_type="text",
            unit=None,
            cue_type="none",
            confidence=CONF_AMBIGUOUS,
            ambiguous=True,
            ambiguity_reason="no_numeric_candidate",
            line_index=-1,
            sentence_index=-1,
            operator_density=0.0,
            competing_candidates=0,
        )
    # Pick first explicit/high candidate; otherwise first candidate.
    high = [c for c in cands if c.canonical.confidence == CONF_HIGH and not c.canonical.ambiguous]
    if high:
        return high[0].canonical
    med = [c for c in cands if c.canonical.confidence == CONF_MED and not c.canonical.ambiguous]
    if med:
        return med[0].canonical
    return cands[0].canonical


def parse_final_answer(text: str) -> ParsedAnswerDecision:
    cands = extract_answer_candidates(text)
    if not cands:
        return ParsedAnswerDecision(
            selected=None,
            all_candidates=tuple(),
            confidence=CONF_AMBIGUOUS,
            ambiguous=True,
            ambiguity_reason="no_numeric_candidate",
            used_fallback_to_none=True,
        )
    selected = canonicalize_answer(text)
    return ParsedAnswerDecision(
        selected=selected,
        all_candidates=tuple(cands),
        confidence=selected.confidence,
        ambiguous=selected.ambiguous or selected.confidence == CONF_AMBIGUOUS,
        ambiguity_reason=selected.ambiguity_reason,
        used_fallback_to_none=False,
    )


def answers_equivalent(a: Any, b: Any) -> bool:
    ca = canonicalize_answer(str(a or ""))
    cb = canonicalize_answer(str(b or ""))
    if ca.canonical_value is None or cb.canonical_value is None:
        return False
    if ca.numeric_value is not None and cb.numeric_value is not None:
        # Treat cents and dollars as equivalent currencies under canonical conversion.
        va = ca.numeric_value / 100.0 if ca.unit == "usd_cent" else ca.numeric_value
        vb = cb.numeric_value / 100.0 if cb.unit == "usd_cent" else cb.numeric_value
        ua = "usd" if ca.unit in {"usd", "usd_cent"} else ca.unit
        ub = "usd" if cb.unit in {"usd", "usd_cent"} else cb.unit
        if ua != ub and ua not in {None, "percent"} and ub not in {None, "percent"}:
            return False
        return abs(va - vb) < 1e-9
    if ca.unit != cb.unit and ca.unit not in {None, "percent"} and cb.unit not in {None, "percent"}:
        return False
    return ca.canonical_value == cb.canonical_value
