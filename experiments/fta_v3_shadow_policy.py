"""Experimental FTA v3 shadow-policy variants (opt-in, not canonical FTA).

Gold-free at runtime: predicates and actions use only candidate-pool answers and
derived runtime-safe features.  Not imported by ``experiments.fta_policy``.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from experiments.support_aware_selector import (
    _normalize_answer,
    external_agreement_signature,
    select_external_majority,
)

FORBIDDEN_RUNTIME_FEATURE_SUBSTRINGS = frozenset(
    {
        "gold",
        "correct",
        "correctness",
        "exact_match",
        "selector_fixable",
        "all_sources_wrong",
        "coverage_limited",
        "recovery",
        "regression",
        "gate_success",
    }
)

RUNTIME_SAFE_V3_FEATURE_NAMES = (
    "fta_norm",
    "frontier_norm",
    "l1_norm",
    "s1_norm",
    "tale_norm",
    "agreement_signature",
    "external_majority_norm",
    "external_unique_answer_count",
    "external_majority_disagrees_with_fta",
    "external_unanimity_disagrees_with_fta",
    "external_2of3_against_fta",
    "override_reason",
    "frontier_support",
    "support_margin",
    "candidate_pool_answer_group_count",
    "confidence_proxy",
    "answer_entropy",
    "answer_entropy_bin",
    "fta_matches_frontier",
    "fta_matches_any_external",
    "exact_2of3_external_norm",
    "unanimous_external_norm",
    "s1_tale_agree_against_fta",
    "frontier_differs_from_external_majority",
)


def assert_runtime_features_gold_free(feature_names: list[str]) -> None:
    for name in feature_names:
        lowered = name.lower()
        for forbidden in FORBIDDEN_RUNTIME_FEATURE_SUBSTRINGS:
            if forbidden in lowered:
                raise ValueError(
                    f"Runtime feature {name!r} contains forbidden substring {forbidden!r}"
                )


assert_runtime_features_gold_free(list(RUNTIME_SAFE_V3_FEATURE_NAMES))


def _cell(row: dict[str, Any], key: str) -> str:
    return str(row.get(key, "") or "").strip()


def _parse_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def answer_entropy(normed_answers: list[str | None]) -> float:
    valid = [a for a in normed_answers if a]
    if not valid:
        return 0.0
    counts = Counter(valid)
    total = len(valid)
    ent = 0.0
    for c in counts.values():
        p = c / total
        ent -= p * math.log2(p)
    return ent


def numeric_bin(value: float | None, edges: list[float], *, missing_label: str = "missing") -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return missing_label
    v = float(value)
    for i, edge in enumerate(edges):
        if v <= edge:
            if i == 0:
                return f"le{edge}"
            return f"gt{edges[i - 1]}_le{edge}"
    return f"gt{edges[-1]}"


def _external_dict_from_row(row: dict[str, Any]) -> dict[str, str]:
    return {
        "external_l1_max": _cell(row, "l1_answer") or _cell(row, "l1_raw"),
        "external_s1_budget_forcing": _cell(row, "s1_answer") or _cell(row, "s1_raw"),
        "external_tale_prompt_budgeting": _cell(row, "tale_answer") or _cell(row, "tale_raw"),
    }


def select_external_majority_for_v3(row: dict[str, Any]) -> str | None:
    """Runtime-safe external majority over L1/S1/TALE."""
    cached = row.get("external_majority_norm")
    if cached:
        return str(cached)
    ext = _external_dict_from_row(row)
    ans, _ = select_external_majority(ext)
    return ans


def select_exact_2of3_external_for_v3(row: dict[str, Any]) -> str | None:
    """Return external answer only when exactly two of L1/S1/TALE agree (not unanimous)."""
    norms = [
        row.get("l1_norm") or _normalize_answer(_cell(row, "l1_answer") or _cell(row, "l1_raw")),
        row.get("s1_norm") or _normalize_answer(_cell(row, "s1_answer") or _cell(row, "s1_raw")),
        row.get("tale_norm")
        or _normalize_answer(_cell(row, "tale_answer") or _cell(row, "tale_raw")),
    ]
    valid = [n for n in norms if n]
    if len(valid) < 3:
        return None
    counts = Counter(valid)
    ans, vote = counts.most_common(1)[0]
    return ans if vote == 2 else None


def select_external_2of3_for_v3(row: dict[str, Any]) -> str | None:
    """Return 2-of-3 external majority (vote >= 2), including unanimous."""
    norms = [
        row.get("l1_norm") or _normalize_answer(_cell(row, "l1_answer") or _cell(row, "l1_raw")),
        row.get("s1_norm") or _normalize_answer(_cell(row, "s1_answer") or _cell(row, "s1_raw")),
        row.get("tale_norm")
        or _normalize_answer(_cell(row, "tale_answer") or _cell(row, "tale_raw")),
    ]
    valid = [n for n in norms if n]
    if len(valid) < 2:
        return None
    counts = Counter(valid)
    ans, vote = counts.most_common(1)[0]
    return ans if vote >= 2 else None


def compute_runtime_safe_v3_features(row: dict[str, Any]) -> dict[str, Any]:
    """Compute gold-free runtime features for v3 shadow predicates."""
    fta_raw = (
        _cell(row, "fta_answer")
        or _cell(row, "fta_selected_answer")
        or _cell(row, "fta_raw")
    )
    frontier_raw = _cell(row, "frontier_answer") or _cell(row, "frontier_raw")
    l1_raw = _cell(row, "l1_answer") or _cell(row, "l1_raw")
    s1_raw = _cell(row, "s1_answer") or _cell(row, "s1_raw")
    tale_raw = _cell(row, "tale_answer") or _cell(row, "tale_raw")

    fta_norm = row.get("fta_norm") or _normalize_answer(fta_raw)
    frontier_norm = row.get("frontier_norm") or _normalize_answer(frontier_raw)
    l1_norm = row.get("l1_norm") or _normalize_answer(l1_raw)
    s1_norm = row.get("s1_norm") or _normalize_answer(s1_raw)
    tale_norm = row.get("tale_norm") or _normalize_answer(tale_raw)

    ext_dict = _external_dict_from_row(row)
    agreement_signature = _cell(row, "agreement_signature") or external_agreement_signature(ext_dict)
    ext_maj_norm, _ = select_external_majority(ext_dict)

    ext_norms = [n for n in (l1_norm, s1_norm, tale_norm) if n]
    ext_unique = len(set(ext_norms))
    unanimous_external_norm = ext_norms[0] if ext_unique == 1 and len(ext_norms) == 3 else None
    exact_2of3 = select_exact_2of3_external_for_v3(
        {"l1_norm": l1_norm, "s1_norm": s1_norm, "tale_norm": tale_norm}
    )
    ext_2of3 = select_external_2of3_for_v3(
        {"l1_norm": l1_norm, "s1_norm": s1_norm, "tale_norm": tale_norm}
    )

    ext_maj_disagrees = bool(ext_maj_norm and fta_norm and ext_maj_norm != fta_norm)
    ext_unanimous_disagrees = bool(
        unanimous_external_norm and fta_norm and unanimous_external_norm != fta_norm
    )
    ext_2of3_against = bool(ext_2of3 and fta_norm and ext_2of3 != fta_norm)
    ent = answer_entropy([frontier_norm, l1_norm, s1_norm, tale_norm])
    fta_matches_frontier = bool(fta_norm and frontier_norm and fta_norm == frontier_norm)
    fta_matches_any_external = bool(
        fta_norm and any(fta_norm == n for n in (l1_norm, s1_norm, tale_norm) if n)
    )
    s1_tale_agree_against_fta = bool(
        s1_norm and tale_norm and s1_norm == tale_norm and fta_norm and s1_norm != fta_norm
    )
    frontier_differs_from_external_majority = bool(
        frontier_norm and ext_maj_norm and frontier_norm != ext_maj_norm
    )

    features: dict[str, Any] = {
        "fta_norm": fta_norm or "",
        "frontier_norm": frontier_norm or "",
        "l1_norm": l1_norm or "",
        "s1_norm": s1_norm or "",
        "tale_norm": tale_norm or "",
        "agreement_signature": agreement_signature,
        "external_majority_norm": ext_maj_norm or "",
        "external_unique_answer_count": ext_unique,
        "external_majority_disagrees_with_fta": int(ext_maj_disagrees),
        "external_unanimity_disagrees_with_fta": int(ext_unanimous_disagrees),
        "external_2of3_against_fta": int(ext_2of3_against),
        "override_reason": _cell(row, "override_reason") or "unknown",
        "frontier_support": _parse_float(row.get("frontier_support")),
        "support_margin": _parse_float(row.get("support_margin")),
        "candidate_pool_answer_group_count": row.get("candidate_pool_answer_group_count"),
        "confidence_proxy": _parse_float(row.get("confidence_proxy")),
        "answer_entropy": round(ent, 4),
        "answer_entropy_bin": numeric_bin(ent, [0.5, 1.0, 1.5]),
        "fta_matches_frontier": int(fta_matches_frontier),
        "fta_matches_any_external": int(fta_matches_any_external),
        "exact_2of3_external_norm": exact_2of3 or "",
        "unanimous_external_norm": unanimous_external_norm or "",
        "s1_tale_agree_against_fta": int(s1_tale_agree_against_fta),
        "frontier_differs_from_external_majority": int(frontier_differs_from_external_majority),
    }
    return features


@dataclass(frozen=True)
class ShadowVariant:
    variant_id: str
    description: str
    predicate: Callable[[dict[str, Any]], bool]
    select_norm: Callable[[dict[str, Any]], str | None]


def _g1_predicate(feat: dict[str, Any]) -> bool:
    return feat.get("fta_matches_frontier") == 0 and feat.get("answer_entropy_bin") == "gt0.5_le1.0"


def _g2_predicate(feat: dict[str, Any]) -> bool:
    return (
        feat.get("external_2of3_against_fta") == 1
        and feat.get("fta_matches_frontier") == 0
        and feat.get("answer_entropy_bin") == "gt0.5_le1.0"
    )


def _g3_predicate(feat: dict[str, Any]) -> bool:
    return (
        feat.get("override_reason") == "single_weak_frontier_branch"
        and feat.get("answer_entropy_bin") == "gt0.5_le1.0"
    )


def _merged_row(row: dict[str, Any]) -> dict[str, Any]:
    feat = compute_runtime_safe_v3_features(row)
    out = dict(row)
    out.update(feat)
    return out


def _variant_definitions() -> list[ShadowVariant]:
    return [
        ShadowVariant(
            "keep_fta",
            "V0: keep FTA baseline (no shadow override).",
            lambda _f: False,
            lambda r: r.get("fta_norm") or None,
        ),
        ShadowVariant(
            "g1_external_majority",
            "V1: G1 gate + external majority.",
            _g1_predicate,
            select_external_majority_for_v3,
        ),
        ShadowVariant(
            "g2_external_2of3",
            "V2: G2 gate + external 2-of-3 majority.",
            _g2_predicate,
            select_external_2of3_for_v3,
        ),
        ShadowVariant(
            "g2_exact_2of3_no_unanimous",
            "V3: G2 gate + exact 2-of-3 (refuse unanimous externals).",
            lambda f: _g2_predicate(f) and f.get("external_unique_answer_count") == 2,
            select_exact_2of3_external_for_v3,
        ),
        ShadowVariant(
            "g1_external_majority_no_unanimous_against_fta",
            "V4: G1 gate + external majority, skip unanimous-external-against-FTA.",
            lambda f: _g1_predicate(f) and not (
                f.get("agreement_signature") == "l1=s1=tale"
                and f.get("external_unanimity_disagrees_with_fta") == 1
            ),
            select_external_majority_for_v3,
        ),
        ShadowVariant(
            "g1_s1_tale_only",
            "V5: G1 gate + S1=TALE agreement against FTA.",
            lambda f: _g1_predicate(f) and f.get("s1_tale_agree_against_fta") == 1,
            lambda r: r.get("s1_norm") or None,
        ),
        ShadowVariant(
            "g1_external_majority_require_fta_not_external",
            "V6: G1 gate + external majority when FTA matches no external.",
            lambda f: _g1_predicate(f) and f.get("fta_matches_any_external") == 0,
            select_external_majority_for_v3,
        ),
        ShadowVariant(
            "g1_external_majority_require_frontier_not_external_majority",
            "V7: G1 gate + external majority when frontier != external majority.",
            lambda f: _g1_predicate(f) and f.get("frontier_differs_from_external_majority") == 1,
            select_external_majority_for_v3,
        ),
    ]


_VARIANTS: dict[str, ShadowVariant] = {v.variant_id: v for v in _variant_definitions()}


def available_fta_v3_shadow_variants() -> tuple[str, ...]:
    return tuple(_VARIANTS.keys())


def apply_fta_v3_shadow_policy_to_row(
    row: dict[str, Any],
    *,
    variant: str = "g1_external_majority",
) -> dict[str, Any]:
    """Apply an experimental v3 shadow variant to one row.

    Returns a decision dict with runtime-safe metadata only (no gold labels).
    """
    if variant not in _VARIANTS:
        raise ValueError(
            f"Unknown variant {variant!r}; choose from {available_fta_v3_shadow_variants()}"
        )
    spec = _VARIANTS[variant]
    merged = _merged_row(row)
    fta_norm = merged.get("fta_norm") or None
    fta_raw = (
        _cell(row, "fta_answer")
        or _cell(row, "fta_selected_answer")
        or _cell(row, "fta_raw")
    )

    if not spec.predicate(merged):
        return {
            "variant": variant,
            "triggered": False,
            "selected_norm": fta_norm,
            "selected_raw": fta_raw,
            "overridden_fta": False,
            "reason": "gate_not_triggered",
            "action": "keep_fta",
        }

    selected = spec.select_norm(merged)
    if not selected:
        return {
            "variant": variant,
            "triggered": True,
            "selected_norm": fta_norm,
            "selected_raw": fta_raw,
            "overridden_fta": False,
            "reason": "gate_triggered_no_actionable_answer",
            "action": "keep_fta",
        }

    overridden = selected != fta_norm
    return {
        "variant": variant,
        "triggered": True,
        "selected_norm": selected,
        "selected_raw": selected,
        "overridden_fta": overridden,
        "reason": spec.description,
        "action": variant,
    }


def gate_g1_triggered(row: dict[str, Any]) -> bool:
    return _g1_predicate(compute_runtime_safe_v3_features(row))


def gate_g2_triggered(row: dict[str, Any]) -> bool:
    return _g2_predicate(compute_runtime_safe_v3_features(row))


def gate_g3_triggered(row: dict[str, Any]) -> bool:
    return _g3_predicate(compute_runtime_safe_v3_features(row))
