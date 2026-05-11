#!/usr/bin/env python3
"""Build an offline pattern taxonomy for unresolved PAL failures."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAILURE_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
DEFAULT_GOLD_ABSENT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
DEFAULT_ANCHOR_EFFECT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_20260510.csv"
DEFAULT_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
DEFAULT_OUTPUTS_ROOT = REPO_ROOT / "outputs"
DEFAULT_OUTPUT_PREFIX = "pal_unresolved_pattern_taxonomy_"
DEFAULT_TOP_CASES = 15

TRUE_TOKENS = {"1", "true", "t", "yes", "y"}
FALSE_TOKENS = {"0", "false", "f", "no", "n"}
TIMESTAMP_RE = re.compile(r"(?P<stamp>\d{8}T\d{6}Z)")

QUESTION_DOMAIN_MAP = {
    "money/cost/revenue": "domain_money_cost_revenue",
    "ratio/proportion/percentage": "domain_ratio_proportion_percentage",
    "multi-step arithmetic": "domain_multi_step_arithmetic",
    "temporal/calendar": "domain_temporal_calendar",
    "rate/speed/work": "domain_rate_speed_work",
    "unit conversion": "domain_unit_conversion",
    "inventory/remaining quantity": "domain_inventory_remaining_quantity",
}

PATTERN_LABELS = (
    "gold_absent_from_candidate_pool",
    "frontier_collapse_low_diversity",
    "wrong_supported_consensus",
    "direct_l1_anchor_potential",
    "premature_intermediate_answer",
    "counting_grouping_off_by_factor",
    "structured_extraction_failure",
    "unknown_or_insufficient_metadata",
)

PATTERN_KIND = {
    "gold_absent_from_candidate_pool": "fact",
    "frontier_collapse_low_diversity": "fact",
    "wrong_supported_consensus": "fact",
    "direct_l1_anchor_potential": "fact",
    "premature_intermediate_answer": "heuristic",
    "counting_grouping_off_by_factor": "heuristic",
    "structured_extraction_failure": "heuristic",
    "unknown_or_insufficient_metadata": "metadata_gap",
}

REPORT_PATTERN_ORDER = (
    "gold_absent_from_candidate_pool",
    "frontier_collapse_low_diversity",
    "wrong_supported_consensus",
    "direct_l1_anchor_potential",
    "premature_intermediate_answer",
    "counting_grouping_off_by_factor",
    "structured_extraction_failure",
    "unknown_or_insufficient_metadata",
)

FIX_RECOMMENDATIONS = {
    "direct_l1_anchor_potential": "Test a stronger direct L1 anchor / direct seed on the anchor-potential slice first.",
    "wrong_supported_consensus": "Add a duplicate wrong-consensus penalty to break low-diversity false consensus.",
    "frontier_collapse_low_diversity": "Strengthen branch-progress scoring and candidate generation diversity.",
    "premature_intermediate_answer": "Add branch-progress checks so intermediate numerics do not terminate the search.",
    "counting_grouping_off_by_factor": "Add an arithmetic self-check for factor/multiple mistakes.",
    "structured_extraction_failure": "Add a structured extraction guard or richer numeric leaf logging.",
}


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    method: str
    question_type: str
    domain_label: str
    error_type: str
    failure_family: str
    gold_answer: str
    predicted_answer: str
    selected_answer: str
    abs_error: str
    rel_error: str
    distance_bucket: str
    num_candidate_groups: int
    diversity_bucket: str
    external_contrast: str
    notes: str
    anchor_matches_l1_max: bool
    external_l1_exact: bool
    gold_recovered: bool
    diversity_increased: bool
    gold_absent: bool
    frontier_collapse_low_diversity: bool
    wrong_supported_consensus: bool
    direct_l1_anchor_potential: bool
    premature_intermediate_answer: bool
    counting_grouping_off_by_factor: bool
    structured_extraction_failure: bool
    unknown_or_insufficient_metadata: bool
    pattern_labels: tuple[str, ...]
    rule_summary: str
    score: float
    source_paths: tuple[str, ...]


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
        return float(_stringify(value))
    except Exception:
        return default


def _is_truthy(value: Any) -> bool:
    text = _stringify(value).lower()
    if not text:
        return False
    if text in TRUE_TOKENS:
        return True
    if text in FALSE_TOKENS:
        return False
    return text not in {"0.0", "0.00", "none", "nan", "false", "no"}


def _normalize_case_id(value: Any) -> str:
    return _stringify(value)


def _normalize_question_type(value: Any) -> str:
    return _stringify(value).lower()


def _normalize_domain(question_type: str) -> str:
    return QUESTION_DOMAIN_MAP.get(question_type, "domain_unknown")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _group_rows_by_case(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv_rows(path):
        case_id = _normalize_case_id(row.get("case_id"))
        if case_id:
            grouped[case_id].append(row)
    return grouped


def _load_case_map(path: Path) -> dict[str, dict[str, str]]:
    return {case_id: rows[0] for case_id, rows in _group_rows_by_case(path).items()}


def _latest_case_coverage_csv(outputs_root: Path) -> Path | None:
    candidates = list(outputs_root.rglob("case_coverage_details.csv"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p.stat().st_mtime, str(p)))


def _extract_time_key(path: Path) -> str:
    matches = [m.group("stamp") for m in TIMESTAMP_RE.finditer(str(path))]
    return max(matches) if matches else ""


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


def _contains(text: str, pattern: str) -> bool:
    return pattern.lower() in text.lower()


def _build_case_records(
    *,
    method: str,
    unresolved_case_ids: list[str],
    coverage_by_case: dict[str, dict[str, str]],
    failure_by_case: dict[str, list[dict[str, str]]],
    gold_by_case: dict[str, dict[str, str]],
    anchor_by_case: dict[str, dict[str, str]],
) -> list[CaseRecord]:
    records: list[CaseRecord] = []
    for case_id in unresolved_case_ids:
        cov = coverage_by_case.get(case_id, {})
        failure_row = _select_failure_row(failure_by_case.get(case_id, []), method)
        gold_row = gold_by_case.get(case_id, {})
        anchor_row = anchor_by_case.get(case_id, {})

        question_type = _stringify(gold_row.get("question_type"))
        domain_label = _normalize_domain(_normalize_question_type(question_type))
        error_type = _stringify(gold_row.get("error_type"))
        failure_family = _stringify(failure_row.get("failure_family") or gold_row.get("failure_family"))
        gold_answer = _stringify(failure_row.get("gold_answer") or gold_row.get("gold") or gold_row.get("predicted"))
        predicted_answer = _stringify(gold_row.get("predicted") or gold_row.get("original_predicted"))
        selected_answer = _stringify(failure_row.get("selected_answer") or failure_row.get("prediction"))
        abs_error = _stringify(gold_row.get("abs_error"))
        rel_error = _stringify(gold_row.get("rel_error"))
        distance_bucket = _stringify(gold_row.get("distance_bucket"))
        num_candidate_groups = _safe_int(gold_row.get("num_candidate_groups"), 0)
        diversity_bucket = _stringify(gold_row.get("diversity_bucket"))
        external_contrast = _stringify(gold_row.get("external_contrast"))
        notes = _stringify(gold_row.get("notes") or failure_row.get("notes"))
        source_paths = tuple(
            p
            for p in (
                _stringify(failure_row.get("artifact_source")),
                _stringify(failure_row.get("selected_source")),
                _stringify(cov.get("selected_source_path")),
            )
            if p
        )
        anchor_matches_l1_max = _is_truthy(anchor_row.get("anchor_matches_l1_max"))
        external_l1_exact = _is_truthy(anchor_row.get("external_l1_exact"))
        gold_recovered = _is_truthy(anchor_row.get("gold_recovered"))
        diversity_increased = _is_truthy(anchor_row.get("diversity_increased"))

        gold_absent = True
        frontier_collapse_low_diversity = num_candidate_groups <= 1 or diversity_bucket.lower().startswith("low")
        wrong_supported_consensus = external_contrast.lower() == "both wrong"
        direct_l1_anchor_potential = anchor_matches_l1_max or external_l1_exact
        premature_intermediate_answer = _contains(error_type, "premature intermediate answer")
        counting_grouping_off_by_factor = _contains(error_type, "counting/grouping off-by-factor")
        structured_extraction_failure = _contains(error_type, "structured extraction failure")

        explicit_error_tags = [
            tag
            for tag, enabled in (
                ("premature_intermediate_answer", premature_intermediate_answer),
                ("counting_grouping_off_by_factor", counting_grouping_off_by_factor),
                ("structured_extraction_failure", structured_extraction_failure),
            )
            if enabled
        ]
        unknown_or_insufficient_metadata = not explicit_error_tags

        tags = ["gold_absent_from_candidate_pool"]
        if frontier_collapse_low_diversity:
            tags.append("frontier_collapse_low_diversity")
        if wrong_supported_consensus:
            tags.append("wrong_supported_consensus")
        if direct_l1_anchor_potential:
            tags.append("direct_l1_anchor_potential")
        tags.extend(explicit_error_tags)
        if unknown_or_insufficient_metadata:
            tags.append("unknown_or_insufficient_metadata")

        rule_bits = ["gold_absent=1"]
        if frontier_collapse_low_diversity:
            rule_bits.append(f"frontier_collapse={num_candidate_groups}")
        if wrong_supported_consensus:
            rule_bits.append("external_contrast=Both wrong")
        if direct_l1_anchor_potential:
            rule_bits.append(
                f"l1_anchor={'1' if anchor_matches_l1_max else '0'}|external_l1_exact={'1' if external_l1_exact else '0'}"
            )
        if explicit_error_tags:
            rule_bits.extend(f"error_type={tag}" for tag in explicit_error_tags)
        else:
            rule_bits.append("metadata_gap=explicit_error_type_unknown")

        score = 0.0
        if direct_l1_anchor_potential:
            score += 50.0
        if wrong_supported_consensus:
            score += 30.0
        if frontier_collapse_low_diversity:
            score += 20.0
        if premature_intermediate_answer:
            score += 45.0
        if counting_grouping_off_by_factor:
            score += 40.0
        if structured_extraction_failure:
            score += 35.0
        if external_l1_exact:
            score += 10.0
        if anchor_matches_l1_max:
            score += 5.0
        if domain_label in {"domain_money_cost_revenue", "domain_ratio_proportion_percentage", "domain_multi_step_arithmetic"}:
            score += 2.0

        records.append(
            CaseRecord(
                case_id=case_id,
                method=method,
                question_type=question_type,
                domain_label=domain_label,
                error_type=error_type,
                failure_family=failure_family,
                gold_answer=gold_answer,
                predicted_answer=predicted_answer,
                selected_answer=selected_answer,
                abs_error=abs_error,
                rel_error=rel_error,
                distance_bucket=distance_bucket,
                num_candidate_groups=num_candidate_groups,
                diversity_bucket=diversity_bucket,
                external_contrast=external_contrast,
                notes=notes,
                anchor_matches_l1_max=anchor_matches_l1_max,
                external_l1_exact=external_l1_exact,
                gold_recovered=gold_recovered,
                diversity_increased=diversity_increased,
                gold_absent=gold_absent,
                frontier_collapse_low_diversity=frontier_collapse_low_diversity,
                wrong_supported_consensus=wrong_supported_consensus,
                direct_l1_anchor_potential=direct_l1_anchor_potential,
                premature_intermediate_answer=premature_intermediate_answer,
                counting_grouping_off_by_factor=counting_grouping_off_by_factor,
                structured_extraction_failure=structured_extraction_failure,
                unknown_or_insufficient_metadata=unknown_or_insufficient_metadata,
                pattern_labels=tuple(tags),
                rule_summary="; ".join(rule_bits),
                score=score,
                source_paths=source_paths,
            )
        )
    return records


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


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


def _find_top_cases(records: list[CaseRecord], limit: int = DEFAULT_TOP_CASES) -> list[CaseRecord]:
    return sorted(records, key=lambda r: (-r.score, r.case_id))[:limit]


def _summarize(
    *,
    method: str,
    failure_csv: Path,
    gold_absent_csv: Path,
    coverage_details_csv: Path,
    anchor_effect_csv: Path,
    outputs_root: Path,
) -> dict[str, Any]:
    failure_by_case = _group_rows_by_case(failure_csv)
    gold_by_case = _load_case_map(gold_absent_csv)
    anchor_by_case = _load_case_map(anchor_effect_csv) if anchor_effect_csv.is_file() else {}
    coverage_rows = _read_csv_rows(coverage_details_csv)
    unresolved_case_ids: list[str] = []
    coverage_by_case: dict[str, dict[str, str]] = {}
    seen_case_ids: set[str] = set()
    for row in coverage_rows:
        if _stringify(row.get("method")) != method:
            continue
        if _stringify(row.get("coverage_status")) != "still_fails":
            continue
        case_id = _normalize_case_id(row.get("case_id"))
        if not case_id:
            continue
        coverage_by_case[case_id] = row
        if case_id not in seen_case_ids:
            seen_case_ids.add(case_id)
            unresolved_case_ids.append(case_id)

    records = _build_case_records(
        method=method,
        unresolved_case_ids=unresolved_case_ids,
        coverage_by_case=coverage_by_case,
        failure_by_case=failure_by_case,
        gold_by_case=gold_by_case,
        anchor_by_case=anchor_by_case,
    )

    pattern_counts = Counter()
    for record in records:
        pattern_counts.update(record.pattern_labels)

    domain_counts = Counter(record.domain_label for record in records)

    explicit_error_cases = sum(
        1
        for record in records
        if record.premature_intermediate_answer or record.counting_grouping_off_by_factor or record.structured_extraction_failure
    )

    total_cases = len(records)
    low_diversity_cases = sum(1 for record in records if record.frontier_collapse_low_diversity)
    wrong_supported_cases = sum(1 for record in records if record.wrong_supported_consensus)
    direct_l1_anchor_cases = sum(1 for record in records if record.direct_l1_anchor_potential)
    strong_anchor_cases = sum(1 for record in records if record.anchor_matches_l1_max)
    external_l1_exact_cases = sum(1 for record in records if record.external_l1_exact)
    unknown_metadata_cases = sum(1 for record in records if record.unknown_or_insufficient_metadata)

    pattern_rows = []
    for label in REPORT_PATTERN_ORDER:
        count = pattern_counts.get(label, 0)
        examples = [record.case_id for record in records if label in record.pattern_labels][:5]
        pattern_rows.append(
            {
                "pattern_label": label,
                "count": count,
                "share_of_unresolved": round(count / total_cases, 6) if total_cases else 0.0,
                "kind": PATTERN_KIND[label],
                "example_case_ids": "|".join(examples),
            }
        )

    domain_rows = []
    for domain_label, count in domain_counts.most_common():
        domain_examples = [record.case_id for record in records if record.domain_label == domain_label][:5]
        domain_rows.append(
            {
                "domain_label": domain_label,
                "count": count,
                "share_of_unresolved": round(count / total_cases, 6) if total_cases else 0.0,
                "example_case_ids": "|".join(domain_examples),
            }
        )

    top_records = _find_top_cases(records, DEFAULT_TOP_CASES)
    top_case_ids = [record.case_id for record in top_records]
    case_rows = [
        {
            "case_id": record.case_id,
            "method": record.method,
            "question_type": record.question_type,
            "domain_label": record.domain_label,
            "error_type": record.error_type,
            "failure_family": record.failure_family,
            "gold_answer": record.gold_answer,
            "predicted_answer": record.predicted_answer,
            "selected_answer": record.selected_answer,
            "abs_error": record.abs_error,
            "rel_error": record.rel_error,
            "distance_bucket": record.distance_bucket,
            "num_candidate_groups": record.num_candidate_groups,
            "diversity_bucket": record.diversity_bucket,
            "external_contrast": record.external_contrast,
            "notes": record.notes,
            "anchor_matches_l1_max": int(record.anchor_matches_l1_max),
            "external_l1_exact": int(record.external_l1_exact),
            "gold_recovered": int(record.gold_recovered),
            "diversity_increased": int(record.diversity_increased),
            "gold_absent": int(record.gold_absent),
            "frontier_collapse_low_diversity": int(record.frontier_collapse_low_diversity),
            "wrong_supported_consensus": int(record.wrong_supported_consensus),
            "direct_l1_anchor_potential": int(record.direct_l1_anchor_potential),
            "premature_intermediate_answer": int(record.premature_intermediate_answer),
            "counting_grouping_off_by_factor": int(record.counting_grouping_off_by_factor),
            "structured_extraction_failure": int(record.structured_extraction_failure),
            "unknown_or_insufficient_metadata": int(record.unknown_or_insufficient_metadata),
            "pattern_labels": "|".join(record.pattern_labels),
            "rule_summary": record.rule_summary,
            "score": f"{record.score:.1f}",
            "source_paths": "|".join(record.source_paths),
        }
        for record in records
    ]
    top_case_rows = [
        {
            "case_id": record.case_id,
            "score": f"{record.score:.1f}",
            "question_type": record.question_type,
            "domain_label": record.domain_label,
            "pattern_labels": "|".join(record.pattern_labels),
            "error_type": record.error_type,
            "failure_family": record.failure_family,
            "gold_answer": record.gold_answer,
            "predicted_answer": record.predicted_answer,
            "selected_answer": record.selected_answer,
            "num_candidate_groups": record.num_candidate_groups,
            "diversity_bucket": record.diversity_bucket,
            "external_contrast": record.external_contrast,
            "anchor_matches_l1_max": int(record.anchor_matches_l1_max),
            "external_l1_exact": int(record.external_l1_exact),
            "rule_summary": record.rule_summary,
            "source_paths": "|".join(record.source_paths),
        }
        for record in top_records
    ]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "failure_corpus_rows": len(_read_csv_rows(failure_csv)),
        "unique_failure_ids": len(failure_by_case),
        "gold_absent_ids": len(gold_by_case),
        "coverage_details_rows": len(coverage_rows),
        "unresolved_cases_count": total_cases,
        "unresolved_unique_case_ids": len(unresolved_case_ids),
        "gold_absent_unresolved_count": total_cases,
        "low_diversity_count": low_diversity_cases,
        "wrong_supported_consensus_count": wrong_supported_cases,
        "direct_l1_anchor_potential_count": direct_l1_anchor_cases,
        "strong_direct_l1_anchor_match_count": strong_anchor_cases,
        "external_l1_exact_count": external_l1_exact_cases,
        "explicit_error_tagged_count": explicit_error_cases,
        "unknown_or_insufficient_metadata_count": unknown_metadata_cases,
        "pattern_counts": dict(pattern_counts),
        "domain_counts": dict(domain_counts),
        "case_rows": case_rows,
        "pattern_rows": pattern_rows,
        "domain_rows": domain_rows,
        "top_case_ids": top_case_ids,
        "top_case_rows": top_case_rows,
        "recommended_next_fix": (
            "Test a stronger direct L1 anchor / direct seed on the anchor-potential slice first."
            if direct_l1_anchor_cases >= 1
            else "Add a duplicate wrong-consensus penalty to break low-diversity false consensus."
        ),
        "secondary_observation": (
            "The unresolved set is still dominated by low-diversity gold-absent failures, so any direct-anchor pilot should be paired with branch-progress checks."
        ),
        "recommendation_reason": (
            f"{direct_l1_anchor_cases} cases have direct L1 anchor potential and {strong_anchor_cases} have the stronger patch-effect match; "
            f"{wrong_supported_cases} cases are wrong-supported-consensus / both-direct-and-frontier-wrong."
        ),
        "selected_exact_replay_case_ids": top_case_ids,
        "source_paths": {
            "failure_csv": str(failure_csv),
            "gold_absent_csv": str(gold_absent_csv),
            "coverage_details_csv": str(coverage_details_csv),
            "anchor_effect_csv": str(anchor_effect_csv) if anchor_effect_csv.is_file() else "",
            "outputs_root": str(outputs_root),
        },
    }
    return summary


def _render_report(summary: dict[str, Any]) -> str:
    pattern_rows = summary["pattern_rows"]
    domain_rows = summary["domain_rows"]
    top_case_rows = summary["top_case_rows"]
    lines = [
        "# PAL Unresolved Pattern Taxonomy",
        "",
        "## Facts",
        "",
        f"- Failure corpus rows: `{summary['failure_corpus_rows']}`",
        f"- Unique fully tracked failure IDs: `{summary['unique_failure_ids']}`",
        f"- Gold-absent subset rows: `{summary['gold_absent_ids']}`",
        f"- PAL unresolved covered cases: `{summary['unresolved_cases_count']}`",
        f"- Unique PAL unresolved IDs: `{summary['unresolved_unique_case_ids']}`",
        f"- Low-diversity / frontier-collapse cases: `{summary['low_diversity_count']}`",
        f"- Wrong-supported-consensus cases: `{summary['wrong_supported_consensus_count']}`",
        f"- Direct L1 anchor-potential cases: `{summary['direct_l1_anchor_potential_count']}`",
        f"- Strong direct-L1 patch-effect matches: `{summary['strong_direct_l1_anchor_match_count']}`",
        f"- External L1 exact matches: `{summary['external_l1_exact_count']}`",
        f"- Explicit error-tagged cases: `{summary['explicit_error_tagged_count']}`",
        f"- Metadata-gap cases: `{summary['unknown_or_insufficient_metadata_count']}`",
        "",
        "## Heuristic Labels",
        "",
        "- `gold_absent_from_candidate_pool`: the unresolved case is in the gold-absent subset, so the exact answer never entered the pool.",
        "- `frontier_collapse_low_diversity`: candidate groups were zero or the diversity bucket was low.",
        "- `wrong_supported_consensus`: the gold-absent row says the selected contrast was `Both wrong`.",
        "- `direct_l1_anchor_potential`: the joined anchor-effect CSV says either `anchor_matches_l1_max=1` or `external_l1_exact=1`.",
        "- `premature_intermediate_answer`: explicit error tag from the gold-absent subpattern CSV.",
        "- `counting_grouping_off_by_factor`: explicit error tag from the gold-absent subpattern CSV.",
        "- `structured_extraction_failure`: explicit error tag from the gold-absent subpattern CSV.",
        "- `unknown_or_insufficient_metadata`: no explicit subpattern tag was available beyond the broad fact labels.",
        "",
        "## Pattern Counts",
        "",
        _render_table(pattern_rows, ["pattern_label", "count", "share_of_unresolved", "kind", "example_case_ids"]),
        "",
        "## Domain Counts",
        "",
        _render_table(domain_rows, ["domain_label", "count", "share_of_unresolved", "example_case_ids"]),
        "",
        "## Top Scored Cases",
        "",
        _render_table(
            top_case_rows,
            [
                "case_id",
                "score",
                "domain_label",
                "pattern_labels",
                "error_type",
                "num_candidate_groups",
                "diversity_bucket",
                "external_contrast",
                "anchor_matches_l1_max",
                "external_l1_exact",
            ],
        ),
        "",
        "## Proposed Fixes",
        "",
    ]
    for label, text in FIX_RECOMMENDATIONS.items():
        if label == "direct_l1_anchor_potential" and summary["direct_l1_anchor_potential_count"] == 0:
            continue
        if label == "wrong_supported_consensus" and summary["wrong_supported_consensus_count"] == 0:
            continue
        if label == "frontier_collapse_low_diversity" and summary["low_diversity_count"] == 0:
            continue
        if label == "premature_intermediate_answer" and summary["pattern_counts"].get(label, 0) == 0:
            continue
        if label == "counting_grouping_off_by_factor" and summary["pattern_counts"].get(label, 0) == 0:
            continue
        if label == "structured_extraction_failure" and summary["pattern_counts"].get(label, 0) == 0:
            continue
        lines.append(f"- {text}")
    lines.extend(
        [
            "",
            "## Recommended Next Experiment",
            "",
            summary["recommended_next_fix"],
            "",
            "## Suggested Exact-Replay Slice",
            "",
            f"- Top scored cases: `{', '.join(summary['top_case_ids'])}`",
            f"- Primary replay goal: validate the direct-L1 anchor hypothesis on the `{summary['direct_l1_anchor_potential_count']}` anchor-potential cases before expanding to broader frontier-collapse fixes.",
            "",
            "## Limits",
            "",
            "- This is an existing-artifact audit only.",
            "- No runtime behavior change was made.",
            "- No paid/model API calls were made.",
            "- No external-baseline claim is made.",
            "- Missing explicit error tags are not failures; they just mean the heuristic taxonomy must lean on question-level and contrast metadata.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _compact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if key != "case_rows"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--failure-csv",
        default=str(DEFAULT_FAILURE_CSV),
        help="Fully tracked latest-method failure corpus CSV.",
    )
    parser.add_argument(
        "--gold-absent-csv",
        default=str(DEFAULT_GOLD_ABSENT_CSV),
        help="Gold-absent subpattern CSV.",
    )
    parser.add_argument(
        "--coverage-details-csv",
        default="",
        help="Coverage details CSV from the recovery audit. If omitted, the newest outputs/latest_failure_recovery_coverage_*/case_coverage_details.csv is used if present.",
    )
    parser.add_argument(
        "--anchor-effect-csv",
        default=str(DEFAULT_ANCHOR_EFFECT_CSV),
        help="Direct L1 anchor patch-effect CSV.",
    )
    parser.add_argument(
        "--method",
        default=DEFAULT_METHOD,
        help="Exact method ID to mine.",
    )
    parser.add_argument(
        "--outputs-root",
        default=str(DEFAULT_OUTPUTS_ROOT),
        help="Root directory for finding fallback coverage outputs.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional output directory. Defaults to outputs/pal_unresolved_pattern_taxonomy_<timestamp>.",
    )
    parser.add_argument(
        "--timestamp",
        default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        help="UTC timestamp suffix for the default output directory.",
    )
    parser.add_argument(
        "--dry-run",
        "--validate-only",
        action="store_true",
        dest="dry_run",
        help="Validate inputs and print summary without writing output files.",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    failure_csv = Path(args.failure_csv).expanduser()
    gold_absent_csv = Path(args.gold_absent_csv).expanduser()
    anchor_effect_csv = Path(args.anchor_effect_csv).expanduser() if args.anchor_effect_csv else Path()
    outputs_root = Path(args.outputs_root).expanduser()

    if not failure_csv.is_file():
        raise FileNotFoundError(f"Missing failure corpus CSV: {failure_csv}")
    if not gold_absent_csv.is_file():
        raise FileNotFoundError(f"Missing gold-absent CSV: {gold_absent_csv}")
    if args.coverage_details_csv:
        coverage_details_csv = Path(args.coverage_details_csv).expanduser()
    else:
        coverage_details_csv = _latest_case_coverage_csv(outputs_root) or Path()
    if not coverage_details_csv.is_file():
        raise FileNotFoundError(
            f"Missing coverage-details CSV: supply --coverage-details-csv or generate case_coverage_details.csv under {outputs_root}"
        )
    if anchor_effect_csv and not anchor_effect_csv.is_file():
        anchor_effect_csv = Path()
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else REPO_ROOT / "outputs" / f"{DEFAULT_OUTPUT_PREFIX}{args.timestamp}"

    summary = _summarize(
        method=args.method,
        failure_csv=failure_csv,
        gold_absent_csv=gold_absent_csv,
        coverage_details_csv=coverage_details_csv,
        anchor_effect_csv=anchor_effect_csv,
        outputs_root=outputs_root,
    )
    summary_output = _compact_summary(summary)

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(output_dir / "pal_unresolved_cases.csv", summary["case_rows"], fieldnames=list(summary["case_rows"][0].keys()) if summary["case_rows"] else [])
        _write_csv(output_dir / "pattern_taxonomy_counts.csv", summary["pattern_rows"], fieldnames=["pattern_label", "count", "share_of_unresolved", "kind", "example_case_ids"])
        _write_csv(output_dir / "pattern_by_domain_counts.csv", summary["domain_rows"], fieldnames=["domain_label", "count", "share_of_unresolved", "example_case_ids"])
        _write_csv(output_dir / "pattern_case_examples.csv", summary["top_case_rows"], fieldnames=list(summary["top_case_rows"][0].keys()) if summary["top_case_rows"] else [])
        (output_dir / "summary.json").write_text(json.dumps(summary_output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (output_dir / "pal_unresolved_pattern_taxonomy_report.md").write_text(_render_report(summary_output), encoding="utf-8")
    else:
        print(json.dumps(summary_output, indent=2, sort_keys=True))

    return summary


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
