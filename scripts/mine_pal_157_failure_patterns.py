#!/usr/bin/env python3
"""Mine no-API deep patterns in the 157 PAL still-failing covered cases."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_pal_unresolved_pattern_taxonomy as taxonomy_builder

DEFAULT_FAILURE_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
DEFAULT_GOLD_ABSENT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
DEFAULT_ANCHOR_EFFECT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_20260510.csv"
DEFAULT_OUTPUTS_ROOT = REPO_ROOT / "outputs"
DEFAULT_OUTPUT_PREFIX = "pal_157_failure_patterns_"
DEFAULT_METHOD = taxonomy_builder.DEFAULT_METHOD
DEFAULT_EXACT_REPLAY_30_JSONL = REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl"
DEFAULT_EXACT_REPLAY_50_JSONL = REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_50case_exact_cases_20260510.jsonl"

TRUE_TOKENS = {"1", "true", "t", "yes", "y"}
FALSE_TOKENS = {"0", "false", "f", "no", "n"}

DOMAIN_TAG_BY_QUESTION_TYPE = {
    "money/cost/revenue": "domain_money_cost_revenue",
    "ratio/proportion/percentage": "domain_ratio_percentage",
    "multi-step arithmetic": "domain_multi_step_arithmetic",
    "temporal/calendar": "domain_temporal_calendar",
    "rate/speed/work": "domain_rate_speed_work",
    "unit conversion": "domain_unit_conversion",
    "inventory/remaining quantity": "domain_inventory_remaining_quantity",
}
DOMAIN_TAGS = tuple(DOMAIN_TAG_BY_QUESTION_TYPE.values())

QUESTION_KEYWORDS = {
    "money": ("$", "cost", "costs", "price", "prices", "revenue", "profit", "fee", "fees", "dollar", "dollars", "cent", "cents", "pay", "paid", "spend", "spent", "save", "saves"),
    "ratio": ("ratio", "proportion", "fraction", "out of", "per "),
    "percentage": ("percent", "%", "percentage"),
    "temporal": ("day", "days", "week", "weeks", "month", "months", "year", "years", "hour", "hours", "minute", "minutes", "age", "old"),
    "rate_unit": ("per", "each", "every", "mph", "speed", "rate", "hour", "minute", "mile", "km", "meter", "meters", "gram", "grams", "kg", "liters", "dollars per"),
    "remaining": ("remaining", "left", "remain", "difference", "more than", "less than", "fewer than", "save", "saves", "change"),
    "factor": ("twice", "triple", "double", "half", "third", "quarter", "times as many", "factor"),
    "multi_step": (" then ", " after ", " before ", " first ", " second ", " finally ", " total", "altogether", "combined", "bought", "sold", "gave", "received", "added", "subtracted"),
    "base_quantity": ("total", "in all", "altogether", "combined", "of the", "from the", "than the"),
}

CASE_FIELDNAMES = [
    "case_id",
    "method",
    "question_type",
    "domain_tag",
    "mechanism_tags",
    "pattern_tags",
    "actionable_tags",
    "failure_family",
    "error_type",
    "num_candidate_groups",
    "diversity_bucket",
    "external_contrast",
    "gold_answer",
    "predicted_answer",
    "selected_answer",
    "anchor_matches_l1_max",
    "external_l1_exact",
    "gold_recovered",
    "diversity_increased",
    "score",
    "source_paths",
    "problem_text",
    "notes",
]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(_stringify(value) or default))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        text = _stringify(value)
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def _is_truthy(value: Any) -> bool:
    text = _stringify(value).lower()
    if not text:
        return False
    if text in TRUE_TOKENS:
        return True
    if text in FALSE_TOKENS or text in {"0.0", "0.00", "none", "nan"}:
        return False
    return bool(text)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _group_rows_by_case(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv_rows(path):
        case_id = _stringify(row.get("case_id") or row.get("example_id"))
        if case_id:
            grouped[case_id].append(row)
    return grouped


def _load_case_map(path: Path) -> dict[str, dict[str, str]]:
    return {case_id: rows[0] for case_id, rows in _group_rows_by_case(path).items()}


def _load_jsonl_case_ids(path: Path) -> set[str]:
    case_ids: set[str] = set()
    if not path.is_file():
        return case_ids
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            case_id = _stringify(payload.get("example_id") or payload.get("case_id"))
            if case_id:
                case_ids.add(case_id)
    return case_ids


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in keywords)


def _normalize_numeric_text(value: Any) -> str:
    text = _stringify(value).replace(",", "")
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


def _domain_tag(question_type: str, question_text: str) -> str:
    normalized = _stringify(question_type).lower()
    if normalized in DOMAIN_TAG_BY_QUESTION_TYPE:
        return DOMAIN_TAG_BY_QUESTION_TYPE[normalized]
    q = question_text.lower()
    if _contains_any(q, QUESTION_KEYWORDS["money"]):
        return "domain_money_cost_revenue"
    if _contains_any(q, QUESTION_KEYWORDS["percentage"]) or _contains_any(q, QUESTION_KEYWORDS["ratio"]):
        return "domain_ratio_percentage"
    if _contains_any(q, QUESTION_KEYWORDS["temporal"]):
        return "domain_temporal_calendar"
    if _contains_any(q, QUESTION_KEYWORDS["rate_unit"]):
        return "domain_rate_speed_work"
    if _contains_any(q, QUESTION_KEYWORDS["remaining"]):
        return "domain_multi_step_arithmetic"
    return "domain_unknown"


def _select_failure_row(rows: list[dict[str, str]], method: str) -> dict[str, str]:
    if not rows:
        return {}
    exact = [row for row in rows if _stringify(row.get("method_id")) == method]
    if exact:
        return exact[0]
    full = [row for row in rows if _stringify(row.get("evidence_completeness")).upper() == "FULL"]
    if full:
        return full[0]
    return rows[0]


def _resolve_taxonomy_summary(
    *,
    method: str,
    failure_csv: Path,
    gold_absent_csv: Path,
    anchor_effect_csv: Path,
    coverage_details_csv: Path,
    outputs_root: Path,
) -> tuple[dict[str, Any], Path]:
    if not coverage_details_csv.is_file():
        found = taxonomy_builder._latest_case_coverage_csv(outputs_root)  # type: ignore[attr-defined]
        if found is not None:
            coverage_details_csv = found
    if not coverage_details_csv.is_file():
        raise FileNotFoundError(
            f"Missing coverage-details CSV: supply --coverage-details-csv or generate case_coverage_details.csv under {outputs_root}"
        )
    summary = taxonomy_builder._summarize(
        method=method,
        failure_csv=failure_csv,
        gold_absent_csv=gold_absent_csv,
        coverage_details_csv=coverage_details_csv,
        anchor_effect_csv=anchor_effect_csv,
        outputs_root=outputs_root,
    )
    return summary, coverage_details_csv


def _mechanism_tags(row: dict[str, Any], question_text: str) -> list[str]:
    error_type = _stringify(row.get("error_type")).lower()
    failure_family = _stringify(row.get("failure_family")).lower()
    notes = _stringify(row.get("notes")).lower()
    text = f" {question_text.lower()} {error_type} {failure_family} {notes} "
    tags: list[str] = []
    if "premature intermediate answer" in error_type:
        tags.append("premature_intermediate_answer")
    if _contains_any(text, QUESTION_KEYWORDS["base_quantity"]):
        tags.append("wrong_base_quantity")
    if _contains_any(text, QUESTION_KEYWORDS["rate_unit"]) or "unit" in error_type:
        tags.append("wrong_unit_or_rate")
    if _contains_any(text, QUESTION_KEYWORDS["remaining"]):
        tags.append("missed_subtraction_or_remaining")
    if "counting/grouping off-by-factor" in error_type or _contains_any(text, QUESTION_KEYWORDS["factor"]):
        tags.append("off_by_factor_or_counting_grouping")
    if _contains_any(text, QUESTION_KEYWORDS["ratio"]):
        tags.append("ratio_base_confusion")
    if _contains_any(text, QUESTION_KEYWORDS["percentage"]):
        tags.append("percentage_base_confusion")
    if _contains_any(text, QUESTION_KEYWORDS["temporal"]):
        tags.append("temporal_counting_confusion")
    if _contains_any(text, QUESTION_KEYWORDS["multi_step"]):
        tags.append("multi_step_dependency_missed")
    if "structured extraction failure" in error_type or "parse" in failure_family or "format" in failure_family:
        tags.append("answer_extraction_or_parse_issue")
    if not tags:
        tags.append("unknown_mechanism")
    return sorted(dict.fromkeys(tags))


def _pattern_tags(row: dict[str, Any], domain: str, mechanisms: list[str]) -> list[str]:
    num_groups = _safe_int(row.get("num_candidate_groups"), 0)
    diversity_bucket = _stringify(row.get("diversity_bucket")).lower()
    external_contrast = _stringify(row.get("external_contrast")).lower()
    predicted = _normalize_numeric_text(row.get("predicted_answer"))
    selected = _normalize_numeric_text(row.get("selected_answer"))
    direct_l1 = _is_truthy(row.get("direct_l1_anchor_potential"))
    patch_match = _is_truthy(row.get("anchor_matches_l1_max"))
    gold_recovered = _is_truthy(row.get("gold_recovered"))

    tags = ["gold_absent", domain]
    if _is_truthy(row.get("frontier_collapse_low_diversity")) or num_groups <= 1 or diversity_bucket.startswith("low"):
        tags.append("frontier_collapse_low_diversity")
    if num_groups <= 1:
        tags.append("single_answer_group_collapse")
    if num_groups <= 2:
        tags.append("low_candidate_answer_group_count")
    if _is_truthy(row.get("wrong_supported_consensus")) or external_contrast == "both wrong":
        tags.append("wrong_supported_consensus")
    if external_contrast == "both wrong" and predicted and selected and predicted == selected:
        tags.append("cross_anchor_same_wrong_answer")
    if not gold_recovered:
        tags.append("direct_seed_wrong_or_missing")
    if direct_l1:
        tags.append("direct_l1_anchor_potential")
        tags.append("needs_stronger_direct_seed")
    if patch_match:
        tags.append("direct_l1_patch_effect_match")
    tags.extend(mechanisms)
    return sorted(dict.fromkeys(tags))


def _case_score(row: dict[str, Any], tags: set[str], exact30: set[str], exact50: set[str]) -> float:
    score = 0.0
    if "direct_l1_anchor_potential" in tags:
        score += 50.0
    if "direct_l1_patch_effect_match" in tags:
        score += 15.0
    if "wrong_supported_consensus" in tags:
        score += 25.0
    if "frontier_collapse_low_diversity" in tags:
        score += 15.0
    if "single_answer_group_collapse" in tags:
        score += 8.0
    if "unknown_mechanism" not in tags:
        score += 5.0
    case_id = _stringify(row.get("case_id"))
    if case_id in exact50:
        score += 6.0
    if case_id in exact30:
        score += 4.0
    return score


def _build_case_rows(
    *,
    taxonomy_rows: list[dict[str, Any]],
    failure_by_case: dict[str, list[dict[str, str]]],
    method: str,
    exact30: set[str],
    exact50: set[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in taxonomy_rows:
        case_id = _stringify(row.get("case_id"))
        if not case_id or case_id in seen:
            continue
        seen.add(case_id)
        failure_row = _select_failure_row(failure_by_case.get(case_id, []), method)
        problem_text = _stringify(failure_row.get("problem_text"))
        domain = _domain_tag(_stringify(row.get("question_type")), problem_text)
        mechanisms = _mechanism_tags(row, problem_text)
        patterns = _pattern_tags(row, domain, mechanisms)
        pattern_set = set(patterns)
        actionable = [
            tag
            for tag in (
                "needs_stronger_direct_seed",
                "wrong_supported_consensus",
                "domain_money_cost_revenue",
                "domain_ratio_percentage",
                "premature_intermediate_answer",
                "answer_extraction_or_parse_issue",
            )
            if tag in pattern_set
        ]
        score = _case_score({"case_id": case_id}, pattern_set, exact30, exact50)
        out.append(
            {
                "case_id": case_id,
                "method": method,
                "question_type": _stringify(row.get("question_type")),
                "domain_tag": domain,
                "mechanism_tags": "|".join(mechanisms),
                "pattern_tags": "|".join(patterns),
                "actionable_tags": "|".join(actionable),
                "failure_family": _stringify(row.get("failure_family")),
                "error_type": _stringify(row.get("error_type")),
                "num_candidate_groups": _safe_int(row.get("num_candidate_groups"), 0),
                "diversity_bucket": _stringify(row.get("diversity_bucket")),
                "external_contrast": _stringify(row.get("external_contrast")),
                "gold_answer": _stringify(row.get("gold_answer")),
                "predicted_answer": _stringify(row.get("predicted_answer")),
                "selected_answer": _stringify(row.get("selected_answer")),
                "anchor_matches_l1_max": int(_is_truthy(row.get("anchor_matches_l1_max"))),
                "external_l1_exact": int(_is_truthy(row.get("external_l1_exact"))),
                "gold_recovered": int(_is_truthy(row.get("gold_recovered"))),
                "diversity_increased": int(_is_truthy(row.get("diversity_increased"))),
                "score": f"{score:.1f}",
                "source_paths": _stringify(row.get("source_paths")),
                "problem_text": problem_text,
                "notes": _stringify(row.get("notes")),
            }
        )
    return sorted(out, key=lambda r: (-_safe_float(r.get("score")), _stringify(r.get("case_id"))))


def _tag_list(row: dict[str, Any], field: str) -> list[str]:
    return [x for x in _stringify(row.get(field)).split("|") if x]


def _count_tags(rows: list[dict[str, Any]], field: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(_tag_list(row, field))
    return counts


def _count_intersections(rows: list[dict[str, Any]]) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        domain = _stringify(row.get("domain_tag")) or "domain_unknown"
        for mechanism in _tag_list(row, "mechanism_tags"):
            counts[(domain, mechanism)] += 1
    return counts


def _rows_for_tags(rows: list[dict[str, Any]], required: set[str], *, limit: int) -> list[dict[str, Any]]:
    selected = []
    for row in rows:
        tags = set(_tag_list(row, "pattern_tags")) | set(_tag_list(row, "mechanism_tags")) | {_stringify(row.get("domain_tag"))}
        if required.issubset(tags):
            selected.append(row)
    return sorted(selected, key=lambda r: (-_safe_float(r.get("score")), _stringify(r.get("case_id"))))[:limit]


def _slice_reason(row: dict[str, Any], slice_id: str) -> str:
    if slice_id.startswith("direct_l1"):
        return "direct_l1_anchor_potential with strongest available artifact score"
    if slice_id.startswith("wrong_supported"):
        return "wrong-supported consensus / both-direct-and-frontier-wrong evidence"
    if slice_id.startswith("money"):
        return "money/cost/revenue domain failure"
    if slice_id.startswith("ratio"):
        return "ratio/percentage domain or mechanism failure"
    return "ranked heuristic slice"


def _build_diagnostic_slices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = [
        ("direct_l1_strong_seed_15case", {"direct_l1_anchor_potential"}, 15),
        ("direct_l1_strong_seed_30case", {"direct_l1_anchor_potential"}, 30),
        ("wrong_supported_consensus_15case", {"wrong_supported_consensus"}, 15),
        ("money_cost_revenue_15case", {"domain_money_cost_revenue"}, 15),
        ("ratio_percentage_15case", {"domain_ratio_percentage"}, 15),
    ]
    slice_rows: list[dict[str, Any]] = []
    for slice_id, required, limit in specs:
        selected = _rows_for_tags(rows, required, limit=limit)
        for rank, row in enumerate(selected, start=1):
            slice_rows.append(
                {
                    "slice_id": slice_id,
                    "rank": rank,
                    "case_id": row["case_id"],
                    "reason": _slice_reason(row, slice_id),
                    "domain_tag": row["domain_tag"],
                    "mechanism_tags": row["mechanism_tags"],
                    "pattern_tags": row["pattern_tags"],
                    "score": row["score"],
                }
            )
    return slice_rows


def _candidate_fix_rows(rows: list[dict[str, Any]], exact50: set[str]) -> list[dict[str, Any]]:
    def count_matching(tags: set[str]) -> tuple[int, int]:
        matched = []
        for row in rows:
            row_tags = set(_tag_list(row, "pattern_tags")) | set(_tag_list(row, "mechanism_tags")) | {_stringify(row.get("domain_tag"))}
            if row_tags.intersection(tags):
                matched.append(row)
        return len(matched), sum(1 for row in matched if row["case_id"] in exact50)

    specs = [
        (
            "stronger_direct_l1_seed_with_independent_arithmetic_unit_self_check",
            {"needs_stronger_direct_seed", "direct_l1_anchor_potential"},
            5,
            2,
            5,
        ),
        (
            "duplicate_wrong_consensus_penalty",
            {"wrong_supported_consensus", "cross_anchor_same_wrong_answer"},
            3,
            3,
            3,
        ),
        (
            "domain_specific_money_unit_ledger_strengthening",
            {"domain_money_cost_revenue", "wrong_unit_or_rate", "missed_subtraction_or_remaining"},
            4,
            3,
            3,
        ),
        (
            "ratio_percentage_base_normalization_anchor",
            {"domain_ratio_percentage", "ratio_base_confusion", "percentage_base_confusion"},
            4,
            3,
            3,
        ),
        (
            "branch_progress_scoring_for_premature_intermediate_answers",
            {"premature_intermediate_answer", "multi_step_dependency_missed"},
            3,
            2,
            2,
        ),
        (
            "richer_tree_logging_before_algorithm_changes",
            {"unknown_mechanism"},
            2,
            1,
            2,
        ),
    ]
    total = max(1, len(rows))
    fix_rows: list[dict[str, Any]] = []
    for fix_id, tags, actionability, risk, confidence in specs:
        coverage, exact_overlap = count_matching(tags)
        score = (coverage / total) * 25.0 + actionability * 15.0 + exact_overlap * 1.5 + confidence * 15.0 - risk * 12.0
        fix_rows.append(
            {
                "candidate_fix": fix_id,
                "coverage_count": coverage,
                "coverage_share": round(coverage / total, 6),
                "actionability_score": actionability,
                "expected_regression_risk": risk,
                "exact_replay_overlap": exact_overlap,
                "metadata_confidence": confidence,
                "heuristic_score": round(score, 3),
            }
        )
    return sorted(fix_rows, key=lambda row: (-_safe_float(row["heuristic_score"]), row["candidate_fix"]))


def _examples_by_pattern(rows: list[dict[str, Any]], limit_per_pattern: int = 5) -> list[dict[str, Any]]:
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for tag in _tag_list(row, "pattern_tags"):
            if len(examples[tag]) < limit_per_pattern:
                examples[tag].append(row)
    out: list[dict[str, Any]] = []
    for tag in sorted(examples, key=lambda t: (-len([r for r in rows if t in _tag_list(r, "pattern_tags")]), t)):
        for rank, row in enumerate(examples[tag], start=1):
            out.append(
                {
                    "pattern_tag": tag,
                    "example_rank": rank,
                    "case_id": row["case_id"],
                    "domain_tag": row["domain_tag"],
                    "mechanism_tags": row["mechanism_tags"],
                    "score": row["score"],
                }
            )
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _render_table(rows: list[dict[str, Any]], headers: list[str]) -> str:
    if not rows:
        return "_No rows._"
    widths = {header: len(header) for header in headers}
    for row in rows:
        for header in headers:
            widths[header] = max(widths[header], len(_stringify(row.get(header, ""))))
    header_line = " | ".join(header.ljust(widths[header]) for header in headers)
    divider = " | ".join("-" * widths[header] for header in headers)
    body = "\n".join(
        " | ".join(_stringify(row.get(header, "")).ljust(widths[header]) for header in headers) for row in rows
    )
    return f"{header_line}\n{divider}\n{body}"


def _counter_rows(counter: Counter[str], name: str, total: int) -> list[dict[str, Any]]:
    return [
        {
            name: key,
            "count": value,
            "share": round(value / max(1, total), 6),
        }
        for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _intersection_rows(counter: Counter[tuple[str, str]], total: int) -> list[dict[str, Any]]:
    return [
        {
            "domain_tag": domain,
            "mechanism_tag": mechanism,
            "count": count,
            "share": round(count / max(1, total), 6),
        }
        for (domain, mechanism), count in sorted(counter.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    ]


def _render_report(summary: dict[str, Any]) -> str:
    top_pattern_rows = summary["pattern_rows"][:10]
    mechanism_rows = summary["mechanism_rows"][:10]
    intersection_rows = summary["domain_mechanism_rows"][:12]
    fix_rows = summary["candidate_fix_rows"]
    direct_rows = [row for row in summary["slice_rows"] if row["slice_id"] == "direct_l1_strong_seed_15case"]
    direct30 = [row for row in summary["slice_rows"] if row["slice_id"] == "direct_l1_strong_seed_30case"]
    lines = [
        "# PAL 157 Failure Pattern Mining",
        "",
        "## Observed Facts From Artifacts",
        "",
        f"- Unresolved PAL cases analyzed: `{summary['unresolved_cases_count']}`",
        f"- Unique case IDs analyzed: `{summary['unique_case_ids']}`",
        f"- Failure corpus rows: `{summary['failure_corpus_rows']}`",
        f"- Gold-absent rows: `{summary['gold_absent_rows']}`",
        f"- Coverage details source: `{summary['coverage_details_csv']}`",
        f"- Direct-L1-anchor-potential cases: `{summary['direct_l1_anchor_potential_count']}`",
        f"- Direct-L1 patch-effect matches: `{summary['direct_l1_patch_effect_match_count']}`",
        f"- Wrong-supported-consensus cases: `{summary['wrong_supported_consensus_count']}`",
        "",
        "## Heuristic Pattern Labels",
        "",
        "The labels below are transparent heuristics over existing CSV columns, question text, and artifact metadata. They are not causal proof.",
        "",
        _render_table(top_pattern_rows, ["pattern_tag", "count", "share"]),
        "",
        "## Inferred Likely Failure Mechanisms",
        "",
        _render_table(mechanism_rows, ["mechanism_tag", "count", "share"]),
        "",
        "## Top Domain / Mechanism Intersections",
        "",
        _render_table(intersection_rows, ["domain_tag", "mechanism_tag", "count", "share"]),
        "",
        "## Direct-L1-Anchor-Potential Subpatterns",
        "",
        _render_table(summary["direct_l1_subpattern_rows"][:10], ["pattern_tag", "count", "share"]),
        "",
        "## Wrong-Supported-Consensus Subpatterns",
        "",
        _render_table(summary["wrong_consensus_subpattern_rows"][:10], ["pattern_tag", "count", "share"]),
        "",
        "## Proposed Targeted Fixes",
        "",
        _render_table(
            fix_rows,
            [
                "candidate_fix",
                "coverage_count",
                "actionability_score",
                "expected_regression_risk",
                "exact_replay_overlap",
                "metadata_confidence",
                "heuristic_score",
            ],
        ),
        "",
        "## Recommendation",
        "",
        f"- Best scored candidate fix: `{summary['best_scored_candidate_fix']}`",
        f"- Stronger Direct L1 seed still recommended: `{summary['stronger_direct_l1_seed_still_recommended']}`",
        f"- Largest actionable pattern: `{summary['largest_actionable_pattern']}`",
        "",
        "## Diagnostic Slices",
        "",
        f"- Direct-L1 strong seed 15-case: `{', '.join(row['case_id'] for row in direct_rows)}`",
        f"- Direct-L1 strong seed 30-case: `{', '.join(row['case_id'] for row in direct30)}`",
        "",
        "## Missing Metadata",
        "",
        "- Stable parent/child tree paths for every candidate branch.",
        "- Per-anchor answer groups and prompt provenance for all direct/diverse seeds.",
        "- Explicit final-target mismatch labels beyond the sparse subpattern tags.",
        "- Gold-free branch-progress and unit/quantity-state features.",
        "",
        "## Claim Boundaries",
        "",
        "- This is existing-artifact analysis only.",
        "- No live controller was run.",
        "- No runtime behavior change was made.",
        "- No paid/model API calls were made.",
        "- No external-baseline claim is made.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _compact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    omitted = {"case_rows", "pattern_rows", "mechanism_rows", "domain_mechanism_rows", "slice_rows", "case_examples_rows"}
    return {key: value for key, value in summary.items() if key not in omitted}


def _build_summary(
    *,
    method: str,
    failure_csv: Path,
    gold_absent_csv: Path,
    anchor_effect_csv: Path,
    coverage_details_csv: Path,
    outputs_root: Path,
    exact_replay_30_jsonl: Path,
    exact_replay_50_jsonl: Path,
) -> dict[str, Any]:
    taxonomy_summary, resolved_coverage_csv = _resolve_taxonomy_summary(
        method=method,
        failure_csv=failure_csv,
        gold_absent_csv=gold_absent_csv,
        anchor_effect_csv=anchor_effect_csv,
        coverage_details_csv=coverage_details_csv,
        outputs_root=outputs_root,
    )
    failure_by_case = _group_rows_by_case(failure_csv)
    exact30 = _load_jsonl_case_ids(exact_replay_30_jsonl)
    exact50 = _load_jsonl_case_ids(exact_replay_50_jsonl)
    case_rows = _build_case_rows(
        taxonomy_rows=list(taxonomy_summary["case_rows"]),
        failure_by_case=failure_by_case,
        method=method,
        exact30=exact30,
        exact50=exact50,
    )

    pattern_counts = _count_tags(case_rows, "pattern_tags")
    mechanism_counts = _count_tags(case_rows, "mechanism_tags")
    domain_mechanism_counts = _count_intersections(case_rows)
    pattern_rows = _counter_rows(pattern_counts, "pattern_tag", len(case_rows))
    mechanism_rows = _counter_rows(mechanism_counts, "mechanism_tag", len(case_rows))
    domain_mechanism_rows = _intersection_rows(domain_mechanism_counts, len(case_rows))
    slice_rows = _build_diagnostic_slices(case_rows)
    candidate_fix_rows = _candidate_fix_rows(case_rows, exact50)
    case_examples_rows = _examples_by_pattern(case_rows)

    direct_subset = _rows_for_tags(case_rows, {"direct_l1_anchor_potential"}, limit=len(case_rows))
    wrong_subset = _rows_for_tags(case_rows, {"wrong_supported_consensus"}, limit=len(case_rows))
    direct_counts = _count_tags(direct_subset, "pattern_tags")
    wrong_counts = _count_tags(wrong_subset, "pattern_tags")
    direct_subpattern_rows = _counter_rows(direct_counts, "pattern_tag", max(1, len(direct_subset)))
    wrong_subpattern_rows = _counter_rows(wrong_counts, "pattern_tag", max(1, len(wrong_subset)))
    best_fix = candidate_fix_rows[0]["candidate_fix"] if candidate_fix_rows else ""
    generic_patterns = {
        "gold_absent",
        "direct_seed_wrong_or_missing",
        "low_candidate_answer_group_count",
        "frontier_collapse_low_diversity",
        "single_answer_group_collapse",
        "unknown_mechanism",
    }
    largest_actionable = next((row["pattern_tag"] for row in pattern_rows if row["pattern_tag"] not in generic_patterns), "")

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "failure_csv": str(failure_csv),
        "gold_absent_csv": str(gold_absent_csv),
        "anchor_effect_csv": str(anchor_effect_csv),
        "coverage_details_csv": str(resolved_coverage_csv),
        "failure_corpus_rows": len(_read_csv_rows(failure_csv)),
        "gold_absent_rows": len(_read_csv_rows(gold_absent_csv)),
        "unresolved_cases_count": len(case_rows),
        "unique_case_ids": len({row["case_id"] for row in case_rows}),
        "direct_l1_anchor_potential_count": pattern_counts.get("direct_l1_anchor_potential", 0),
        "direct_l1_patch_effect_match_count": pattern_counts.get("direct_l1_patch_effect_match", 0),
        "wrong_supported_consensus_count": pattern_counts.get("wrong_supported_consensus", 0),
        "top_pattern_counts": pattern_rows[:10],
        "top_mechanism_counts": mechanism_rows[:10],
        "top_domain_mechanism_intersections": domain_mechanism_rows[:12],
        "best_scored_candidate_fix": best_fix,
        "stronger_direct_l1_seed_still_recommended": bool(
            best_fix == "stronger_direct_l1_seed_with_independent_arithmetic_unit_self_check"
        ),
        "largest_actionable_pattern": largest_actionable,
        "direct_l1_strong_seed_15case_ids": [
            row["case_id"] for row in slice_rows if row["slice_id"] == "direct_l1_strong_seed_15case"
        ],
        "direct_l1_strong_seed_30case_ids": [
            row["case_id"] for row in slice_rows if row["slice_id"] == "direct_l1_strong_seed_30case"
        ],
        "wrong_supported_consensus_15case_ids": [
            row["case_id"] for row in slice_rows if row["slice_id"] == "wrong_supported_consensus_15case"
        ],
        "money_cost_revenue_15case_ids": [
            row["case_id"] for row in slice_rows if row["slice_id"] == "money_cost_revenue_15case"
        ],
        "ratio_percentage_15case_ids": [
            row["case_id"] for row in slice_rows if row["slice_id"] == "ratio_percentage_15case"
        ],
        "candidate_fix_rows": candidate_fix_rows,
        "direct_l1_subpattern_rows": direct_subpattern_rows,
        "wrong_consensus_subpattern_rows": wrong_subpattern_rows,
        "case_rows": case_rows,
        "pattern_rows": pattern_rows,
        "mechanism_rows": mechanism_rows,
        "domain_mechanism_rows": domain_mechanism_rows,
        "slice_rows": slice_rows,
        "case_examples_rows": case_examples_rows,
    }
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-details-csv", default="", help="Coverage details CSV from recovery audit.")
    parser.add_argument("--failure-csv", default=str(DEFAULT_FAILURE_CSV), help="Fully tracked latest-method failure CSV.")
    parser.add_argument("--gold-absent-csv", default=str(DEFAULT_GOLD_ABSENT_CSV), help="Gold-absent subpattern CSV.")
    parser.add_argument("--anchor-effect-csv", default=str(DEFAULT_ANCHOR_EFFECT_CSV), help="Direct L1 anchor patch-effect CSV.")
    parser.add_argument("--method", default=DEFAULT_METHOD, help="Exact PAL/current method ID to mine.")
    parser.add_argument("--outputs-root", default=str(DEFAULT_OUTPUTS_ROOT), help="Root for fallback coverage-details discovery.")
    parser.add_argument("--exact-replay-30-jsonl", default=str(DEFAULT_EXACT_REPLAY_30_JSONL), help="Exact 30-case replay JSONL.")
    parser.add_argument("--exact-replay-50-jsonl", default=str(DEFAULT_EXACT_REPLAY_50_JSONL), help="Exact 50-case replay JSONL.")
    parser.add_argument("--output-dir", default="", help="Output directory. Defaults to outputs/pal_157_failure_patterns_<timestamp>.")
    parser.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--dry-run", "--validate-only", action="store_true", dest="dry_run")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    failure_csv = Path(args.failure_csv).expanduser()
    gold_absent_csv = Path(args.gold_absent_csv).expanduser()
    anchor_effect_csv = Path(args.anchor_effect_csv).expanduser()
    coverage_details_csv = Path(args.coverage_details_csv).expanduser() if args.coverage_details_csv else Path()
    outputs_root = Path(args.outputs_root).expanduser()
    exact30 = Path(args.exact_replay_30_jsonl).expanduser()
    exact50 = Path(args.exact_replay_50_jsonl).expanduser()

    if not failure_csv.is_file():
        raise FileNotFoundError(f"Missing failure corpus CSV: {failure_csv}")
    if not gold_absent_csv.is_file():
        raise FileNotFoundError(f"Missing gold-absent CSV: {gold_absent_csv}")
    if not anchor_effect_csv.is_file():
        raise FileNotFoundError(f"Missing anchor-effect CSV: {anchor_effect_csv}")

    output_dir = Path(args.output_dir).expanduser() if args.output_dir else REPO_ROOT / "outputs" / f"{DEFAULT_OUTPUT_PREFIX}{args.timestamp}"
    summary = _build_summary(
        method=str(args.method),
        failure_csv=failure_csv,
        gold_absent_csv=gold_absent_csv,
        anchor_effect_csv=anchor_effect_csv,
        coverage_details_csv=coverage_details_csv,
        outputs_root=outputs_root,
        exact_replay_30_jsonl=exact30,
        exact_replay_50_jsonl=exact50,
    )
    compact = _compact_summary(summary)

    if args.dry_run:
        print(json.dumps(compact, indent=2, sort_keys=True))
        return compact

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "pal_157_unresolved_cases.csv", summary["case_rows"], CASE_FIELDNAMES)
    _write_csv(output_dir / "pattern_counts.csv", summary["pattern_rows"], ["pattern_tag", "count", "share"])
    _write_csv(output_dir / "pattern_by_domain_counts.csv", summary["domain_mechanism_rows"], ["domain_tag", "mechanism_tag", "count", "share"])
    _write_csv(output_dir / "mechanism_counts.csv", summary["mechanism_rows"], ["mechanism_tag", "count", "share"])
    _write_csv(output_dir / "actionable_slices.csv", summary["candidate_fix_rows"])
    _write_csv(output_dir / "recommended_diagnostic_slices.csv", summary["slice_rows"])
    _write_csv(output_dir / "case_examples_by_pattern.csv", summary["case_examples_rows"])
    (output_dir / "summary.json").write_text(json.dumps(compact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "pal_157_failure_pattern_report.md").write_text(_render_report(summary), encoding="utf-8")
    return compact


def main() -> int:
    try:
        run()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
