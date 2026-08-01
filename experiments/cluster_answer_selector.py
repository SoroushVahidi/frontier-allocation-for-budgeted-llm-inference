"""Offline FIX-7 cluster selector primitives.

This module is intentionally offline-first and gold-free at runtime.
It provides conservative parsing/canonicalization, answer clustering,
and a conservative default selector used by offline replay scripts.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import re
from typing import Any


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class CanonicalAnswer:
    raw_text: str
    canonical_answer: str | None
    numeric_value: float | None
    normalized_unit: str | None
    parser_confidence: str
    ambiguous: bool
    cue: str | None


@dataclass(frozen=True)
class ParsedAnswerCandidate:
    raw_text: str
    cue: str | None
    canonical: CanonicalAnswer


@dataclass(frozen=True)
class AnswerEvidence:
    source: str
    source_kind: str
    raw_text: str
    parser_confidence: str
    canonical_answer: str | None
    normalized_unit: str | None
    branch_id: str | None = None


@dataclass
class AnswerCluster:
    cluster_id: str
    canonical_answer: str | None
    normalized_unit: str | None
    evidences: list[AnswerEvidence]
    parser_confidence_min: str
    parser_confidence_mean: float


@dataclass(frozen=True)
class Fix7Decision:
    selected_cluster_id: str | None
    selected_answer: str | None
    rule_name: str
    override_applied: bool
    override_reason: str


_BOXED_RE = re.compile(r"\\boxed\{([^{}]+)\}")
_NUM_RE = re.compile(
    r"(?P<sign>[-+]?)"
    r"(?P<num>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\d+\s*/\s*\d+)"
    r"\s*(?P<pct>%?)"
    r"(?:\s*(?P<unit>[a-zA-Z][a-zA-Z0-9_\-/]*))?"
)
_TRAILING_UNIT_RE = re.compile(r"^\s*(.+?)\s+([a-zA-Z][a-zA-Z0-9_\-/]*)\s*$")


def _clean_text(text: Any) -> str:
    return str(text or "").strip()


def _normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.strip().lower()
    return u or None


def _normalize_number(num_text: str, pct: str = "") -> tuple[str | None, float | None]:
    s = num_text.strip().replace(",", "")
    try:
        if "/" in s and re.match(r"^\d+\s*/\s*\d+$", s):
            frac = Fraction(s.replace(" ", ""))
            value = Decimal(frac.numerator) / Decimal(frac.denominator)
        else:
            value = Decimal(s)
        if pct == "%":
            # Keep explicit percentage as proportion for canonical numeric comparison.
            value = value / Decimal("100")
        value = value.normalize()
        if value == value.to_integral():
            canonical = str(int(value))
        else:
            canonical = format(value, "f").rstrip("0").rstrip(".")
        return canonical, float(value)
    except (InvalidOperation, ZeroDivisionError, ValueError, OverflowError):
        return None, None


def extract_final_answer_candidates(text: str) -> list[ParsedAnswerCandidate]:
    """Extract conservative answer candidates with cue prioritization."""
    t = _clean_text(text)
    if not t:
        return []

    cands: list[ParsedAnswerCandidate] = []

    for m in _BOXED_RE.finditer(t):
        raw = m.group(1).strip()
        cands.append(
            ParsedAnswerCandidate(
                raw_text=raw,
                cue="boxed",
                canonical=canonicalize_answer_text(raw, cue="boxed", explicit=True),
            )
        )

    cue_patterns = [
        ("hashes", re.compile(r"####\s*([^\n]+)")),
        ("final_answer", re.compile(r"(?:final answer|answer)\s*[:\-]\s*([^\n]+)", re.IGNORECASE)),
        ("the_answer_is", re.compile(r"(?:the answer is|so the answer is)\s+([^\n\.]+)", re.IGNORECASE)),
    ]
    for cue, pat in cue_patterns:
        for m in pat.finditer(t):
            raw = m.group(1).strip()
            if raw:
                cands.append(
                    ParsedAnswerCandidate(
                        raw_text=raw,
                        cue=cue,
                        canonical=canonicalize_answer_text(raw, cue=cue, explicit=True),
                    )
                )

    if cands:
        return cands

    # Fallback: collect numeric mentions and keep last one as medium confidence.
    nums = list(_NUM_RE.finditer(t))
    if nums:
        for i, m in enumerate(nums):
            raw = m.group(0).strip()
            conf = "medium" if i == len(nums) - 1 and len(nums) == 1 else "low"
            cands.append(
                ParsedAnswerCandidate(
                    raw_text=raw,
                    cue="numeric_fallback",
                    canonical=canonicalize_answer_text(raw, cue="numeric_fallback", explicit=False, forced_confidence=conf),
                )
            )
        return cands

    # Last resort: plain text candidate with low confidence.
    cands.append(
        ParsedAnswerCandidate(
            raw_text=t,
            cue="raw_fallback",
            canonical=CanonicalAnswer(
                raw_text=t,
                canonical_answer=t.lower(),
                numeric_value=None,
                normalized_unit=None,
                parser_confidence="low",
                ambiguous=True,
                cue="raw_fallback",
            ),
        )
    )
    return cands


def canonicalize_answer_text(
    text: str,
    *,
    cue: str | None = None,
    explicit: bool = False,
    forced_confidence: str | None = None,
) -> CanonicalAnswer:
    """Canonicalize text into a conservative numeric/text answer representation."""
    raw = _clean_text(text)
    if not raw:
        return CanonicalAnswer(
            raw_text=raw,
            canonical_answer=None,
            numeric_value=None,
            normalized_unit=None,
            parser_confidence="low",
            ambiguous=True,
            cue=cue,
        )

    # Strip currency markers early, keep unit separately.
    stripped = raw.replace("$", "").replace("€", "").replace("£", "").strip()

    # Fast path: whole-string fraction (with optional sign/unit/percent).
    frac_full = re.match(
        r"^\s*(?P<sign>[-+]?)\s*(?P<num>\d+\s*/\s*\d+)\s*(?P<pct>%?)\s*(?P<unit>[a-zA-Z][a-zA-Z0-9_\-/]*)?\s*$",
        stripped,
    )
    if frac_full:
        sign = frac_full.group("sign") or ""
        frac_num = frac_full.group("num") or ""
        pct = frac_full.group("pct") or ""
        unit = _normalize_unit(frac_full.group("unit"))
        canonical, numeric_value = _normalize_number(f"{sign}{frac_num}", pct=pct)
        conf = forced_confidence if forced_confidence in {"low", "medium", "high"} else ("high" if explicit else "medium")
        return CanonicalAnswer(
            raw_text=raw,
            canonical_answer=canonical,
            numeric_value=numeric_value,
            normalized_unit=unit,
            parser_confidence=conf,
            ambiguous=False,
            cue=cue,
        )

    unit: str | None = None
    m_unit = _TRAILING_UNIT_RE.match(stripped)
    if m_unit:
        left, unit_candidate = m_unit.group(1), m_unit.group(2)
        # Only split if left side looks numeric-ish.
        if _NUM_RE.search(left):
            stripped = left.strip()
            unit = _normalize_unit(unit_candidate)

    num_match = _NUM_RE.search(stripped)
    canonical: str | None = None
    numeric_value: float | None = None
    ambiguous = False
    if num_match:
        canonical, numeric_value = _normalize_number(
            (num_match.group("sign") or "") + (num_match.group("num") or ""),
            pct=(num_match.group("pct") or ""),
        )
        if not unit:
            unit = _normalize_unit(num_match.group("unit"))
        # Ambiguous if multiple numeric tokens appear in the same candidate text.
        ambiguous = len(list(_NUM_RE.finditer(stripped))) > 1
    else:
        canonical = stripped.lower() if stripped else None
        ambiguous = True

    if forced_confidence in {"low", "medium", "high"}:
        conf = forced_confidence
    elif explicit and cue in {"boxed", "hashes", "final_answer", "the_answer_is"} and canonical is not None:
        conf = "high"
    elif canonical is not None and not ambiguous:
        conf = "medium"
    else:
        conf = "low"

    return CanonicalAnswer(
        raw_text=raw,
        canonical_answer=canonical,
        numeric_value=numeric_value,
        normalized_unit=unit,
        parser_confidence=conf,
        ambiguous=ambiguous,
        cue=cue,
    )


def cluster_answers(candidates: list[AnswerEvidence]) -> list[AnswerCluster]:
    """Cluster evidence by canonical value and normalized unit."""
    buckets: dict[tuple[str | None, str | None], list[AnswerEvidence]] = {}
    for ev in candidates:
        key = (ev.canonical_answer, ev.normalized_unit)
        buckets.setdefault(key, []).append(ev)

    clusters: list[AnswerCluster] = []
    for idx, ((canonical, unit), evidences) in enumerate(buckets.items(), start=1):
        conf_values = [CONFIDENCE_ORDER.get(ev.parser_confidence, 0) for ev in evidences]
        parser_conf_mean = (sum(conf_values) / len(conf_values)) if conf_values else 0.0
        parser_conf_min = min((ev.parser_confidence for ev in evidences), key=lambda x: CONFIDENCE_ORDER.get(x, 0))
        clusters.append(
            AnswerCluster(
                cluster_id=f"C{idx:02d}",
                canonical_answer=canonical,
                normalized_unit=unit,
                evidences=evidences,
                parser_confidence_min=parser_conf_min,
                parser_confidence_mean=parser_conf_mean,
            )
        )
    return clusters


def compute_cluster_features(
    cluster: AnswerCluster,
    *,
    baseline_answer: str | None,
    frontier_answer: str | None,
    l1_answer: str | None,
    s1_answer: str | None,
    tale_answer: str | None,
    low_depth_flag: bool,
    high_disagreement_flag: bool,
    support_margin: float | None,
    override_reason: str | None,
) -> dict[str, Any]:
    """Build runtime-safe features for a cluster."""
    ext_methods = {"external_l1_max", "external_s1_budget_forcing", "external_tale_prompt_budgeting"}
    method_set = {ev.source for ev in cluster.evidences}
    source_kinds = [ev.source_kind for ev in cluster.evidences]
    branch_ids = {ev.branch_id for ev in cluster.evidences if ev.branch_id}

    external_count = len(method_set.intersection(ext_methods))
    frontier_count = sum(1 for k in source_kinds if k.startswith("frontier"))
    support_mass = len(cluster.evidences)

    return {
        "cluster_id": cluster.cluster_id,
        "canonical_answer": cluster.canonical_answer,
        "normalized_unit": cluster.normalized_unit,
        "methods_present": sorted(method_set),
        "external_count": external_count,
        "frontier_count": frontier_count,
        "independent_path_count": len(branch_ids),
        "final_node_count": sum(1 for k in source_kinds if k == "frontier_final_node"),
        "support_mass": support_mass,
        "parser_confidence_mean": cluster.parser_confidence_mean,
        "parser_confidence_min": cluster.parser_confidence_min,
        "contains_fix24_answer": bool(cluster.canonical_answer and cluster.canonical_answer == baseline_answer),
        "contains_frontier_answer": bool(cluster.canonical_answer and cluster.canonical_answer == frontier_answer),
        "contains_tale_answer": bool(cluster.canonical_answer and cluster.canonical_answer == tale_answer),
        "contains_l1_answer": bool(cluster.canonical_answer and cluster.canonical_answer == l1_answer),
        "contains_s1_answer": bool(cluster.canonical_answer and cluster.canonical_answer == s1_answer),
        "external_majority_count": external_count,
        "external_unanimous": external_count >= 3,
        "low_depth_flag": bool(low_depth_flag),
        "high_disagreement_flag": bool(high_disagreement_flag),
        "override_reason": override_reason or "",
        "support_margin_runtime": support_margin,
    }


def select_fix7_cluster_v0(group: dict[str, Any], base_fix24_answer: str | None) -> Fix7Decision:
    """Conservative default selector for offline FIX-7-v0.

    Rule order:
    1) Keep baseline by default.
    2) Only override if another cluster has unanimous external support (3/3),
       is represented in frontier evidence, baseline parser confidence is lower,
       and low-depth flag is false.
    """
    cluster_features = list(group.get("cluster_features") or [])
    if not cluster_features:
        return Fix7Decision(None, base_fix24_answer, "R0", False, "no_cluster_features")

    base = next((c for c in cluster_features if c.get("contains_fix24_answer")), None)
    if not base:
        return Fix7Decision(None, base_fix24_answer, "R0", False, "baseline_cluster_not_found")

    if bool(base.get("low_depth_flag")):
        return Fix7Decision(str(base.get("cluster_id")), base_fix24_answer, "R0", False, "low_depth_guard_keep_baseline")

    challengers = [
        c
        for c in cluster_features
        if c.get("cluster_id") != base.get("cluster_id")
        and int(c.get("external_count", 0)) >= 3
        and int(c.get("frontier_count", 0)) >= 1
    ]
    if not challengers:
        return Fix7Decision(str(base.get("cluster_id")), base_fix24_answer, "R0", False, "no_safe_challenger")

    base_conf = float(base.get("parser_confidence_mean", 0.0))
    challengers.sort(
        key=lambda c: (
            int(c.get("external_count", 0)),
            float(c.get("parser_confidence_mean", 0.0)),
            int(c.get("support_mass", 0)),
        ),
        reverse=True,
    )
    top = challengers[0]
    if float(top.get("parser_confidence_mean", 0.0)) < base_conf:
        return Fix7Decision(str(base.get("cluster_id")), base_fix24_answer, "R0", False, "challenger_parser_weaker")

    return Fix7Decision(
        selected_cluster_id=str(top.get("cluster_id")),
        selected_answer=top.get("canonical_answer"),
        rule_name="R5_combined_conservative_v0",
        override_applied=True,
        override_reason="external_unanimous_realized_parser_guard",
    )


def apply_fix7_offline(group: dict[str, Any]) -> Fix7Decision:
    """Apply default FIX-7-v0 policy to a precomputed group payload."""
    base_fix24_answer = group.get("baseline_answer")
    return select_fix7_cluster_v0(group, base_fix24_answer)
